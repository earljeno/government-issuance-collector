import os
import sys
import re
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response

from config import DEPARTMENTS, EXPORTS_DIR, DATABASE_PATH
from database.db import (
    init_db,
    get_all_department_statuses,
    update_department_status,
    get_issuances,
    get_issuance_count,
    delete_all_issuances,
    remove_duplicates_cleanup,
    get_failed_pages,
    save_issuances_batch,
    get_all_checkpoints,
    get_checkpoint,
    clear_checkpoint
)
from database.models import IssuanceRecord
from scrapers.da import DAScraper
from scrapers.deped import DepEdScraper
from scrapers.doh import DOHScraper
from scrapers.denr import DENRScraper
from scrapers.manual_url import ManualURLExtractor
from exporters.word_exporter import generate_word_document
from exporters.excel_exporter import generate_excel_document
from exporters.csv_exporter import generate_csv_document, generate_txt_document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

# Global background worker state
active_threads: list[threading.Thread] = []
cancel_event = threading.Event()
active_progress = {
    "is_running": False,
    "department": "",
    "category": "",
    "current_page": 0,
    "total_pages": "0",
    "records_collected": 0,
    "status": "Idle",
    "message": ""
}
progress_lock = threading.Lock()

def progress_callback(update_data: dict):
    with progress_lock:
        active_progress.update(update_data)
        active_progress["is_running"] = (update_data.get("status") == "Running")

def run_extraction_worker(selected_depts: list, cat_filters: dict, year_filter: str, max_pages: int = None, resume: bool = False):
    global cancel_event
    cancel_event.clear()

    with progress_lock:
        active_progress["is_running"] = True
        active_progress["status"] = "Running"
        active_progress["message"] = f"{'Resuming' if resume else 'Starting'} extraction for {', '.join(selected_depts)}"

    scrapers = {
        "Department of Agriculture": DAScraper(),
        "Department of Education": DepEdScraper(),
        "Department of Health": DOHScraper(),
        "Department of Environment and Natural Resources": DENRScraper()
    }

    try:
        for dept_name in selected_depts:
            if cancel_event.is_set():
                break

            scraper = scrapers.get(dept_name)
            if not scraper:
                continue

            cats = cat_filters.get(dept_name)
            if not cats or len(cats) == 0:
                # All categories for this department
                dept_key = None
                for k, v in DEPARTMENTS.items():
                    if v["name"] == dept_name:
                        dept_key = k
                        break
                cats = list(DEPARTMENTS[dept_key]["categories"].keys()) if dept_key else None

            logger.info(f"{'Resuming' if resume else 'Starting'} worker for {dept_name}...")
            if isinstance(scraper, DepEdScraper):
                scraper.scrape(
                    categories=cats,
                    year=year_filter,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                    max_pages_per_category=max_pages,
                    resume=resume
                )
            elif isinstance(scraper, DAScraper):
                scraper.scrape(
                    categories=cats,
                    year=year_filter,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                    resume=resume
                )
            else:
                scraper.scrape(
                    categories=cats,
                    year=year_filter,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event
                )

    except Exception as e:
        logger.exception(f"Unexpected worker error: {e}")
        with progress_lock:
            active_progress["status"] = "Error"
            active_progress["message"] = str(e)
    finally:
        with progress_lock:
            active_progress["is_running"] = False
            if cancel_event.is_set():
                active_progress["status"] = "Stopped"
                active_progress["message"] = "Extraction process was stopped."
            elif active_progress["status"] == "Running":
                active_progress["status"] = "Completed"
                active_progress["message"] = "Extraction finished."

# ----------------- ROUTES ----------------- #

@app.route("/")
def index():
    return render_template("dashboard.html", departments=DEPARTMENTS)

@app.route("/api/status", methods=["GET"])
def get_status():
    dept_statuses = get_all_department_statuses()
    total_db_records = get_issuance_count()
    failed = get_failed_pages()
    checkpoints = get_all_checkpoints()
    with progress_lock:
        curr_progress = dict(active_progress)

    return jsonify({
        "departments": dept_statuses,
        "total_records": total_db_records,
        "failed_pages_count": len(failed),
        "progress": curr_progress,
        "checkpoints": checkpoints
    })

