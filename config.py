import os
import tempfile
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent

# Detect if we are running on Vercel
IS_VERCEL = os.environ.get("VERCEL") == "1"

# 1. FILE STORAGE ROUTING
if IS_VERCEL:
    # Vercel requires writing to /tmp
    DATA_DIR = Path(tempfile.gettempdir()) / "data"
else:
    # Local development writes to the project folder
    DATA_DIR = Path(__file__).parent / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 2. DATABASE ROUTING
if IS_VERCEL:
    # Use Vercel Postgres in production (must use postgresql:// for SQLAlchemy)
    raw_url = os.environ.get("POSTGRES_URL", "")
    DATABASE_PATH = DATA_DIR / "database.db"
    if raw_url:
        DATABASE_URI = raw_url.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
else:
    # Use SQLite locally
    DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(DATA_DIR / "database.db")))
    DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Migrate legacy database files if database.db does not exist yet
legacy_db = BASE_DIR / "database" / "issuances.db"
legacy_data_db = DATA_DIR / "issuances.db"
if not DATABASE_PATH.exists():
    for old_db in [legacy_data_db, legacy_db]:
        if old_db.exists():
            try:
                import shutil
                shutil.copy2(old_db, DATABASE_PATH)
                break
            except Exception:
                pass

# Application Settings
APP_HOST = "127.0.0.1"
APP_PORT = 5000
DEBUG = False

# HTTP Request Defaults
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_USER_AGENT = USER_AGENT
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_DELAY_SECONDS = 1.0  # Polite crawl delay
MAX_RETRIES = 3

# Departments and Categories Configuration
DEPARTMENTS = {
    "DA": {
        "name": "Department of Agriculture",
        "code": "DA",
        "base_url": "https://www.da.gov.ph/",
        "categories": {
            "Administrative Orders": "https://www.da.gov.ph/laws-and-issuances/administrative-orders/",
            "Administrative Circulars": "https://www.da.gov.ph/laws-and-issuances/administrative-circulars/",
            "Department Orders": "https://www.da.gov.ph/laws-and-issuances/department-orders/",
            "Department Circulars": "https://www.da.gov.ph/laws-and-issuances/department-circulars/",
            "Memorandum Orders": "https://www.da.gov.ph/laws-and-issuances/memorandum-orders/",
            "Memorandum Circulars": "https://www.da.gov.ph/laws-and-issuances/memorandum-circulars/",
            "Joint Administrative Orders": "https://www.da.gov.ph/laws-and-issuances/joint-administrative-orders/",
            "Joint Department Circulars": "https://www.da.gov.ph/laws-and-issuances/joint-department-circular/",
            "Joint Memorandum Circulars": "https://www.da.gov.ph/laws-and-issuances/joint-memorandum-circulars/",
            "Joint Memorandum Orders": "https://www.da.gov.ph/laws-and-issuances/joint-memorandum-order/",
            "Joint Special Orders": "https://www.da.gov.ph/laws-and-issuances/joint-special-orders/",
            "Special Orders": "https://www.da.gov.ph/laws-and-issuances/special-orders/",
            "General Memorandum Orders": "https://www.da.gov.ph/laws-and-issuances/general-memorandum-orders/",
            "Office Orders": "https://www.da.gov.ph/laws-and-issuances/office-orders/",
            "Inter-Agency Circulars": "https://www.da.gov.ph/laws-and-issuances/inter-agency-circulars/",
            "Republic Acts and Proclamations": "https://www.da.gov.ph/laws-and-issuances/republic-acts/"
        }
    },
    "DOH": {
        "name": "Department of Health",
        "code": "DOH",
        "base_url": "https://app.doh.gov.ph:1024/",
        "categories": {
            "Administrative Orders": "KMITS_AISAO",
            "Department Circulars": "KMITS_AISDC",
            "Memorandum Circulars": "KMITS_AISMC",
            "Implementing Rules and Regulations": "KMITS_AISIRR",
            "Joint Administrative Orders": "KMITS_AISJAO",
            "Joint Memorandum Circulars": "KMITS_AISJMC",
            "Joint Circulars": "KMITS_AISJC",
            "Executive Orders": "KMITS_AISEO",
            "Republic Acts": "KMITS_AISRA"
        }
    },
    "DENR": {
        "name": "Department of Environment and Natural Resources",
        "code": "DENR",
        "base_url": "https://denr.gov.ph/",
        "categories": {
            "Administrative Orders": "https://denr.gov.ph/laws-and-policies/administrative-orders/",
            "Memorandum Circulars": "https://denr.gov.ph/laws-and-policies/memorandum-circulars/",
            "Memorandum Orders": "https://denr.gov.ph/laws-and-policies/memorandum-orders/",
            "Joint Administrative Orders": "https://denr.gov.ph/laws-and-policies/joint-administrative-orders/",
            "Joint Memorandum Circulars": "https://denr.gov.ph/laws-and-policies/joint-memorandum-circulars/",
            "Special Orders": "https://denr.gov.ph/laws-and-policies/special-orders/",
            "Executive Orders": "https://denr.gov.ph/laws-and-policies/executive-orders/",
            "Republic Acts": "https://denr.gov.ph/laws-and-policies/republic-acts/",
            "Presidential Decrees": "https://denr.gov.ph/laws-and-policies/presidential-decrees/",
            "Commonwealth Acts": "https://denr.gov.ph/laws-and-policies/commonwealth-acts/"
        }
    },
    "DepEd": {
        "name": "Department of Education",
        "code": "DepEd",
        "base_url": "https://www.deped.gov.ph/",
        "categories": {
            "DepEd Advisories": "https://www.deped.gov.ph/category/issuances/deped-advisories/",
            "DepEd Memoranda": "https://www.deped.gov.ph/category/issuances/deped-memoranda/",
            "DepEd Orders": "https://www.deped.gov.ph/category/issuances/deped-orders/",
            "Joint Memorandum Circular": "https://www.deped.gov.ph/category/issuances/joint-memorandum-circular/",
            "Office Orders": "https://www.deped.gov.ph/category/issuances/office-order/",
            "Implementing Rules and Regulations": "https://www.deped.gov.ph/category/issuances/implementing-rules-and-regulations/"
        }
    }
}
