import os
from datetime import datetime
from typing import List, Dict, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import EXPORTS_DIR

def generate_excel_document(issuances: List[Dict], filename: Optional[str] = None, department_name: Optional[str] = None) -> str:
    """
    Generates an Excel spreadsheet with columns:
    Department | Category | Issuance Number | Title | Date | Source URL
    Includes filters, frozen header row, and professional styling.
    Supports single department export or all departments.
    """
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Philippine_Government_Issuances_{ts}.xlsx"

    file_path = EXPORTS_DIR / filename
    wb = openpyxl.Workbook()
    ws = wb.active

    unique_depts = {item.get("department") for item in issuances if item.get("department")}
    single_dept = department_name or (list(unique_depts)[0] if len(unique_depts) == 1 else None)
    if single_dept:
        dept_abbr_map = {
            "Department of Agriculture": "DA",
            "Department of Health": "DOH",
            "Department of Environment and Natural Resources": "DENR",
            "Department of Education": "DepEd"
        }
        short_name = dept_abbr_map.get(single_dept, single_dept[:20])
        ws.title = f"{short_name} Issuances"[:31]
    else:
        ws.title = "Government Issuances"

    # Define Header
    headers = ["Department", "Category", "Issuance Number", "Title", "Date", "Source URL"]
    ws.append(headers)

    # Style Header Row
    header_fill = PatternFill(start_color="102C57", end_color="102C57", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # Border style
    thin_border = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    # Append Data
    for row_idx, item in enumerate(issuances, start=2):
        row_data = [
            item.get("department", ""),
            item.get("category", ""),
            item.get("issuance_number", ""),
            item.get("title", ""),
            item.get("publication_date", ""),
            item.get("source_url", "")
        ]
        ws.append(row_data)

        # Style data row
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = Font(name="Calibri", size=10)
            cell.border = thin_border
            if col_idx in [1, 2, 3, 5, 7]:
                cell.alignment = Alignment(vertical="center")
            else:
                cell.alignment = Alignment(vertical="center", wrap_text=False)

    # Freeze Header Row
    ws.freeze_panes = "A2"

    # Auto Filter
    ws.auto_filter.ref = ws.dimensions

    # Adjust Column Widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        # Cap between 12 and 60
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

    # Specific override for Title and URL
    ws.column_dimensions["D"].width = 50
    ws.column_dimensions["F"].width = 40

    wb.save(str(file_path))
    return str(file_path)
