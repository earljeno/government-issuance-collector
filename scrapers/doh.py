import logging
import re
import time
from datetime import datetime
from typing import Callable, List, Optional
from threading import Event
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from config import DEPARTMENTS, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS, DEFAULT_USER_AGENT
from database.models import IssuanceRecord
from database.db import save_checkpoint, get_checkpoint, clear_checkpoint, log_quarantine

logger = logging.getLogger(__name__)

# Map friendly category names to internal Inforouter property set IDs
DOH_PROPERTY_SETS = {
    "Administrative Orders": "KMITS_AISAO",
    "Department Circulars": "KMITS_AISDC",
    "Memorandum Circulars": "KMITS_AISMC",
    "Implementing Rules and Regulations": "KMITS_AISIRR",
    "Joint Administrative Orders": "KMITS_AISJAO",
    "Joint Memorandum Circulars": "KMITS_AISJMC",
    "Joint Circulars": "KMITS_AISJC",
    "Executive Orders": "KMITS_AISEO",
    "Republic Acts": "KMITS_AISRA",
    # Aliases & singular forms
    "Administrative Order": "KMITS_AISAO",
    "Department Circular": "KMITS_AISDC",
    "Memorandum Circular": "KMITS_AISMC",
    "Implementing Rules & Regulations": "KMITS_AISIRR",
    "Joint Administrative Order": "KMITS_AISJAO",
    "Joint Memorandum Circular": "KMITS_AISJMC",
    "Joint Circular": "KMITS_AISJC",
    "Executive Order": "KMITS_AISEO",
    "Republic Act": "KMITS_AISRA",
}


