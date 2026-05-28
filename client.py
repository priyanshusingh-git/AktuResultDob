from __future__ import annotations

from bs4 import BeautifulSoup, SoupStrainer
import requests
import urllib3

from .models import SessionBootstrapError, StudentResult, StudentScrapeError
from .parser import extract_identity_markers, has_result_markers, parse_result_payload


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ONEVIEW_URL = "https://oneview.aktu.ac.in/WebPages/aktu/OneView.aspx"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Origin": "https://oneview.aktu.ac.in",
    "Referer": ONEVIEW_URL,
    "Upgrade-Insecure-Requests": "1",
}


class OneViewHttpClient:
    def __init__(self, logger, slot_id: int = 0):
        self.logger = logger
        self.slot_id = slot_id
        self.session_bootstraps = 0
        self.session = self._new_session()

    def _new_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = False
        session.headers.update(DEFAULT_HEADERS)
        return session

    def reset_session(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._new_session()

    @staticmethod
    def extract_hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
        fields = {}
        for field_name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
            field = soup.select_one(f"#{field_name}")
            fields[field_name] = field.get("value", "") if field else ""
        return fields

    @staticmethod
    def has_dob_form(html: str) -> bool:
        lowered = (html or "").lower()
        return 'id="txtdob"' in lowered and 'id="btnsearch"' in lowered

    @staticmethod
    def extract_message(soup: BeautifulSoup) -> str | None:
        for selector in ("#lblMessage", "#ctl00_ContentPlaceHolder1_lblMessage"):
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(" ", strip=True)
        return None

    def scrape_student(self, roll_no: str, dob: str, semesters: list[int]) -> StudentResult:
        last_error: StudentScrapeError | None = None
        for _ in range(2):
            try:
                return self._scrape_student_once(roll_no, dob, semesters)
            except SessionBootstrapError as exc:
                last_error = exc
                self.logger.debug(f"Slot {self.slot_id + 1}: resetting HTTP session for {roll_no} after bootstrap failure: {exc.message}")
                self.reset_session()

        if last_error is not None:
            raise last_error
        raise SessionBootstrapError("Failed to establish HTTP session")

    def _scrape_student_once(self, roll_no: str, dob: str, semesters: list[int]) -> StudentResult:
        entry_soup = self._load_entry_page()
        proceed_soup = self._submit_roll_number(entry_soup, roll_no)
        result_html = self._submit_dob(proceed_soup, roll_no, dob)
        payload = parse_result_payload(result_html, roll_no, dob, semesters)
        if not payload["Semesters"]:
            raise StudentScrapeError("Requested semesters not found", permanent=True)
        return payload

    def _load_entry_page(self) -> BeautifulSoup:
        self.session_bootstraps += 1
        response = self.session.get(ONEVIEW_URL, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        fields = self.extract_hidden_fields(soup)
        if not fields["__VIEWSTATE"]:
            raise SessionBootstrapError("Entry page did not provide ASP.NET hidden fields")
        if "ASP.NET_SessionId" not in self.session.cookies:
            raise SessionBootstrapError("Entry page did not establish ASP.NET session")
        return soup

    def _submit_roll_number(self, soup: BeautifulSoup, roll_no: str) -> BeautifulSoup:
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            **self.extract_hidden_fields(soup),
            "txtRollNo": str(roll_no).strip(),
            "btnProceed": "आगे बढ़े",
        }
        response = self.session.post(ONEVIEW_URL, data=payload, timeout=20)
        response.raise_for_status()
        next_soup = BeautifulSoup(response.text, "html.parser")
        if self.has_dob_form(response.text):
            return next_soup

        message = self.extract_message(next_soup)
        if message:
            raise StudentScrapeError(message, permanent=self._is_permanent_failure(message))

        raise SessionBootstrapError("Proceed step did not reach DOB form")

    def _submit_dob(self, soup: BeautifulSoup, roll_no: str, dob: str) -> str:
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            **self.extract_hidden_fields(soup),
            "txtRollNo": str(roll_no).strip(),
            "txtDOB": dob,
            "btnSearch": "Search",
        }
        response = self.session.post(ONEVIEW_URL, data=payload, timeout=25)
        response.raise_for_status()
        result_soup = BeautifulSoup(response.text, "html.parser", parse_only=SoupStrainer(["span", "table"]))
        if has_result_markers(result_soup):
            return response.text

        message = self.extract_message(result_soup)
        if message:
            raise StudentScrapeError(message, permanent=self._is_permanent_failure(message))

        lowered = response.text.lower()
        if "no result" in lowered:
            raise StudentScrapeError("No Result Found (HTTP)", permanent=True)
        if extract_identity_markers(result_soup):
            return response.text
        raise SessionBootstrapError("Search step did not return a parseable result page")

    @staticmethod
    def _is_permanent_failure(message: str | None) -> bool:
        lowered = (message or "").lower()
        permanent_markers = (
            "invalid",
            "no result",
            "requested semesters not found",
            "record not found",
        )
        return any(marker in lowered for marker in permanent_markers)