@app.route("/api/extract", methods=["POST"])
def start_extraction():
    with progress_lock:
        if active_progress["is_running"]:
            return jsonify({"success": False, "message": "An extraction task is already in progress."}), 400

    data = request.get_json() or {}
    depts = data.get("departments", [])
    if depts == "ALL" or not depts:
        selected_depts = [
            "Department of Agriculture",
            "Department of Education",
            "Department of Health",
            "Department of Environment and Natural Resources"
        ]
    elif isinstance(depts, list):
        selected_depts = depts
    else:
        selected_depts = [depts]

    cat_filters = data.get("categories", {})
    year_filter = data.get("year", "").strip() or None
    max_pages = data.get("max_pages")
    resume = data.get("resume", False)
    if max_pages:
        try:
            max_pages = int(max_pages)
        except ValueError:
            max_pages = None

    t = threading.Thread(
        target=run_extraction_worker,
        args=(selected_depts, cat_filters, year_filter, max_pages, resume),
        daemon=True
    )
    t.start()

    return jsonify({
        "success": True,
        "message": f"{'Resumed' if resume else 'Extraction started'} for {len(selected_depts)} department(s)."
    })

@app.route("/api/resume", methods=["POST"])
def resume_extraction():
    with progress_lock:
        if active_progress["is_running"]:
            return jsonify({"success": False, "message": "An extraction task is already in progress."}), 400

    data = request.get_json() or {}
    checkpoints = get_all_checkpoints()
    dept = data.get("department")

    if dept:
        selected_depts = [dept]
    elif checkpoints:
        selected_depts = list(checkpoints.keys())
    else:
        # Fallback to interrupted or stopped departments in department_status
        dept_statuses = get_all_department_statuses()
        selected_depts = [d["department"] for d in dept_statuses if d.get("status") in ["Interrupted", "Stopped"]]

    if not selected_depts:
        return jsonify({"success": False, "message": "No stopped or interrupted department found to resume."}), 400

    year_filter = data.get("year", "").strip() or None
    max_pages = data.get("max_pages")
    if max_pages:
        try:
            max_pages = int(max_pages)
        except ValueError:
            max_pages = None

    t = threading.Thread(
        target=run_extraction_worker,
        args=(selected_depts, {}, year_filter, max_pages, True),
        daemon=True
    )
    t.start()

    return jsonify({
        "success": True,
        "message": f"Resuming extraction for {', '.join(selected_depts)} from saved checkpoint."
    })

@app.route("/api/stop", methods=["POST"])
def stop_extraction():
    cancel_event.set()
    with progress_lock:
        active_progress["status"] = "Stopping..."
        active_progress["message"] = "Stop signal delivered. Terminating current requests..."
    return jsonify({"success": True, "message": "Stopping extraction..."})

@app.route("/api/records", methods=["GET"])
def list_records():
    dept = request.args.get("department", "").strip() or None
    cat = request.args.get("category", "").strip() or None
    year = request.args.get("year", "").strip() or None
    search = request.args.get("search", "").strip() or None
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))

    offset = (page - 1) * page_size
    records = get_issuances(department=dept, category=cat, year=year, search=search, limit=page_size, offset=offset)
    total_count = get_issuance_count(department=dept, category=cat, year=year, search=search)

    return jsonify({
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": max(1, (total_count + page_size - 1) // page_size),
        "records": records
    })

@app.route("/api/records/cleanup-duplicates", methods=["POST"])
def cleanup_duplicates():
    removed_count = remove_duplicates_cleanup()
    return jsonify({
        "success": True,
        "removed": removed_count,
        "message": f"Successfully removed {removed_count} duplicate records."
    })

@app.route("/api/records/delete", methods=["POST"])
def clear_records():
    data = request.get_json() or {}
    dept = data.get("department")
    delete_all_issuances(department=dept)
    target_name = dept or "all departments"
    return jsonify({
        "success": True,
        "message": f"Records deleted for {target_name}."
    })

