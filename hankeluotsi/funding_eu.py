"""Bounded read-only access to the documented EU Portal public search API.

Requests use fixed Horizon Europe/open-topic filters. No project input is accepted
or transmitted. Returned metadata must independently satisfy those filters.
"""

import gzip
import json
import re
import ssl
import zlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from io import BytesIO
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from hankeluotsi.funding_calls import FundingCall, LiveSearchResult, parse_call_date


API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***"
PAGE_SIZE = 10
MAX_PAGES = 2
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 10
_BOUNDARY = "HankeLuotsiFundingSearchBoundary"
_QUERY = {"bool": {"must": [
    {"terms": {"type": ["1"]}},
    {"terms": {"status": ["31094502"]}},
    {"terms": {"frameworkProgramme": ["43108390"]}},
]}}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("The official API redirected; automatic redirects are disabled.")


def _page_url(page: int) -> str:
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("Requested API page is outside the bounded search window.")
    return f"{API_URL}&pageSize={PAGE_SIZE}&pageNumber={page}"


def _request_body() -> bytes:
    # This API requires JSON file parts; ordinary URL-encoded form fields are
    # silently ignored. The fixed values contain no user or project information.
    parts = []
    for name, value in (("query", _QUERY), ("languages", ["en"])):
        parts.append(
            f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{name}.json"\r\nContent-Type: application/json\r\n\r\n'
            f"{json.dumps(value, separators=(',', ':'))}\r\n"
        )
    return ("".join(parts) + f"--{_BOUNDARY}--\r\n").encode("utf-8")


def _tls_context() -> ssl.SSLContext:
    # certifi is already supplied by the existing OpenAI/httpx installation.
    # Preserve certificate verification; use system trust if it is unavailable.
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_api_page(page: int) -> dict:
    request = Request(_page_url(page), data=_request_body(), headers={
        "User-Agent": "HankeLuotsiAI/0.1 (public funding research)",
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
    })
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=_tls_context()))
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.headers.get_content_type() != "application/json":
            raise ValueError("The API did not return JSON.")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("The API response exceeds the size limit.")
        encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=BytesIO(payload)) as compressed:
                    payload = compressed.read(MAX_RESPONSE_BYTES + 1)
            except (EOFError, zlib.error) as error:
                raise ValueError("The API returned invalid compressed JSON.") from error
            if len(payload) > MAX_RESPONSE_BYTES:
                raise ValueError("The decoded API response exceeds the size limit.")
        elif encoding not in ("", "identity"):
            raise ValueError("The API uses an unsupported content encoding.")
        return json.loads(payload.decode("utf-8"))


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _one(metadata: dict, name: str) -> str:
    values = metadata.get(name)
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or not values[0].strip():
        raise ValueError(f"Missing or ambiguous {name} metadata.")
    return values[0].strip()


def _excerpt(metadata: dict, field: str, label: str, limit: int, uncertainties: list[str]) -> str | None:
    try:
        raw = _one(metadata, field)
    except ValueError:
        uncertainties.append(f"{label} were not available as one verified API field.")
        return None
    parser = _PlainText()
    try:
        parser.feed(raw)
    except (ValueError, AssertionError):
        uncertainties.append(f"{label} could not be safely extracted from the source markup.")
        return None
    text = " ".join(" ".join(parser.parts).split())
    if not text:
        uncertainties.append(f"{label} were empty in the API response.")
        return None
    if len(text) > limit:
        uncertainties.append(f"{label} are a shortened excerpt; read the complete official topic page.")
        text = text[:limit] + "…"
    return text


def _date(metadata: dict, name: str, label: str, uncertainties: list[str]):
    try:
        raw = _one(metadata, name)
    except ValueError:
        uncertainties.append(f"{label} is missing or has multiple values; no stage or date was selected automatically.")
        return None
    parsed = parse_call_date(raw, midnight_is_date=True)
    if parsed is None:
        uncertainties.append(f"{label} could not be parsed with verified date/time precision.")
    elif not isinstance(parsed.value, datetime):
        uncertainties.append(f"{label} is date-only; the API midnight value does not verify a deadline time or timezone.")
    return parsed


