import re
import requests
import urllib3
import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT_SECONDS
from database.models import IssuanceRecord

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class ManualURLExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def analyze_and_extract(
        self,
        url: Optional[str] = None,
        html_content: Optional[str] = None,
        department_name: str = "Manual Import",
        category_name: str = "General Issuances"
    ) -> Dict:
        """
        Fetches or takes provided HTML, detects page record structure,
        extracts issuance records and pagination links, and returns a preview.
        """
        if not html_content and url:
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to fetch URL. HTTP Status: {resp.status_code}",
                        "records": [],
                        "structure": "None",
                        "pagination": []
                    }
                html_content = resp.text
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Network error fetching URL: {str(e)}",
                    "records": [],
                    "structure": "None",
                    "pagination": []
                }

        if not html_content:
            return {
                "success": False,
                "error": "No URL or HTML content provided",
                "records": [],
                "structure": "None",
                "pagination": []
            }

        base_url = url or "https://official.gov.ph"
        soup = BeautifulSoup(html_content, "html.parser")

        # Detect pagination
        pagination_links = self._detect_pagination(soup, base_url)

        # Attempt 1: Table Detection
        records, struct_name = self._extract_from_tables(soup, base_url, department_name, category_name)

        # Attempt 2: Article / Post Container Detection
        if not records:
            records, struct_name = self._extract_from_articles(soup, base_url, department_name, category_name)

        # Attempt 3: List / Link Pattern Detection
        if not records:
            records, struct_name = self._extract_from_links(soup, base_url, department_name, category_name)

        return {
            "success": True,
            "structure": struct_name,
            "total_found": len(records),
            "pagination": pagination_links,
            "records": [r.to_dict() for r in records]
        }

    def _detect_pagination(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        pagination_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            txt = a.get_text(strip=True).lower()
            if any(k in txt for k in ["next", "older", "prev", "page", "›", "»", "→"]) or re.search(r"page[=/]\d+", href):
                full = urljoin(base_url, href)
                if full not in pagination_links and full != base_url:
                    pagination_links.append(full)
        return pagination_links[:10]

    def _extract_from_tables(self, soup: BeautifulSoup, base_url: str, dept: str, cat: str) -> Tuple[List[IssuanceRecord], str]:
        tables = soup.find_all("table")
        records: List[IssuanceRecord] = []
        
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Header mapping
            col_map = {"num": 0, "title": 1, "date": 2}
            first_row_cells = rows[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True).upper() for c in first_row_cells]

            for idx, h in enumerate(headers):
                if any(k in h for k in ["NO", "NUMBER", "CODE", "SERIES"]):
                    col_map["num"] = idx
                elif any(k in h for k in ["TITLE", "SUBJECT", "NAME", "DESCRIPTION"]):
                    col_map["title"] = idx
                elif any(k in h for k in ["DATE", "YEAR", "PUBLISHED", "ISSUED"]):
                    col_map["date"] = idx

            for r in rows[1:]:
                cells = r.find_all("td")
                if len(cells) < 2:
                    continue

                num = cells[col_map["num"]].get_text(strip=True) if col_map["num"] < len(cells) else ""
                title = cells[col_map["title"]].get_text(strip=True) if col_map["title"] < len(cells) else ""
                date = cells[col_map["date"]].get_text(strip=True) if col_map["date"] < len(cells) else ""

                if not title and not num:
                    continue

                final_title = title or num
                if not final_title:
                    continue

                a_tag = r.find("a", href=True)
                src = ""
                if a_tag and a_tag.get("href"):
                    raw_href = a_tag["href"].strip()
                    if raw_href and raw_href != "#":
                        candidate = urljoin(base_url, raw_href)
                        if candidate != base_url:
                            src = candidate

                if src:
                    lower_url = src.lower()
                    if lower_url.endswith(".jpg") or lower_url.endswith(".jpeg") or lower_url.endswith(".png") or "drive.google.com" in lower_url:
                        logger.warning(f"[ManualImport] Academic Provenance Warning: Non-PDF/HTML or non-government drive URL: {src}")

                records.append(IssuanceRecord(
                    department=dept,
                    category=cat,
                    issuance_number=num,
                    title=final_title,
                    publication_date=date,
                    source_url=src
                ))

        if records:
            return records, f"HTML Table ({len(records)} rows detected)"
        return [], "None"

    def _extract_from_articles(self, soup: BeautifulSoup, base_url: str, dept: str, cat: str) -> Tuple[List[IssuanceRecord], str]:
        items = soup.find_all(["article", "div"], class_=lambda c: c and any(k in c.lower() for k in ["post", "entry", "item", "card"]))
        records: List[IssuanceRecord] = []

        for item in items:
            h = item.find(["h1", "h2", "h3", "h4", "h5"])
            if not h:
                continue
            title_text = h.get_text(strip=True)
            if len(title_text) < 4:
                continue

            a_tag = h.find("a", href=True) or item.find("a", href=True)
            src = ""
            if a_tag and a_tag.get("href"):
                raw_href = a_tag["href"].strip()
                if raw_href and raw_href != "#":
                    candidate = urljoin(base_url, raw_href)
                    if candidate != base_url:
                        src = candidate

            if src:
                lower_url = src.lower()
                if lower_url.endswith(".jpg") or lower_url.endswith(".jpeg") or lower_url.endswith(".png") or "drive.google.com" in lower_url:
                    logger.warning(f"[ManualImport] Academic Provenance Warning: Non-PDF/HTML or non-government drive URL: {src}")

            # Extract date
            time_tag = item.find("time") or item.find(class_=lambda c: c and "date" in c.lower())
            date_text = time_tag.get_text(strip=True) if time_tag else ""
            if not date_text:
                d_match = re.search(r"\b([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})\b", item.get_text())
                date_text = d_match.group(1) if d_match else ""

            # Extract issuance number
            num_match = re.search(r"((?:AO|DO|DM|MC|SO|AC|JAO)\s*(?:No\.)?\s*[\d-]+(?:,\s*s\.\s*\d{4})?)", title_text, re.IGNORECASE)
            num_text = num_match.group(1) if num_match else ""

            records.append(IssuanceRecord(
                department=dept,
                category=cat,
                issuance_number=num_text,
                title=title_text,
                publication_date=date_text,
                source_url=src
            ))

        if records:
            return records, f"Post / Article Cards ({len(records)} items detected)"
        return [], "None"

    def _extract_from_links(self, soup: BeautifulSoup, base_url: str, dept: str, cat: str) -> Tuple[List[IssuanceRecord], str]:
        records: List[IssuanceRecord] = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"].strip()
            if len(text) > 10 and any(k in text.lower() or k in href.lower() for k in ["order", "circular", "memorand", "advisory", "act", "resolution"]):
                src = urljoin(base_url, href) if href and href != "#" else ""
                if src == base_url:
                    src = ""
                if src:
                    lower_url = src.lower()
                    if lower_url.endswith(".jpg") or lower_url.endswith(".jpeg") or lower_url.endswith(".png") or "drive.google.com" in lower_url:
                        logger.warning(f"[ManualImport] Academic Provenance Warning: Non-PDF/HTML or non-government drive URL: {src}")
                records.append(IssuanceRecord(
                    department=dept,
                    category=cat,
                    issuance_number="",
                    title=text,
                    publication_date="",
                    source_url=src
                ))
        if records:
            return records, f"Hyperlink Document Listing ({len(records)} links detected)"
        return [], "None"
