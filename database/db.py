import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
    update,
    delete,
    func,
    or_
)
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker, declarative_base

import config
from config import DATABASE_URI
from database.models import IssuanceRecord

def get_engine_kwargs(uri: str) -> dict:
    """
    Configures SQLAlchemy connection pooling dynamically:
    - Supabase Transaction pooler (port 6543 / pooler.supabase.com): uses NullPool so connections
      are managed externally by Supavisor and never hoard pooled connections.
    - Cloud production (Render, Vercel): limits pool_size=2 and max_overflow=3.
    - Local / Dev: unconstrained pool (pool_size=10, max_overflow=20) for fast parallel scraping without limits.
    """
    is_supabase_pooler = "pooler.supabase.com" in (uri or "") or ":6543" in (uri or "")
    is_remote_or_prod = getattr(config, "IS_PROD", False) or is_supabase_pooler or any(
        host in (uri or "") for host in ("supabase.", "render.com", "neon.tech", "aws")
    )

    kwargs = {
        "pool_pre_ping": True,
        "connect_args": {"prepare_threshold": None}
    }

    if is_supabase_pooler:
        # Use NullPool with Supabase Transaction pooler so connections are released back immediately
        kwargs["poolclass"] = NullPool
    elif is_remote_or_prod:
        kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", 2))
        kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", 3))
        kwargs["pool_recycle"] = 300
    else:
        kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", 10))
        kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", 20))

    return kwargs


engine = create_engine(DATABASE_URI, **get_engine_kwargs(DATABASE_URI))
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
    """Returns or refreshes the active SQLAlchemy engine if DATABASE_URI changed."""
    global engine, SessionLocal
    uri = getattr(config, "DATABASE_URI", DATABASE_URI)
    if uri and str(engine.url) != uri:
        engine = create_engine(uri, **get_engine_kwargs(uri))
        SessionLocal.configure(bind=engine)
    return engine


def get_db_session():
    """Returns a new SQLAlchemy Session bound to the active engine."""
    get_current_engine()
    return SessionLocal()


@contextmanager
def get_connection():
    """Yields a raw engine connection context for compatibility."""
    curr_engine = get_current_engine()
    with curr_engine.connect() as conn:
        yield conn


def init_db():
    """Initializes PostgreSQL database schema and ensures default department rows exist."""
    curr_engine = get_current_engine()
    Base.metadata.create_all(bind=curr_engine)

    default_depts = [
        "Department of Agriculture",
        "Department of Health",
        "Department of Environment and Natural Resources",
        "Department of Education"
    ]

    with get_db_session() as session:
        session.execute(
            update(DepartmentStatusModel)
            .where(DepartmentStatusModel.status == "Running")
            .values(
                status="Interrupted",
                error_message="Interrupted by server restart or shutdown. Click Resume to continue."
            )
        )
        existing_depts = set(session.scalars(select(DepartmentStatusModel.department)).all())
        for dept in default_depts:
            if dept not in existing_depts:
                session.add(DepartmentStatusModel(department=dept, status="Idle", total_records=0))
        session.commit()


def save_issuance(record: IssuanceRecord) -> bool:
    """
    Saves an issuance record using PostgreSQL native ON CONFLICT DO NOTHING.
    Returns True if inserted, False if duplicate.
    """
    dup_hash = record.generate_duplicate_hash()
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = record.extraction_timestamp or now_ts

    stmt = (
        pg_insert(IssuanceModel)
        .values(
            department=record.department,
            category=record.category,
            issuance_number=record.issuance_number,
            title=record.title,
            publication_date=record.publication_date,
            source_url=record.source_url,
            extraction_timestamp=timestamp,
            duplicate_hash=dup_hash
        )
        .on_conflict_do_nothing(index_elements=["duplicate_hash"])
        .returning(IssuanceModel.id)
    )

    with get_db_session() as session:
        res = session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        session.commit()
        return inserted_id is not None


