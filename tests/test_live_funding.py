"""Offline Aurora timetable checks using entirely fictional call records."""

import csv
import gzip
import io
from datetime import date, datetime, timezone
from email.message import Message
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from hankeluotsi import funding_eu, live_funding
from hankeluotsi.funding_calls import FundingCall, LiveSearchResult


RETRIEVED_AT = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
CSV_URL = (
    "https://www.interregaurora.eu/wp-content/uploads/"
    "Timetable-of-the-planned-calls-for-proposals-FICTIONAL.csv"
)
HEADERS = (
    "Funding call title", "Funding call identifier", "Policy objective",
    "Specific objective", "Status", "Start date", "End date",
    "Indicative amount of ERDF-support for the call  (EUR)",
    "Indicative amount of IR-support for the call (EUR)",
    "Geographical area covered by the call for proposal", "Type of eligible applicants",
    "Programme title", "Programme CCI", "Additional information to support applicants",
    "Time of update",
)


def fictional_row(**changes):
    row = dict.fromkeys(HEADERS, "")
    row.update({
        "Funding call title": "Fictional Tørndal digital training call",
        "Funding call identifier": "FICTIONAL_REG_1",
        "Policy objective": "Fictional skills development",
        "Specific objective": "Fictional digital education across borders",
        "Status": "Open",
        "Start date": "2026-09-01",
        "End date": "2026-12-01",
        "Geographical area covered by the call for proposal": "Fictional northern district",
        "Type of eligible applicants": "Fictional learning associations; verify individual conditions",
        "Programme title": "Fictional Aurora training programme",
        "Programme CCI": "FICTIONAL_CCI",
        "Time of update": "2026-11-01",
    })
    row.update(changes)
    return row


def timetable(*rows, encoding="utf-8", headers=HEADERS):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=headers, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in rows or (fictional_row(),):
        writer.writerow({key: row.get(key, "") for key in headers})
    return text.getvalue().encode(encoding)


def parse(content):
    return live_funding.parse_aurora_csv(content, CSV_URL, retrieved_at=RETRIEVED_AT)


def response(content, content_type="text/html", content_encoding=None):
    headers = Message()
    headers["Content-Type"] = content_type
    if content_encoding:
        headers["Content-Encoding"] = content_encoding
    result = Mock()
    result.headers = headers
    result.read.return_value = content
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252"])
def test_observed_csv_contract_preserves_source_fields_and_date_precision(encoding):
    result = parse(timetable(encoding=encoding))

    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.identifier == "FICTIONAL_REG_1"
    assert call.title == "Fictional Tørndal digital training call"
    assert call.programme == "Fictional Aurora training programme"
    assert call.objectives == "Fictional skills development\nFictional digital education across borders"
    assert call.geographic_area == "Fictional northern district"
    assert "Fictional learning associations" in call.applicant_requirements
    assert call.opening.value == date(2026, 9, 1)
    assert call.deadline.value == date(2026, 12, 1)
    assert "exact time/timezone unverified" in call.deadline.display
    assert call.official_status == "open"
    assert call.source_updated_on == date(2026, 11, 1)
    assert call.retrieved_at == RETRIEVED_AT
    assert call.source_url == live_funding.AURORA_CALLS_URL
    assert call.evidence_url == CSV_URL
    assert any("indicative" in message for message in call.uncertainties)
    assert any("not an eligibility assessment" in message for message in call.uncertainties)


@pytest.mark.parametrize(("label", "expected"), [
    ("Open", "open"), ("CLOSED", "closed"), ("Upcoming", "upcoming"),
    ("Planned", "upcoming"), ("Unverified", "unknown"), ("", "unknown"),
])
def test_source_status_labels_remain_distinct_from_date_assessment(label, expected):
    call = parse(timetable(fictional_row(Status=label))).calls[0]
    assert call.official_status == expected


def test_missing_dates_and_optional_conditions_are_unknown_without_inventing_values():
    call = parse(timetable(fictional_row(**{
        "Start date": "not-a-date", "End date": "", "Time of update": "unknown",
        "Policy objective": "", "Specific objective": "",
        "Geographical area covered by the call for proposal": "",
        "Type of eligible applicants": "",
    }))).calls[0]
    assert call.opening is None and call.deadline is None
    assert call.source_updated_on is None
    assert call.objectives is None
    assert call.geographic_area is None
    assert call.applicant_requirements is None
    assert any("missing or invalid" in message for message in call.uncertainties)


