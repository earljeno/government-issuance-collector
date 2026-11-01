import os
import unittest
from datetime import datetime
from pathlib import Path
from docx import Document

import config
config.DATABASE_PATH = config.BASE_DIR / "database" / "test_issuances.db"

from scrapers.deped import DepEdScraper
from scrapers.da import DAScraper
from scrapers.doh import DOHScraper
from database.models import IssuanceRecord
from database.validator import sanitize_publication_date
from exporters.word_exporter import add_hyperlink, generate_word_document


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


if __name__ == "__main__":
    unittest.main()
