"""
pin_gateway.py
Lightweight, temporary in-memory PIN gateway for Flask.
Enforces a single global active session (one active user at a time)
without requiring any database.
"""

import os
import time
import uuid
import hmac
import threading
from functools import wraps
from typing import Optional, Set
from flask import (
    Blueprint,
    request,
    jsonify,
    make_response,
    redirect,
    url_for,
    render_template,
    Response,
)

COOKIE_NAME = "session_access_token"
RATE_LIMIT_ATTEMPTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

# 1. Environment-based PIN configuration
ACCESS_PIN: Optional[str] = os.environ.get("ACCESS_PIN")

# 2. In-Memory Single Global Session (Thread-Safe)
# Enforces "one active user at a time". Overwritten whenever a valid PIN is entered.
_active_session_token: Optional[str] = None
_session_lock = threading.Lock()

# 3. In-Memory Rate Limiting (Thread-Safe)
# Maps client IP -> list of attempt epoch timestamps.
_rate_limit_records: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()

pin_blueprint = Blueprint("pin_gateway", __name__)


def set_access_pin(pin: str) -> None:
    """Helper to dynamically set/override the ACCESS_PIN (useful for testing or runtime reload)."""
    global ACCESS_PIN
    ACCESS_PIN = str(pin).strip()


def get_active_session_token() -> Optional[str]:
    """Retrieve the current active session token in a thread-safe manner."""
    with _session_lock:
        return _active_session_token


def reset_gateway_state() -> None:
    """Reset active session and rate limit records (primarily for testing)."""
    global _active_session_token
    with _session_lock:
        _active_session_token = None
    with _rate_limit_lock:
        _rate_limit_records.clear()


def get_client_ip() -> str:
    """Extract client IP, honoring reverse-proxy headers (X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def is_rate_limited(ip: str, max_attempts: int = RATE_LIMIT_ATTEMPTS, window: int = RATE_LIMIT_WINDOW_SECONDS) -> bool:
    """Check if an IP has exceeded the allowed attempt threshold within the sliding time window."""
    now = time.time()
    with _rate_limit_lock:
        timestamps = [t for t in _rate_limit_records.get(ip, []) if now - t < window]
        if len(timestamps) >= max_attempts:
            _rate_limit_records[ip] = timestamps
            return True
        timestamps.append(now)
        _rate_limit_records[ip] = timestamps
        return False


def rate_limit(max_attempts: int = RATE_LIMIT_ATTEMPTS, window: int = RATE_LIMIT_WINDOW_SECONDS):
    """Decorator to apply IP-based rate limiting to sensitive routes."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = get_client_ip()
            if is_rate_limited(ip, max_attempts=max_attempts, window=window):
                return jsonify({
                    "error": "Too many attempts. Please wait 1 minute before trying again."
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


def is_session_valid(token: Optional[str]) -> bool:
    """Check if the provided token matches the single global active session token."""
    with _session_lock:
        if not token or not _active_session_token:
            return False
        return hmac.compare_digest(token, _active_session_token)


def require_pin_session(f):
    """
    Decorator for protected routes.
    If ACCESS_PIN is configured in the environment:
      Enforces that the caller's cookie matches the server's current activeSessionToken.
      If not valid, returns 401 Unauthorized to kick out the old session
      (or redirects to /login for browser HTML navigation).
    If ACCESS_PIN is not configured, bypasses authentication to allow unblocked dev/testing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_pin = ACCESS_PIN or os.environ.get("ACCESS_PIN")
        if not current_pin:
            return f(*args, **kwargs)

        cookie_token = request.cookies.get(COOKIE_NAME)
        if not is_session_valid(cookie_token):
            accept = request.headers.get("Accept", "")
            # Only redirect if this is an explicit browser page request (HTML only, non-API)
            if "text/html" in accept and "application/json" not in accept and not request.path.startswith("/api"):
                return redirect(url_for("pin_gateway.login_page"))

            return jsonify({
                "error": "Unauthorized: Session invalid or superseded by another user."
            }), 401
        return f(*args, **kwargs)
    return decorated_function


# ----------------- GATEWAY ROUTES & APPLICATION HOOK ----------------- #

@pin_blueprint.before_app_request
def enforce_global_pin_session():
    """
    Application-wide gateway hook.
    When ACCESS_PIN is set in the environment, protects all routes except:
      - Static assets (/static/...)
      - Gateway authentication endpoints (/login, /api/auth/...)
    """
    current_pin = ACCESS_PIN or os.environ.get("ACCESS_PIN")
    if not current_pin:
        return None  # Dev/testing pass-through when ACCESS_PIN is unset

    # Exempt static assets and authentication routes
    endpoint = request.endpoint or ""
    if endpoint == "static" or endpoint.startswith("pin_gateway."):
        return None
    if request.path.startswith("/static/") or request.path.startswith("/login") or request.path.startswith("/api/auth/"):
        return None

    cookie_token = request.cookies.get(COOKIE_NAME)
    if not is_session_valid(cookie_token):
        accept = request.headers.get("Accept", "")
        # Redirect browser page visits to the login UI
        if "text/html" in accept and "application/json" not in accept and not request.path.startswith("/api"):
            return redirect(url_for("pin_gateway.login_page"))

        return jsonify({
            "error": "Unauthorized: Session invalid or superseded by another user."
        }), 401

    return None


@pin_blueprint.route("/login", methods=["GET"])
def login_page():
    """Serves the frontend PIN entry component."""
    # If already logged in with the valid session token, redirect directly to dashboard
    cookie_token = request.cookies.get(COOKIE_NAME)
    if is_session_valid(cookie_token):
        return redirect("/")
    return render_template("pin_entry.html")


@pin_blueprint.route("/api/auth/pin", methods=["POST"])
@rate_limit(max_attempts=RATE_LIMIT_ATTEMPTS, window=RATE_LIMIT_WINDOW_SECONDS)
def verify_pin():
    """
    Authenticates the submitted PIN.
    On success:
      - Generates a random UUID.
      - Overwrites global _active_session_token (superseding any prior session).
      - Returns HttpOnly cookie.
    On failure:
      - Returns 401 Unauthorized with generic "Incorrect PIN" error.
    """
    global _active_session_token

    current_pin = ACCESS_PIN or os.environ.get("ACCESS_PIN")
    if not current_pin:
        return jsonify({"error": "Gateway misconfigured: ACCESS_PIN is unset."}), 500

    data = request.get_json(silent=True) or {}
    submitted_pin = str(data.get("pin", "")).strip()

    # Timing-safe comparison
    if not submitted_pin or not hmac.compare_digest(submitted_pin, current_pin):
        return jsonify({"error": "Incorrect PIN"}), 401

    # Overwrite the single global active session
    new_token = str(uuid.uuid4())
    with _session_lock:
        _active_session_token = new_token

    response = make_response(jsonify({
        "success": True,
        "message": "Authenticated successfully"
    }))

    # Send new token via HttpOnly cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=new_token,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/"
    )
    return response, 200


@pin_blueprint.route("/api/auth/logout", methods=["POST"])
def logout():
    """Invalidates the cookie and clears global session if owned by current user."""
    global _active_session_token
    cookie_token = request.cookies.get(COOKIE_NAME)

    with _session_lock:
        if cookie_token and _active_session_token and hmac.compare_digest(cookie_token, _active_session_token):
            _active_session_token = None

    response = make_response(jsonify({"success": True}))
    response.delete_cookie(COOKIE_NAME, path="/")
    return response, 200
