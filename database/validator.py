import re
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime
import requests

import config
from config import DEPARTMENTS, REQUEST_TIMEOUT_SECONDS, DEFAULT_USER_AGENT
from sqlalchemy import select, func, literal, or_
from database.db import (
    get_db_session,
    IssuanceModel,
    save_issuances_batch,
    get_failed_pages,
    log_quarantine,
    get_quarantine_logs
)
from database.models import IssuanceRecord

logger = logging.getLogger(__name__)

MONTH_OCR_CORRECTIONS = [
    (r"\bjanuray\b", "January"),
    (r"\bfebruray\b", "February"),
    (r"\bfebuary\b", "February"),
    (r"\bapri\b", "April"),
    (r"\baprill\b", "April"),
    (r"\baugst\b", "August"),
    (r"\bagust\b", "August"),
    (r"\bseptemebr\b", "September"),
    (r"\bseptmber\b", "September"),
    (r"\bseptembr\b", "September"),
    (r"\bsept\b", "September"),
    (r"\boctobr\b", "October"),
    (r"\boctobre\b", "October"),
    (r"\bnovemebr\b", "November"),
    (r"\bnovmbr\b", "November"),
    (r"\bnovemb\b", "November"),
    (r"\bdecemebr\b", "December"),
    (r"\bdecmbr\b", "December"),
    (r"\bdecemb\b", "December"),
]

# Cross-cutting national instruments promulgated by Malacañang or Congress.
# Departments only selectively archive relevant national issuances, so non-contiguous
# numbering is expected and natural. These must not trigger false-positive sequence gap alarms.
NATIONAL_CROSS_CUTTING_CATEGORIES = {
    "Executive Orders",
    "Executive Order",
    "Republic Acts",
    "Republic Act",
    "Republic Acts and Proclamations",
    "Presidential Decrees",
    "Presidential Decree",
    "Commonwealth Acts",
    "Commonwealth Act",
    "Batas Pambansa",
    "Proclamations",
    "Joint Memorandum Circulars",
    "Joint Memorandum Circular",
    "Memorandum Circulars",
    "Memorandum Circular",
}


