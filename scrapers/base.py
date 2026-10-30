import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Event
from typing import Callable, List, Optional

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import (
    DEFAULT_USER_AGENT,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from database.db import (
    record_failed_page,
    save_issuances_batch,
    update_department_status,
)
from database.models import IssuanceRecord

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Shared HTTP and persistence behavior for department scrapers."""

    RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
    MAX_BACKOFF_SECONDS = 60

    def __init__(self, department_name: str, department_code: str):
        self.department_name = department_name
        self.department_code = department_code
        self.session = requests.Session()
        # Keep TLS certificate verification enabled.
        self.session.verify = True
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> Optional[float]:
        """Parse Retry-After as seconds or an HTTP date."""
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def fetch_url(
        self,
        url: str,
        retries: int = MAX_RETRIES,
    ) -> Optional[requests.Response]:
        """
        Fetch an authorized public page with bounded retries.

        403 is treated as an access-policy decision and is never retried.
        429/5xx and transient network errors use capped exponential backoff.
        """
        retries = max(1, retries)

        for attempt in range(1, retries + 1):
            if REQUEST_DELAY_SECONDS > 0:
                time.sleep(REQUEST_DELAY_SECONDS)

            try:
                response = self.session.get(
                    url,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    allow_redirects=True,
                )

                if response.status_code == 200:
                    return response

                if response.status_code == 403:
                    logger.error(
                        "[%s] HTTP 403 for %s. Access denied; stopping without "
                        "attempting to bypass the site's protection.",
                        self.department_code,
                        url,
                    )
                    return response

                if response.status_code not in self.RETRYABLE_STATUSES:
                    logger.warning(
                        "[%s] Non-retryable HTTP %s for %s",
                        self.department_code,
                        response.status_code,
                        url,
                    )
                    return response

                if attempt == retries:
                    logger.error(
                        "[%s] HTTP %s for %s after %s attempt(s); giving up.",
                        self.department_code,
                        response.status_code,
                        url,
                        retries,
                    )
                    return response

                retry_after = self._retry_after_seconds(response)
                backoff = min(2 ** (attempt - 1), self.MAX_BACKOFF_SECONDS)
                delay = min(
                    self.MAX_BACKOFF_SECONDS,
                    retry_after if retry_after is not None else backoff,
                )
                logger.warning(
                    "[%s] HTTP %s for %s (attempt %s/%s); retrying in %.1fs.",
                    self.department_code,
                    response.status_code,
                    url,
                    attempt,
                    retries,
                    delay,
                )
                time.sleep(delay)

            except requests.exceptions.RequestException as exc:
                if attempt == retries:
                    logger.exception(
                        "[%s] Request failed for %s after %s attempt(s): %s",
                        self.department_code,
                        url,
                        retries,
                        exc,
                    )
                    return None

                delay = min(2 ** (attempt - 1), self.MAX_BACKOFF_SECONDS)
                logger.warning(
                    "[%s] Network error for %s (attempt %s/%s): %s; "
                    "retrying in %.1fs.",
                    self.department_code,
                    url,
                    attempt,
                    retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

        return None

    @staticmethod
    def is_access_challenge(html: str) -> bool:
        """Identify common access-challenge pages; do not attempt to solve them."""
        sample = html[:50000].lower()
        return any(marker in sample for marker in (
            "just a moment...",
            "cf-chl-",
            "challenge-platform",
            "verify you are human",
            "attention required! | cloudflare",
        ))

    def fetch_rendered_html(self, url: str) -> Optional[str]:
        """
        Render a publicly accessible, JavaScript-dependent page with Chromium.

        This is a rendering fallback, not an access-control bypass: it does not
        spoof fingerprints, rotate proxies, reuse challenge tokens, or solve
        CAPTCHAs. If a challenge page appears, it stops and returns None.
        Call only after the ordinary HTTP request has returned status 200.
        """
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                    )
                    if response is not None and response.status in (403, 429, 503):
                        logger.warning(
                            "[%s] Browser render received HTTP %s for %s; stopping.",
                            self.department_code,
                            response.status,
                            url,
                        )
                        return None

                    try:
                        page.wait_for_load_state(
                            "networkidle",
                            timeout=min(5000, REQUEST_TIMEOUT_SECONDS * 1000),
                        )
                    except PlaywrightTimeoutError:
                        # Some public pages keep analytics or long polling open.
                        pass

                    html = page.content()
                    if self.is_access_challenge(html):
                        logger.warning(
                            "[%s] Browser render reached an access challenge at %s; "
                            "no challenge-solving or bypass will be attempted.",
                            self.department_code,
                            url,
                        )
                        return None
                    return html
                finally:
                    browser.close()
        except Exception:
            logger.exception(
                "[%s] Playwright rendering failed for %s",
                self.department_code,
                url,
            )
            return None

    def save_records(self, records: List[IssuanceRecord]) -> tuple[int, int]:
        """Batch saves extracted records to the SQLite database."""
        if not records:
            return 0, 0
        return save_issuances_batch(records)

    def report_progress(
        self,
        progress_callback: Optional[Callable],
        category: str,
        current_page: int,
        total_pages: str,
        records_collected: int,
        status: str,
        message: Optional[str] = None,
    ):
        """Notifies UI and updates department_status in database."""
        update_department_status(
            department=self.department_name,
            status=status,
            current_category=category,
            current_page=current_page,
            total_pages=total_pages,
            error_message=message,
        )
        if progress_callback:
            progress_callback({
                "department": self.department_name,
                "code": self.department_code,
                "category": category,
                "current_page": current_page,
                "total_pages": total_pages,
                "records_collected": records_collected,
                "status": status,
                "message": message or "",
            })

    def log_failed_page(self, category: str, url: str, error_message: str):
        record_failed_page(self.department_name, category, url, error_message)

    @abstractmethod
    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None,
    ) -> int:
        """Execute extraction for the department and return newly inserted count."""
        raise NotImplementedError