def save_issuances_batch(records: List[IssuanceRecord]) -> Tuple[int, int]:
    """
    Batch inserts records via PostgreSQL bulk insert with conflict handling.
    Returns (inserted_count, duplicates_count).
    """
    if not records:
        return 0, 0

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values_list = []
    for r in records:
        dup_hash = r.generate_duplicate_hash()
        timestamp = r.extraction_timestamp or now_ts
        values_list.append({
            "department": r.department,
            "category": r.category,
            "issuance_number": r.issuance_number,
            "title": r.title,
            "publication_date": r.publication_date,
            "source_url": r.source_url,
            "extraction_timestamp": timestamp,
            "duplicate_hash": dup_hash
        })

    stmt = (
        pg_insert(IssuanceModel)
        .values(values_list)
        .on_conflict_do_nothing(index_elements=["duplicate_hash"])
        .returning(IssuanceModel.id)
    )

    with get_db_session() as session:
        res = session.execute(stmt)
        inserted_ids = res.scalars().all()
        session.commit()
        inserted = len(inserted_ids)
        duplicates = len(records) - inserted
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
    with get_db_session() as session:
        query = select(IssuanceModel)
        if department:
            query = query.where(IssuanceModel.department == department)
        if category:
            query = query.where(IssuanceModel.category == category)
        if year:
            query = query.where(
                or_(
                    IssuanceModel.publication_date.ilike(f"%{year}%"),
                    IssuanceModel.title.ilike(f"%{year}%")
                )
            )
        if search:
            query = query.where(
                or_(
                    IssuanceModel.title.ilike(f"%{search}%"),
                    IssuanceModel.issuance_number.ilike(f"%{search}%")
                )
            )

        query = query.order_by(IssuanceModel.id.desc())
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        rows = session.scalars(query).all()
        return [
            {
                "id": r.id,
                "department": r.department,
                "category": r.category,
                "issuance_number": r.issuance_number,
                "title": r.title,
                "publication_date": r.publication_date,
                "source_url": r.source_url,
                "extraction_timestamp": r.extraction_timestamp,
                "duplicate_hash": r.duplicate_hash
            }
            for r in rows
        ]


def get_issuance_count(
    department: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[str] = None,
    search: Optional[str] = None
) -> int:
    """Returns total count of matching records."""
    with get_db_session() as session:
        query = select(func.count(IssuanceModel.id))
        if department:
            query = query.where(IssuanceModel.department == department)
        if category:
            query = query.where(IssuanceModel.category == category)
        if year:
            query = query.where(
                or_(
                    IssuanceModel.publication_date.ilike(f"%{year}%"),
                    IssuanceModel.title.ilike(f"%{year}%")
                )
            )
        if search:
            query = query.where(
                or_(
                    IssuanceModel.title.ilike(f"%{search}%"),
                    IssuanceModel.issuance_number.ilike(f"%{search}%")
                )
            )
        return session.scalar(query) or 0


