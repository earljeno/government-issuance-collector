import csv
from datetime import datetime
from typing import List, Dict, Optional
from config import EXPORTS_DIR

def generate_csv_document(issuances: List[Dict], filename: Optional[str] = None) -> str:
    """Exports records to standard CSV file."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Philippine_Government_Issuances_{ts}.csv"

    file_path = EXPORTS_DIR / filename
    headers = ["Department", "Category", "Issuance Number", "Title", "Date", "Source URL"]

    with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in issuances:
            writer.writerow([
                item.get("department", ""),
                item.get("category", ""),
                item.get("issuance_number", ""),
                item.get("title", ""),
                item.get("publication_date", ""),
                item.get("source_url", "")
            ])
    return str(file_path)

def generate_txt_document(issuances: List[Dict], filename: Optional[str] = None, department_name: Optional[str] = None) -> str:
    """Exports records to human-readable TXT summary."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Philippine_Government_Issuances_{ts}.txt"

    unique_depts = {item.get("department") for item in issuances if item.get("department")}
    single_dept = department_name or (list(unique_depts)[0] if len(unique_depts) == 1 else None)

    file_path = EXPORTS_DIR / filename
    with open(file_path, mode="w", encoding="utf-8") as f:
        if single_dept:
            f.write(f"PHILIPPINE GOVERNMENT LAWS AND ISSUANCES\n{single_dept.upper()}\n")
        else:
            f.write("PHILIPPINE GOVERNMENT LAWS AND ISSUANCES\n")
        f.write("Official Compendium of Laws, Policies, and Administrative Issuances\n")
        f.write("=" * 80 + "\n\n")

        for idx, item in enumerate(issuances, start=1):
            f.write(f"[{idx}] {item.get('department')} | {item.get('category')}\n")
            if item.get("issuance_number"):
                f.write(f"    Number: {item.get('issuance_number')}\n")
            f.write(f"    Title:  {item.get('title')}\n")
            if item.get("publication_date"):
                f.write(f"    Date:   {item.get('publication_date')}\n")
            if item.get("source_url"):
                f.write(f"    Source: {item.get('source_url')}\n")
            f.write("-" * 60 + "\n")

    return str(file_path)
