import time
import requests
import urllib3
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable
from threading import Event

from config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT_SECONDS, REQUEST_DELAY_SECONDS, MAX_RETRIES
from database.models import IssuanceRecord
from database.db import save_issuances_batch, update_department_status, record_failed_page

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, department_name: str, department_code: str):
        self.department_name = department_name
        self.department_code = department_code
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive"
        })

    def fetch_url(self, url: str, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """Fetches a URL with retries, timeout, and polite delays."""
        for attempt in range(1, retries + 1):
            try:
                time.sleep(REQUEST_DELAY_SECONDS)
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code in [403, 429, 503]:
                    logger.warning(f"[{self.department_code}] Received HTTP {resp.status_code} for {url} (attempt {attempt}/{retries})")
                    if attempt == retries:
                        return resp
                else:
                    logger.warning(f"[{self.department_code}] HTTP {resp.status_code} for {url}")
            except Exception as e:
                logger.error(f"[{self.department_code}] Attempt {attempt}/{retries} error fetching {url}: {e}")
                if attempt == retries:
                    return None
            time.sleep(attempt * 1.5)
        return None

    def save_records(self, records: List[IssuanceRecord]) -> (int, int):
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
        message: Optional[str] = None
    ):
        """Notifies UI and updates department_status in database."""
        update_department_status(
            department=self.department_name,
            status=status,
            current_category=category,
            current_page=current_page,
            total_pages=total_pages,
            error_message=message
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
                "message": message or ""
            })

    def log_failed_page(self, category: str, url: str, error_message: str):
        record_failed_page(self.department_name, category, url, error_message)

    @abstractmethod
    def scrape(
        self,
        categories: Optional[List[str]] = None,
        year: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[Event] = None
    ) -> int:
        """
        Executes extraction for the department.
        Returns total newly inserted records count.
        """
        pass
