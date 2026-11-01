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

        # Attempt 4: Plain Text / Screen Copy Heuristic Detection
        if not records and html_content:
            records, struct_name = self._extract_from_plain_text(html_content, base_url, department_name, category_name)

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

    def _extract_from_plain_text(self, text: str, base_url: str, dept: str, cat: str) -> Tuple[List[IssuanceRecord], str]:
        """
        Parses unformatted or formatted text copied directly from a screen/table.
        Supports tab-separated clipboard tables, multi-line blocks, and line streams.
        """
        from database.validator import sanitize_publication_date
        records: List[IssuanceRecord] = []
        clean_text = text.strip()
        if not clean_text:
            return [], "None"

        default_url = base_url if (base_url and base_url != "https://official.gov.ph") else ""

        # Case 1: Tab-separated table copy
        lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
        if any("\t" in ln for ln in lines):
            for ln in lines:
                parts = [p.strip() for p in ln.split("\t") if p.strip()]
                if not parts:
                    continue
                # Skip header row if all parts look like column headers
                if any(h in parts[0].upper() for h in ["NUMBER", "NO.", "SERIES", "ISSUANCE"]) and any(h in "".join(parts).upper() for h in ["TITLE", "SUBJECT", "DATE"]):
                    continue

                num = ""
                title = ""
                date = ""
                src = default_url

                for part in parts:
                    if part.startswith("http://") or part.startswith("https://"):
                        src = part
                    elif not date and re.search(r"\b(20\d{2}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})\b", part):
                        date = sanitize_publication_date(part)
                    elif not num and (re.search(r"\b(20\d{2}-\d{1,5}|\d{1,5})\b", part) or any(k in part.upper() for k in ["AO", "DO", "DC", "MC", "EO", "RA", "NO."])):
                        num = part
                    elif not title:
                        title = part
                    else:
                        title += f" - {part}"

                if title or num:
                    records.append(IssuanceRecord(
                        department=dept,
                        category=cat,
                        issuance_number=num,
                        title=title or num,
                        publication_date=date,
                        source_url=src
                    ))
            if records:
                return records, f"Tab-Separated Screen Table ({len(records)} records detected)"

        # Case 2: Multi-line and line-stream smart grouping
        def is_url(s: str) -> bool:
            return s.startswith("http://") or s.startswith("https://")

        def is_date(s: str) -> bool:
            return bool(re.search(r"\b([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b", s))

        def is_num(s: str) -> bool:
            return bool(re.search(r"\b((?:Executive Order|Administrative Order|Department Circular|Memorandum Circular|Republic Act|AO|DO|DC|MC|EO|RA|SO|JAO|JMC)\s*(?:No\.?)?\s*[\d-]+|\b20\d{2}-\d{1,5}\b|^\d{1,4}$)\b", s, re.IGNORECASE))

        curr_num = ""
        curr_title = ""
        curr_date = ""
        curr_url = default_url

        for ln in lines:
            if is_url(ln):
                curr_url = ln
            elif is_date(ln) and not curr_date:
                curr_date = sanitize_publication_date(ln)
            elif is_num(ln) and not curr_num:
                curr_num = ln
            elif not curr_title:
                curr_title = ln
            else:
                if is_num(ln) or (curr_title and curr_date):
                    records.append(IssuanceRecord(
                        department=dept,
                        category=cat,
                        issuance_number=curr_num,
                        title=curr_title or curr_num,
                        publication_date=curr_date,
                        source_url=curr_url
                    ))
                    curr_num = ln if is_num(ln) else ""
                    curr_title = "" if is_num(ln) else ln
                    curr_date = ""
                    curr_url = default_url
                else:
                    curr_title += f" {ln}"

        if curr_title or curr_num:
            records.append(IssuanceRecord(
                department=dept,
                category=cat,
                issuance_number=curr_num,
                title=curr_title or curr_num,
                publication_date=curr_date,
                source_url=curr_url
            ))

        if records:
            return records, f"Screen Text Stream ({len(records)} records detected)"
        return [], "None"
