import unittest
import os
import time
from flask import Flask, jsonify
from pin_gateway import (
    pin_blueprint,
    require_pin_session,
    set_access_pin,
    reset_gateway_state,
    get_active_session_token,
    COOKIE_NAME,
)

class TestPinGateway(unittest.TestCase):
    def setUp(self):
        reset_gateway_state()
        self.test_pin = "849201"
        set_access_pin(self.test_pin)

        self.app = Flask(__name__, template_folder="../templates")
        self.app.config["TESTING"] = True
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(pin_blueprint)

        @self.app.route("/protected-api")
        @require_pin_session
        def protected_api():
            return jsonify({"status": "ok", "message": "classified data"})

        @self.app.route("/protected-page")
        @require_pin_session
        def protected_page():
            return "<h1>Dashboard</h1>"

        @self.app.route("/undecorated-route")
        def undecorated_route():
            return jsonify({"status": "open"})

        self.client = self.app.test_client()

    def tearDown(self):
        reset_gateway_state()
        set_access_pin(None)

    def test_incorrect_pin_returns_401(self):
        response = self.client.post("/api/auth/pin", json={"pin": "000000"})
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data.get("error"), "Incorrect PIN")
        self.assertIsNone(get_active_session_token())

    def test_correct_pin_sets_cookie_and_token(self):
        response = self.client.post("/api/auth/pin", json={"pin": self.test_pin})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

        active_token = get_active_session_token()
        self.assertIsNotNone(active_token)

        # Check cookie
        cookie = response.headers.get("Set-Cookie")
        self.assertIn(COOKIE_NAME, cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn(active_token, cookie)

    def test_protected_route_unauthorized_without_cookie(self):
        # Default request returns 401
        response = self.client.get("/protected-api")
        self.assertEqual(response.status_code, 401)

        # Web page with HTML Accept header redirects to login
        page_response = self.client.get("/protected-page", headers={"Accept": "text/html"})
        self.assertEqual(page_response.status_code, 302)
        self.assertIn("/login", page_response.headers.get("Location"))

    def test_single_global_session_enforcement(self):
        """
        Enforce 'one active user at a time':
        When User B logs in, User A's session is superseded and receives 401.
        """
        # User A logs in
        client_a = self.app.test_client()
        res_a = client_a.post("/api/auth/pin", json={"pin": self.test_pin})
        self.assertEqual(res_a.status_code, 200)

        # User A accesses protected API successfully
        res_protected_a1 = client_a.get("/protected-api")
        self.assertEqual(res_protected_a1.status_code, 200)

        # User B logs in from another client
        client_b = self.app.test_client()
        res_b = client_b.post("/api/auth/pin", json={"pin": self.test_pin})
        self.assertEqual(res_b.status_code, 200)

        # User B is now the active user
        res_protected_b = client_b.get("/protected-api")
        self.assertEqual(res_protected_b.status_code, 200)

        # User A is kicked out (401 Unauthorized)
        res_protected_a2 = client_a.get("/protected-api")
        self.assertEqual(res_protected_a2.status_code, 401)

    def test_rate_limiting_enforcement(self):
        """Ensure IP is rate-limited after 10 attempts in 60s."""
        ip = "192.168.1.100"
        for i in range(10):
            res = self.client.post(
                "/api/auth/pin",
                json={"pin": "wrong"},
                environ_base={"REMOTE_ADDR": ip}
            )
            self.assertEqual(res.status_code, 401)

        # 11th attempt must trigger 429 Too Many Requests
        res_11 = self.client.post(
            "/api/auth/pin",
            json={"pin": "wrong"},
            environ_base={"REMOTE_ADDR": ip}
        )
        self.assertEqual(res_11.status_code, 429)
        self.assertIn("Too many attempts", res_11.get_json()["error"])

        # Different IP is not affected
        res_diff_ip = self.client.post(
            "/api/auth/pin",
            json={"pin": "wrong"},
            environ_base={"REMOTE_ADDR": "192.168.1.200"}
        )
        self.assertEqual(res_diff_ip.status_code, 401)

    def test_application_wide_protection_when_pin_configured(self):
        # Without session, undecorated route is also protected
        resp = self.client.get("/undecorated-route")
        self.assertEqual(resp.status_code, 401)

        # After login, undecorated route works
        self.client.post("/api/auth/pin", json={"pin": self.test_pin})
        resp_authed = self.client.get("/undecorated-route")
        self.assertEqual(resp_authed.status_code, 200)

    def test_static_and_login_exemptions(self):
        # /login is accessible without authentication
        login_resp = self.client.get("/login")
        self.assertEqual(login_resp.status_code, 200)

    def test_legal_routes_exempt_and_accessible_without_auth(self):
        # /terms is accessible without authentication
        terms_resp = self.client.get("/terms")
        self.assertEqual(terms_resp.status_code, 200)
        self.assertIn(b"Terms of Service", terms_resp.data)

        # /privacy is accessible without authentication
        privacy_resp = self.client.get("/privacy")
        self.assertEqual(privacy_resp.status_code, 200)
        self.assertIn(b"Privacy Policy", privacy_resp.data)

        # /legal redirects to /terms
        legal_resp = self.client.get("/legal")
        self.assertEqual(legal_resp.status_code, 302)
        self.assertIn("/terms", legal_resp.headers.get("Location"))

    def test_pin_verification_requires_terms_acceptance(self):
        # Attempting to submit with terms_agreed=False returns 400
        res_disagreed = self.client.post("/api/auth/pin", json={
            "pin": self.test_pin,
            "terms_agreed": False
        })
        self.assertEqual(res_disagreed.status_code, 400)
        data = res_disagreed.get_json()
        self.assertIn("agree to the Terms of Service and Privacy Policy", data.get("error", ""))
        self.assertIsNone(get_active_session_token())

        # Submitting with terms_agreed=True succeeds
        res_agreed = self.client.post("/api/auth/pin", json={
            "pin": self.test_pin,
            "terms_agreed": True
        })
        self.assertEqual(res_agreed.status_code, 200)
        self.assertTrue(res_agreed.get_json().get("success"))
        self.assertIsNotNone(get_active_session_token())

    def test_logout(self):
        self.client.post("/api/auth/pin", json={"pin": self.test_pin})
        self.assertIsNotNone(get_active_session_token())

        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        self.assertIsNone(get_active_session_token())

        protected_res = self.client.get("/protected-api")
        self.assertEqual(protected_res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
