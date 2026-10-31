import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import config
# Use an isolated test database so production/user records are never wiped
config.DATABASE_PATH = config.BASE_DIR / "database" / "test_issuances.db"

from scrapers.da import DAScraper
from scrapers.deped import DepEdScraper
from scrapers.doh import DOHScraper
from scrapers.denr import DENRScraper
from scrapers.manual_url import ManualURLExtractor
from database.models import IssuanceRecord
from database.db import (
    init_db,
    save_issuance,
    save_issuances_batch,
    get_issuances,
    get_issuance_count,
    remove_duplicates_cleanup,
    delete_all_issuances
)
from exporters.word_exporter import generate_word_document
from exporters.excel_exporter import generate_excel_document
from exporters.csv_exporter import generate_csv_document, generate_txt_document

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

class TestScrapersAndApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import config
        # Use an isolated test database so production/user records are never wiped
        config.DATABASE_PATH = config.BASE_DIR / "database" / "test_issuances.db"
        init_db()

    def setUp(self):
        delete_all_issuances()

    def test_da_parsing(self):
        """Verify DA table parsing, code extraction, title extraction, and year filtering."""
        html_path = FIXTURES_DIR / "da_administrative_orders.html"
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        scraper = DAScraper()
        records = scraper._parse_category_page(html, "Administrative Orders", "https://www.da.gov.ph/laws-and-issuances/administrative-orders/")

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].issuance_number, "AO No. 27")
        self.assertIn("Supplementary Guidelines", records[0].title)
        self.assertEqual(records[0].publication_date, "21 October 2026")
        self.assertEqual(records[0].source_url, "https://www.da.gov.ph/wp-content/uploads/2026/10/ao27_s2026.pdf")

        # Test year filtering (only 2025)
        filtered_2025 = scraper._parse_category_page(html, "Administrative Orders", "https://www.da.gov.ph/test", year_filter="2025")
        self.assertEqual(len(filtered_2025), 1)
        self.assertEqual(filtered_2025[0].issuance_number, "AO No. 20")

    def test_deped_parsing_and_pagination(self):
        """Verify DepEd article parsing, metadata extraction, older records (1996), and next page link."""
        html_p1 = (FIXTURES_DIR / "deped_memoranda_p1.html").read_text(encoding="utf-8")
        scraper = DepEdScraper()

        records_p1, next_url = scraper._parse_page(html_p1, "DepEd Memoranda", "https://www.deped.gov.ph/category/issuances/deped-memoranda/")
        self.assertEqual(len(records_p1), 2)
        self.assertEqual(records_p1[0].issuance_number, "DM 064, s. 2026")
        self.assertEqual(records_p1[0].publication_date, "October 26, 2026")
        self.assertIn("Anticipatory Action", records_p1[0].title)
        self.assertEqual(next_url, "https://www.deped.gov.ph/category/issuances/deped-memoranda/page/2/")

        # Test older page (1996 record)
        html_p2 = (FIXTURES_DIR / "deped_memoranda_p2.html").read_text(encoding="utf-8")
        records_p2, next_url_p2 = scraper._parse_page(html_p2, "DepEd Memoranda", "https://www.deped.gov.ph/category/issuances/deped-memoranda/page/2/")
        self.assertEqual(len(records_p2), 1)
        self.assertEqual(records_p2[0].issuance_number, "DM 120, s. 1996")
        self.assertEqual(records_p2[0].publication_date, "May 10, 1996")
        self.assertIn("Reorganization of Division Field Offices", records_p2[0].title)
        self.assertIsNone(next_url_p2)

    def test_deped_last_page_no_backward_loop(self):
        html = '<nav id="nav-below"><div class="nav-next"><a href="https://www.deped.gov.ph/category/issuances/deped-advisories/page/453/">Newer posts</a></div></nav><article class="post"><h2><a href="#">DA 01</a></h2></article>'
        scraper = DepEdScraper()
        records, next_url = scraper._parse_page(html, "DepEd Advisories", "https://www.deped.gov.ph/category/issuances/deped-advisories/page/454/")
        self.assertEqual(len(records), 1)
        self.assertIsNone(next_url)

    def test_doh_parsing(self):
        """Verify DOH table parsing from HTML fixture."""
        html = (FIXTURES_DIR / "doh_health_policies.html").read_text(encoding="utf-8")
        scraper = DOHScraper()
        records = scraper.parse_html_listing(html, "Administrative Orders", "https://doh.gov.ph/policies/")

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].issuance_number, "AO No. 2026-0015")
        self.assertEqual(records[0].title, "National Health Workforce Strategic Plan 2026-2030")
        self.assertEqual(records[0].publication_date, "September 12, 2026")
        self.assertEqual(records[0].source_url, "https://doh.gov.ph/policies/ao2026-0015.pdf")


    def test_doh_api_scrape_mocked(self):
        """Verify DOH scraper interacts correctly with API endpoints."""
        scraper = DOHScraper()

        def mock_post(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if 'SearchDocuments' in url:
                mock_resp.json.return_value = {'success': True, 'error': '', 'data': None}
            elif 'GetFirstPage' in url:
                mock_resp.json.return_value = {
                    'success': True,
                    'error': '',
                    'data': {
                        'items': [{
                            'documentId': 99999,
                            'issuanceNumber': 'AO-2026-TEST',
                            'issuanceType': 'Administrative Order',
                            'subject': 'Mock Policy Guideline',
                            'documentDate': '2026-06-15T00:00:00+08:00'
                        }],
                        'firstPage': True,
                        'lastPage': True
                    }
                }
            return mock_resp

        def mock_get(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        scraper.session.get = mock_get
        scraper.session.post = mock_post

        inserted = scraper.scrape(categories=['Administrative Orders'], max_pages_per_category=1)
        self.assertGreaterEqual(inserted, 1)

        records = get_issuances(department='Department of Health', limit=50)
        test_records = [r for r in records if r['issuance_number'] == 'AO-2026-TEST']
        self.assertEqual(len(test_records), 1)
        self.assertEqual(test_records[0]['title'], 'Mock Policy Guideline')
        self.assertEqual(test_records[0]['publication_date'], '2026-06-15')
        self.assertEqual(test_records[0]['source_url'], 'https://app.doh.gov.ph:1024/Rest/GetFile?id=99999')

    def test_denr_parsing(self):
        """Verify DENR table parsing from HTML fixture."""
        html = (FIXTURES_DIR / "denr_laws.html").read_text(encoding="utf-8")
        scraper = DENRScraper()
        records = scraper.parse_html_listing(html, "Administrative Orders", "https://denr.gov.ph/laws/")

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].issuance_number, "DAO 2026-08")
        self.assertEqual(records[0].title, "Revised Guidelines on Watershed Management and Forest Protection")
        self.assertEqual(records[0].publication_date, "July 18, 2026")

    def test_manual_url_extractor(self):
        """Verify manual URL / HTML analyzer and extraction preview."""
        html = (FIXTURES_DIR / "da_administrative_orders.html").read_text(encoding="utf-8")
        extractor = ManualURLExtractor()
        res = extractor.analyze_and_extract(
            html_content=html,
            department_name="Department of Agriculture",
            category_name="Administrative Orders"
        )
        self.assertTrue(res["success"])
        self.assertIn("Table", res["structure"])
        self.assertEqual(res["total_found"], 3)
        self.assertEqual(res["records"][0]["issuance_number"], "AO No. 27")

    def test_database_duplicates_and_scrubbing(self):
        """Verify duplicate prevention and duplicate cleanup."""
        rec1 = IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 1",
            title="General Guidelines",
            publication_date="2026-01-01",
            source_url="https://da.gov.ph/ao1.pdf"
        )
        rec2 = IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 1",
            title="General Guidelines",
            publication_date="2026-01-01",
            source_url="https://da.gov.ph/ao1.pdf"
        )
        rec3 = IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 2",
            title="Specific Guidelines",
            publication_date="2026-01-02",
            source_url="https://da.gov.ph/ao2.pdf"
        )

        saved1 = save_issuance(rec1)
        self.assertTrue(saved1)

        # Second identical record must be rejected as duplicate
        saved2 = save_issuance(rec2)
        self.assertFalse(saved2)

        # Batch save with a duplicate and a new record
        ins, dups = save_issuances_batch([rec2, rec3])
        self.assertEqual(ins, 1)
        self.assertEqual(dups, 1)

        total = get_issuance_count()
        self.assertEqual(total, 2)

    def test_exporters(self):
        """Verify Microsoft Word, Excel, CSV, and TXT exports."""
        records = [
            {
                "id": 1,
                "department": "Department of Agriculture",
                "category": "Administrative Orders",
                "issuance_number": "AO No. 27",
                "title": "Supplementary Guidelines for Officers",
                "publication_date": "October 21, 2026",
                "source_url": "https://www.da.gov.ph/wp-content/uploads/2026/10/ao27.pdf",
                "extraction_timestamp": "2026-10-30 18:00:00"
            },
            {
                "id": 2,
                "department": "Department of Education",
                "category": "DepEd Memoranda",
                "issuance_number": "DM 064, s. 2026",
                "title": "Anticipatory Action for Super El Niño",
                "publication_date": "October 26, 2026",
                "source_url": "https://www.deped.gov.ph/2026/10/26/dm-064/",
                "extraction_timestamp": "2026-10-30 18:00:00"
            }
        ]

        # Word Document
        docx_path = generate_word_document(records, "test_output.docx")
        self.assertTrue(os.path.exists(docx_path))
        self.assertGreater(os.path.getsize(docx_path), 5000)

        # Excel Document
        xlsx_path = generate_excel_document(records, "test_output.xlsx")
        self.assertTrue(os.path.exists(xlsx_path))
        self.assertGreater(os.path.getsize(xlsx_path), 4000)

        # CSV Document
        csv_path = generate_csv_document(records, "test_output.csv")
        self.assertTrue(os.path.exists(csv_path))
        self.assertGreater(os.path.getsize(csv_path), 100)

        # TXT Document
        txt_path = generate_txt_document(records, "test_output.txt")
        self.assertTrue(os.path.exists(txt_path))
        self.assertGreater(os.path.getsize(txt_path), 100)

if __name__ == "__main__":
    unittest.main()
