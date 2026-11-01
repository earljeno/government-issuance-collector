import os
import sys
import re
import json
import logging
import threading
import concurrent.futures
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response

from config import DEPARTMENTS, EXPORTS_DIR, is_prod_env
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
    clear_checkpoint,
    get_quarantine_logs,
    resolve_quarantine_log
)
from database.models import IssuanceRecord
from database.validator import run_full_validation, backfill_missing_doh_records
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
    "message": "",
    "active_departments": set(),
    "department_progress": {}
}
progress_lock = threading.Lock()

def progress_callback(update_data: dict):
    with progress_lock:
        dept = update_data.get("department", "")
        status = update_data.get("status", "")

        if dept:
            active_progress["department_progress"][dept] = update_data
            if status == "Running":
                active_progress["active_departments"].add(dept)
            elif status in ["Completed", "Stopped", "Error", "Temporarily Inaccessible"]:
                active_progress["active_departments"].discard(dept)

        is_active = len(active_progress["active_departments"]) > 0
        active_progress["is_running"] = is_active
        if is_active:
            active_progress["status"] = "Running"
        elif status in ["Completed", "Stopped", "Error"]:
            active_progress["status"] = status

        active_progress["records_collected"] = sum(
            dp.get("records_collected", 0)
            for dp in active_progress["department_progress"].values()
        )

        active_progress["department"] = (
            ", ".join(sorted(active_progress["active_departments"]))
            if active_progress["active_departments"] else dept
        )
        active_progress["category"] = update_data.get("category", "")
        active_progress["current_page"] = update_data.get("current_page", 0)
        active_progress["total_pages"] = update_data.get("total_pages", "Unknown")
        active_progress["message"] = f"[{update_data.get('code', dept)}] {update_data.get('message', '')}"

