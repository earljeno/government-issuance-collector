import re
import logging
from typing import List, Optional, Callable, Tuple
from threading import Event
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from config import DEPARTMENTS
from database.models import IssuanceRecord
from database.db import save_checkpoint, get_checkpoint, clear_checkpoint, log_quarantine

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
        max_pages_per_category: Optional[int] = None,
        resume: bool = False
    ) -> int:
        target_cats = categories if categories else list(self.categories_map.keys())
        total_inserted = 0
        total_duplicates = 0

        # Load active checkpoint if resuming
        checkpoint = get_checkpoint(self.department_name) if resume else None
        completed_cats = set(checkpoint.get("completed_categories", [])) if checkpoint else set()
        resume_cat = checkpoint.get("category") if checkpoint else None
        resume_page = checkpoint.get("page", 1) if checkpoint else 1

        self.report_progress(
            progress_callback=progress_callback,
            category="Initializing",
            current_page=0,
            total_pages=str(len(target_cats)),
            records_collected=0,
            status="Running",
            message=f"Starting DepEd extraction across {len(target_cats)} categories" + (f" (Resuming from {resume_cat} page {resume_page})" if resume and resume_cat else "")
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

            # Skip categories already completed in previous run
            if resume and cat_name in completed_cats:
                logger.info(f"[DepEd] Skipping already completed category: {cat_name}")
                continue

            base_cat_url = self.categories_map.get(cat_name)
            if not base_cat_url:
                continue

            # Determine starting page
            if resume and cat_name == resume_cat and resume_page > 1:
                cat_url = f"{base_cat_url.rstrip('/')}/page/{resume_page}/"
                logger.info(f"[DepEd] Resuming category {cat_name} from page {resume_page}: {cat_url}")
                resume_cat = None  # Consumed checkpoint page
            else:
                cat_url = base_cat_url

            visited_urls = set()
            cat_records_count = 0

            while cat_url:
                if cancel_event and cancel_event.is_set():
                    save_checkpoint(self.department_name, cat_name, current_page_num, cat_url, list(completed_cats))
                    break

                if cat_url in visited_urls:
                    logger.info(f"[DepEd] URL already visited ({cat_url}). Stopping pagination loop for {cat_name}.")
                    break
                visited_urls.add(cat_url)

                curr_match = re.search(r"/page/(\d+)/?", cat_url)
                current_page_num = int(curr_match.group(1)) if curr_match else 1

                # Safety guard against infinite loops (DepEd categories max out under 500 pages)
                if current_page_num > 600:
                    logger.warning(f"[DepEd] Safety page limit (600) reached for {cat_name}. Stopping.")
                    break

                # Save checkpoint before processing
                save_checkpoint(self.department_name, cat_name, current_page_num, cat_url, list(completed_cats))

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
                else:
                    # If page returned no records or is an empty/out-of-bounds page, end category
                    logger.info(f"[DepEd] No issuance records found on page {current_page_num} for {cat_name}. Ending category.")
                    break

                # Pagination limit check if set
                if max_pages_per_category and current_page_num >= max_pages_per_category:
                    logger.info(f"[DepEd] Reached max requested pages limit ({max_pages_per_category}) for {cat_name}.")
                    break

                if next_url and next_url != cat_url:
                    cat_url = next_url
                else:
                    logger.info(f"[DepEd] No further pages found for {cat_name} after page {current_page_num}.")
                    break

            # Mark category completed in checkpoint
            completed_cats.add(cat_name)
            save_checkpoint(self.department_name, cat_name, 1, "", list(completed_cats))

        # Clear checkpoint when entire run completes
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

        generic_titles = {
            "DEPED ORDER",
            "DEPED ORDERS",
            "DEPED MEMORANDUM",
            "DEPED MEMORANDA",
            "DEPED ADVISORY",
            "DEPED ADVISORIES",
            "OFFICE ORDER",
            "OFFICE ORDERS",
            "JOINT MEMORANDUM CIRCULAR",
            "IMPLEMENTING RULES AND REGULATIONS",
        }

        for art in articles:
            # Action 3: Scope title extraction exclusively to .entry-title a, h2.title a, h3 a
            title_tag = art.select_one(".entry-title a, h2.title a, h3 a")
            if not title_tag:
                continue

            # Action 2: Exclude pagination navigation links
            raw_href = title_tag.get("href", "").strip()
            if not raw_href or "/page/" in raw_href:
                continue

            post_link = urljoin(current_url, raw_href)
            if post_link == current_url or "/page/" in post_link:
                continue

            raw_title = title_tag.get_text(strip=True)
            if not raw_title or len(raw_title) < 4:
                continue

            # Reject generic placeholder titles
            if raw_title.upper() in generic_titles or re.match(r"^DEPED\s+(?:ORDER|ORDERS|MEMORANDUM|MEMORANDA|ADVISORY|ADVISORIES)$", raw_title, re.IGNORECASE):
                details = f"Generic placeholder title rejected: '{raw_title}'"
                log_quarantine(self.department_name, category_name, "Missing Metadata", details, post_link or current_url)
                continue

            # Parse issuance metadata from title and post
            iss_num, date_str, title_str = self._extract_metadata(raw_title, post_link, art)

            final_title = (title_str or raw_title).strip()
            if final_title.upper() in generic_titles or re.match(r"^DEPED\s+(?:ORDER|ORDERS|MEMORANDUM|MEMORANDA|ADVISORY|ADVISORIES)$", final_title, re.IGNORECASE):
                details = f"Generic placeholder title rejected: '{final_title}'"
                log_quarantine(self.department_name, category_name, "Missing Metadata", details, post_link or current_url)
                continue

            # Academic provenance: title must reflect policy and never be empty
            if not final_title and not iss_num:
                details = f"Post lacks both title and issuance number. Raw title: '{raw_title}', Date: '{date_str}'"
                log_quarantine(self.department_name, category_name, "Missing Metadata", details, post_link or current_url)
                continue
            if not final_title and iss_num:
                final_title = iss_num

            if not final_title:
                details = f"Post missing valid title. Number: '{iss_num}', Date: '{date_str}'"
                log_quarantine(self.department_name, category_name, "Missing Metadata", details, post_link or current_url)
                continue

            # Year filter checking
            if year_filter:
                year_s = str(year_filter)
                if year_s not in date_str and year_s not in raw_title and f"/{year_s}/" not in post_link:
                    continue

            self.check_url_academic_provenance(post_link, self.department_code, category=category_name, department_name=self.department_name)

            record = IssuanceRecord(
                department=self.department_name,
                category=category_name,
                issuance_number=iss_num,
                title=final_title,
                publication_date=date_str,
                source_url=post_link
            )
            records.append(record)

        # Detect next page URL (strictly forward pagination into older archives)
        curr_match = re.search(r"/page/(\d+)/?", current_url)
        curr_p = int(curr_match.group(1)) if curr_match else 1
        next_url = None

        # 1. Look for WordPress standard nav-previous container (which holds the older posts link)
        nav_prev = soup.find("div", class_="nav-previous")
        if nav_prev:
            a_tag = nav_prev.find("a", href=True)
            if a_tag and "/page/" in a_tag["href"]:
                candidate = urljoin(current_url, a_tag["href"].strip())
                cand_m = re.search(r"/page/(\d+)/?", candidate)
                if cand_m and int(cand_m.group(1)) > curr_p:
                    next_url = candidate

        # 2. Look for an explicit 'older' link (never follow 'newer' links which point backward)
        if not next_url:
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"].strip()
                if "older" in text and "newer" not in text and "/page/" in href:
                    candidate = urljoin(current_url, href)
                    cand_m = re.search(r"/page/(\d+)/?", candidate)
                    if cand_m and int(cand_m.group(1)) > curr_p:
                        next_url = candidate
                        break

        # 3. Fallback to standard /page/<curr_p + 1>/ candidate if explicitly present and not 'newer'
        if not next_url:
            candidate = re.sub(r"/page/\d+/?", f"/page/{curr_p + 1}/", current_url) if curr_match else current_url.rstrip("/") + "/page/2/"
            for a in soup.find_all("a", href=lambda h: h and candidate in h):
                text = a.get_text(strip=True).lower()
                if "newer" not in text:
                    next_url = candidate
                    break

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

        return issuance_number or "", date_str, title
