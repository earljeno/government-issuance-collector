import re
import logging
from typing import List, Optional, Callable
from threading import Event
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from config import DEPARTMENTS
from database.models import IssuanceRecord
from database.db import save_checkpoint, get_checkpoint, clear_checkpoint, log_quarantine

logger = logging.getLogger(__name__)

class DAScraper(BaseScraper):
    def __init__(self):
        dept_cfg = DEPARTMENTS["DA"]
        super().__init__(dept_cfg["name"], dept_cfg["code"])
        self.categories_map = dept_cfg["categories"]

    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
        resume: bool = False
    ) -> int:
        target_cats = categories if categories else list(self.categories_map.keys())
        total_inserted = 0
        total_duplicates = 0

        # Load active checkpoint if resuming
        checkpoint = get_checkpoint(self.department_name) if resume else None
        completed_cats = set(checkpoint.get("completed_categories", [])) if checkpoint else set()
        
        self.report_progress(
            progress_callback=progress_callback,
            category="Initializing",
            current_page=0,
            total_pages=str(len(target_cats)),
            records_collected=0,
            status="Running",
            message=f"Starting extraction for {len(target_cats)} categories" + (f" ({len(completed_cats)} already completed)" if resume and completed_cats else "")
        )

        for cat_idx, cat_name in enumerate(target_cats, start=1):
            if cancel_event and cancel_event.is_set():
                logger.info("[DA] Extraction cancelled by user.")
                save_checkpoint(self.department_name, cat_name, 1, "", list(completed_cats))
                self.report_progress(
                    progress_callback=progress_callback,
                    category=cat_name,
                    current_page=cat_idx,
                    total_pages=str(len(target_cats)),
                    records_collected=total_inserted,
                    status="Stopped",
                    message="Extraction stopped by user"
                )
                return total_inserted

            if resume and cat_name in completed_cats:
                logger.info(f"[DA] Skipping already completed category: {cat_name}")
                continue

            cat_url = self.categories_map.get(cat_name)
            if not cat_url:
                continue

            save_checkpoint(self.department_name, cat_name, 1, cat_url, list(completed_cats))

            self.report_progress(
                progress_callback=progress_callback,
                category=cat_name,
                current_page=cat_idx,
                total_pages=str(len(target_cats)),
                records_collected=total_inserted,
                status="Running",
                message=f"Fetching category: {cat_name}"
            )

            resp = self.fetch_url(cat_url)
            if not resp or resp.status_code != 200:
                err_msg = f"Failed to fetch {cat_url} (HTTP {resp.status_code if resp else 'No response'})"
                logger.error(f"[DA] {err_msg}")
                self.log_failed_page(cat_name, cat_url, err_msg)
                continue

            records_in_cat = self._parse_category_page(resp.text, cat_name, cat_url, year_filter=year)
            
            if records_in_cat:
                ins, dups = self.save_records(records_in_cat)
                total_inserted += ins
                total_duplicates += dups
                logger.info(f"[DA] {cat_name}: {len(records_in_cat)} extracted ({ins} new, {dups} duplicates)")

            completed_cats.add(cat_name)
            save_checkpoint(self.department_name, cat_name, 1, "", list(completed_cats))

            self.report_progress(
                progress_callback=progress_callback,
                category=cat_name,
                current_page=cat_idx,
                total_pages=str(len(target_cats)),
                records_collected=total_inserted,
                status="Running",
                message=f"Completed category {cat_name}: {len(records_in_cat)} records found"
            )

        if not cancel_event or not cancel_event.is_set():
            clear_checkpoint(self.department_name)

        self.report_progress(
            progress_callback=progress_callback,
            category="All Categories",
            current_page=len(target_cats),
            total_pages=str(len(target_cats)),
            records_collected=total_inserted,
            status="Completed",
            message=f"Extraction completed. {total_inserted} new records added ({total_duplicates} duplicates skipped)."
        )
        return total_inserted

    def _parse_category_page(self, html: str, category_name: str, page_url: str, year_filter: Optional[str] = None) -> List[IssuanceRecord]:
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")
        
        tables = soup.find_all("table", class_=lambda c: c and "tablepress" in c)
        if not tables:
            # Fallback to any tables in content
            content = soup.find("div", class_="entry-content") or soup.find("main") or soup
            tables = content.find_all("table")

        for table in tables:
            # Find associated year from previous header or accordion
            table_year = ""
            prev_elem = table.find_previous(["h1", "h2", "h3", "h4", "h5", "h6", "button", "div"])
            if prev_elem:
                year_match = re.search(r"\b(19\d\d|20\d\d)\b", prev_elem.get_text())
                if year_match:
                    table_year = year_match.group(1)

            # If user filtered by year, check if table matches or date matches
            if year_filter and table_year and table_year != str(year_filter):
                continue

            # Parse columns
            rows = table.find_all("tr")
            if not rows:
                continue

            code_idx = 0
            title_idx = 1
            date_idx = 2

            header_cells = rows[0].find_all(["th", "td"])
            if header_cells:
                headers = [th.get_text(strip=True).upper() for th in header_cells]
                for idx, h in enumerate(headers):
                    if "CODE" in h or "NUMBER" in h or "NO." in h:
                        code_idx = idx
                    elif "TITLE" in h or "SUBJECT" in h:
                        title_idx = idx
                    elif "DATE" in h:
                        date_idx = idx

            # Process data rows
            data_rows = rows[1:] if len(rows) > 1 else rows
            for row in data_rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                code_no = cells[code_idx].get_text(strip=True) if code_idx < len(cells) else ""
                title_text = cells[title_idx].get_text(strip=True) if title_idx < len(cells) else ""
                date_text = cells[date_idx].get_text(strip=True) if date_idx < len(cells) else ""

                if not title_text and not code_no:
                    details = f"Row lacks both title and issuance number. Extracted date: '{date_text}'"
                    log_quarantine(self.department_name, category_name, "Missing Metadata", details, page_url)
                    continue

                # Fallback: if title is empty, code might have full title
                if not title_text and code_no:
                    title_text = code_no
                    code_no = ""

                if not title_text:
                    details = f"Row lacks valid title. Code: '{code_no}', Date: '{date_text}'"
                    log_quarantine(self.department_name, category_name, "Missing Metadata", details, page_url)
                    continue

                # Filter by year if specified
                if year_filter:
                    year_str = str(year_filter)
                    if table_year != year_str and year_str not in date_text and year_str not in title_text:
                        continue

                # Extract source document link without falling back to category listing
                link_tag = row.find("a", href=True)
                source_link = ""
                if link_tag and link_tag.get("href"):
                    raw_href = link_tag["href"].strip()
                    if raw_href and raw_href != "#":
                        candidate = urljoin(page_url, raw_href)
                        if candidate != page_url:
                            source_link = candidate

                self.check_url_academic_provenance(source_link, self.department_code, category=category_name, department_name=self.department_name)

                record = IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=code_no,
                    title=title_text,
                    publication_date=date_text or table_year,
                    source_url=source_link
                )
                records.append(record)

        return records
