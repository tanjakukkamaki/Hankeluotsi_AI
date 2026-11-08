"""User-initiated official live sources; no project information enters requests."""

import csv
import gzip
import io
import re
import zlib
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener

from pydantic import ValidationError

from hankeluotsi.funding import _NoRedirect
from hankeluotsi.funding_calls import FundingCall, LiveSearchResult, parse_call_date


AURORA_CALLS_URL = "https://www.interregaurora.eu/projects/calls-for-applications-2/"
MAX_RESPONSE_BYTES = 1_000_000
MAX_CSV_ROWS = 200
REQUIRED_COLUMNS = {
    "Funding call title", "Funding call identifier", "Policy objective", "Specific objective",
    "Status", "Start date", "End date", "Geographical area covered by the call for proposal",
    "Type of eligible applicants", "Programme title", "Time of update",
}
SOURCE_FAILURE = "Live source unavailable or its response could not be verified. Use the official link and programme guidance."


def _valid_csv_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https" and parsed.netloc == "www.interregaurora.eu"
        and not parsed.query and not parsed.fragment
        and bool(re.fullmatch(r"/wp-content/uploads/Timetable-of-the-planned-calls-for-proposals-[A-Za-z0-9_-]+\.csv", parsed.path))
    )


class _TimetableLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                url = urljoin(AURORA_CALLS_URL, href)
                if _valid_csv_url(url):
                    self.links.add(url)


def _download_aurora(url: str) -> bytes:
    if url != AURORA_CALLS_URL and not _valid_csv_url(url):
        raise ValueError("Only the official Aurora calls page and its timetable CSV may be read.")
    request = Request(url, headers={"User-Agent": "HankeLuotsiAI/0.2 public funding research"})
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        expected = ("text/html",) if url == AURORA_CALLS_URL else ("text/csv", "text/plain", "application/csv")
        if response.headers.get_content_type() not in expected:
            raise ValueError("Unexpected official source content type")
        content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("Official response exceeds the size limit")
        encoding = response.headers.get("Content-Encoding", "identity").lower()
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                content = compressed.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("Decoded response exceeds the size limit")
        elif encoding not in ("", "identity"):
            raise ValueError("Unsupported official source encoding")
        return content


def parse_aurora_csv(content: bytes, evidence_url: str, *, retrieved_at: datetime) -> LiveSearchResult:
    if not _valid_csv_url(evidence_url):
        raise ValueError("Timetable provenance is not an official Aurora CSV")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=";", strict=True)
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Official CSV columns changed or are missing")
    calls = {}
    conflicting_ids = set()
    notices = []
    for row_number, row in enumerate(reader, start=1):
        if row_number > MAX_CSV_ROWS:
            notices.append("Interreg Aurora: timetable row limit reached; results are partial.")
            break
        if not any(row.values()):
            continue
        if None in row or any(value is None for value in row.values()):
            notices.append("Interreg Aurora: skipped a malformed timetable row.")
            continue
        row = {key: value.strip() for key, value in row.items()}
        if not row["Funding call title"] or not row["Funding call identifier"]:
            notices.append("Interreg Aurora: skipped a row without an official title/identifier.")
            continue
        opening = parse_call_date(row["Start date"])
        deadline = parse_call_date(row["End date"])
        uncertainty = [
            "Official timetable information may be indicative. Detailed call terms and priority restrictions prevail.",
            "Applicant categories and geographical coverage are source information, not an eligibility assessment.",
        ]
        if not opening or not deadline:
            uncertainty.append("An opening/deadline date is missing or invalid; verify the call page.")
        if any(item and isinstance(item.value, date) and not isinstance(item.value, datetime) for item in (opening, deadline)):
            uncertainty.append("Calendar dates have no verified deadline time or timezone.")
        try:
            updated = date.fromisoformat(row["Time of update"])
        except ValueError:
            updated = None
            uncertainty.append("Source update date is missing or invalid.")
        official_status = {"open": "open", "closed": "closed", "upcoming": "upcoming", "planned": "upcoming"}.get(row["Status"].casefold(), "unknown")
        try:
            call = FundingCall(
                source="Interreg Aurora", programme=row["Programme title"] or "Interreg Aurora",
                identifier=row["Funding call identifier"], title=row["Funding call title"],
                objectives="\n".join(value for value in (row["Policy objective"], row["Specific objective"]) if value) or None,
                geographic_area=row["Geographical area covered by the call for proposal"] or None,
                applicant_requirements=row["Type of eligible applicants"] or None,
                opening=opening, deadline=deadline, official_status=official_status,
                source_url=AURORA_CALLS_URL, evidence_url=evidence_url,
                retrieved_at=retrieved_at, source_updated_on=updated, uncertainties=tuple(uncertainty),
            )
        except ValidationError:
            notices.append("Interreg Aurora: skipped a record that failed structured validation.")
            continue
        if call.identifier in conflicting_ids:
            continue
        if call.identifier in calls:
            if calls[call.identifier] != call:
                conflicting_ids.add(call.identifier)
                del calls[call.identifier]
                notices.append("Interreg Aurora: omitted a conflicting duplicate call identifier.")
            continue
        calls[call.identifier] = call
    return LiveSearchResult(calls=tuple(calls.values()), notices=tuple(notices))


def fetch_aurora_calls() -> LiveSearchResult:
    try:
        parser = _TimetableLinks()
        parser.feed(_download_aurora(AURORA_CALLS_URL).decode("utf-8"))
        if len(parser.links) != 1:
            raise ValueError("A unique official timetable link could not be verified")
        evidence_url = next(iter(parser.links))
        content = _download_aurora(evidence_url)
        return parse_aurora_csv(content, evidence_url, retrieved_at=datetime.now(timezone.utc))
    except (URLError, OSError, HTTPException, ValueError, LookupError, EOFError, zlib.error, csv.Error, AssertionError):
        return LiveSearchResult(notices=("Interreg Aurora: " + SOURCE_FAILURE,))


def search_live_funding_calls() -> LiveSearchResult:
    # A fixed request for each supported source; there is no project argument.
    from hankeluotsi.funding_eu import fetch_horizon_calls

    results = (fetch_aurora_calls(), fetch_horizon_calls())
    return LiveSearchResult(
        calls=tuple(call for result in results for call in result.calls),
        notices=tuple(notice for result in results for notice in result.notices) + (
            "EURA 2021: live call retrieval is unavailable in this version; see the official calls link and general guidance.",
            "Business Finland: public pages were verified, but call-level parsing/pagination are not integrated; use the official source.",
        ),
    )
