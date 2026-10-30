import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "issuances.db"
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

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
        "base_url": "https://doh.gov.ph/",
        "categories": {
            "Administrative Orders": "https://doh.gov.ph/health-policies/administrative-orders/",
            "Implementing Rules and Regulations": "https://doh.gov.ph/health-policies/implementing-rules-and-regulations/",
            "Memorandum Circulars": "https://doh.gov.ph/health-policies/memorandum-circulars/",
            "Memorandum Orders": "https://doh.gov.ph/health-policies/memorandum-orders/",
            "Department Circulars": "https://doh.gov.ph/health-policies/department-circulars/",
            "Department Memoranda": "https://doh.gov.ph/health-policies/department-memoranda/",
            "Joint Administrative Orders": "https://doh.gov.ph/health-policies/joint-administrative-orders/",
            "Joint Circulars": "https://doh.gov.ph/health-policies/joint-circulars/",
            "Republic Acts": "https://doh.gov.ph/health-policies/republic-acts/",
            "Executive Orders": "https://doh.gov.ph/health-policies/executive-orders/",
            "Presidential Decrees": "https://doh.gov.ph/health-policies/presidential-decrees/"
        }
    },
    "DENR": {
        "name": "Department of Environment and Natural Resources",
        "code": "DENR",
        "base_url": "http://www.denrtwelve.com:8090/das12/",
        "categories": {
            "Administrative Orders": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=19",
            "Memorandum Circulars and Orders": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=20",
            "Joint Administrative Orders & Circulars": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=22",
            "Executive Orders": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=21",
            "Republic Acts": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=23",
            "Presidential Decrees": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=24",
            "Commonwealth Acts": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=10&sub=25",
            "Special Orders": "http://www.denrtwelve.com:8090/das12/index.php?view=category&cat=13&sub=30",
            "Technical Bulletins": "https://elibrary.bmb.gov.ph/elibrary/laws-and-policies/technical-bulletins/",
            "BMB Memorandum Circulars": "https://elibrary.bmb.gov.ph/elibrary/laws-and-policies/bmb-memorandum-circulars/"
        }
    },
    "DepEd": {
        "name": "Department of Education",
        "code": "DepEd",
        "base_url": "https://www.deped.gov.ph/",
        "categories": {
            "DepEd Advisories": "https://www.deped.gov.ph/category/issuances/deped-advisories/",
            "DepEd Memoranda": "https://www.deped.gov.ph/category/issuances/deped-memoranda/",
            "DepEd Orders": "https://www.deped.gov.ph/deped-orders/",
            "Joint Memorandum Circular": "https://www.deped.gov.ph/category/issuances/joint-memorandum-circular/",
            "Office Orders": "https://www.deped.gov.ph/category/issuances/office-order/",
            "Unnumbered Memoranda": "https://www.deped.gov.ph/category/issuances/unnumbered-memorandum/",
            "Implementing Rules and Regulations": "https://www.deped.gov.ph/category/issuances/implementing-rules-and-regulations/"
        }
    }
}