@pytest.mark.parametrize("missing", ["Funding call identifier", "End date", "Type of eligible applicants"])
def test_missing_required_headers_fail_closed(missing):
    headers = tuple(header for header in HEADERS if header != missing)
    with pytest.raises(ValueError, match="columns"):
        parse(timetable(headers=headers))


def test_duplicate_headers_are_rejected_instead_of_overwriting_evidence():
    with pytest.raises(ValueError, match="columns"):
        parse(timetable(headers=HEADERS + ("End date",)))


def test_blank_and_incomplete_rows_do_not_create_fake_calls():
    good = timetable(fictional_row(), dict.fromkeys(HEADERS, ""), fictional_row(**{
        "Funding call identifier": "", "Funding call title": "Fictional incomplete row",
    }))
    malformed = good + b"Fictional truncated row;FICTIONAL_BROKEN\n"
    result = parse(malformed)
    assert [call.identifier for call in result.calls] == ["FICTIONAL_REG_1"]
    assert any("without an official title/identifier" in message for message in result.notices)
    assert any("malformed timetable row" in message for message in result.notices)


def test_identical_duplicates_coalesce_and_conflicting_duplicates_are_removed():
    first = fictional_row()
    identical = parse(timetable(first, first))
    assert len(identical.calls) == 1
    second = fictional_row(**{"End date": "2027-01-01"})
    third = fictional_row(**{"Funding call identifier": "FICTIONAL_REG_2"})
    conflicting = parse(timetable(first, second, first, third))
    assert [call.identifier for call in conflicting.calls] == ["FICTIONAL_REG_2"]
    assert any("conflicting duplicate" in message for message in conflicting.notices)


def test_csv_row_bound_reports_partial_results(monkeypatch):
    monkeypatch.setattr(live_funding, "MAX_CSV_ROWS", 1)
    result = parse(timetable(fictional_row(), fictional_row(**{
        "Funding call identifier": "FICTIONAL_REG_2",
    })))
    assert len(result.calls) == 1
    assert any("row limit" in message and "partial" in message for message in result.notices)


def test_fetch_discovers_link_and_sends_only_two_fixed_official_gets(monkeypatch):
    page = f'<html><a href="{CSV_URL}">Official machine-readable timetable</a></html>'.encode()
    html_response = response(page)
    csv_response = response(timetable(encoding="cp1252"), "text/csv")
    opener = Mock()
    opener.open.side_effect = [html_response, csv_response]
    monkeypatch.setattr(live_funding, "build_opener", Mock(return_value=opener))

    result = live_funding.fetch_aurora_calls()

    assert len(result.calls) == 1
    requests = [entry.args[0] for entry in opener.open.call_args_list]
    assert [request.full_url for request in requests] == [live_funding.AURORA_CALLS_URL, CSV_URL]
    assert all(request.get_method() == "GET" and request.data is None for request in requests)
    assert all(entry.kwargs["timeout"] == 10 for entry in opener.open.call_args_list)
    assert all(call.retrieved_at.utcoffset().total_seconds() == 0 for call in result.calls)
    html_response.read.assert_called_once_with(live_funding.MAX_RESPONSE_BYTES + 1)
    csv_response.read.assert_called_once_with(live_funding.MAX_RESPONSE_BYTES + 1)


@pytest.mark.parametrize("href", [
    "http://www.interregaurora.eu/wp-content/uploads/Timetable-of-the-planned-calls-for-proposals-FICTIONAL.csv",
    "https://untrusted.invalid/Timetable-of-the-planned-calls-for-proposals-FICTIONAL.csv",
    CSV_URL + "?project=fictional-private-data",
    CSV_URL + "#fragment", "https://www.interregaurora.eu/wp-content/uploads/unverified.csv",
])
def test_unverified_timetable_links_never_trigger_a_second_request(monkeypatch, href):
    download = Mock(return_value=f'<a href="{href}">Timetable</a>'.encode())
    monkeypatch.setattr(live_funding, "_download_aurora", download)
    result = live_funding.fetch_aurora_calls()
    assert result.calls == ()
    assert any("unavailable" in message for message in result.notices)
    download.assert_called_once_with(live_funding.AURORA_CALLS_URL)


def test_relative_link_and_repeated_identical_link_are_one_verified_dataset(monkeypatch):
    relative = CSV_URL.split("www.interregaurora.eu", 1)[1]
    page = f'<a href="{relative}">Timetable</a><a href="{CSV_URL}">Same timetable</a>'.encode()
    download = Mock(side_effect=[page, timetable()])
    monkeypatch.setattr(live_funding, "_download_aurora", download)
    assert len(live_funding.fetch_aurora_calls().calls) == 1
    assert download.call_count == 2