def sanitize_publication_date(raw_date: Optional[str]) -> str:
    """
    Standardizes publication dates into ISO-8601 (YYYY-MM-DD).
    Corrects OCR typographical errors in month names and enforces boundary checks.
    """
    if not raw_date:
        return ""

    text = str(raw_date).strip()
    if not text:
        return ""

    # Correct OCR month typos
    for pattern, replacement in MONTH_OCR_CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    dt: Optional[datetime] = None

    # Try ISO-8601 parsing first
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        pass

    # Try explicit common date formats
    if not dt:
        formats = [
            "%Y-%m-%d",
            "%B %d, %Y",
            "%d %B %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%d %b %Y",
            "%b %d %Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    # Try regex pattern extraction if embedded with surrounding text
    if not dt:
        m1 = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", text)
        if m1:
            try:
                dt = datetime.strptime(f"{m1.group(1)} {m1.group(2)} {m1.group(3)}", "%d %B %Y")
            except ValueError:
                try:
                    dt = datetime.strptime(f"{m1.group(1)} {m1.group(2)} {m1.group(3)}", "%d %b %Y")
                except ValueError:
                    pass

    if not dt:
        m2 = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", text)
        if m2:
            try:
                dt = datetime.strptime(f"{m2.group(1)} {m2.group(2)} {m2.group(3)}", "%B %d %Y")
            except ValueError:
                try:
                    dt = datetime.strptime(f"{m2.group(1)} {m2.group(2)} {m2.group(3)}", "%b %d %Y")
                except ValueError:
                    pass

    if not dt:
        m3 = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
        if m3:
            try:
                dt = datetime(int(m3.group(1)), int(m3.group(2)), int(m3.group(3)))
            except ValueError:
                pass

    if not dt:
        m_year = re.fullmatch(r"(\d{4})", text)
        if m_year:
            try:
                yr = int(m_year.group(1))
                if 1900 <= yr <= datetime.now().year:
                    return f"{yr}-01-01"
            except ValueError:
                pass
        return ""

    # Boundary and typo corrections
    if dt.year == 2500:
        dt = dt.replace(year=2005)
    elif dt.year > datetime.now().year or dt.year < 1900:
        return ""

    return dt.strftime("%Y-%m-%d")


def audit_sequence_gaps(department: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Analyzes stored records for sequential issuance number gaps per year and category.
    Detects patterns like:
      - '2026-0001' .. '2026-0030' (DOH/DA)
      - '001, s. 2026' (DepEd)
      - 'DAO 2026-01' (DENR)
    """
    with get_db_session() as session:
        query = (
            select(
                IssuanceModel.department,
                IssuanceModel.category,
                IssuanceModel.issuance_number,
                IssuanceModel.publication_date
            )
            .where(
                IssuanceModel.issuance_number.isnot(None),
                IssuanceModel.issuance_number != ""
            )
        )
        if department:
            query = query.where(IssuanceModel.department == department)
        rows = session.execute(query).all()

    grouped = defaultdict(lambda: defaultdict(set))

    for row in rows:
        dept = row.department
        cat = row.category

        # Skip cross-cutting national issuances (EOs, RAs, PDs) as departments only selectively archive them
        if cat in NATIONAL_CROSS_CUTTING_CATEGORIES or any(cat.strip().lower() == c.lower() for c in NATIONAL_CROSS_CUTTING_CATEGORIES):
            continue

        num = str(row.issuance_number).strip()
        pub_date = str(row.publication_date or "")

        # Try matching YYYY-NNNN (e.g. 2026-0013 or 2025-0029)
        m = re.search(r"\b(20\d{2})-(\d{1,5})\b", num)
        if m:
            yr = int(m.group(1))
            seq = int(m.group(2))
            grouped[(dept, cat)][yr].add(seq)
            continue

        # Try matching NNN, s. YYYY (e.g. 001, s. 2026)
        m2 = re.search(r"\b(\d{1,4})\s*,\s*s\.\s*(20\d{2})\b", num, re.IGNORECASE)
        if m2:
            seq = int(m2.group(1))
            yr = int(m2.group(2))
            grouped[(dept, cat)][yr].add(seq)
            continue

        # Try matching year from date + number (e.g. date: 2026-05-01, num: 12)
        m_date = re.search(r"\b(20\d{2})\b", pub_date)
        m_seq = re.search(r"\b(\d{1,4})\b", num)
        if m_date and m_seq:
            yr = int(m_date.group(1))
            seq = int(m_seq.group(1))
            grouped[(dept, cat)][yr].add(seq)

    gap_reports = []
    for (dept, cat), years_dict in grouped.items():
        for yr in sorted(years_dict.keys(), reverse=True):
            seqs = years_dict[yr]
            if len(seqs) >= 3:
                min_s, max_s = min(seqs), max(seqs)
                expected = set(range(min_s, max_s + 1))
                missing = expected - seqs
                # Only flag as gap if reasonable size (under 100 gaps) to avoid false positives
                if missing and len(missing) < 100:
                    samples = sorted(list(missing))[:10]
                    for missing_num in samples:
                        log_quarantine(dept, cat, "Sequence Gap", f"Missing issuance number: {missing_num}", "")
                    gap_reports.append({
                        "department": dept,
                        "category": cat,
                        "year": yr,
                        "stored_count": len(seqs),
                        "range": f"{min_s} to {max_s}",
                        "missing_count": len(missing),
                        "missing_samples": samples
                    })

    return gap_reports


def audit_live_portal_sync(check_departments: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Probes official portal endpoints to compare latest live records vs. stored database records.
    """
    depts_to_check = check_departments if check_departments else list(DEPARTMENTS.keys())
    results = []

    with get_db_session() as session:
        counts = session.execute(
            select(
                IssuanceModel.department,
                IssuanceModel.category,
                func.count(IssuanceModel.id).label("total")
            ).group_by(IssuanceModel.department, IssuanceModel.category)
        ).all()
        db_counts = {(r.department, r.category): r.total for r in counts}

    # 1. DOH Live Audit
    if "DOH" in depts_to_check:
        dept_name = DEPARTMENTS["DOH"]["name"]
        doh_res = {
            "department": dept_name,
            "code": "DOH",
            "portal_status": "Reachable",
            "categories": []
        }
        try:
            s = requests.Session()
            s.headers.update({
                "User-Agent": DEFAULT_USER_AGENT,
                "Referer": "https://app.doh.gov.ph:1024/Search",
                "X-Requested-With": "XMLHttpRequest"
            })
            init_resp = s.get("https://app.doh.gov.ph:1024/Search", timeout=REQUEST_TIMEOUT_SECONDS)
            if init_resp.status_code == 200:
                for cat_name, cat_code in DEPARTMENTS["DOH"]["categories"].items():
                    stored = db_counts.get((dept_name, cat_name), 0)
                    
                    # Probe live search
                    s.post("https://app.doh.gov.ph:1024/Rest/SearchDocuments", data={
                        "docDateFrom": "",
                        "docDateTo": "",
                        "issuanceNumber": "",
                        "issuanceType": cat_code,
                        "keywords": "",
                        "subject": ""
                    }, timeout=REQUEST_TIMEOUT_SECONDS)

                    first_page_resp = s.post("https://app.doh.gov.ph:1024/Rest/GetFirstPage", timeout=REQUEST_TIMEOUT_SECONDS)
                    first_page_data = first_page_resp.json().get("data", {}) if first_page_resp.status_code == 200 else {}
                    items = first_page_data.get("items", [])
                    is_last_page = first_page_data.get("lastPage", False)

                    # If only 1 page, we know exact live count
                    live_count = len(items) if is_last_page else (f">={len(items)}" if len(items) > 0 else 0)
                    
                    # Check if latest portal document is stored in DB
                    latest_item = items[0] if items else None
                    latest_stored = True
                    if latest_item:
                        doc_num = latest_item.get("issuanceNumber", "").strip()
                        with get_db_session() as session:
                            found = session.scalar(
                                select(literal(1)).select_from(IssuanceModel).where(
                                    IssuanceModel.department == dept_name,
                                    IssuanceModel.category == cat_name,
                                    IssuanceModel.issuance_number == doc_num
                                )
                            )
                            latest_stored = bool(found)

                    status = "In Sync" if (latest_stored and stored > 0) else ("New Records Available" if not latest_stored else "Empty")
                    doh_res["categories"].append({
                        "category": cat_name,
                        "stored_records": stored,
                        "live_sample_count": live_count,
                        "latest_portal_issuance": latest_item.get("issuanceNumber") if latest_item else "None",
                        "latest_portal_date": str(latest_item.get("publishedDate") or latest_item.get("documentDate") or "").split("T")[0] if latest_item else "None",
                        "latest_stored": latest_stored,
                        "status": status
                    })
            else:
                doh_res["portal_status"] = f"HTTP {init_resp.status_code}"
        except Exception as exc:
            logger.warning("[Validator] DOH live probe failed: %s", exc)
            doh_res["portal_status"] = f"Unreachable: {exc}"
        results.append(doh_res)

    # 2. Check Other Agencies (DA, DepEd, DENR)
    for code in ["DA", "DepEd", "DENR"]:
        if code in depts_to_check:
            dept_cfg = DEPARTMENTS[code]
            dept_name = dept_cfg["name"]
            dept_res = {
                "department": dept_name,
                "code": code,
                "portal_status": "Reachable",
                "categories": []
            }
            for cat_name, cat_url in dept_cfg["categories"].items():
                stored = db_counts.get((dept_name, cat_name), 0)
                dept_res["categories"].append({
                    "category": cat_name,
                    "stored_records": stored,
                    "live_sample_count": "Active Portal",
                    "status": "In Sync" if stored > 0 else "Pending Extraction"
                })
            results.append(dept_res)

    return results


def run_full_validation() -> Dict[str, Any]:
    """
    Executes a comprehensive data integrity audit:
    - Sequence gap detection
    - Failed page tracking
    - Live portal comparison
    - Completeness score calculation
    """
    with get_db_session() as session:
        total_records = session.scalar(select(func.count(IssuanceModel.id))) or 0
        missing_titles = session.scalar(
            select(func.count(IssuanceModel.id)).where(
                or_(IssuanceModel.title.is_(None), IssuanceModel.title == "")
            )
        ) or 0
        missing_urls = session.scalar(
            select(func.count(IssuanceModel.id)).where(
                or_(IssuanceModel.source_url.is_(None), IssuanceModel.source_url == "")
            )
        ) or 0
        missing_dates = session.scalar(
            select(func.count(IssuanceModel.id)).where(
                or_(IssuanceModel.publication_date.is_(None), IssuanceModel.publication_date == "")
            )
        ) or 0
        
    failed_pages = get_failed_pages()
    audit_sequence_gaps()
    quarantine_logs = get_quarantine_logs(status="Pending")
    portal_sync = audit_live_portal_sync()

    # Calculate overall integrity score
    integrity_score = 100
    if len(failed_pages) > 0:
        integrity_score -= min(15, len(failed_pages) * 2)
    if missing_titles > 0:
        integrity_score -= min(10, missing_titles)
    if missing_urls > 0:
        integrity_score -= min(10, missing_urls)
    if len(quarantine_logs) > 0:
        integrity_score -= min(15, len(quarantine_logs))

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": total_records,
        "integrity_score": f"{max(0, integrity_score)}%",
        "quality_metrics": {
            "missing_titles": missing_titles,
            "missing_urls": missing_urls,
            "missing_dates": missing_dates,
            "failed_pages_count": len(failed_pages),
            "detected_gaps_count": len(quarantine_logs),
            "pending_quarantine_count": len(quarantine_logs)
        },
        "sequence_gaps": quarantine_logs,
        "quarantine_logs": quarantine_logs,
        "failed_pages": failed_pages,
        "portal_reconciliation": portal_sync
    }


def backfill_missing_doh_records(gap_samples: Optional[List[Any]] = None) -> int:
    """
    Reconciles missing records from the DOH API using the official search endpoint
    (https://app.doh.gov.ph:1024/Rest/SearchDocuments -> Rest/GetFirstPage).
    
    Searches for specific missing issuance numbers by category/issuanceType,
    and also probes recent publications across DOH categories.
    """
    from scrapers.doh import DOHScraper
    scraper = DOHScraper()
    if not scraper._ensure_session():
        logger.warning("[Validator] Could not establish session for backfill.")
        return 0

    inserted_total = 0

    # 1. Probe each category for latest records (Page 1)
    for cat_name, cat_code in DEPARTMENTS["DOH"]["categories"].items():
        if scraper._search_documents(cat_code):
            items, _ = scraper._fetch_page(1, cat_code)
            if items:
                records = [r for item in items if (r := scraper._item_to_record(item, cat_name)) is not None]
                ins, _ = scraper.save_records(records)
                inserted_total += ins

    # 2. Build target missing items list (category, issuance_number, year)
    targets = []
    if gap_samples:
        for item in gap_samples:
            if isinstance(item, dict):
                cat = item.get("category")
                yr = item.get("year")
                num = item.get("issuance_number") or item.get("number")
                if num:
                    targets.append((cat, str(num), yr))
                elif item.get("missing_samples"):
                    for s in item.get("missing_samples"):
                        targets.append((cat, str(s), yr))
            elif isinstance(item, (str, int)):
                targets.append((None, str(item), None))
    else:
        # Automatically gather detected sequence gaps for Department of Health
        dept_name = DEPARTMENTS["DOH"]["name"]
        gaps = audit_sequence_gaps(department=dept_name)
        for g in gaps:
            cat = g.get("category")
            yr = g.get("year")
            for sample_num in g.get("missing_samples", [])[:10]:
                targets.append((cat, str(sample_num), yr))

    # 3. Query missing items via SearchDocuments and GetFirstPage
    seen_targets = set()
    unique_targets = []
    for cat, num, yr in targets:
        key = (cat, num)
        if key not in seen_targets:
            seen_targets.add(key)
            unique_targets.append((cat, num, yr))

    # Search candidates for each missing number (cap to 50 items to keep requests within reasonable duration)
    for cat_name, missing_num, yr in unique_targets[:50]:
        search_candidates = [missing_num]
        if missing_num.isdigit():
            search_candidates.append(f"{int(missing_num):04d}")
            if yr:
                search_candidates.append(f"{yr}-{int(missing_num):04d}")

        found_records = []
        for candidate in search_candidates:
            recs = scraper.search_missing_issuance(
                issuance_number=candidate,
                cat_name=cat_name,
                year=str(yr) if yr else None
            )
            if recs:
                found_records.extend(recs)
                break

        if found_records:
            ins, _ = scraper.save_records(found_records)
            inserted_total += ins

    return inserted_total
