import os
import unittest
from unittest.mock import patch
import config

config.DATABASE_URI = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:root@localhost:5432/government_issuances_test"
)

from app import app
from database.db import init_db, get_issuance_count

class TestAppEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        from database.db import save_issuance
        from database.models import IssuanceRecord
        save_issuance(IssuanceRecord(
            department="Department of Agriculture",
            category="Administrative Orders",
            issuance_number="AO No. 01",
            title="General Guidelines for Testing",
            publication_date="2026-01-01",
            source_url="https://da.gov.ph/ao1.pdf"
        ))

    def test_dashboard_get(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Philippine Government Issuance Title Collector", resp.data)
        self.assertIn(b"Department of Agriculture", resp.data)
        self.assertIn(b"Department of Health", resp.data)
        self.assertIn(b"Department of Environment and Natural Resources", resp.data)
        self.assertIn(b"Department of Education", resp.data)

    @patch("app.is_prod_env", return_value=True)
    def test_dashboard_get_prod_disabled_audit(self, mock_is_prod):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'id="btn-validate-records"', resp.data)
        self.assertIn(b'disabled', resp.data)
        self.assertIn(b'Audit &amp; Reconcile Data is disabled in production', resp.data)

    def test_api_status(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("departments", data)
        self.assertIn("total_records", data)
        self.assertIn("progress", data)
        self.assertIn("is_prod", data)

    @patch("app.is_prod_env", return_value=True)
    def test_api_status_prod(self, mock_is_prod):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("is_prod"))

    def test_api_records(self):
        resp = self.client.get("/api/records?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("records", data)
        self.assertIn("total_count", data)

    def test_export_word(self):
        resp = self.client.get("/api/export/word")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertGreater(len(resp.data), 1000)

    def test_export_excel(self):
        resp = self.client.get("/api/export/excel")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertGreater(len(resp.data), 1000)

    def test_export_csv(self):
        resp = self.client.get("/api/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/csv")
        self.assertGreater(len(resp.data), 50)

    def test_export_txt(self):
        resp = self.client.get("/api/export/txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/plain")
        self.assertGreater(len(resp.data), 50)

    def test_export_specific_department_csv(self):
        resp = self.client.get("/api/export/csv?department=Department+of+Agriculture")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/csv")
        content = resp.data.decode("utf-8-sig")
        self.assertIn("Department of Agriculture", content)
        self.assertIn("AO No. 01", content)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("DA_Issuances_", disposition)

    def test_export_specific_department_word(self):
        resp = self.client.get("/api/export/word?department=Department+of+Agriculture")
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("DA_Issuances_", disposition)
        self.assertGreater(len(resp.data), 1000)

    def test_export_specific_department_excel(self):
        resp = self.client.get("/api/export/excel?department=Department+of+Agriculture")
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("DA_Issuances_", disposition)
        self.assertGreater(len(resp.data), 1000)

    def test_export_specific_department_txt(self):
        resp = self.client.get("/api/export/txt?department=Department+of+Agriculture")
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")
        self.assertIn("DEPARTMENT OF AGRICULTURE", content)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("DA_Issuances_", disposition)

    def test_export_empty_department_returns_404(self):
        resp = self.client.get("/api/export/csv?department=NonExistentDepartment")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("No records found", data["message"])

    def test_checkpoint_and_resume_api(self):
        from database.db import save_checkpoint, get_checkpoint, clear_checkpoint
        save_checkpoint("Department of Education", "DepEd Advisories", 15, "https://deped.gov.ph/page/15/")
        
        # Test status returns checkpoint
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("checkpoints", data)
        self.assertIn("Department of Education", data["checkpoints"])
        self.assertEqual(data["checkpoints"]["Department of Education"]["page"], 15)

        # Test resume endpoint triggers worker with specific agency (mock thread to prevent live network calls)
        from unittest.mock import patch, MagicMock
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            res_resp = self.client.post("/api/resume", json={"department": "Department of Education"})
            self.assertEqual(res_resp.status_code, 200)
            self.assertTrue(res_resp.get_json()["success"])
            self.assertIn("Department of Education", res_resp.get_json()["message"])

            # Test resume endpoint with all
            res_all_resp = self.client.post("/api/resume", json={"department": "all"})
            self.assertIn(res_all_resp.status_code, [200, 400])

        clear_checkpoint("Department of Education")
        self.assertIsNone(get_checkpoint("Department of Education"))

    def test_backup_db_endpoint(self):
        resp = self.client.get("/api/backup-db")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Content-Type"), "application/json")
        data = resp.get_json()
        self.assertIn("issuances", data)
        self.assertIn("department_statuses", data)

if __name__ == "__main__":
    unittest.main()
