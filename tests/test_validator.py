import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import os
config.DATABASE_URI = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:root@localhost:5432/government_issuances_test"
)

from app import app
from database.db import init_db, save_issuance, delete_all_issuances
from database.models import IssuanceRecord
from database.validator import audit_sequence_gaps, run_full_validation


class TestValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = app.test_client()

    def setUp(self):
        delete_all_issuances()

    def test_audit_sequence_gaps(self):
        records = [
            IssuanceRecord(department="Department of Health", category="Administrative Orders", issuance_number="2026-0001", title="AO 1", publication_date="2026-01-01"),
            IssuanceRecord(department="Department of Health", category="Administrative Orders", issuance_number="2026-0002", title="AO 2", publication_date="2026-01-02"),
            IssuanceRecord(department="Department of Health", category="Administrative Orders", issuance_number="2026-0004", title="AO 4", publication_date="2026-01-04"),
        ]
        for r in records:
            save_issuance(r)

        gaps = audit_sequence_gaps(department="Department of Health")
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["year"], 2026)
        self.assertEqual(gaps[0]["missing_count"], 1)
        self.assertIn(3, gaps[0]["missing_samples"])

    def test_audit_sequence_gaps_skips_national_instruments(self):
        # National cross-cutting instruments (EOs, RAs, PDs) must not trigger false positive gaps
        records = [
            IssuanceRecord(department="Department of Environment and Natural Resources", category="Executive Orders", issuance_number="2026-0001", title="EO 1", publication_date="2026-01-01"),
            IssuanceRecord(department="Department of Environment and Natural Resources", category="Executive Orders", issuance_number="2026-0002", title="EO 2", publication_date="2026-01-02"),
            IssuanceRecord(department="Department of Environment and Natural Resources", category="Executive Orders", issuance_number="2026-0020", title="EO 20", publication_date="2026-01-20"),
            IssuanceRecord(department="Department of Agriculture", category="Republic Acts and Proclamations", issuance_number="2026-0001", title="RA 1", publication_date="2026-01-01"),
            IssuanceRecord(department="Department of Agriculture", category="Republic Acts and Proclamations", issuance_number="2026-0050", title="RA 50", publication_date="2026-01-10"),
        ]
        for r in records:
            save_issuance(r)

        gaps_denr = audit_sequence_gaps(department="Department of Environment and Natural Resources")
        self.assertEqual(len(gaps_denr), 0)

        gaps_da = audit_sequence_gaps(department="Department of Agriculture")
        self.assertEqual(len(gaps_da), 0)

    @patch("database.validator.audit_live_portal_sync")
    def test_run_full_validation(self, mock_portal_sync):
        mock_portal_sync.return_value = [{"department": "Department of Agriculture", "code": "DA", "portal_status": "Reachable", "categories": []}]
        r = IssuanceRecord(department="Department of Agriculture", category="Administrative Orders", issuance_number="AO 2026-01", title="DA AO 1", publication_date="2026-02-01", source_url="https://da.gov.ph/ao1")
        save_issuance(r)

        report = run_full_validation()
        self.assertIn("integrity_score", report)
        self.assertIn("quality_metrics", report)
        self.assertIn("portal_reconciliation", report)
        self.assertEqual(report["total_records"], 1)

    @patch("app.run_full_validation")
    def test_api_validate_endpoint(self, mock_full_validation):
        mock_full_validation.return_value = {
            "integrity_score": "100%",
            "total_records": 10,
            "quality_metrics": {},
            "portal_reconciliation": []
        }
        resp = self.client.get("/api/validate")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("report", data)

    @patch("app.backfill_missing_doh_records")
    def test_api_reconcile_endpoint(self, mock_backfill):
        mock_backfill.return_value = 5
        resp = self.client.post("/api/reconcile", json={"gap_samples": ["2026-0003"]})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["recovered_count"], 5)

    @patch("app.is_prod_env", return_value=True)
    def test_api_validate_disabled_on_prod(self, mock_is_prod):
        resp = self.client.get("/api/validate")
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("disabled in production", data["error"])

    @patch("app.is_prod_env", return_value=True)
    def test_api_reconcile_disabled_on_prod(self, mock_is_prod):
        resp = self.client.post("/api/reconcile", json={"gap_samples": ["2026-0003"]})
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("disabled in production", data["error"])

    @patch("scrapers.doh.DOHScraper._fetch_page")
    @patch("scrapers.doh.DOHScraper._ensure_session", return_value=True)
    def test_doh_search_missing_issuance(self, mock_session, mock_fetch):
        from scrapers.doh import DOHScraper
        scraper = DOHScraper()
        mock_fetch.return_value = ([{
            "documentId": 12345,
            "issuanceNumber": "132",
            "issuanceType": "Executive Order",
            "subject": "Authorizing Poro Point Mgt Corp",
            "documentDate": "2011-04-18T00:00:00+08:00"
        }], True)

        with patch.object(scraper.session, "post") as mock_post:
            mock_resp = unittest.mock.MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"success": True}
            mock_post.return_value = mock_resp

            records = scraper.search_missing_issuance("132", cat_name="Executive Orders")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].issuance_number, "132")
            self.assertEqual(records[0].category, "Executive Orders")

            # Check that SearchDocuments was called with issuanceNumber and issuanceType
            call_args = mock_post.call_args[1]
            data = call_args["data"]
            self.assertEqual(data["issuanceNumber"], "132")
            self.assertEqual(data["issuanceType"], "KMITS_AISEO")


if __name__ == "__main__":
    unittest.main()
