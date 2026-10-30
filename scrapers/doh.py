import re
import logging
from typing import List, Optional, Callable, Tuple
from threading import Event
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from config import DEPARTMENTS
from database.models import IssuanceRecord

logger = logging.getLogger(__name__)

class DOHScraper(BaseScraper):
    def __init__(self):
        dept_cfg = DEPARTMENTS["DOH"]
        super().__init__(dept_cfg["name"], dept_cfg["code"])
        self.categories_map = dept_cfg["categories"]

    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None
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
            message="Checking DOH portal accessibility..."
        )

        # Check accessibility of official DOH portal
        test_url = "https://doh.gov.ph/"
        resp = self.fetch_url(test_url)
        
        is_blocked = False
        block_reason = ""
        
        if not resp:
            is_blocked = True
            block_reason = "Connection timeout or unreachable"
        elif resp.status_code == 403 or "Just a moment..." in resp.text or "cf-chl" in resp.text:
            is_blocked = True
            block_reason = "Protected by Cloudflare WAF / Turnstile verification"

        if is_blocked:
            err_msg = (
                f"DOH official website (doh.gov.ph) is currently {block_reason}. "
                "Per security compliance, automated bypass of access controls is prohibited. "
                "Please use the 'Manual URL / HTML Import' tool to extract from an accessible mirror or saved listing."
            )
            logger.warning(f"[DOH] {err_msg}")
            self.log_failed_page("All Categories", test_url, err_msg)
            self.report_progress(
                progress_callback=progress_callback,
                category="All Categories",
                current_page=0,
                total_pages=str(len(target_cats)),
                records_collected=0,
                status="Temporarily Inaccessible",
                message=err_msg
            )
            return 0

        # If accessible, proceed with category extraction
        for cat_idx, cat_name in enumerate(target_cats, start=1):
            if cancel_event and cancel_event.is_set():
                break

            cat_url = self.categories_map.get(cat_name)
            if not cat_url:
                continue

            self.report_progress(
                progress_callback=progress_callback,
                category=cat_name,
                current_page=cat_idx,
                total_pages=str(len(target_cats)),
                records_collected=total_inserted,
                status="Running",
                message=f"Extracting DOH {cat_name}"
            )

            resp = self.fetch_url(cat_url)
            if not resp or resp.status_code != 200:
                self.log_failed_page(cat_name, cat_url, f"HTTP {resp.status_code if resp else 'No response'}")
                continue

            records = self.parse_html_listing(resp.text, cat_name, cat_url, year_filter=year)
            if records:
                ins, dups = self.save_records(records)
                total_inserted += ins

        self.report_progress(
            progress_callback=progress_callback,
            category="All Categories",
            current_page=len(target_cats),
            total_pages=str(len(target_cats)),
            records_collected=total_inserted,
            status="Completed",
            message=f"DOH extraction completed with {total_inserted} records."
        )
        return total_inserted

    def parse_html_listing(
        self,
        html: str,
        category_name: str,
        source_url: str,
        year_filter: Optional[str] = None
    ) -> List[IssuanceRecord]:
        """
        Parses DOH Health Policies listings from HTML tables or card views.
        """
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Search for table-based listings
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Header detection
            col_map = {"num": 0, "title": 1, "date": 2}
            headers = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]
            for idx, h in enumerate(headers):
                if any(k in h for k in ["NO", "NUMBER", "CODE"]):
                    col_map["num"] = idx
                elif any(k in h for k in ["TITLE", "SUBJECT", "POLICY"]):
                    col_map["title"] = idx
                elif any(k in h for k in ["DATE", "PUBLISHED"]):
                    col_map["date"] = idx

            for r in rows[1:]:
                cells = r.find_all("td")
                if len(cells) < 2:
                    continue

                num_text = cells[col_map["num"]].get_text(strip=True) if col_map["num"] < len(cells) else ""
                title_text = cells[col_map["title"]].get_text(strip=True) if col_map["title"] < len(cells) else ""
                date_text = cells[col_map["date"]].get_text(strip=True) if col_map["date"] < len(cells) else ""

                if not title_text and not num_text:
                    continue

                if year_filter:
                    y_str = str(year_filter)
                    if y_str not in date_text and y_str not in title_text and y_str not in num_text:
                        continue

                link = r.find("a", href=True)
                full_link = urljoin(source_url, link["href"].strip()) if link else source_url

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=title_text or num_text,
                    publication_date=date_text,
                    source_url=full_link
                ))

        # 2. Search for div/card listings if no table records found
        if not records:
            items = soup.find_all(class_=lambda c: c and any(k in c.lower() for k in ["policy-item", "view-content", "views-row", "item-list"]))
            for item in items:
                title_elem = item.find(["h2", "h3", "h4", "a"])
                if not title_elem:
                    continue
                title_text = title_elem.get_text(strip=True)
                if len(title_text) < 4:
                    continue

                link_elem = item.find("a", href=True)
                full_link = urljoin(source_url, link_elem["href"].strip()) if link_elem else source_url
                
                # Extract date and number
                date_match = re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})\b", item.get_text())
                date_text = date_match.group(1) if date_match else ""
                
                num_match = re.search(r"((?:AO|DC|DM|JAO|JC)\s*(?:No\.)?\s*[\d-]+(?:\s*s\.\s*\d{4})?)", title_text, re.IGNORECASE)
                num_text = num_match.group(1) if num_match else ""

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=title_text,
                    publication_date=date_text,
                    source_url=full_link
                ))

        return records
