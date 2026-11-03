# Changelog

All notable changes to the **Philippine Government Issuance Title Collector** are documented in this file.

The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.

---

## [1.4.0] - 2026-11-03

### Added
- **Extraction Audit & Run History Reporting Suite**: Comprehensive audit reports and structured machine-readable dataset in `reports/extraction-audit/` (`EXTRACTION_REPORT.md`, `EXTRACTION_EVIDENCE.md`, `extraction_report.json`).
- **Semantic Versioning & Metadata Engine**: Dedicated single source of truth in `version.py`, standardized PEP 621 `pyproject.toml`, and runtime metadata integration in `config.py`.
- **System Version API**: Endpoint `GET /api/version` exposing application name, version, build date, and runtime status; updated `GET /api/status` with version fields.
- **Administrative Dashboard Version Elements**: Sovereign header version tag and accessible administrative footer with application name, version, and build date.

---

## [1.3.1] - 2026-11-03

> **Note:** This revision (`commit 1f3a409`) is the exact build used to execute the extraction runs that collected the delivered datasets for DA, DOH, and DepEd (47,023 total records).

### Fixed
- **PostgreSQL Ingestion Batch Chunking**: Chunked bulk issuance inserts into batches of 1,000 items to prevent exceeding PostgreSQL's 65,535 query parameter limit during large extraction runs.

---

## [1.3.0] - 2026-11-01

### Added
- **Legal Compliance Suite**: Comprehensive Terms of Service (`TERMS_OF_SERVICE.md`), Privacy Policy (`PRIVACY_POLICY.md`), and interactive modal login consent verification.

---

## [1.2.0] - 2026-11-01

### Added
- **Quarantine Triage Workflow**: Interactive manual review workflow for suspicious titles, data provenance resolution guide (`QUARANTINE_RESOLUTION_GUIDE.md`), and automated validation triage in `database/validator.py`.

---

## [1.1.0] - 2026-11-01

### Added
- **PIN Gateway Protection**: Lightweight in-memory PIN access gateway (`pin_gateway.py`) with single active session enforcement and configurable environment secret.

---

## [1.0.0] - 2026-11-01

### Major / Breaking Changes
- **PostgreSQL Architecture Migration**: Migrated the core database persistence and ingestion pipeline from local SQLite to PostgreSQL (`database/db.py`).
- **Connection Pool Routing**: Implemented automatic detection and routing for Supabase transaction pooler (`:6543`) with `NullPool` integration to avoid connection saturation.

### Added
- **PostgreSQL Storage Layer**: Chunked batch inserts with `ON CONFLICT DO NOTHING` idempotency for duplicate hashes.

---

## [0.8.0] - 2026-11-01

### Added
- **Hybrid Storage Architecture**: Supported dual-mode storage routing between local filesystem and Vercel Blob cloud storage (`storage.py`).

---

## [0.7.0] - 2026-11-01

### Added
- **Parallel Category Extraction for DepEd**: Implemented multi-threaded worker pools in `scrapers/deped.py` with composite multi-category checkpointing (`extraction_checkpoints.category_pages`).

---

## [0.6.0] - 2026-11-01

### Added
- **Persistent Quarantine Ledger**: Created `quarantine_logs` table for tracking suspicious or generic titles and recording data provenance audit trials.

---

## [0.5.0] - 2026-11-01

### Added
- **Environment-Aware Persistence**: Added runtime environment detection (`is_prod_env()`) and file routing in `config.py`.

---

## [0.4.0] - 2026-10-31

### Added
- **Actionable UI Controls**: Ensured extraction resume controls, agency selection buttons, and status monitors are always visible and responsive in `templates/dashboard.html` and `static/js/dashboard.js`.

---

## [0.3.0] - 2026-10-31

### Added
- **State Checkpointing & Resume Engine**: Implemented `extraction_checkpoints` table and resume workflows in scrapers.
- **DepEd Loop Prevention**: Fixed pagination termination logic to stop loops on circular WordPress archive pages.

---

## [0.2.0] - 2026-10-30

### Added
- **Compliant DOH Listing Extraction**: Added paginated REST API scraping for Department of Health Inforouter portal.

---

## [0.1.0] - 2026-10-30

### Added
- **Initial Prototype**: Multi-department scraper application covering Department of Agriculture (DA), Department of Health (DOH), Department of Education (DepEd), and Department of Environment and Natural Resources (DENR).
- **Export Engines**: Word (`.docx`), Excel (`.xlsx`), CSV, and TXT document generators.
