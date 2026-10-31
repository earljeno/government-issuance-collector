import os
from datetime import datetime
from typing import List, Dict, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

from config import EXPORTS_DIR

def add_hyperlink(paragraph, url: str, text: str, color="004B87", underline=True):
    """
    Inserts a clickable hyperlink element into a python-docx paragraph.
    """
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    hyperlink = parse_xml(f'<w:hyperlink xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" r:id="{r_id}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>')
    new_run = parse_xml(f'<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    rPr = parse_xml(f'<w:rPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')

    if color:
        c = parse_xml(f'<w:color xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:val="{color}"/>')
        rPr.append(c)
    if underline:
        u = parse_xml(f'<w:u xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:val="single"/>')
        rPr.append(u)

    new_run.append(rPr)
    new_run_text = parse_xml(f'<w:t xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xml:space="preserve">{text}</w:t>')
    new_run.append(new_run_text)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)

def add_footer_page_number(run):
    """Adds Word page number field to a run in footer."""
    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), 'PAGE')
    run._r.append(fldSimple)

def set_cell_background(cell, fill_hex: str):
    """Sets background fill color for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'))

def set_cell_margins(cell, top=60, bottom=60, left=100, right=100):
    """Sets cell padding (top, bottom, left, right) in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_table_borders(table):
    """Sets clean academic/professional borders on the table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="1B365D"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="9CA3AF"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def make_row_header(row):
    """Marks row as repeating table header on new pages and prevents page split."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

