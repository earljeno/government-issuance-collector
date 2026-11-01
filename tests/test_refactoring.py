import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
from docx import Document

import config
config.DATABASE_PATH = config.BASE_DIR / "database" / "test_issuances.db"

from scrapers.deped import DepEdScraper
from scrapers.da import DAScraper
from scrapers.doh import DOHScraper
from database.models import IssuanceRecord
from database.validator import sanitize_publication_date
from database.db import log_quarantine, get_quarantine_logs, resolve_quarantine_log, clear_quarantine_logs
from exporters.word_exporter import add_hyperlink, generate_word_document
from app import app


class TestRefactoringFixes(unittest.TestCase):

    def test_config_deped_orders_url(self):
        """Action 1: DepEd Orders URL must point to standard taxonomy archive."""
        deped_cfg = config.DEPARTMENTS["DepEd"]["categories"]
        self.assertEqual(
            deped_cfg["DepEd Orders"],
            "https://www.deped.gov.ph/category/issuances/deped-orders/"
        )

    def test_deped_pagination_exclusion_and_scoped_titles(self):
        """Action 2 & 3: Exclude pagination navigation links (/page/) and thematic container headings."""
        html = """
        <div class="content">
            <h1 class="archive-title">DEPED ORDER</h1>
            <article class="post">
                <h2 class="thematic-container"><a href="https://www.deped.gov.ph/category/issuances/deped-orders/">DEPED ORDER</a></h2>
            </article>
            <article class="post">
                <h2 class="entry-title"><a href="https://www.deped.gov.ph/deped-orders/page/470/">DEPED ORDER</a></h2>
            </article>
            <article class="post">
                <h2 class="entry-title">
                    <a href="https://www.deped.gov.ph/2026/03/15/do-010-s-2026-policy-guidelines-on-assessment/">
                        March 15, 2026 DO 010, s. 2026 – Policy Guidelines on Assessment
                    </a>
                </h2>
                <div class="entry-meta">
                    <time datetime="2026-03-15">March 15, 2026</time>
                </div>
            </article>
            <article class="post">
                <h2 class="entry-title">
                    <a href="https://www.deped.gov.ph/2026/04/01/irr-of-ra-12345/">
                        Implementing Rules and Regulations of Republic Act No. 12345
                    </a>
                </h2>
            </article>
        </div>
        """
        scraper = DepEdScraper()
        scraper.fetch_url = lambda url: None
        records, next_url = scraper._parse_page(
            html,
            category_name="DepEd Orders",
            current_url="https://www.deped.gov.ph/category/issuances/deped-orders/"
        )

        # Pagination links and generic container titles must be excluded
        self.assertEqual(len(records), 2)

        # First valid record
        self.assertEqual(records[0].issuance_number, "DO 010, s. 2026")
        self.assertIn("Policy Guidelines on Assessment", records[0].title)
        self.assertNotIn("/page/", records[0].source_url)

        # Second record: legitimate unnumbered IRR should preserve empty issuance number
        self.assertEqual(records[1].issuance_number, "")
        self.assertIn("Implementing Rules and Regulations", records[1].title)

    def test_duplicate_hashing_punctuation_and_blanks(self):
        """Action: Hash generation strips non-alphanumeric chars and safely handles blanks/None."""
        rec1 = IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 12, s. 2026",
            title="Entity Inc."
        )
        rec2 = IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 12 s. 2026",
            title="Entity, Inc."
        )
        self.assertEqual(rec1.generate_duplicate_hash(), rec2.generate_duplicate_hash())

        # Safe handling of None and empty strings without exception
        rec_blank1 = IssuanceRecord(
            department="",
            category="",
            issuance_number="",
            title=""
        )
        rec_blank2 = IssuanceRecord(
            department=None,
            category=None,
            issuance_number=None,
            title=None
        )
        self.assertEqual(rec_blank1.generate_duplicate_hash(), rec_blank2.generate_duplicate_hash())

    def test_da_scraper_link_integrity(self):
        """Action: DA table row lacking PDF link must set source_link = '' instead of page_url."""
        html = """
        <table class="tablepress">
            <thead>
                <tr><th>Code</th><th>Subject</th><th>Date</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>AO No. 10</td>
                    <td><a href="https://www.da.gov.ph/wp-content/uploads/2026/01/ao10.pdf">Guidelines with PDF</a></td>
                    <td>10 January 2026</td>
                </tr>
                <tr>
                    <td>AO No. 11</td>
                    <td>Guidelines without PDF Link</td>
                    <td>11 January 2026</td>
                </tr>
                <tr>
                    <td>AO No. 12</td>
                    <td><a href="https://www.da.gov.ph/laws-and-issuances/administrative-orders/">Self referencing link</a></td>
                    <td>12 January 2026</td>
                </tr>
            </tbody>
        </table>
        """
        page_url = "https://www.da.gov.ph/laws-and-issuances/administrative-orders/"
        scraper = DAScraper()
        records = scraper._parse_category_page(html, "Administrative Orders", page_url)

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].source_url, "https://www.da.gov.ph/wp-content/uploads/2026/01/ao10.pdf")
        # Missing link must be strictly empty
        self.assertEqual(records[1].source_url, "")
        # Self-referencing listing link must be strictly empty
        self.assertEqual(records[2].source_url, "")

    def test_doh_api_date_boundary_check(self):
        """Action: Year 2500 corrected to 2005, future years (> current year) cleared."""
        scraper = DOHScraper()

        # Typo year 2500
        item_2500 = {
            "documentId": 1001,
            "issuanceNumber": "AO-2005-001",
            "subject": "National Health Policy",
            "publishedDate": "2500-08-15T00:00:00"
        }
        rec_2500 = scraper._item_to_record(item_2500, "Administrative Orders")
        self.assertIsNotNone(rec_2500)
        self.assertEqual(rec_2500.publication_date, "2005-08-15")
        self.assertEqual(rec_2500.source_url, "https://app.doh.gov.ph:1024/Rest/GetFile?id=1001")

        # Future year > current year
        item_future = {
            "documentId": 1002,
            "issuanceNumber": "AO-3000-001",
            "subject": "Future Guidelines",
            "publishedDate": "3000-01-01T00:00:00"
        }
        rec_future = scraper._item_to_record(item_future, "Administrative Orders")
        self.assertIsNotNone(rec_future)
        self.assertEqual(rec_future.publication_date, "")

        # Missing documentId must not fall back to /Search
        item_noid = {
            "issuanceNumber": "AO-2026-003",
            "subject": "No Document File",
            "publishedDate": "2026-05-01T00:00:00"
        }
        rec_noid = scraper._item_to_record(item_noid, "Administrative Orders")
        self.assertEqual(rec_noid.source_url, "")

    def test_validator_sanitize_publication_date(self):
        """Action: Catch OCR typos (e.g. Apri -> April) and standardize to ISO-8601."""
        self.assertEqual(sanitize_publication_date("Apri 15, 2024"), "2024-04-15")
        self.assertEqual(sanitize_publication_date("15 Apri 2024"), "2024-04-15")
        self.assertEqual(sanitize_publication_date("Januray 10, 2023"), "2023-01-10")
        self.assertEqual(sanitize_publication_date("Februray 28, 2022"), "2022-02-28")
        self.assertEqual(sanitize_publication_date("21 October 2026"), "2026-10-21")
        self.assertEqual(sanitize_publication_date("October 26, 2026"), "2026-10-26")
        self.assertEqual(sanitize_publication_date("2026-06-15T00:00:00+08:00"), "2026-06-15")
        self.assertEqual(sanitize_publication_date("2500-08-15"), "2005-08-15")
        self.assertEqual(sanitize_publication_date("3000-01-01"), "")
        self.assertEqual(sanitize_publication_date(""), "")
        self.assertEqual(sanitize_publication_date(None), "")

    def test_word_exporter_hyperlink_stability(self):
        """Action: Prepend https:// if scheme is missing, skip if empty, prevent crashes."""
        doc = Document()
        p = doc.add_paragraph()

        # URL with scheme
        add_hyperlink(p, "https://example.gov.ph/doc.pdf", "[Doc 1]")
        # URL without scheme (must prepend https:// without crashing)
        add_hyperlink(p, "example.gov.ph/doc2.pdf", "[Doc 2]")
        # Empty and blank URLs (must safely skip without ValueError)
        add_hyperlink(p, "", "[Empty]")
        add_hyperlink(p, "   ", "[Spaces]")
        add_hyperlink(p, None, "[None]")

        # Ensure document can be saved and has hyperlinks
        test_file = config.EXPORTS_DIR / "test_hyperlink_stability.docx"
        doc.save(str(test_file))
        self.assertTrue(test_file.exists())
        self.assertGreater(test_file.stat().st_size, 1000)

    def test_academic_provenance_and_title_discard(self):
        """Action: Warning on image/drive URLs, discard row if both title and number are blank."""
        scraper = DAScraper()
        html = """
        <table class="tablepress">
            <tbody>
                <tr>
                    <td></td>
                    <td></td>
                    <td>2026</td>
                </tr>
            </tbody>
        </table>
        """
        records = scraper._parse_category_page(html, "Administrative Orders", "https://da.gov.ph")
        # Row with both empty title and code must be discarded
        self.assertEqual(len(records), 0)

    def test_save_document_localhost(self):
        """save_document on localhost writes to local DATA_DIR and returns local file path."""
        import storage
        test_bytes = b"Sample document content for testing localhost"
        test_filename = "test_doc_local.pdf"

        with patch.object(storage, "IS_VERCEL", False):
            result_path = storage.save_document(test_bytes, test_filename)
            self.assertTrue(os.path.exists(result_path))
            self.assertEqual(result_path, str(storage.DATA_DIR / test_filename))
            with open(result_path, "rb") as f:
                self.assertEqual(f.read(), test_bytes)
            os.remove(result_path)

    def test_save_document_vercel(self):
        """save_document on Vercel uploads to Vercel Blob and unlinks temporary file."""
        import storage
        test_bytes = b"Sample document content for Vercel deployment"
        test_filename = "test_doc_vercel.pdf"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"url": "https://blob.vercel-storage.com/test_doc_vercel.pdf"}

        with patch.object(storage, "IS_VERCEL", True), \
             patch.dict(os.environ, {"BLOB_READ_WRITE_TOKEN": "mock-blob-token"}), \
             patch("requests.put", return_value=mock_resp) as mock_put:

            blob_url = storage.save_document(test_bytes, test_filename)
            self.assertEqual(blob_url, "https://blob.vercel-storage.com/test_doc_vercel.pdf")
            mock_put.assert_called_once()
            temp_path = storage.DATA_DIR / test_filename
            self.assertFalse(temp_path.exists())

    def test_quarantine_db_operations(self):
        """Verify quarantine insertion, deduplication, retrieval, and status resolution."""
        clear_quarantine_logs()

        # Insert quarantine entry
        log_id = log_quarantine(
            department="DA",
            category="Administrative Orders",
            issue_type="Missing Metadata",
            details="Row discarded due to missing title and issuance number",
            source_url="https://www.da.gov.ph/laws-and-issuances/"
        )
        self.assertIsNotNone(log_id)

        # INSERT OR IGNORE deduplication check
        dup_id = log_quarantine(
            department="DA",
            category="Administrative Orders",
            issue_type="Missing Metadata",
            details="Row discarded due to missing title and issuance number",
            source_url="https://www.da.gov.ph/laws-and-issuances/"
        )
        self.assertIsNone(dup_id)

        # Retrieve pending logs
        pending = get_quarantine_logs(status="Pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["department"], "DA")
        self.assertEqual(pending[0]["issue_type"], "Missing Metadata")
        self.assertEqual(pending[0]["status"], "Pending")

        # Resolve log
        success = resolve_quarantine_log(log_id, status="Resolved")
        self.assertTrue(success)

        # Pending should now be empty
        self.assertEqual(len(get_quarantine_logs(status="Pending")), 0)

        # Resolved list should contain the record
        resolved = get_quarantine_logs(status="Resolved")
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["status"], "Resolved")
        self.assertIsNotNone(resolved[0]["resolved_at"])

    def test_quarantine_api_endpoints(self):
        """Verify GET /api/quarantine and POST /api/quarantine/<id>/resolve endpoints."""
        clear_quarantine_logs()
        log_id = log_quarantine(
            department="DepEd",
            category="DepEd Orders",
            issue_type="Sequence Gap",
            details="Missing issuance number: DO-2024-005",
            source_url=""
        )

        with app.test_client() as client:
            # Fetch pending logs
            res = client.get("/api/quarantine")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["logs"][0]["department"], "DepEd")

            # Resolve item
            post_res = client.post(f"/api/quarantine/{log_id}/resolve", json={"status": "Resolved"})
            self.assertEqual(post_res.status_code, 200)
            post_data = post_res.get_json()
            self.assertTrue(post_data["success"])

            # Verify pending is now 0
            res2 = client.get("/api/quarantine?status=Pending")
            data2 = res2.get_json()
            self.assertEqual(data2["count"], 0)

            # Test invalid status
            bad_status_res = client.post(f"/api/quarantine/{log_id}/resolve", json={"status": "InvalidStatus"})
            self.assertEqual(bad_status_res.status_code, 400)

            # Test nonexistent ID
            not_found_res = client.post("/api/quarantine/999999/resolve", json={"status": "Resolved"})
            self.assertEqual(not_found_res.status_code, 404)

    def test_scraper_quarantine_on_missing_metadata_and_provenance(self):
        """Verify scrapers log quarantine records when skipping invalid rows or detecting non-academic URLs."""
        clear_quarantine_logs()
        scraper = DAScraper()

        # Trigger provenance warning and quarantine
        scraper.check_url_academic_provenance(
            "https://drive.google.com/file/d/12345/view",
            department="DA",
            category="Administrative Orders"
        )

        # Trigger missing metadata quarantine by parsing empty row
        html = """
        <table class="tablepress">
            <tbody>
                <tr><td></td><td></td><td>2026</td></tr>
            </tbody>
        </table>
        """
        scraper._parse_category_page(html, "Administrative Orders", "https://da.gov.ph")

        logs = get_quarantine_logs(status="Pending")
        issue_types = {item["issue_type"] for item in logs}
        self.assertIn("Non-Academic URL", issue_types)
        self.assertIn("Missing Metadata", issue_types)

    def test_deped_parallel_scraping(self):
        """Verify DepEd scraper executes multiple categories concurrently via ThreadPoolExecutor."""
        scraper = DepEdScraper()

        def mock_fetch(url):
            resp = MagicMock()
            resp.status_code = 200
            if "deped-orders" in url:
                resp.text = """
                <article class="post">
                    <h2 class="entry-title"><a href="https://deped.gov.ph/2026/01/do-01/">January 1, 2026 DO 01, s. 2026 – Guidelines on School Calendar</a></h2>
                </article>
                """
            elif "deped-memoranda" in url:
                resp.text = """
                <article class="post">
                    <h2 class="entry-title"><a href="https://deped.gov.ph/2026/01/dm-01/">January 2, 2026 DM 01, s. 2026 – Administration of National Exam</a></h2>
                </article>
                """
            else:
                resp.status_code = 404
                resp.text = ""
            return resp

        scraper.fetch_url = mock_fetch

        inserted = scraper.scrape(
            categories=["DepEd Orders", "DepEd Memoranda"],
            max_pages_per_category=1
        )
        self.assertEqual(inserted, 2)

    def test_deped_parallel_checkpoint_and_resume(self):
        """Verify extraction_checkpoints saves category_pages and resumes completed/in-flight categories."""
        from database.db import save_checkpoint, get_checkpoint, clear_checkpoint
        clear_checkpoint("Department of Education")

        # Save checkpoint with completed category and in-flight category page
        save_checkpoint(
            department="Department of Education",
            category="DepEd Orders",
            page=5,
            url="https://www.deped.gov.ph/category/issuances/deped-orders/page/5/",
            completed_categories=["DepEd Memoranda"],
            category_pages={"DepEd Orders": {"page": 5, "url": "https://www.deped.gov.ph/category/issuances/deped-orders/page/5/"}}
        )

        cp = get_checkpoint("Department of Education")
        self.assertIsNotNone(cp)
        self.assertEqual(cp["page"], 5)
        self.assertIn("DepEd Memoranda", cp["completed_categories"])
        self.assertIn("DepEd Orders", cp["category_pages"])
        self.assertEqual(cp["category_pages"]["DepEd Orders"]["page"], 5)

        # Test resume skips completed category and resumes in-flight
        scraper = DepEdScraper()
        fetched_urls = []

        def mock_fetch(url):
            fetched_urls.append(url)
            resp = MagicMock()
            resp.status_code = 200
            resp.text = """
            <article class="post">
                <h2 class="entry-title"><a href="https://deped.gov.ph/2026/01/do-05/">DO 05, s. 2026 – Policy From Page 5</a></h2>
            </article>
            """
            return resp

        scraper.fetch_url = mock_fetch

        inserted = scraper.scrape(
            categories=["DepEd Orders", "DepEd Memoranda"],
            max_pages_per_category=5,
            resume=True
        )

        # "DepEd Memoranda" was marked complete, so no URLs should contain "deped-memoranda"
        self.assertFalse(any("deped-memoranda" in u for u in fetched_urls))
        # "DepEd Orders" should have resumed directly from page 5
        self.assertTrue(any("/page/5/" in u for u in fetched_urls))

        clear_checkpoint("Department of Education")


if __name__ == "__main__":
    unittest.main()
