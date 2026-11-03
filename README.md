# Philippine Government Issuance Title Collector

**Version 1.0.0** &bull; **Build Date: 2026-11-03**

An administrative web application built with Python and Flask for automatically collecting and compiling the **TITLES** of laws, policies, and administrative issuances from four key Philippine government departments:

1. **Department of Agriculture (DA)** – `https://www.da.gov.ph/`
2. **Department of Education (DepEd)** – `https://www.deped.gov.ph/`
3. **Department of Health (DOH)** – `https://doh.gov.ph/`
4. **Department of Environment and Natural Resources (DENR)** – `https://denr.gov.ph/`

The application compiles collected government issuance titles into an organized Microsoft Word document (`.docx`), an Excel spreadsheet (`.xlsx`), CSV, and TXT files.

---

## 🌟 Key Features

- **Department-Specific Scrapers**: Custom extraction modules tailored to each website's unique architecture (WordPress TablePress for DA, WordPress categorized pagination for DepEd, card/table layouts for DOH and DENR).
- **Background Multi-Threaded Execution**: Extractions run asynchronously in background threads without blocking or freezing the web dashboard.
- **Real-Time Live Progress**: Tracks current department, category, page number, total pages, and record counts via dynamic polling.
- **Robust Duplicate Detection**: Prevents duplicate insertions using a SHA-256 hash composite key (`department + category + normalized issuance number + normalized title`). Includes an on-demand duplicate scrubber.
- **Academic Microsoft Word Export (.docx)**: Generates a professionally formatted document on A4 paper with Roman numeral department headings, alphabetical category headings, numbered entries, and clickable hyperlinks for each source URL.
- **Structured Excel Export (.xlsx)**: Features auto-fit columns, frozen header row, active auto-filters, and clean typography.
- **Manual URL / HTML Import Mode**: Allows pasting any official listing URL or raw HTML source. Automatically detects table or article structures, parses records, and provides an interactive preview before committing to the database.
- **Compliance & Reliability**: Strictly adheres to access limits, distinguishes unavailable/protected portals from scraper errors, and logs failed requests for retries without fabricating records.
- **Digitization & Completeness Notice**: The tool retrieves only records that government agencies have actively published in digital format online. It cannot extract issuances that exist solely in physical paper archives, internal agency filing rooms, or un-indexed historical repositories. The absence of an issuance in this database does not indicate that the issuance does not exist under Philippine law.

---

## 🛠️ Project Structure

```text
government-issuance-collector/
├── version.py                 # Single source of truth for version and build metadata
├── pyproject.toml             # Standard PEP 621 package metadata
├── app.py                     # Flask application & background task manager
├── config.py                  # Department URLs, scraper settings, and file paths
├── requirements.txt           # Python dependencies
├── README.md                  # Installation and usage instructions
├── database/
│   ├── models.py              # IssuanceRecord dataclass & duplicate key hashing
│   └── db.py                  # PostgreSQL database engine, models, and queries
├── scrapers/
│   ├── base.py                # Abstract BaseScraper with retry, delay, and callbacks
│   ├── da.py                  # Department of Agriculture (TablePress scraper)
│   ├── deped.py               # Department of Education (Pagination scraper)
│   ├── doh.py                 # Department of Health (WAF/accessibility detector)
│   ├── denr.py                # Department of Environment and Natural Resources
│   └── manual_url.py          # Generic table/article structure extractor
├── exporters/
│   ├── word_exporter.py       # Professional A4 Word document (.docx) generator
│   ├── excel_exporter.py      # Styled Excel spreadsheet (.xlsx) generator
│   └── csv_exporter.py        # CSV and TXT document generators
├── templates/
│   └── dashboard.html         # Responsive administrative dashboard
├── static/
│   ├── css/style.css          # Modern dashboard styling & Philippine theme
│   └── js/dashboard.js        # Asynchronous API polling and UI controls
├── tests/
│   ├── test_scrapers.py       # Unit tests for scrapers, models, and exporters
│   ├── test_app.py            # API endpoint integration tests
│   └── fixtures/              # Offline HTML fixtures for reproducible tests
└── exports/                   # Default storage folder for exported files
```

---

## 🚀 Quick Start (Windows Installation)

### Prerequisites

- **Python 3.11+** installed and added to your system `PATH`.
- **Git** (optional).

### 1. Install Dependencies

Open PowerShell or Command Prompt in the project folder and run:

```powershell
pip install -r requirements.txt
playwright install chromium
```

### 2. Start the Application

```powershell
python app.py
```

### 3. Open the Web Dashboard

Open your web browser and navigate to:

```text
http://127.0.0.1:5000
```

---

## 📖 How to Use

### 1. Extract All Departments
Click the **"Extract All Departments"** button at the top of the dashboard. The application will sequentially crawl the selected categories across all departments in the background.

### 2. Extract a Single Department
Choose a department card (e.g. **Department of Agriculture** or **Department of Education**) and click **"Extract [Department]"**. You can uncheck individual categories if you only want specific issuances (e.g. only *Administrative Orders* or *DepEd Memoranda*).

### 3. Apply Year and Page Limits
- Use the **Year Filter** dropdown (e.g. `2026`, `2025`, `2024`, etc.) to collect issuances from a specific year.
- Use the **Page Limit** dropdown (e.g. `1 Page`, `3 Pages`, `All Pages`) to run quick verification crawls.

### 4. Stopping and Retrying
- Click **"Stop Extraction"** at any time to gracefully halt background scraping.
- Click **"Retry Failed Pages"** to re-attempt pages that encountered temporary network timeouts.

### 5. Manual URL / HTML Import Mode
If an official government website changes layout or is protected by Cloudflare WAF:
1. Click **"Manual URL / HTML Import"**.
2. Select the target department and category name.
3. Paste the webpage URL (Option A) or paste the page's HTML source (Option B).
4. Click **"Analyze & Preview Structure"**.
5. Inspect the detected table/card entries in the live preview.
6. Click **"Approve & Save Records"** to commit them to the database.

### 6. Review & Export
- Browse the extracted records in the interactive table with instant search and pagination.
- Click **"Remove Duplicates"** to scrub any redundant entries.
- Click **"Export Word (.docx)"** to download the compiled academic Word document with clickable hyperlinks.
- Click **"Export Excel (.xlsx)"** to download the spreadsheet with frozen headers and auto-filters.
- Also supports **CSV** and **TXT** downloads.

---

## 🧪 Running Unit Tests

The test suite runs against saved offline HTML fixtures without hitting government servers:

```powershell
python -m unittest discover -s tests
```

All 14 tests verify:
- Accurate extraction of title, issuance number, and publication date
- Year extraction and accordion detection in DA TablePress
- Pagination detection and older records (dating back to 1996) in DepEd
- Cloudflare WAF accessibility checks for DOH and DENR
- Duplicate prevention and database hash uniqueness
- Document generation for Word, Excel, CSV, and TXT
- Web API endpoints and status reporting
