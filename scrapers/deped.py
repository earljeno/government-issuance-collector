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

class DepEdScraper(BaseScraper):
    def __init__(self):
        dept_cfg = DEPARTMENTS["DepEd"]
        super().__init__(dept_cfg["name"], dept_cfg["code"])
        self.categories_map = dept_cfg["categories"]

    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
        max_pages_per_category: Optional[int] = None
    ) -> int:
        target_cats = categories if categories else list(self.categories_map.keys())
        total_inserted = 0
        total_duplicates = 0

        self.report_progress(
            progress_callback=progress_callback,
            category="Initializing",
            current_page=0,
            total_pages=str(len(target_cats)),
            records_collected=0,
            status="Running",
            message=f"Starting DepEd extraction across {len(target_cats)} categories"
        )

        for cat_idx, cat_name in enumerate(target_cats, start=1):
            if cancel_event and cancel_event.is_set():
                logger.info("[DepEd] Extraction cancelled by user.")
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

            base_cat_url = self.categories_map.get(cat_name)
            if not base_cat_url:
                continue

            current_page_num = 1
            cat_url = base_cat_url
            cat_records_count = 0

            while cat_url:
                if cancel_event and cancel_event.is_set():
                    break

                self.report_progress(
                    progress_callback=progress_callback,
                    category=cat_name,
                    current_page=current_page_num,
                    total_pages="Scanning...",
                    records_collected=total_inserted,
                    status="Running",
                    message=f"Processing {cat_name} (Page {current_page_num})"
                )

                resp = self.fetch_url(cat_url)
                if not resp or resp.status_code != 200:
                    if resp and resp.status_code == 404:
                        logger.info(f"[DepEd] Reached end of pagination for {cat_name} at page {current_page_num}.")
                    else:
                        err_msg = f"Failed to fetch {cat_url} (HTTP {resp.status_code if resp else 'No response'})"
                        logger.error(f"[DepEd] {err_msg}")
                        self.log_failed_page(cat_name, cat_url, err_msg)
                    break

                page_records, next_url = self._parse_page(resp.text, cat_name, cat_url, year_filter=year)

                if page_records:
                    ins, dups = self.save_records(page_records)
                    total_inserted += ins
                    total_duplicates += dups
                    cat_records_count += len(page_records)

                # Pagination limit check if set
                if max_pages_per_category and current_page_num >= max_pages_per_category:
                    logger.info(f"[DepEd] Reached max requested pages limit ({max_pages_per_category}) for {cat_name}.")
                    break

                if next_url and next_url != cat_url:
                    cat_url = next_url
                    current_page_num += 1
                else:
                    logger.info(f"[DepEd] No further pages found for {cat_name} after page {current_page_num}.")
                    break

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

    def _parse_page(
        self,
        html: str,
        category_name: str,
        current_url: str,
        year_filter: Optional[str] = None
    ) -> Tuple[List[IssuanceRecord], Optional[str]]:
        records: List[IssuanceRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        articles = soup.find_all("article")
        if not articles:
            articles = soup.find_all(class_=lambda c: c and ("post" in c or "entry" in c))

        for art in articles:
            h_tag = art.find(["h1", "h2", "h3", "h4"])
            if not h_tag:
                continue

            raw_title = h_tag.get_text(strip=True)
            if not raw_title or len(raw_title) < 4:
                continue

            # Link
            a_tag = h_tag.find("a", href=True)
            post_link = urljoin(current_url, a_tag["href"].strip()) if a_tag else current_url

            # Parse issuance metadata from title and post
            iss_num, date_str, title_str = self._extract_metadata(raw_title, post_link, art)

            # Year filter checking
            if year_filter:
                year_s = str(year_filter)
                if year_s not in date_str and year_s not in raw_title and f"/{year_s}/" not in post_link:
                    continue

            record = IssuanceRecord(
                department=self.department_name,
                category=category_name,
                issuance_number=iss_num,
                title=title_str or raw_title,
                publication_date=date_str,
                source_url=post_link
            )
            records.append(record)

        # Detect next page URL
        next_url = None
        # Look for "Older posts" link or next pagination anchor
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"].strip()
            if ("older" in text or "next" in text or "→" in text or "»" in text) and "/page/" in href:
                next_url = urljoin(current_url, href)
                break

        # Fallback to standard /page/<n+1>/ link if not found above
        if not next_url:
            curr_match = re.search(r"/page/(\d+)/?", current_url)
            if curr_match:
                curr_page = int(curr_match.group(1))
                candidate = re.sub(r"/page/\d+/?", f"/page/{curr_page + 1}/", current_url)
                if soup.find("a", href=lambda h: h and candidate in h):
                    next_url = candidate
            else:
                candidate = current_url.rstrip("/") + "/page/2/"
                if soup.find("a", href=lambda h: h and candidate in h):
                    next_url = candidate

        return records, next_url

    def _extract_metadata(self, raw_title: str, post_link: str, article_elem) -> Tuple[str, str, str]:
        """
        Extracts issuance_number, date, and clean title using a multi-stage fault-tolerant pipeline:
        Stage 1: Listing title pattern matching (handles non-standard spacing, tabs, missing 's.')
        Stage 2: Permalink URL slug analysis (handles 'may-4-2016-da-106-s-2016', 'may-4-2016-da-107-2016', etc.)
        Stage 3: Webpage inspection fallback (fetches post page to inspect PDF attachment codes like 'DA_s2016_107')
        """
        clean_title = re.sub(r'[\t\r\n]+', ' ', raw_title).strip()
        issuance_number = ""
        date_str = ""
        title = clean_title

        # --- DATE EXTRACTION ---
        url_date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", post_link)
        if url_date_match:
            y, m, d = url_date_match.groups()
            date_str = f"{y}-{m}-{d}"
            url_year = y
        else:
            y_match = re.search(r"/(\d{4})/", post_link) or re.search(r"\b(19\d\d|20\d\d)\b", clean_title)
            url_year = y_match.group(1) if y_match else ""

        if article_elem:
            time_tag = article_elem.find("time")
            if time_tag and time_tag.get_text(strip=True):
                date_str = time_tag.get_text(strip=True)

        date_prefix_match = re.match(
            r"^([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*(?:–|-|:)?\s*",
            clean_title
        )
        if date_prefix_match:
            date_str = date_prefix_match.group(1).strip()

        # --- STAGE 1: TITLE PATTERN MATCHING ---
        # 1A. Direct code: DA_s2016_107, DM_s2020_040
        m_direct = re.search(r"\b((?:DA|DM|DO|AO|DC)_[sS]\d{4}_\d+[\w-]*)\b", clean_title, re.IGNORECASE)
        if m_direct:
            issuance_number = m_direct.group(1).upper()

        # 1B. Prefix + number + year/series (e.g. 'DA 107, 2016', 'DA 106, s. 2016', 'ADVISORY 247, s. 2025')
        if not issuance_number:
            pat_full = re.search(
                r"\b("
                r"(?:ADVISORY|DepEd Advisory|DA|DM|DO|DepEd Order|DepEd Memorandum|Joint Memorandum Circular|JMC|Office Order|Bid Bulletin)\s*"
                r"(?:No\.?|Number)?\s*"
                r"(\d+)[\w-]*(?:,\s*|\s+)(?:s\.\s*|series of\s*)?(\d{4})"
                r")\b",
                clean_title,
                re.IGNORECASE
            )
            if pat_full:
                full_txt = pat_full.group(1).strip()
                num_val = pat_full.group(2)
                yr_val = pat_full.group(3)
                prefix = full_txt.split()[0].upper()
                if prefix in ["ADVISORY", "DEPED"]:
                    prefix = "DA"

                m_s = re.search(r's\.\s*\d{4}', full_txt, re.IGNORECASE)
                if not m_s:
                    base_txt = re.sub(r',\s*\d{4}$', '', full_txt).strip()
                    canonical = f"{base_txt}, s. {yr_val}"
                    code_suffix = f"{prefix}_s{yr_val}_{num_val}" if prefix in ["DA", "DM", "DO", "AO"] else ""
                    issuance_number = f"{canonical} ({code_suffix})" if code_suffix else canonical
                else:
                    issuance_number = full_txt

        # 1C. Prefix + number without year (e.g. 'DA 217', 'DA 215')
        if not issuance_number:
            pat_no_yr = re.search(
                r"\b("
                r"(?:ADVISORY|DepEd Advisory|DA|DM|DO|DepEd Order|DepEd Memorandum|Office Order|Bid Bulletin)\s*"
                r"(?:No\.?|Number)?\s*"
                r"(\d+)[\w-]*"
                r")\b",
                clean_title,
                re.IGNORECASE
            )
            if pat_no_yr:
                candidate = pat_no_yr.group(1).strip()
                num_val = pat_no_yr.group(2)
                if candidate.lower() not in ["advisory", "order", "memorandum", "bulletin", "da", "dm", "do"]:
                    prefix = candidate.split()[0].upper()
                    if prefix in ["ADVISORY", "DEPED"]:
                        prefix = "DA"
                    if url_year:
                        canonical = f"{candidate}, s. {url_year}"
                        code_suffix = f"{prefix}_s{url_year}_{num_val}" if prefix in ["DA", "DM", "DO", "AO"] else ""
                        issuance_number = f"{canonical} ({code_suffix})" if code_suffix else canonical
                    else:
                        issuance_number = candidate

        # --- STAGE 2: URL PERMALINK / SLUG ANALYSIS ---
        # Handles slugs like:
        # 'may-4-2016-da-106-s-2016-...'
        # 'may-4-2016-da-107-2016-...'
        # 'december-29-2016-da-365-s-2016-...'
        if not issuance_number and post_link:
            slug = post_link.split("/")[-2] if post_link.endswith("/") else post_link.split("/")[-1]
            slug_pat = re.search(
                r'(?:^|[-_])'
                r'(da|dm|do|ao|dc|advisory|order|memorandum)'
                r'[-_](?:no[-_])?'
                r'(\d+)'
                r'[-_](?:s[-_]|series[-_])?'
                r'(\d{4})',
                slug,
                re.IGNORECASE
            )
            if slug_pat:
                p = slug_pat.group(1).upper()
                if p in ["ADVISORY", "DEPED"]:
                    p = "DA"
                elif p == "MEMORANDUM":
                    p = "DM"
                elif p == "ORDER":
                    p = "DO"
                num_val = slug_pat.group(2)
                yr_val = slug_pat.group(3)
                issuance_number = f"{p} {num_val}, s. {yr_val} ({p}_s{yr_val}_{num_val})"

        # --- STAGE 3: WEBPAGE DEEP INSPECTION (FAULT TOLERANCE) ---
        # If still not securely identified, fetch the post webpage to inspect PDF attachments & text
        if (not issuance_number or "Unnumbered" in issuance_number) and post_link and "deped.gov.ph" in post_link:
            try:
                resp = self.fetch_url(post_link)
                if resp and resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    content = soup.find('div', class_='entry-content') or soup

                    # 3A. Look for PDF attachment anchor texts and hrefs (e.g. 'DA_s2016_107', 'DA_s2016_106')
                    for a in content.find_all('a', href=True):
                        txt = a.get_text(strip=True)
                        href = a['href']
                        m_pdf = re.search(r'\b((?:DA|DM|DO|AO|OSEC)[-_][sS]?\d{4}[-_]\d+[\w-]*)\b', txt, re.IGNORECASE) or \
                                re.search(r'/((?:DA|DM|DO|AO|OSEC)[-_][sS]?\d{4}[-_]\d+[\w-]*)\.pdf', href, re.IGNORECASE) or \
                                re.search(r'\b((?:DA|DM|DO|AO|OSEC)[-_]\w+)\b', txt)
                        if m_pdf:
                            code_found = m_pdf.group(1).upper()
                            # Parse code if possible: e.g. DA_S2016_107 -> DA 107, s. 2016 (DA_s2016_107)
                            m_code_parts = re.search(r'([A-Z]+)[-_][sS]?(\d{4})[-_](\d+)', code_found)
                            if m_code_parts:
                                p, y, n = m_code_parts.groups()
                                issuance_number = f"{p} {n}, s. {y} ({p}_s{y}_{n})"
                            else:
                                issuance_number = code_found
                            break

                    # 3B. Check article headings / body if still not found
                    if not issuance_number:
                        for p_elem in content.find_all(['h1', 'h2', 'h3', 'p']):
                            p_txt = p_elem.get_text(strip=True)
                            m_body = re.search(r'\b((?:DepEd\s+)?(?:Advisory|Order|Memorandum)\s*(?:No\.?)?\s*\d+[\w-]*(?:,\s*s\.\s*\d{4})?)\b', p_txt, re.IGNORECASE)
                            if m_body:
                                issuance_number = m_body.group(1).strip()
                                break
            except Exception as e:
                logger.debug(f"[DepEd] Webpage inspection error for {post_link}: {e}")

        # --- STAGE 4: CLEAN TITLE ---
        parts = re.split(r"\s*[–—]\s*", clean_title, maxsplit=1)
        if len(parts) > 1 and len(parts[1].strip()) > 3:
            title = parts[1].strip()
        elif issuance_number:
            t_sub = re.sub(r"^([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*", "", clean_title)
            parts2 = re.split(r"\s*[–—]\s*", t_sub, maxsplit=1)
            if len(parts2) > 1:
                title = parts2[1].strip()

        return issuance_number or "Unnumbered Notice", date_str, title
