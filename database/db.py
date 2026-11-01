import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base

import config
from config import DATABASE_URI
from database.models import IssuanceRecord

# Connect to either Local SQLite or Vercel Postgres based on config
connect_args = {"check_same_thread": False} if (DATABASE_URI and DATABASE_URI.startswith("sqlite")) else {}
engine = create_engine(DATABASE_URI, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class IssuanceModel(Base):
    __tablename__ = "issuances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False)
    issuance_number = Column(String(255), nullable=True)
    title = Column(Text, nullable=False)
    publication_date = Column(String(50), nullable=True)
    source_url = Column(Text, nullable=True)
    extraction_timestamp = Column(String(50), nullable=False)
    duplicate_hash = Column(String(64), unique=True, nullable=True)


class DepartmentStatusModel(Base):
    __tablename__ = "department_status"
    department = Column(String(255), primary_key=True)
    status = Column(String(50), default="Idle")
    total_records = Column(Integer, default=0)
    last_extraction = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    current_category = Column(String(255), nullable=True)
    current_page = Column(Integer, default=0)
    total_pages = Column(String(50), default="Unknown")


class FailedPageModel(Base):
    __tablename__ = "failed_pages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    error_message = Column(Text, nullable=True)
    timestamp = Column(String(50), nullable=False)
    retry_count = Column(Integer, default=0)


class ExtractionCheckpointModel(Base):
    __tablename__ = "extraction_checkpoints"
    department = Column(String(255), primary_key=True)
    category = Column(String(255), nullable=True)
    page = Column(Integer, default=1)
    url = Column(Text, nullable=True)
    completed_categories = Column(Text, nullable=True)
    updated_at = Column(String(50), nullable=True)
    category_pages = Column(Text, default="{}")


class QuarantineLogModel(Base):
    __tablename__ = "quarantine_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    issue_type = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    status = Column(String(50), default="Pending", index=True)
    created_at = Column(String(50), nullable=True)
    resolved_at = Column(String(50), nullable=True)
    __table_args__ = (
        UniqueConstraint("department", "category", "issue_type", "details", name="uq_quarantine_log"),
    )


def get_current_engine():
    uri = getattr(config, "DATABASE_URI", DATABASE_URI)
    db_path = getattr(config, "DATABASE_PATH", None)
    if uri and uri.startswith("sqlite") and db_path:
        expected_uri = f"sqlite:///{db_path}"
        if expected_uri != str(engine.url):
            return create_engine(expected_uri, connect_args={"check_same_thread": False})
    return engine


def get_connection():
    uri = getattr(config, "DATABASE_URI", DATABASE_URI)
    if not uri or uri.startswith("sqlite"):
        db_path = getattr(config, "DATABASE_PATH", config.DATA_DIR / "database.db")
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        return conn
    else:
        curr_engine = get_current_engine()
        return curr_engine.raw_connection()


def init_db():
    """Initializes database schema and default rows across SQLite or PostgreSQL."""
    curr_engine = get_current_engine()
    Base.metadata.create_all(bind=curr_engine)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Mark any abandoned 'Running' tasks as 'Interrupted' on server start
        cursor.execute("""
            UPDATE department_status
            SET status = 'Interrupted',
                error_message = 'Interrupted by server restart or shutdown. Click Resume to continue.'
            WHERE status = 'Running'
        """)

        # Initialize default department statuses if not present
        default_depts = [
            "Department of Agriculture",
            "Department of Health",
            "Department of Environment and Natural Resources",
            "Department of Education"
        ]
        for dept in default_depts:
            cursor.execute("""
                INSERT OR IGNORE INTO department_status (department, status, total_records)
                VALUES (?, 'Idle', 0)
            """, (dept,))

        conn.commit()

def save_issuance(record: IssuanceRecord) -> bool:
    """
    Saves an issuance record. Returns True if inserted, False if duplicate.
    Preserves original title, issuance number, and metadata.
    """
    dup_hash = record.generate_duplicate_hash()
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = record.extraction_timestamp or now_ts
    
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO issuances (
                    department, category, issuance_number, title,
                    publication_date, source_url, extraction_timestamp, duplicate_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.department,
                record.category,
                record.issuance_number,
                record.title,
                record.publication_date,
                record.source_url,
                timestamp,
                dup_hash
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate record based on duplicate_hash
            return False

def save_issuances_batch(records: List[IssuanceRecord]) -> Tuple[int, int]:
    """
    Batch inserts records.
    Returns (inserted_count, duplicates_count).
    """
    inserted = 0
    duplicates = 0
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for r in records:
            dup_hash = r.generate_duplicate_hash()
            timestamp = r.extraction_timestamp or now_ts
            try:
                cursor.execute("""
                    INSERT INTO issuances (
                        department, category, issuance_number, title,
                        publication_date, source_url, extraction_timestamp, duplicate_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.department,
                    r.category,
                    r.issuance_number,
                    r.title,
                    r.publication_date,
                    r.source_url,
                    timestamp,
                    dup_hash
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()
    return inserted, duplicates

def get_issuances(
    department: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[Dict]:
    """Retrieves issuances with optional filters and pagination."""
    query = "SELECT * FROM issuances WHERE 1=1"
    params = []
    
    if department:
        query += " AND department = ?"
        params.append(department)
    if category:
        query += " AND category = ?"
        params.append(category)
    if year:
        query += " AND (publication_date LIKE ? OR title LIKE ?)"
        params.append(f"%{year}%")
        params.append(f"%{year}%")
    if search:
        query += " AND (title LIKE ? OR issuance_number LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")
        
    query += " ORDER BY id DESC"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        query += " OFFSET ?"
        params.append(offset)
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_issuance_count(
    department: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[str] = None,
    search: Optional[str] = None
) -> int:
    """Returns total count of matching records."""
    query = "SELECT COUNT(*) as cnt FROM issuances WHERE 1=1"
    params = []
    
    if department:
        query += " AND department = ?"
        params.append(department)
    if category:
        query += " AND category = ?"
        params.append(category)
    if year:
        query += " AND (publication_date LIKE ? OR title LIKE ?)"
        params.append(f"%{year}%")
        params.append(f"%{year}%")
    if search:
        query += " AND (title LIKE ? OR issuance_number LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()["cnt"]

def update_department_status(
    department: str,
    status: str,
    current_category: Optional[str] = None,
    current_page: Optional[int] = None,
    total_pages: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Updates runtime progress and status for a department."""
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM issuances WHERE department = ?", (department,))
        total_records = cursor.fetchone()["cnt"]
        
        cursor.execute("""
            UPDATE department_status
            SET status = ?,
                total_records = ?,
                last_extraction = ?,
                current_category = COALESCE(?, current_category),
                current_page = COALESCE(?, current_page),
                total_pages = COALESCE(?, total_pages),
                error_message = ?
            WHERE department = ?
        """, (
            status,
            total_records,
            now_ts,
            current_category,
            current_page,
            total_pages,
            error_message,
            department
        ))
        conn.commit()

def get_all_department_statuses() -> List[Dict]:
    """Returns status cards info for all departments."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM department_status ORDER BY department ASC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Re-count records to ensure 100% accuracy
            cursor.execute("SELECT COUNT(*) as cnt FROM issuances WHERE department = ?", (d["department"],))
            d["total_records"] = cursor.fetchone()["cnt"]
            result.append(d)
        return result

def record_failed_page(department: str, category: str, url: str, error_message: str):
    """Logs a failed page for retry."""
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO failed_pages (department, category, url, error_message, timestamp, retry_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (department, category, url, error_message, now_ts))
        conn.commit()

def get_failed_pages(department: Optional[str] = None) -> List[Dict]:
    """Retrieves all failed pages."""
    query = "SELECT * FROM failed_pages WHERE 1=1"
    params = []
    if department:
        query += " AND department = ?"
        params.append(department)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

def clear_failed_page(failed_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM failed_pages WHERE id = ?", (failed_id,))
        conn.commit()

def delete_all_issuances(department: Optional[str] = None):
    """Cleans issuances table for a given department or all."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if department:
            cursor.execute("DELETE FROM issuances WHERE department = ?", (department,))
            cursor.execute("UPDATE department_status SET total_records = 0 WHERE department = ?", (department,))
        else:
            cursor.execute("DELETE FROM issuances")
            cursor.execute("UPDATE department_status SET total_records = 0")
        conn.commit()

def remove_duplicates_cleanup() -> int:
    """
    Explicit database duplicate scrubber.
    Finds and deletes any records with matching duplicate hash, keeping lowest id.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM issuances
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM issuances
                GROUP BY duplicate_hash
            )
        """)
        deleted = cursor.rowcount
        conn.commit()
    return deleted

def save_checkpoint(
    department: str,
    category: str,
    page: int = 1,
    url: str = "",
    completed_categories: Optional[List[str]] = None,
    category_pages: Optional[Dict] = None
):
    """Saves or updates progress checkpoint for seamless continuation."""
    completed_json = json.dumps(completed_categories or [])
    category_pages_json = json.dumps(category_pages or {})
    now_ts = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO extraction_checkpoints (department, category, page, url, completed_categories, updated_at, category_pages)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(department) DO UPDATE SET
                category = excluded.category,
                page = excluded.page,
                url = excluded.url,
                completed_categories = excluded.completed_categories,
                updated_at = excluded.updated_at,
                category_pages = excluded.category_pages
        """, (department, category, page, url, completed_json, now_ts, category_pages_json))
        conn.commit()

def get_checkpoint(department: str) -> Optional[Dict]:
    """Retrieves active checkpoint for a department."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM extraction_checkpoints WHERE department = ?", (department,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            try:
                d["completed_categories"] = json.loads(d.get("completed_categories") or "[]")
            except Exception:
                d["completed_categories"] = []
            try:
                d["category_pages"] = json.loads(d.get("category_pages") or "{}")
            except Exception:
                d["category_pages"] = {}
            return d
    return None

def get_all_checkpoints() -> Dict[str, Dict]:
    """Retrieves all active checkpoints across departments."""
    results = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM extraction_checkpoints")
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["completed_categories"] = json.loads(d.get("completed_categories") or "[]")
            except Exception:
                d["completed_categories"] = []
            try:
                d["category_pages"] = json.loads(d.get("category_pages") or "{}")
            except Exception:
                d["category_pages"] = {}
            results[d["department"]] = d
    return results

def clear_checkpoint(department: str):
    """Clears checkpoint upon successful completion of all categories."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM extraction_checkpoints WHERE department = ?", (department,))
        conn.commit()


def log_quarantine(department: str, category: str, issue_type: str, details: str, source_url: str = "") -> Optional[int]:
    """
    Records skipped items, missing metadata, or sequence gaps into quarantine_logs.
    Uses INSERT OR IGNORE based on (department, category, issue_type, details) to prevent duplicates.
    Returns the inserted log ID, or None if skipped as duplicate.
    """
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO quarantine_logs (
                department, category, issue_type, details, source_url, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (department or "", category or "", issue_type or "", details or "", source_url or "", created_at))
        conn.commit()
        return cursor.lastrowid if cursor.rowcount > 0 else None


def get_quarantine_logs(status: Optional[str] = "Pending") -> List[Dict]:
    """Retrieves quarantine logs filtered by status (default 'Pending'). If status is None or 'all', returns all logs."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if status and status.lower() != "all":
            cursor.execute("""
                SELECT id, department, category, issue_type, details, source_url, status, created_at, resolved_at
                FROM quarantine_logs
                WHERE status = ?
                ORDER BY id DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT id, department, category, issue_type, details, source_url, status, created_at, resolved_at
                FROM quarantine_logs
                ORDER BY id DESC
            """)
        return [dict(row) for row in cursor.fetchall()]


def resolve_quarantine_log(log_id: int, status: str = "Resolved") -> bool:
    """Updates status of a quarantine log to 'Resolved' or 'Ignored' with resolved timestamp."""
    resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE quarantine_logs
            SET status = ?, resolved_at = ?
            WHERE id = ?
        """, (status, resolved_at, log_id))
        conn.commit()
        return cursor.rowcount > 0


def clear_quarantine_logs():
    """Clears all quarantine logs (used primarily for test isolation)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quarantine_logs")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'quarantine_logs'")
        conn.commit()

