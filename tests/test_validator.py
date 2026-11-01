import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import os
config.DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or config.DATABASE_URI.replace(
    "/government_issuances", "/government_issuances_test"
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


if __name__ == "__main__":
    unittest.main()
