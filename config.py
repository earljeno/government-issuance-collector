import os
import tempfile
from pathlib import Path
# Base Paths
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Detect if we are running in cloud production (Vercel, Render, etc.)
IS_VERCEL = os.environ.get("VERCEL") == "1"
IS_RENDER = os.environ.get("RENDER") in ("true", "1")
IS_PROD = (
    IS_VERCEL
    or IS_RENDER
    or os.environ.get("ENV") == "production"
    or os.environ.get("ENVIRONMENT") == "production"
    or os.environ.get("FLASK_ENV") == "production"
)


def is_prod_env() -> bool:
    """Dynamically determine if the application is running in production."""
    import sys
    conf = sys.modules.get("config")
    prod_flag = getattr(conf, "IS_PROD", False) if conf else IS_PROD
    return bool(
        prod_flag
        or os.environ.get("VERCEL") == "1"
        or os.environ.get("RENDER") in ("true", "1")
        or os.environ.get("ENV") == "production"
        or os.environ.get("ENVIRONMENT") == "production"
        or os.environ.get("FLASK_ENV") == "production"
    )


# 1. File storage routing
if IS_VERCEL:
    DATA_DIR = Path(tempfile.gettempdir()) / "data"
else:
    DATA_DIR = Path(__file__).parent / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 2. Database routing (PostgreSQL via SQLAlchemy)
raw_url = (
    os.environ.get("POSTGRES_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://postgres:postgres@localhost:5432/government_issuances"
)
DATABASE_URI = raw_url.replace("postgres://", "postgresql://", 1)

# Automatically route Supabase pooler from Session mode (:5432 with 15-client limit)
# to Transaction mode (:6543) to avoid EMAXCONNSESSION
if "pooler.supabase.com:5432" in DATABASE_URI:
    DATABASE_URI = DATABASE_URI.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")

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
        "portal_url": "https://www.da.gov.ph/",
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
        "portal_url": "https://doh.gov.ph/",
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
        "portal_url": "https://denr.gov.ph/",
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
        "portal_url": "https://www.deped.gov.ph/",
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
