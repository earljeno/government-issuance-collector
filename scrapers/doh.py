import logging
import re
from typing import Callable, List, Optional
from threading import Event
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from config import DEPARTMENTS
from database.models import IssuanceRecord

logger = logging.getLogger(__name__)


class DOHScraper(BaseScraper):
    """
    DOH listing scraper.

    Pagination uses the site's ordinary page query parameter (page=0, 1, ...).
    If the site denies access or presents a challenge page, the scraper stops
    and records the issue rather than attempting to circumvent that control.
    """

    def __init__(self):
        dept_cfg = DEPARTMENTS["DOH"]
        super().__init__(dept_cfg["name"], dept_cfg["code"])
        self.categories_map = dept_cfg["categories"]

    @staticmethod
    def _page_url(base_url: str, page_number: int) -> str:
        parts = urlsplit(base_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["page"] = str(page_number)
        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        ))

    @staticmethod
    def _looks_like_access_challenge(html: str) -> bool:
        sample = html[:50000].lower()
        return (
            "just a moment..." in sample
            or "cf-chl-" in sample
            or "challenge-platform" in sample
            or "verify you are human" in sample
        )

    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
    ) -> int:
        target_cats = categories if categories else list(self.categories_map.keys())
        total_inserted = 0

        self.report_progress(
            progress_callback=progress_callback,
            category="Connectivity Check",
            current_page=0,
            total_pages=str(len(target_cats)),
            records_collected=0,
            status="Running",
            message="Checking DOH portal accessibility...",
        )

        test_url = "https://doh.gov.ph/"
        resp = self.fetch_url(test_url)

        if not resp or resp.status_code != 200 or self._looks_like_access_challenge(resp.text):
            if resp is None:
                block_reason = "Connection failed or timed out"
            elif resp.status_code == 403:
                block_reason = "HTTP 403 access denied by the website"
            elif resp.status_code != 200:
                block_reason = f"HTTP {resp.status_code}"
            else:
                block_reason = "A Cloudflare verification/challenge page was returned"

            err_msg = (
                f"DOH portal is not currently available for automated collection: "
                f"{block_reason}. No access-control bypass will be attempted. "
                "Use an authorized DOH API/export, request access from the site "
                "administrator, or import an officially provided HTML/PDF export."
            )
            logger.warning("[DOH] %s", err_msg)
            self.log_failed_page("All Categories", test_url, err_msg)
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

            cat_url = self.categories_map.get(cat_name)
            if not cat_url:
                logger.warning("[DOH] Unknown category requested: %s", cat_name)
                continue

            self.report_progress(
                progress_callback=progress_callback,
                category=cat_name,
                current_page=0,
                total_pages="Unknown",
                records_collected=total_inserted,
                status="Running",
                message=f"Extracting DOH {cat_name}",
            )

            page_number = 0
            category_inserted = 0
            while True:
                if cancel_event and cancel_event.is_set():
                    break

                page_url = self._page_url(cat_url, page_number)
                page_resp = self.fetch_url(page_url)

                if not page_resp or page_resp.status_code != 200:
                    status = page_resp.status_code if page_resp is not None else "No response"
                    error = f"HTTP {status} while retrieving page {page_number}"
                    self.log_failed_page(cat_name, page_url, error)
                    logger.warning("[DOH] %s: %s", cat_name, error)
                    break

                if self._looks_like_access_challenge(page_resp.text):
                    error = (
                        "Access challenge page returned during pagination; "
                        "stopping this category without attempting a bypass."
                    )
                    self.log_failed_page(cat_name, page_url, error)
                    logger.warning("[DOH] %s: %s", cat_name, error)
                    break

                records = self.parse_html_listing(
                    page_resp.text,
                    cat_name,
                    page_url,
                    year_filter=year,
                )

                # An empty parsed page is the normal end-of-pagination signal.
                if not records:
                    logger.info(
                        "[DOH] No listing records on %s page %s; pagination complete.",
                        cat_name,
                        page_number,
                    )
                    break

                ins, dups = self.save_records(records)
                category_inserted += ins
                total_inserted += ins

                self.report_progress(
                    progress_callback=progress_callback,
                    category=cat_name,
                    current_page=page_number + 1,
                    total_pages="Unknown",
                    records_collected=total_inserted,
                    status="Running",
                    message=(
                        f"Page {page_number + 1}: {len(records)} parsed, "
                        f"{ins} inserted, {dups} duplicates."
                    ),
                )

                page_number += 1

            logger.info(
                "[DOH] Finished %s: %s new records across %s page(s).",
                cat_name,
                category_inserted,
                page_number,
            )

        final_status = "Stopped" if cancel_event and cancel_event.is_set() else "Completed"
        self.report_progress(
            progress_callback=progress_callback,
            category="All Categories",
            current_page=len(target_cats),
            total_pages=str(len(target_cats)),
            records_collected=total_inserted,
            status=final_status,
            message=f"DOH extraction {final_status.lower()} with {total_inserted} new records.",
        )
        return total_inserted

    def parse_html_listing(
        self,
        html: str,
        category_name: str,
        source_url: str,
        year_filter: Optional[str] = None,
    ) -> List[IssuanceRecord]:
        """Parse DOH Health Policies listings from HTML tables or card views."""
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Search for table-based listings.
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
                    continue

                if year_filter:
                    year_value = str(year_filter)
                    if (
                        year_value not in date_text
                        and year_value not in title_text
                        and year_value not in num_text
                    ):
                        continue

                link = row.find("a", href=True)
                from urllib.parse import urljoin
                full_link = (
                    urljoin(source_url, link["href"].strip())
                    if link else source_url
                )

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=title_text or num_text,
                    publication_date=date_text,
                    source_url=full_link,
                ))

        # 2. Search for div/card listings if no table records were found.
        if not records:
            items = soup.find_all(class_=lambda classes: classes and any(
                key in " ".join(classes).lower()
                if isinstance(classes, list)
                else key in classes.lower()
                for key in ["policy-item", "view-content", "views-row", "item-list"]
            ))
            for item in items:
                title_elem = item.find(["h2", "h3", "h4", "a"])
                if not title_elem:
                    continue

                title_text = title_elem.get_text(strip=True)
                if len(title_text) < 4:
                    continue

                link_elem = item.find("a", href=True)
                from urllib.parse import urljoin
                full_link = (
                    urljoin(source_url, link_elem["href"].strip())
                    if link_elem else source_url
                )

                date_match = re.search(
                    r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})\b",
                    item.get_text(),
                )
                date_text = date_match.group(1) if date_match else ""

                num_match = re.search(
                    r"((?:AO|DC|DM|JAO|JC)\s*(?:No\.)?\s*[\d-]+(?:\s*s\.\s*\d{4})?)",
                    title_text,
                    re.IGNORECASE,
                )
                num_text = num_match.group(1) if num_match else ""

                if year_filter and str(year_filter) not in (
                    title_text + " " + date_text + " " + num_text
                ):
                    continue

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=title_text,
                    publication_date=date_text,
                    source_url=full_link,
                ))

        return records