def run_extraction_worker(selected_depts: list, cat_filters: dict, year_filter: str, max_pages: int = None, resume: bool = False):
    global cancel_event
    cancel_event.clear()

    with progress_lock:
        active_progress["is_running"] = True
        active_progress["status"] = "Running"
        active_progress["active_departments"] = set(selected_depts)
        active_progress["department_progress"] = {}
        active_progress["records_collected"] = 0
        active_progress["message"] = f"{'Resuming' if resume else 'Starting'} parallel extraction for {', '.join(selected_depts)}"
        active_progress["department"] = ", ".join(selected_depts)

    scraper_classes = {
        "Department of Agriculture": DAScraper,
        "Department of Education": DepEdScraper,
        "Department of Health": DOHScraper,
        "Department of Environment and Natural Resources": DENRScraper
    }

    def run_single_department(dept_name: str):
        if cancel_event.is_set():
            return

        scraper_cls = scraper_classes.get(dept_name)
        if not scraper_cls:
            return

        scraper = scraper_cls()
        cats = cat_filters.get(dept_name)
        if not cats or len(cats) == 0:
            dept_key = None
            for k, v in DEPARTMENTS.items():
                if v["name"] == dept_name:
                    dept_key = k
                    break
            cats = list(DEPARTMENTS[dept_key]["categories"].keys()) if dept_key else None

        logger.info(f"{'Resuming' if resume else 'Starting'} worker for {dept_name}...")
        try:
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
            elif isinstance(scraper, DOHScraper):
                scraper.scrape(
                    categories=cats,
                    year=year_filter,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                    max_pages_per_category=max_pages,
                    resume=resume
                )
            else:
                scraper.scrape(
                    categories=cats,
                    year=year_filter,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event
                )
        except Exception as exc:
            logger.exception(f"Error in {dept_name} scraper: {exc}")
            progress_callback({
                "department": dept_name,
                "code": scraper.department_code,
                "category": "Error",
                "current_page": 0,
                "total_pages": "0",
                "records_collected": 0,
                "status": "Error",
                "message": str(exc),
            })

    try:
        # Run selected departments in parallel (1 thread per agency, max 4 concurrent)
        max_workers = min(4, max(1, len(selected_depts)))
        logger.info(f"Launching parallel extraction pool with {max_workers} worker thread(s) for: {selected_depts}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_single_department, d): d for d in selected_depts}
            for future in concurrent.futures.as_completed(futures):
                d = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.exception(f"Worker thread for {d} raised exception: {exc}")

    except Exception as e:
        logger.exception(f"Unexpected worker error: {e}")
        with progress_lock:
            active_progress["status"] = "Error"
            active_progress["message"] = str(e)
    finally:
        with progress_lock:
            active_progress["is_running"] = False
            active_progress["active_departments"].clear()
            if cancel_event.is_set():
                active_progress["status"] = "Stopped"
                active_progress["message"] = "Extraction process was stopped."
            elif active_progress["status"] == "Running":
                active_progress["status"] = "Completed"
                active_progress["message"] = "All agency extractions finished."

# ----------------- ROUTES ----------------- #

@app.route("/")
def index():
    return render_template("dashboard.html", departments=DEPARTMENTS, is_prod=is_prod_env())

@app.route("/api/status", methods=["GET"])
def get_status():
    dept_statuses = get_all_department_statuses()
    total_db_records = get_issuance_count()
    failed = get_failed_pages()
    checkpoints = get_all_checkpoints()
    with progress_lock:
        curr_progress = dict(active_progress)
        if isinstance(curr_progress.get("active_departments"), set):
            curr_progress["active_departments"] = list(curr_progress["active_departments"])

    return jsonify({
        "departments": dept_statuses,
        "total_records": total_db_records,
        "failed_pages_count": len(failed),
        "progress": curr_progress,
        "checkpoints": checkpoints,
        "is_prod": is_prod_env()
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

    if dept and dept.strip().lower() != "all":
        selected_depts = [dept.strip()]
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

@app.route("/api/validate", methods=["GET"])
def api_validate():
    if is_prod_env():
        return jsonify({
            "success": False,
            "error": "Audit & Reconcile Data is disabled in production."
        }), 403
    try:
        report = run_full_validation()
        return jsonify({"success": True, "report": report})
    except Exception as exc:
        logger.exception(f"Validation error: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

@app.route("/api/reconcile", methods=["POST"])
def api_reconcile():
    if is_prod_env():
        return jsonify({
            "success": False,
            "error": "Audit & Reconcile Data is disabled in production."
        }), 403
    try:
        data = request.get_json() or {}
        gap_samples = data.get("gap_samples", [])
        recovered = backfill_missing_doh_records(gap_samples)
        return jsonify({
            "success": True,
            "recovered_count": recovered,
            "message": f"Reconciliation complete. {recovered} missing record(s) recovered and added to the database."
        })
    except Exception as exc:
        logger.exception(f"Reconciliation error: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

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

@app.route("/api/quarantine", methods=["GET"])
def api_quarantine():
    try:
        status = request.args.get("status", "Pending")
        logs = get_quarantine_logs(status=status)
        return jsonify({
            "success": True,
            "logs": logs,
            "count": len(logs)
        })
    except Exception as exc:
        logger.exception("Error fetching quarantine logs: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500

@app.route("/api/quarantine/<int:log_id>/resolve", methods=["POST"])
def api_resolve_quarantine(log_id: int):
    try:
        data = request.get_json(silent=True) or {}
        status = data.get("status", "Resolved")
        if status not in ["Resolved", "Ignored", "Pending"]:
            return jsonify({"success": False, "message": f"Invalid status: {status}"}), 400

        success = resolve_quarantine_log(log_id, status)
        if success:
            return jsonify({
                "success": True,
                "message": f"Quarantine log #{log_id} marked as {status}."
            })
        return jsonify({
            "success": False,
            "message": f"Quarantine log #{log_id} not found."
        }), 404
    except Exception as exc:
        logger.exception("Error resolving quarantine log %s: %s", log_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 500

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
    """Allows downloading a complete JSON snapshot of all database records."""
    issuances = get_issuances()
    statuses = get_all_department_statuses()
    payload = {
        "exported_at": datetime.now().isoformat(),
        "total_records": len(issuances),
        "department_statuses": statuses,
        "issuances": issuances
    }
    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"government_issuances_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/api/restore-db", methods=["POST"])
def restore_database():
    """Allows uploading and restoring issuances from a JSON backup file."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    try:
        content = file.read().decode("utf-8")
        data = json.loads(content)
        raw_records = data.get("issuances", []) if isinstance(data, dict) else data
        if not isinstance(raw_records, list):
            return jsonify({"success": False, "message": "Invalid backup file structure: expected 'issuances' list."}), 400

        records = [
            IssuanceRecord(
                department=r.get("department", ""),
                category=r.get("category", ""),
                issuance_number=r.get("issuance_number"),
                title=r.get("title", ""),
                publication_date=r.get("publication_date"),
                source_url=r.get("source_url"),
                extraction_timestamp=r.get("extraction_timestamp")
            )
            for r in raw_records
            if r.get("department") and r.get("title")
        ]
        inserted, duplicates = save_issuances_batch(records)
        return jsonify({
            "success": True,
            "message": f"Database successfully restored: {inserted} records inserted, {duplicates} duplicates skipped."
        })
    except Exception as exc:
        logger.exception("Database restore failed: %s", exc)
        return jsonify({"success": False, "message": f"Restore failed: {str(exc)}"}), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==================================================================")
    print(f"Philippine Government Issuance Title Collector starting on:")
    print(f"http://127.0.0.1:{port}")
    print(f"==================================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