def test_multiple_distinct_timetable_links_are_not_guessed(monkeypatch):
    other = CSV_URL.replace("FICTIONAL", "FICTIONAL-OTHER")
    download = Mock(return_value=f'<a href="{CSV_URL}">One</a><a href="{other}">Two</a>'.encode())
    monkeypatch.setattr(live_funding, "_download_aurora", download)
    result = live_funding.fetch_aurora_calls()
    assert result.calls == ()
    assert download.call_count == 1


@pytest.mark.parametrize("failure", [
    TimeoutError("fictional timeout"), URLError("fictional DNS error"),
    IncompleteRead(b"fictional incomplete body", 20), BadStatusLine("fictional malformed status"),
    HTTPError(live_funding.AURORA_CALLS_URL, 403, "Forbidden", None, None),
], ids=["timeout", "dns", "incomplete-body", "malformed-status", "forbidden"])
def test_source_errors_return_notices_without_fake_calls(monkeypatch, failure):
    monkeypatch.setattr(live_funding, "_download_aurora", Mock(side_effect=failure))
    result = live_funding.fetch_aurora_calls()
    assert result.calls == ()
    assert result.notices == ("Interreg Aurora: " + live_funding.SOURCE_FAILURE,)


@pytest.mark.parametrize("bad_csv", [
    b"<html>Fictional error page</html>",
    b"title;identifier\nFictional title;FICTIONAL_1\n",
    timetable() + b'"Fictional unfinished quoted field',
], ids=["html", "wrong-columns", "invalid-quoting"])
def test_invalid_csv_has_no_successful_records_or_retrieval_timestamps(monkeypatch, bad_csv):
    page = f'<a href="{CSV_URL}">Official timetable</a>'.encode()
    monkeypatch.setattr(live_funding, "_download_aurora", Mock(side_effect=[page, bad_csv]))
    result = live_funding.fetch_aurora_calls()
    assert result.calls == ()
    assert any("unavailable" in message for message in result.notices)


@pytest.mark.parametrize(("content", "mime", "encoding"), [
    (b"a" * (live_funding.MAX_RESPONSE_BYTES + 1), "text/html", None),
    (b"{}", "application/json", None),
    (b"compressed", "text/html", "br"),
    (gzip.compress(b"a" * (live_funding.MAX_RESPONSE_BYTES + 1)), "text/html", "gzip"),
], ids=["oversized", "wrong-mime", "unsupported-encoding", "gzip-expanded-oversize"])
def test_bounded_download_rejects_invalid_source_responses(monkeypatch, content, mime, encoding):
    opener = Mock()
    opener.open.return_value = response(content, mime, encoding)
    monkeypatch.setattr(live_funding, "build_opener", Mock(return_value=opener))
    with pytest.raises(ValueError):
        live_funding._download_aurora(live_funding.AURORA_CALLS_URL)


def test_redirect_handler_is_installed_and_refuses_external_destinations(monkeypatch):
    factory = Mock()
    factory.return_value.open.return_value = response(b"<html></html>")
    monkeypatch.setattr(live_funding, "build_opener", factory)
    live_funding._download_aurora(live_funding.AURORA_CALLS_URL)
    handler = factory.call_args.args[0]
    with pytest.raises(ValueError, match="redirected"):
        handler.redirect_request(None, None, 302, "Found", {}, "https://untrusted.invalid/")


@pytest.mark.parametrize("successful_source", ["aurora", "eu"])
def test_aggregator_preserves_successes_and_reports_each_unavailable_source(monkeypatch, successful_source):
    call = FundingCall(
        source="Interreg Aurora", programme="Fictional programme", identifier="FICTIONAL_1",
        title="Fictional skills call", source_url=live_funding.AURORA_CALLS_URL,
        evidence_url=CSV_URL, retrieved_at=RETRIEVED_AT,
    )
    success = LiveSearchResult(calls=(call,))
    failure = LiveSearchResult(notices=("Fictional source unavailable",))
    aurora = Mock(return_value=success if successful_source == "aurora" else failure)
    horizon = Mock(return_value=success if successful_source == "eu" else failure)
    monkeypatch.setattr(live_funding, "fetch_aurora_calls", aurora)
    monkeypatch.setattr(funding_eu, "fetch_horizon_calls", horizon)

    result = live_funding.search_live_funding_calls()

    assert result.calls == (call,)
    assert "Fictional source unavailable" in result.notices
    assert any("EURA 2021" in message and "unavailable" in message for message in result.notices)
    assert any("Business Finland" in message for message in result.notices)
    aurora.assert_called_once_with()
    horizon.assert_called_once_with()