def update_department_status(
    department: str,
    status: str,
    current_category: Optional[str] = None,
    current_page: Optional[int] = None,
    total_pages: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Updates runtime progress and status for a department using PostgreSQL UPSERT."""
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_session() as session:
        total_records = session.scalar(
            select(func.count(IssuanceModel.id)).where(IssuanceModel.department == department)
        ) or 0

        stmt = (
            pg_insert(DepartmentStatusModel)
            .values(
                department=department,
                status=status,
                total_records=total_records,
                last_extraction=now_ts,
                current_category=current_category,
                current_page=current_page or 0,
                total_pages=total_pages or "Unknown",
                error_message=error_message
            )
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["department"],
            set_={
                "status": stmt.excluded.status,
                "total_records": stmt.excluded.total_records,
                "last_extraction": stmt.excluded.last_extraction,
                "current_category": func.coalesce(stmt.excluded.current_category, DepartmentStatusModel.current_category),
                "current_page": func.coalesce(stmt.excluded.current_page, DepartmentStatusModel.current_page),
                "total_pages": func.coalesce(stmt.excluded.total_pages, DepartmentStatusModel.total_pages),
                "error_message": stmt.excluded.error_message
            }
        )
        session.execute(stmt)
        session.commit()


def get_all_department_statuses() -> List[Dict]:
    """Returns status cards info for all departments."""
    with get_db_session() as session:
        statuses = session.scalars(
            select(DepartmentStatusModel).order_by(DepartmentStatusModel.department.asc())
        ).all()
        result = []
        for s in statuses:
            total = session.scalar(
                select(func.count(IssuanceModel.id)).where(IssuanceModel.department == s.department)
            ) or 0
            result.append({
                "department": s.department,
                "status": s.status,
                "total_records": total,
                "last_extraction": s.last_extraction,
                "error_message": s.error_message,
                "current_category": s.current_category,
                "current_page": s.current_page,
                "total_pages": s.total_pages
            })
        return result


def record_failed_page(department: str, category: str, url: str, error_message: str):
    """Logs a failed page for retry."""
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_session() as session:
        session.add(
            FailedPageModel(
                department=department,
                category=category,
                url=url,
                error_message=error_message,
                timestamp=now_ts,
                retry_count=0
            )
        )
        session.commit()


def get_failed_pages(department: Optional[str] = None) -> List[Dict]:
    """Retrieves all failed pages."""
    with get_db_session() as session:
        query = select(FailedPageModel)
        if department:
            query = query.where(FailedPageModel.department == department)
        rows = session.scalars(query).all()
        return [
            {
                "id": r.id,
                "department": r.department,
                "category": r.category,
                "url": r.url,
                "error_message": r.error_message,
                "timestamp": r.timestamp,
                "retry_count": r.retry_count
            }
            for r in rows
        ]


def clear_failed_page(failed_id: int):
    """Removes a failed page entry once resolved."""
    with get_db_session() as session:
        session.execute(delete(FailedPageModel).where(FailedPageModel.id == failed_id))
        session.commit()


def delete_all_issuances(department: Optional[str] = None):
    """Cleans issuances table for a given department or all."""
    with get_db_session() as session:
        if department:
            session.execute(delete(IssuanceModel).where(IssuanceModel.department == department))
            session.execute(
                update(DepartmentStatusModel)
                .where(DepartmentStatusModel.department == department)
                .values(total_records=0)
            )
        else:
            session.execute(delete(IssuanceModel))
            session.execute(update(DepartmentStatusModel).values(total_records=0))
        session.commit()


def remove_duplicates_cleanup() -> int:
    """
    Explicit database duplicate scrubber.
    Finds and deletes any records with matching duplicate hash, keeping lowest id.
    """
    with get_db_session() as session:
        subquery = (
            select(func.min(IssuanceModel.id))
            .where(IssuanceModel.duplicate_hash.isnot(None))
            .group_by(IssuanceModel.duplicate_hash)
        )
        stmt = delete(IssuanceModel).where(
            IssuanceModel.duplicate_hash.isnot(None),
            IssuanceModel.id.not_in(subquery)
        )
        res = session.execute(stmt)
        session.commit()
        return res.rowcount or 0


def save_checkpoint(
    department: str,
    category: str,
    page: int = 1,
    url: str = "",
    completed_categories: Optional[List[str]] = None,
    category_pages: Optional[Dict] = None
):
    """Saves or updates progress checkpoint for seamless continuation via PostgreSQL UPSERT."""
    completed_json = json.dumps(completed_categories or [])
    category_pages_json = json.dumps(category_pages or {})
    now_ts = datetime.now().isoformat()

    stmt = (
        pg_insert(ExtractionCheckpointModel)
        .values(
            department=department,
            category=category,
            page=page,
            url=url,
            completed_categories=completed_json,
            updated_at=now_ts,
            category_pages=category_pages_json
        )
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["department"],
        set_={
            "category": stmt.excluded.category,
            "page": stmt.excluded.page,
            "url": stmt.excluded.url,
            "completed_categories": stmt.excluded.completed_categories,
            "updated_at": stmt.excluded.updated_at,
            "category_pages": stmt.excluded.category_pages
        }
    )
    with get_db_session() as session:
        session.execute(stmt)
        session.commit()


def get_checkpoint(department: str) -> Optional[Dict]:
    """Retrieves active checkpoint for a department."""
    with get_db_session() as session:
        cp = session.scalar(
            select(ExtractionCheckpointModel).where(ExtractionCheckpointModel.department == department)
        )
        if not cp:
            return None
        res = {
            "department": cp.department,
            "category": cp.category,
            "page": cp.page,
            "url": cp.url,
            "updated_at": cp.updated_at
        }
        try:
            res["completed_categories"] = json.loads(cp.completed_categories or "[]")
        except Exception:
            res["completed_categories"] = []
        try:
            res["category_pages"] = json.loads(cp.category_pages or "{}")
        except Exception:
            res["category_pages"] = {}
        return res


def get_all_checkpoints() -> Dict[str, Dict]:
    """Retrieves all active checkpoints across departments."""
    results = {}
    with get_db_session() as session:
        rows = session.scalars(select(ExtractionCheckpointModel)).all()
        for cp in rows:
            d = {
                "department": cp.department,
                "category": cp.category,
                "page": cp.page,
                "url": cp.url,
                "updated_at": cp.updated_at
            }
            try:
                d["completed_categories"] = json.loads(cp.completed_categories or "[]")
            except Exception:
                d["completed_categories"] = []
            try:
                d["category_pages"] = json.loads(cp.category_pages or "{}")
            except Exception:
                d["category_pages"] = {}
            results[cp.department] = d
    return results


def clear_checkpoint(department: str):
    """Clears checkpoint upon successful completion of all categories."""
    with get_db_session() as session:
        session.execute(
            delete(ExtractionCheckpointModel).where(ExtractionCheckpointModel.department == department)
        )
        session.commit()


def log_quarantine(department: str, category: str, issue_type: str, details: str, source_url: str = "") -> Optional[int]:
    """
    Records skipped items, missing metadata, or sequence gaps into quarantine_logs.
    Uses PostgreSQL ON CONFLICT DO NOTHING based on uq_quarantine_log to prevent duplicate entries.
    Returns the inserted log ID, or None if skipped as duplicate.
    """
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stmt = (
        pg_insert(QuarantineLogModel)
        .values(
            department=department or "",
            category=category or "",
            issue_type=issue_type or "",
            details=details or "",
            source_url=source_url or "",
            status="Pending",
            created_at=created_at
        )
        .on_conflict_do_nothing(constraint="uq_quarantine_log")
        .returning(QuarantineLogModel.id)
    )

    with get_db_session() as session:
        res = session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        session.commit()
        return inserted_id


def get_quarantine_logs(status: Optional[str] = "Pending") -> List[Dict]:
    """Retrieves quarantine logs filtered by status (default 'Pending'). If status is None or 'all', returns all logs."""
    with get_db_session() as session:
        query = select(QuarantineLogModel).order_by(QuarantineLogModel.id.desc())
        if status and status.lower() != "all":
            query = query.where(QuarantineLogModel.status == status)
        rows = session.scalars(query).all()
        return [
            {
                "id": r.id,
                "department": r.department,
                "category": r.category,
                "issue_type": r.issue_type,
                "details": r.details,
                "source_url": r.source_url,
                "status": r.status,
                "created_at": r.created_at,
                "resolved_at": r.resolved_at
            }
            for r in rows
        ]


def resolve_quarantine_log(log_id: int, status: str = "Resolved") -> bool:
    """Updates status of a quarantine log to 'Resolved' or 'Ignored' with resolved timestamp."""
    resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_session() as session:
        res = session.execute(
            update(QuarantineLogModel)
            .where(QuarantineLogModel.id == log_id)
            .values(status=status, resolved_at=resolved_at)
        )
        session.commit()
        return (res.rowcount or 0) > 0


def clear_quarantine_logs():
    """Clears all quarantine logs (used primarily for test isolation)."""
    with get_db_session() as session:
        session.execute(delete(QuarantineLogModel))
        session.commit()