def _parse_call(row: dict, *, page: int, retrieved_at: datetime) -> FundingCall:
    if not isinstance(row, dict) or not isinstance(row.get("metadata"), dict):
        raise ValueError("Topic metadata is missing.")
    metadata = row["metadata"]
    for field, expected in (
        ("DATASOURCE", "SEDIA"), ("type", "1"),
        ("frameworkProgramme", "43108390"), ("language", "en"), ("status", "31094502"),
    ):
        if _one(metadata, field) != expected:
            raise ValueError("Returned topic does not satisfy the requested official source filters.")
    if row.get("accessRestriction") is True:
        raise ValueError("Returned topic is marked access-restricted.")
    identifier = _one(metadata, "identifier")
    if not re.fullmatch(r"HORIZON-[A-Za-z0-9-]+", identifier, flags=re.IGNORECASE):
        raise ValueError("Returned topic identifier is not a Horizon Europe identifier.")
    source_url = row.get("url")
    if not isinstance(source_url, str):
        raise ValueError("The API did not provide an official topic URL.")
    parsed_url = urlsplit(source_url)
    expected_path = "/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/" + identifier
    if (
        parsed_url.scheme != "https" or parsed_url.hostname != "ec.europa.eu"
        or parsed_url.username or parsed_url.password or parsed_url.port not in (None, 443)
        or unquote(parsed_url.path).rstrip("/").casefold() != expected_path.casefold()
        or parsed_url.query or parsed_url.fragment
    ):
        raise ValueError("The returned official topic URL does not match its identifier.")
    uncertainties = [
        "Geographic eligibility was not extracted; verify countries and applicant conditions on the official topic page.",
        "API condition text is guidance for manual checking, not a confirmed eligibility assessment.",
    ]
    objectives = _excerpt(metadata, "descriptionByte", "Funding objectives", 1200, uncertainties)
    conditions = _excerpt(metadata, "topicConditions", "Applicant conditions", 1600, uncertainties)
    opening = _date(metadata, "startDate", "Opening date", uncertainties)
    deadline = _date(metadata, "deadlineDate", "Application deadline", uncertainties)
    try:
        call_identifier = _one(metadata, "callIdentifier")
    except ValueError:
        call_identifier = None
        uncertainties.append("Parent call identifier was unavailable or ambiguous.")
    return FundingCall(
        source="EU Funding & Tenders Portal", programme="Horizon Europe",
        identifier=identifier, title=_one(metadata, "title"), call_identifier=call_identifier,
        objectives=objectives, geographic_area=None, applicant_requirements=conditions,
        opening=opening, deadline=deadline, official_status="open", source_url=source_url,
        evidence_url=_page_url(page), retrieved_at=retrieved_at, uncertainties=tuple(uncertainties),
    )


def _validate_page(payload, page: int) -> tuple[list, int]:
    if not isinstance(payload, dict):
        raise ValueError("The API response is not an object.")
    for key in ("pageNumber", "pageSize", "totalResults"):
        if type(payload.get(key)) is not int:
            raise ValueError(f"The API response lacks valid {key} metadata.")
    rows = payload.get("results")
    total = payload["totalResults"]
    expected_count = min(PAGE_SIZE, max(0, total - (page - 1) * PAGE_SIZE))
    if (
        payload["pageNumber"] != page or payload["pageSize"] != PAGE_SIZE or total < 0
        or not isinstance(rows, list) or len(rows) != expected_count
    ):
        raise ValueError("The API pagination contract is inconsistent.")
    return rows, total


def fetch_horizon_calls() -> LiveSearchResult:
    """Fetch at most twenty source-labelled open Horizon topics without project text."""
    calls = []
    notices = []
    seen = {}
    conflicted = set()
    first_total = None
    for page in range(1, MAX_PAGES + 1):
        try:
            payload = _fetch_api_page(page)
            rows, total = _validate_page(payload, page)
        except (URLError, OSError, HTTPException, ValueError, LookupError) as error:
            kind = "network, TLS, HTTP or protocol error" if isinstance(error, (URLError, OSError, HTTPException)) else "invalid response contract"
            notices.append(f"EU Portal page {page} unavailable ({kind}); earlier verified results, if any, are retained. Use the official Portal link to check other calls.")
            break
        retrieved_at = datetime.now(timezone.utc)
        if first_total is None:
            first_total = total
        elif total != first_total:
            notices.append("EU Portal result count changed during pagination; this is an incomplete snapshot.")
        if payload.get("warnings"):
            notices.append("EU Portal returned service warnings; result completeness is unverified.")
        for row in rows:
            try:
                call = _parse_call(row, page=page, retrieved_at=retrieved_at)
            except (ValueError, TypeError):
                notices.append(f"EU Portal page {page}: an unverified or malformed record was skipped.")
                continue
            key = call.identifier.casefold()
            if key in conflicted:
                continue
            if key in seen:
                previous = seen[key]
                excluded = {"retrieved_at", "evidence_url"}
                if call.model_dump(exclude=excluded) == previous.model_dump(exclude=excluded):
                    notices.append("EU Portal repeated a topic across results; the duplicate was omitted.")
                else:
                    calls = [item for item in calls if item.identifier.casefold() != key]
                    conflicted.add(key)
                    notices.append("EU Portal returned conflicting evidence for a repeated topic; all versions of that topic were omitted.")
                continue
            seen[key] = call
            calls.append(call)
        if total <= page * PAGE_SIZE:
            break
        if page == MAX_PAGES:
            notices.append(f"EU Portal search is limited to the first {MAX_PAGES} pages ({MAX_PAGES * PAGE_SIZE} records); additional source results were not retrieved.")
    if first_total == 0:
        notices.append("EU Portal returned no calls for the fixed Horizon Europe open-topic filter.")
    return LiveSearchResult(calls=tuple(calls), notices=tuple(dict.fromkeys(notices)))