def make_row_cant_split(row):
    """Prevents row from being split across page breaks."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

def generate_word_document(issuances: List[Dict], filename: Optional[str] = None, department_name: Optional[str] = None) -> str:
    """
    Generates a high-quality, professional Microsoft Word document
    with structured tables for consistent formatting across all departments and categories.
    Supports specific department export or all departments.
    """
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Philippine_Government_Issuances_{ts}.docx"
    
    file_path = EXPORTS_DIR / filename
    doc = Document()

    core_props = doc.core_properties
    core_props.author = "Government Records Repository"
    core_props.last_modified_by = ""
    core_props.comments = ""

    unique_depts = {item.get("department") for item in issuances if item.get("department")}
    single_dept = department_name or (list(unique_depts)[0] if len(unique_depts) == 1 else None)

    # Standard A4 dimensions (8.27 x 11.69 in) with 0.8 in margins
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

        footer = section.footer
        footer_p = footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        page_lbl = footer_p.add_run("Page ")
        page_lbl.font.name = "Calibri"
        page_lbl.font.size = Pt(9)
        page_lbl.font.color.rgb = RGBColor(128, 128, 128)
        
        page_run = footer_p.add_run()
        page_run.font.name = "Calibri"
        page_run.font.size = Pt(9)
        page_run.font.color.rgb = RGBColor(128, 128, 128)
        add_footer_page_number(page_run)

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    
    if single_dept:
        run_title = title_p.add_run(f"PHILIPPINE GOVERNMENT LAWS AND ISSUANCES\n{single_dept.upper()}")
    else:
        run_title = title_p.add_run("PHILIPPINE GOVERNMENT LAWS AND ISSUANCES")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(17 if single_dept else 18)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(16, 44, 87)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(18)
    run_sub = sub_p.add_run("Official Compendium of Laws, Policies, and Administrative Issuances")
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(10.5)
    run_sub.font.color.rgb = RGBColor(100, 100, 100)

    # Group records: Department -> Category -> items
    departments_order = [
        "Department of Agriculture",
        "Department of Health",
        "Department of Environment and Natural Resources",
        "Department of Education"
    ]
    
    grouped: Dict[str, Dict[str, List[Dict]]] = {}
    for item in issuances:
        dept = item.get("department", "Other Department")
        cat = item.get("category", "General")
        if dept not in grouped:
            grouped[dept] = {}
        if cat not in grouped[dept]:
            grouped[dept][cat] = []
        grouped[dept][cat].append(item)

    all_depts = sorted(grouped.keys(), key=lambda d: departments_order.index(d) if d in departments_order else 99)
    roman_numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

    # Column widths sum to 6.67 in to match available width on A4 with 0.8 in margins
    col_widths = [
        Inches(0.45),
        Inches(1.40),
        Inches(3.32),
        Inches(0.85),
        Inches(0.65)
    ]

    for d_idx, dept in enumerate(all_depts):
        r_num = roman_numerals[d_idx] if d_idx < len(roman_numerals) else f"{d_idx+1}"
        
        dept_p = doc.add_paragraph()
        dept_p.paragraph_format.space_before = Pt(16)
        dept_p.paragraph_format.space_after = Pt(6)
        dept_p.paragraph_format.keep_with_next = True
        run_dept = dept_p.add_run(f"{r_num}. {dept.upper()}")
        run_dept.font.name = "Calibri"
        run_dept.font.size = Pt(14)
        run_dept.font.bold = True
        run_dept.font.color.rgb = RGBColor(27, 54, 93)

        categories = sorted(grouped[dept].keys())
        for c_idx, cat in enumerate(categories):
            letter = chr(65 + c_idx) if c_idx < 26 else f"C{c_idx+1}"
            records = grouped[dept][cat]
            
            cat_p = doc.add_paragraph()
            cat_p.paragraph_format.space_before = Pt(12)
            cat_p.paragraph_format.space_after = Pt(6)
            cat_p.paragraph_format.keep_with_next = True
            run_cat = cat_p.add_run(f"{letter}. {cat.upper()}")
            run_cat.font.name = "Calibri"
            run_cat.font.size = Pt(11.5)
            run_cat.font.bold = True
            run_cat.font.color.rgb = RGBColor(50, 50, 50)

            table = doc.add_table(rows=1, cols=5)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            set_table_borders(table)

            hdr_row = table.rows[0]
            make_row_header(hdr_row)
            hdr_titles = ["#", "Issuance No.", "Title", "Date", "Source"]
            hdr_alignments = [
                WD_ALIGN_PARAGRAPH.CENTER,
                WD_ALIGN_PARAGRAPH.LEFT,
                WD_ALIGN_PARAGRAPH.LEFT,
                WD_ALIGN_PARAGRAPH.CENTER,
                WD_ALIGN_PARAGRAPH.CENTER
            ]

            for i, cell in enumerate(hdr_row.cells):
                cell.width = col_widths[i]
                set_cell_background(cell, "1B365D")
                set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p = cell.paragraphs[0]
                p.alignment = hdr_alignments[i]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(hdr_titles[i])
                run.font.name = "Calibri"
                run.font.size = Pt(9.5)
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)

            for r_idx, rec in enumerate(records, start=1):
                row = table.add_row()
                make_row_cant_split(row)
                row_bg = "F8FAFC" if r_idx % 2 == 0 else "FFFFFF"

                num = rec.get("issuance_number", "").strip() or "-"
                title = rec.get("title", "").strip() or "Untitled Issuance"
                pub_date = rec.get("publication_date", "").strip() or "-"
                src_url = rec.get("source_url", "").strip()

                cell_data = [
                    (str(r_idx), WD_ALIGN_PARAGRAPH.CENTER, False, Pt(9), RGBColor(100, 100, 100)),
                    (num, WD_ALIGN_PARAGRAPH.LEFT, True, Pt(9), RGBColor(20, 20, 20)),
                    (title, WD_ALIGN_PARAGRAPH.LEFT, False, Pt(9), RGBColor(30, 30, 30)),
                    (pub_date, WD_ALIGN_PARAGRAPH.CENTER, False, Pt(8.5), RGBColor(80, 80, 80))
                ]

                for col_idx in range(4):
                    cell = row.cells[col_idx]
                    cell.width = col_widths[col_idx]
                    set_cell_background(cell, row_bg)
                    set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    p = cell.paragraphs[0]
                    text, align, bold, size, color = cell_data[col_idx]
                    p.alignment = align
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    run = p.add_run(text)
                    run.font.name = "Calibri"
                    run.font.size = size
                    run.font.bold = bold
                    run.font.color.rgb = color

                cell_src = row.cells[4]
                cell_src.width = col_widths[4]
                set_cell_background(cell_src, row_bg)
                set_cell_margins(cell_src, top=60, bottom=60, left=60, right=60)
                cell_src.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p_src = cell_src.paragraphs[0]
                p_src.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_src.paragraph_format.space_before = Pt(0)
                p_src.paragraph_format.space_after = Pt(0)

                if src_url:
                    add_hyperlink(p_src, src_url, "[View]", color="004B87", underline=True)
                else:
                    run_none = p_src.add_run("-")
                    run_none.font.name = "Calibri"
                    run_none.font.size = Pt(8.5)
                    run_none.font.color.rgb = RGBColor(160, 160, 160)

            doc.add_paragraph().paragraph_format.space_after = Pt(6)

    doc.save(str(file_path))
    return str(file_path)