class DOHScraper(BaseScraper):
    """
    DOH API-based Issuance Scraper.

    Interacts directly with the official DOH Health Policies portal API
    at https://app.doh.gov.ph:1024. Uses session-based search endpoints:
      1. GET  /Search                 -> initialize session
      2. POST /Rest/SearchDocuments   -> configure category/year filters
      3. POST /Rest/GetFirstPage      -> retrieve page 1 (100 items/page)
      4. POST /Rest/GetNextPage       -> iterate subsequent pages
      5. GET  /Rest/GetFile?id=...    -> direct PDF download link
    """

    def __init__(self):
        dept_cfg = DEPARTMENTS["DOH"]
        super().__init__(dept_cfg["name"], dept_cfg["code"])
        self.categories_map = dept_cfg.get("categories", {})
        self.base_url = dept_cfg.get("base_url", "https://app.doh.gov.ph:1024").rstrip("/")
        
        # Configure session headers for the DOH REST API
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": f"{self.base_url}/Search",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })

    def _ensure_session(self) -> bool:
        """Initialize the ASP.NET session cookie required for queries."""
        try:
            url = f"{self.base_url}/Search"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
            if resp.status_code == 200:
                return True
            logger.warning("[DOH] Failed to initialize session: HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.exception("[DOH] Connection error initializing session: %s", exc)
            return False

    def _search_documents(self, cat_code: str, year: Optional[str] = None) -> bool:
        """Submit search criteria to cache query results in the session."""
        date_from = f"01/01/{year}" if year else ""
        date_to = f"12/31/{year}" if year else ""

        payload = {
            "docDateFrom": date_from,
            "docDateTo": date_to,
            "issuanceNumber": "",
            "issuanceType": cat_code,
            "keywords": "",
            "subject": "",
        }

        url = f"{self.base_url}/Rest/SearchDocuments"
        try:
            resp = self.session.post(url, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return True
                logger.warning("[DOH] Search failed: %s", data.get("error"))
                return False
            logger.warning("[DOH] SearchDocuments HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.exception("[DOH] Error querying SearchDocuments: %s", exc)
            return False

    def _fetch_page(self, page_number: int, cat_code: str, year: Optional[str] = None) -> tuple[List[dict], bool]:
        """
        Fetch a page of results. Returns (items_list, is_last_page).
        Automatically re-authenticates and re-runs search if the session expired.
        """
        endpoint = "/Rest/GetFirstPage" if page_number <= 1 else "/Rest/GetNextPage"
        url = f"{self.base_url}{endpoint}"

        for attempt in range(2):
            try:
                resp = self.session.post(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("success"):
                        data = res_json.get("data") or {}
                        items = data.get("items") or []
                        is_last = bool(data.get("lastPage", True))
                        return items, is_last
                    
                    error_msg = res_json.get("error", "")
                    if error_msg == "expired" and attempt == 0:
                        logger.info("[DOH] Session expired; re-initializing and retrying page %s...", page_number)
                        if self._ensure_session() and self._search_documents(cat_code, year):
                            # Advance pages if past page 1
                            if page_number > 1:
                                self.session.post(f"{self.base_url}/Rest/GetFirstPage", timeout=REQUEST_TIMEOUT_SECONDS)
                                for _ in range(page_number - 2):
                                    self.session.post(f"{self.base_url}/Rest/GetNextPage", timeout=REQUEST_TIMEOUT_SECONDS)
                            continue
                    logger.warning("[DOH] API error on %s: %s", endpoint, error_msg)
                    return [], True
                logger.warning("[DOH] HTTP %s for %s", resp.status_code, url)
                return [], True
            except Exception as exc:
                logger.warning("[DOH] Request exception on %s (attempt %s): %s", endpoint, attempt + 1, exc)
                time.sleep(1.0)

        return [], True

    def _item_to_record(self, item: dict, cat_name: str) -> Optional[IssuanceRecord]:
        """Convert a DOH JSON item to an IssuanceRecord."""
        doc_id = item.get("documentId")
        doc_type = item.get("issuanceType") or cat_name
        doc_num = (item.get("issuanceNumber") or "").strip()
        subject = (item.get("subject") or "").strip()

        if not subject:
            fallback = f"{doc_type} {doc_num}".strip()
            subject = fallback if fallback else (doc_num or "")

        if not subject and not doc_num:
            details = f"DOH record lacks subject and issuance number. Doc ID: {doc_id}, Type: {doc_type}, Date: {raw_date}"
            log_quarantine(self.department_name, cat_name, "Missing Metadata", details, f"{self.base_url}/Rest/GetFile?id={doc_id}" if doc_id else "")
            return None

        # Parse publication date and apply boundary checks
        raw_date = (
            item.get("publishedDate")
            or item.get("documentDate")
            or item.get("dateCreated")
            or ""
        )
        pub_date = ""
        if raw_date:
            raw_str = str(raw_date).strip()
            dt = None
            try:
                dt = datetime.fromisoformat(raw_str)
            except (ValueError, TypeError):
                m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", raw_str)
                if m:
                    try:
                        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    except ValueError:
                        pass

            if dt:
                if dt.year == 2500:
                    dt = dt.replace(year=2005)
                    pub_date = dt.strftime("%Y-%m-%d")
                elif dt.year > datetime.now().year:
                    pub_date = ""
                else:
                    pub_date = dt.strftime("%Y-%m-%d")

        file_url = f"{self.base_url}/Rest/GetFile?id={doc_id}" if doc_id else ""
        self.check_url_academic_provenance(file_url, self.department_code, category=cat_name, department_name=self.department_name)

        return IssuanceRecord(
            department=self.department_name,
            category=cat_name,
            issuance_number=doc_num,
            title=subject,
            publication_date=pub_date,
            source_url=file_url,
        )

    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
        max_pages_per_category: Optional[int] = None,
        resume: bool = False,
    ) -> int:
        target_cats = categories if categories else list(self.categories_map.keys())
        total_inserted = 0

        # Load active checkpoint if resuming
        checkpoint = get_checkpoint(self.department_name) if resume else None
        completed_cats = set(checkpoint.get("completed_categories", [])) if checkpoint else set()
        resume_cat = checkpoint.get("category") if checkpoint else None
        resume_page = checkpoint.get("page", 1) if checkpoint else 1

        self.report_progress(
            progress_callback=progress_callback,
            category="Connecting",
            current_page=0,
            total_pages=str(len(target_cats)),
            records_collected=0,
            status="Running",
            message="Initializing DOH API connection...",
        )

        if not self._ensure_session():
            err_msg = "Could not establish session with DOH API portal."
            self.log_failed_page("All Categories", f"{self.base_url}/Search", err_msg)
            self.report_progress(
                progress_callback=progress_callback,
                category="All Categories",
                current_page=0,
                total_pages=str(len(target_cats)),
                records_collected=0,
                status="Temporarily Inaccessible",
                message=err_msg,
            )
            return 0

        for cat_idx, cat_name in enumerate(target_cats, start=1):
            if cancel_event and cancel_event.is_set():
                break

            if cat_name in completed_cats:
                logger.info("[DOH] Skipping already completed category: %s", cat_name)
                continue

            cat_code = DOH_PROPERTY_SETS.get(cat_name) or self.categories_map.get(cat_name, "")
            
            self.report_progress(
                progress_callback=progress_callback,
                category=cat_name,
                current_page=0,
                total_pages=str(len(target_cats)),
                records_collected=total_inserted,
                status="Running",
                message=f"Querying DOH {cat_name}...",
            )

            if not self._search_documents(cat_code, year):
                error_msg = f"Failed to execute search for category {cat_name}"
                self.log_failed_page(cat_name, f"{self.base_url}/Rest/SearchDocuments", error_msg)
                continue

            page_number = 1
            if cat_name == resume_cat and resume_page > 1:
                logger.info("[DOH] Fast-forwarding category %s to page %s...", cat_name, resume_page)
                # Catch up pagination to resume_page
                self.session.post(f"{self.base_url}/Rest/GetFirstPage", timeout=REQUEST_TIMEOUT_SECONDS)
                for _ in range(resume_page - 1):
                    self.session.post(f"{self.base_url}/Rest/GetNextPage", timeout=REQUEST_TIMEOUT_SECONDS)
                page_number = resume_page
                resume_cat = None

            category_inserted = 0

            while True:
                if cancel_event and cancel_event.is_set():
                    logger.info("[DOH] Extraction cancelled by user.")
                    save_checkpoint(self.department_name, cat_name, page_number, "", list(completed_cats))
                    break

                if max_pages_per_category and page_number > max_pages_per_category:
                    logger.info("[DOH] Reached max page limit (%s) for %s", max_pages_per_category, cat_name)
                    break

                save_checkpoint(self.department_name, cat_name, page_number, "", list(completed_cats))

                items, is_last_page = self._fetch_page(page_number, cat_code, year)
                if not items:
                    break

                records = [r for item in items if (r := self._item_to_record(item, cat_name)) is not None]

                if year:
                    year_val = str(year)
                    records = [
                        r for r in records
                        if year_val in (r.publication_date + " " + r.title + " " + r.issuance_number)
                    ]

                ins, dups = self.save_records(records)
                category_inserted += ins
                total_inserted += ins

                self.report_progress(
                    progress_callback=progress_callback,
                    category=cat_name,
                    current_page=page_number,
                    total_pages="Unknown",
                    records_collected=total_inserted,
                    status="Running",
                    message=(
                        f"Page {page_number}: {len(records)} records, "
                        f"{ins} inserted, {dups} duplicates."
                    ),
                )

                if is_last_page:
                    break

                page_number += 1
                if REQUEST_DELAY_SECONDS > 0:
                    time.sleep(REQUEST_DELAY_SECONDS)

            completed_cats.add(cat_name)
            save_checkpoint(self.department_name, cat_name, page_number, "", list(completed_cats))

        if not cancel_event or not cancel_event.is_set():
            clear_checkpoint(self.department_name)

        final_status = "Stopped" if cancel_event and cancel_event.is_set() else "Completed"
        self.report_progress(
            progress_callback=progress_callback,
            category="All Categories",
            current_page=len(target_cats),
            total_pages=str(len(target_cats)),
            records_collected=total_inserted,
            status=final_status,
            message=f"DOH collection {final_status.lower()}: {total_inserted} new records collected.",
        )
        return total_inserted

    def parse_html_listing(
        self,
        html: str,
        category_name: str,
        source_url: str,
        year_filter: Optional[str] = None,
    ) -> List[IssuanceRecord]:
        """Parse DOH listings from HTML tables (retained for backward compatibility and fixtures)."""
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            col_map = {"num": 0, "title": 1, "date": 2}
            headers = [
                th.get_text(strip=True).upper()
                for th in rows[0].find_all(["th", "td"])
            ]
            for idx, header in enumerate(headers):
                if any(key in header for key in ["NO", "NUMBER", "CODE"]):
                    col_map["num"] = idx
                elif any(key in header for key in ["TITLE", "SUBJECT", "POLICY"]):
                    col_map["title"] = idx
                elif any(key in header for key in ["DATE", "PUBLISHED"]):
                    col_map["date"] = idx

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                num_text = (
                    cells[col_map["num"]].get_text(strip=True)
                    if col_map["num"] < len(cells) else ""
                )
                title_text = (
                    cells[col_map["title"]].get_text(strip=True)
                    if col_map["title"] < len(cells) else ""
                )
                date_text = (
                    cells[col_map["date"]].get_text(strip=True)
                    if col_map["date"] < len(cells) else ""
                )

                if not title_text and not num_text:
                    details = f"DOH HTML row lacks both title and number. Date: '{date_text}'"
                    log_quarantine(self.department_name, category_name, "Missing Metadata", details, source_url)
                    continue

                final_title = title_text or num_text
                if not final_title:
                    details = f"DOH HTML row missing title. Number: '{num_text}', Date: '{date_text}'"
                    log_quarantine(self.department_name, category_name, "Missing Metadata", details, source_url)
                    continue

                if year_filter:
                    year_val = str(year_filter)
                    if (
                        year_val not in date_text
                        and year_val not in final_title
                        and year_val not in num_text
                    ):
                        continue

                link = row.find("a", href=True)
                full_link = ""
                if link and link.get("href"):
                    raw_href = link["href"].strip()
                    if raw_href and raw_href != "#":
                        candidate = urljoin(source_url, raw_href)
                        if candidate != source_url:
                            full_link = candidate

                self.check_url_academic_provenance(full_link, self.department_code, category=category_name, department_name=self.department_name)

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=final_title,
                    publication_date=date_text,
                    source_url=full_link,
                ))

        return records