@app.route("/api/failed-pages", methods=["GET"])
def failed_pages_endpoint():
    failed = get_failed_pages()
    return jsonify({"failed_pages": failed})

@app.route("/api/manual-url/preview", methods=["POST"])
def manual_url_preview():
    data = request.get_json() or {}
    url = data.get("url", "").strip() or None
    html_content = data.get("html", "").strip() or None
    dept = data.get("department", "Manual Import").strip()
    cat = data.get("category", "General Issuances").strip()

    extractor = ManualURLExtractor()
    result = extractor.analyze_and_extract(
        url=url,
        html_content=html_content,
        department_name=dept,
        category_name=cat
    )
    return jsonify(result)

@app.route("/api/manual-url/save", methods=["POST"])
def manual_url_save():
    data = request.get_json() or {}
    raw_records = data.get("records", [])
    if not raw_records:
        return jsonify({"success": False, "message": "No records to save."}), 400

    record_objs = []
    for r in raw_records:
        record_objs.append(IssuanceRecord(
            department=r.get("department", "Manual Import"),
            category=r.get("category", "General Issuances"),
            issuance_number=r.get("issuance_number", ""),
            title=r.get("title", ""),
            publication_date=r.get("publication_date", ""),
            source_url=r.get("source_url", "")
        ))

    ins, dups = save_issuances_batch(record_objs)
    return jsonify({
        "success": True,
        "inserted": ins,
        "duplicates": dups,
        "message": f"Successfully saved {ins} records ({dups} duplicates skipped)."
    })

@app.route("/api/export/<fmt>", methods=["GET"])
def export_file(fmt: str):
    dept = request.args.get("department", "").strip() or None
    cat = request.args.get("category", "").strip() or None
    year = request.args.get("year", "").strip() or None
    search = request.args.get("search", "").strip() or None

    issuances = get_issuances(department=dept, category=cat, year=year, search=search)
    if not issuances:
        return jsonify({"success": False, "message": "No records found matching export criteria."}), 404

    fmt = fmt.lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Clean department prefix for filename
    code_map = {
        "Department of Agriculture": "DA",
        "Department of Health": "DOH",
        "Department of Environment and Natural Resources": "DENR",
        "Department of Education": "DepEd"
    }
    if dept:
        dept_tag = code_map.get(dept, re.sub(r'[^a-zA-Z0-9]', '_', dept).strip('_'))
        filename_prefix = f"{dept_tag}_Issuances_{ts}"
    else:
        filename_prefix = f"Philippine_Issuances_{ts}"

    if fmt == "word" or fmt == "docx":
        file_path = generate_word_document(issuances, f"{filename_prefix}.docx", department_name=dept)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        as_attachment = True
    elif fmt == "excel" or fmt == "xlsx":
        file_path = generate_excel_document(issuances, f"{filename_prefix}.xlsx", department_name=dept)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        as_attachment = True
    elif fmt == "csv":
        file_path = generate_csv_document(issuances, f"{filename_prefix}.csv")
        mimetype = "text/csv"
        as_attachment = True
    elif fmt == "txt":
        file_path = generate_txt_document(issuances, f"{filename_prefix}.txt", department_name=dept)
        mimetype = "text/plain"
        as_attachment = True
    else:
        return jsonify({"success": False, "message": f"Unsupported format: {fmt}"}), 400

    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=os.path.basename(file_path)
    )

@app.route("/api/backup-db", methods=["GET"])
def backup_database():
    """Allows downloading the raw SQLite database file directly."""
    if not os.path.exists(DATABASE_PATH):
        return jsonify({"error": "Database not initialized"}), 404
    return send_file(
        DATABASE_PATH,
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name="issuances.db"
    )

@app.route("/api/restore-db", methods=["POST"])
def restore_database():
    """Allows uploading and restoring a SQLite database file."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400
    
    file.save(DATABASE_PATH)
    return jsonify({"success": True, "message": "Database successfully restored."})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==================================================================")
    print(f"Philippine Government Issuance Title Collector starting on:")
    print(f"http://127.0.0.1:{port}")
    print(f"==================================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
