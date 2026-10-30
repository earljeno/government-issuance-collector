import re
import logging
from typing import List, Optional, Callable
from threading import Event
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from config import DEPARTMENTS
from database.models import IssuanceRecord

logger = logging.getLogger(__name__)

class DENRScraper(BaseScraper):
    def __init__(self):
        dept_cfg = DEPARTMENTS["DENR"]
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
            message="Connecting to DENR Digital Archive Portal..."
        )

        test_url = "http://www.denrtwelve.com:8090/das12/"
        resp = self.fetch_url(test_url)

        is_blocked = False
        block_reason = ""

        if not resp:
            is_blocked = True
            block_reason = "Connection timeout or domain unreachable"
        elif resp.status_code == 403 or "Just a moment..." in resp.text or "cf-chl" in resp.text:
            is_blocked = True
            block_reason = "Protected by Cloudflare WAF / Access Verification Required"

        if is_blocked:
            err_msg = (
                f"DENR portal is currently {block_reason}. "
                "Per system guidelines, automated bypass of access controls is prohibited and records must never be fabricated. "
                "Recorded department status as Temporarily Inaccessible. "
                "You may provide an accessible mirror URL via the 'Manual URL / HTML Import' button below."
            )
            logger.warning(f"[DENR] {err_msg}")
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

        # Process each category
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
                message=f"Extracting DENR {cat_name}"
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
            message=f"DENR extraction completed with {total_inserted} records."
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
        Parses DENR table-based digital archive listings and fallback structures.
        Extracts full official titles, complete dates, issuance numbers, and PDF URLs.
        """
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Primary: Structured Tables (as on DENR Digital Archive System & official policy repositories)
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Identify column indices dynamically by matching headers
            header_row = rows[0]
            headers = [th.get_text(strip=True).upper() for th in header_row.find_all(["th", "td"])]

            num_col = None
            title_col = None
            date_col = None

            for idx, h in enumerate(headers):
                if h in ["NO.", "NO", "DAO NO.", "NUMBER", "CODE", "ISSUANCE NO.", "ISSUANCE NUMBER"]:
                    num_col = idx
                elif any(k in h for k in ["SUBJECT", "TITLE", "DESCRIPTION", "POLICY"]):
                    title_col = idx
                elif any(k in h for k in ["DATE", "APPROVED", "YEAR", "ISSUED", "DATE APPROVED"]):
                    date_col = idx

            # Fallback column defaults if header matching didn't catch specific names
            if num_col is None and len(headers) >= 3:
                num_col = 0
            if title_col is None and len(headers) >= 3:
                title_col = 1
            if date_col is None and len(headers) >= 3:
                date_col = 2

            for r in rows[1:]:
                cells = r.find_all("td")
                if not cells:
                    continue

                num_text = cells[num_col].get_text(strip=True) if num_col is not None and num_col < len(cells) else ""
                title_text = cells[title_col].get_text(strip=True) if title_col is not None and title_col < len(cells) else ""
                date_text = cells[date_col].get_text(strip=True) if date_col is not None and date_col < len(cells) else ""

                if not title_text and not num_text:
                    continue

                # Clean up title: normalize whitespace
                clean_title = re.sub(r'\s+', ' ', title_text).strip()
                final_title = clean_title or num_text

                # Apply year filter if requested
                if year_filter:
                    y_str = str(year_filter)
                    if y_str not in date_text and y_str not in final_title and y_str not in num_text:
                        continue

                # Locate document attachment/download URL
                link = r.find("a", href=True)
                full_link = urljoin(source_url, link["href"].strip()) if link else source_url

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=num_text,
                    title=final_title,
                    publication_date=date_text,
                    source_url=full_link
                ))

            if records:
                return records

        # 2. Fallback: WordPress File Blocks (wp-block-file)
        file_blocks = soup.find_all("div", class_="wp-block-file")
        if file_blocks:
            for block in file_blocks:
                a_tag = block.find("a", class_=lambda c: not c or "button" not in c)
                if not a_tag:
                    a_tag = block.find("a", href=True)
                if not a_tag:
                    continue

                raw_title = a_tag.get_text(strip=True)
                file_url = urljoin(source_url, a_tag.get("href", "").strip())

                m_num = re.search(r'(?:DAO|DMC|DMO|JMC|JAO)?[\s_-]*((?:20\d\d|19\d\d)[-_]\d+[\w-]*)', raw_title, re.IGNORECASE)
                iss_num = m_num.group(0).strip() if m_num else ""

                m_yr = re.search(r'\b(19\d\d|20\d\d)\b', raw_title)
                pub_year = m_yr.group(1) if m_yr else ""

                if year_filter and str(year_filter) != pub_year:
                    continue

                records.append(IssuanceRecord(
                    department=self.department_name,
                    category=category_name,
                    issuance_number=iss_num,
                    title=raw_title,
                    publication_date=pub_year,
                    source_url=file_url
                ))

        return records
