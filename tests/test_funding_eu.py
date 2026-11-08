"""Fictional offline API responses; no funding or model service is contacted."""

import gzip
import json
import ssl
from copy import deepcopy
from datetime import date, datetime, timezone
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from hankeluotsi import funding_eu as eu
from hankeluotsi.funding_calls import assess_call_status


def topic(number=1):
    identifier = f"HORIZON-FICTIONAL-2026-{number:02d}"
    return {
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/" + identifier.lower(),
        "accessRestriction": False,
        "metadata": {
            "DATASOURCE": ["SEDIA"], "type": ["1"], "frameworkProgramme": ["43108390"],
            "language": ["en"], "status": ["31094502"], "identifier": [identifier],
            "title": [f"Fictional digital skills research call {number}"],
            "callIdentifier": ["HORIZON-FICTIONAL-2026"],
            "startDate": ["2026-09-01T00:00:00.000+0000"],
            "deadlineDate": ["2026-12-01T00:00:00.000+0000"],
            "descriptionByte": ["<p>Fictional research &amp; digital training.</p><script>hidden tracking text</script>"],
            "topicConditions": ["<h4>Fictional conditions</h4><p>Read the complete official terms before applying.</p>"],
        },
    }


def page(rows=None, *, number=1, total=None):
    rows = [topic()] if rows is None else rows
    return {"pageNumber": number, "pageSize": eu.PAGE_SIZE,
            "totalResults": len(rows) if total is None else total, "results": rows}


def test_actual_topic_contract_maps_evidence_and_conservative_date_precision(monkeypatch):
    payload = page()
    original = deepcopy(payload)
    fetch = Mock(return_value=payload)
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    fetch.assert_called_once_with(1)
    assert payload == original
    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.identifier == "HORIZON-FICTIONAL-2026-01"
    assert call.call_identifier == "HORIZON-FICTIONAL-2026"
    assert call.title == "Fictional digital skills research call 1"
    assert call.programme == "Horizon Europe"
    assert call.source == "EU Funding & Tenders Portal"
    assert call.objectives == "Fictional research & digital training."
    assert "hidden tracking" not in call.objectives
    assert call.applicant_requirements.startswith("Fictional conditions")
    assert call.geographic_area is None
    assert call.opening.value == date(2026, 9, 1)
    assert type(call.deadline.value) is date
    assert call.deadline.raw == "2026-12-01T00:00:00.000+0000"
    assert call.official_status == "open"
    assert call.retrieved_at.utcoffset().total_seconds() == 0
    assert call.evidence_url == eu._page_url(1)
    assert call.source_url == payload["results"][0]["url"]
    assert any("date-only" in note for note in call.uncertainties)
    assert any("Geographic eligibility" in note for note in call.uncertainties)


@pytest.mark.parametrize(("field", "value"), [
    ("DATASOURCE", ["SEDIA-EVENTS-PROD"]), ("type", ["0"]),
    ("frameworkProgramme", ["OTHER"]), ("language", ["fi"]),
    ("status", ["31094501"]), ("identifier", ["FICTIONAL-NOT-HORIZON"]),
    ("title", []), ("title", "not-a-list"),
])
def test_ignored_filters_or_malformed_required_fields_are_not_presented_as_verified_calls(monkeypatch, field, value):
    row = topic()
    row["metadata"][field] = value
    monkeypatch.setattr(eu, "_fetch_api_page", Mock(return_value=page([row])))

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert any("skipped" in notice for notice in result.notices)


@pytest.mark.parametrize("source_url", [
    "https://unofficial.invalid/topic/HORIZON-FICTIONAL-2026-01",
    "http://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-FICTIONAL-2026-01",
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-FICTIONAL-2026-99",
    "https://user:secret@ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-FICTIONAL-2026-01",
    None,
])
def test_unverified_or_mismatched_topic_links_are_never_invented_or_followed(monkeypatch, source_url):
    row = topic()
    row["url"] = source_url
    fetch = Mock(return_value=page([row]))
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert result.notices
    fetch.assert_called_once_with(1)


def test_missing_or_multistage_dates_stay_unknown_without_selecting_arbitrary_deadline(monkeypatch):
    row = topic()
    row["metadata"].pop("startDate")
    row["metadata"]["deadlineDate"] = ["2026-11-01", "2027-02-01"]
    row["metadata"].pop("topicConditions")
    monkeypatch.setattr(eu, "_fetch_api_page", Mock(return_value=page([row])))

    call = eu.fetch_horizon_calls().calls[0]

    assert call.opening is None and call.deadline is None
    assert call.applicant_requirements is None
    assert any("multiple values" in note for note in call.uncertainties)
    status, _ = assess_call_status(call, now=call.retrieved_at)
    assert status == "unknown"


def test_exact_offset_dates_survive_and_invalid_naive_times_stay_unknown(monkeypatch):
    row = topic()
    row["metadata"]["startDate"] = ["2026-09-01T09:00:00+03:00"]
    row["metadata"]["deadlineDate"] = ["2026-12-01T17:00:00"]
    monkeypatch.setattr(eu, "_fetch_api_page", Mock(return_value=page([row])))

    call = eu.fetch_horizon_calls().calls[0]

    assert isinstance(call.opening.value, datetime)
    assert call.opening.value.utcoffset().total_seconds() == 3 * 3600
    assert call.deadline is None
    assert any("could not be parsed" in note for note in call.uncertainties)


def test_long_conditions_are_plain_text_and_explicitly_shortened(monkeypatch):
    row = topic()
    row["metadata"]["topicConditions"] = ["<p>" + "Fictional requirement. " * 150 + "</p>"]
    monkeypatch.setattr(eu, "_fetch_api_page", Mock(return_value=page([row])))

    call = eu.fetch_horizon_calls().calls[0]

    assert len(call.applicant_requirements) <= 1601
    assert call.applicant_requirements.endswith("…")
    assert any("shortened excerpt" in note for note in call.uncertainties)


def test_two_page_bound_deduplicates_and_explains_incomplete_result_window(monkeypatch):
    fetch = Mock(side_effect=[
        page([topic(n) for n in range(1, 11)], total=40),
        page([topic(n) for n in range(10, 20)], number=2, total=40),
    ])
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert [call.args[0] for call in fetch.call_args_list] == [1, 2]
    assert len(result.calls) == 19
    assert len({call.identifier for call in result.calls}) == 19
    assert any("duplicate" in notice for notice in result.notices)
    assert any("first 2 pages" in notice for notice in result.notices)
    assert result.calls[-1].evidence_url == eu._page_url(2)


def test_short_last_page_does_not_silently_claim_complete_results(monkeypatch):
    fetch = Mock(side_effect=[
        page([topic(n) for n in range(1, 11)], total=15),
        page([topic(11), topic(12)], number=2, total=15),
    ])
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert len(result.calls) == 10
    assert any("page 2 unavailable (invalid response contract)" in notice for notice in result.notices)


def test_conflicting_duplicate_dates_remove_all_versions_of_that_topic(monkeypatch):
    changed = topic(10)
    changed["metadata"]["deadlineDate"] = ["2027-04-01T00:00:00.000+0000"]
    fetch = Mock(side_effect=[
        page([topic(n) for n in range(1, 11)], total=20),
        page([changed] + [topic(n) for n in range(11, 20)], number=2, total=20),
    ])
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert len(result.calls) == 18
    assert not any(call.identifier == changed["metadata"]["identifier"][0] for call in result.calls)
    assert any("conflicting evidence" in notice for notice in result.notices)


@pytest.mark.parametrize("failure", [
    TimeoutError("network timeout"), URLError("offline"),
    ssl.SSLCertVerificationError("invalid certificate"),
    HTTPError(eu.API_URL, 403, "Forbidden", None, None),
    IncompleteRead(b"partial", 4), BadStatusLine("malformed"),
    ValueError("invalid JSON"),
])
def test_later_page_failure_preserves_verified_first_page_and_warns_about_partial_results(monkeypatch, failure):
    fetch = Mock(side_effect=[page([topic(n) for n in range(1, 11)], total=20), failure])
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert len(result.calls) == 10
    assert fetch.call_count == 2
    assert any("page 2 unavailable" in notice for notice in result.notices)
    assert any("earlier verified results" in notice for notice in result.notices)


@pytest.mark.parametrize("payload", [
    [], {}, {"results": []},
    {"pageNumber": 9, "pageSize": eu.PAGE_SIZE, "totalResults": 1, "results": [topic()]},
    {"pageNumber": 1, "pageSize": 100, "totalResults": 1, "results": [topic()]},
    {"pageNumber": 1, "pageSize": eu.PAGE_SIZE, "totalResults": 2, "results": []},
    {"pageNumber": True, "pageSize": eu.PAGE_SIZE, "totalResults": 0, "results": []},
], ids=["array", "empty-object", "missing-envelope", "wrong-page", "ignored-page-size", "missing-records", "boolean-page"])
def test_invalid_response_contract_returns_no_fabricated_calls(monkeypatch, payload):
    fetch = Mock(return_value=payload)
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert any("invalid response contract" in notice for notice in result.notices)
    fetch.assert_called_once_with(1)


def test_empty_valid_results_are_explained_without_network_retries(monkeypatch):
    fetch = Mock(return_value=page([]))
    monkeypatch.setattr(eu, "_fetch_api_page", fetch)

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert any("returned no calls" in notice for notice in result.notices)
    fetch.assert_called_once_with(1)


def mock_transport(monkeypatch, *, body=None, content_type="application/json"):
    response = Mock()
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    response.read.return_value = json.dumps(page()).encode() if body is None else body
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(eu, "build_opener", Mock(return_value=opener))
    return response, opener


def test_transport_sends_only_fixed_json_file_parts_and_uses_bounded_read_and_timeout(monkeypatch):
    response, opener = mock_transport(monkeypatch)

    result = eu._fetch_api_page(1)

    request = opener.open.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.full_url == eu._page_url(1)
    assert opener.open.call_args.kwargs["timeout"] == 10
    response.read.assert_called_once_with(eu.MAX_RESPONSE_BYTES + 1)
    content_type = request.get_header("Content-type")
    multipart = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + request.data
    )
    parts = {part.get_param("name", header="content-disposition"): part for part in multipart.iter_parts()}
    assert set(parts) == {"query", "languages"}
    assert all(part.get_content_type() == "application/json" and part.get_filename() for part in parts.values())
    assert json.loads(parts["query"].get_payload(decode=True)) == {
        "bool": {"must": [
            {"terms": {"type": ["1"]}}, {"terms": {"status": ["31094502"]}},
            {"terms": {"frameworkProgramme": ["43108390"]}},
        ]}
    }
    assert json.loads(parts["languages"].get_payload(decode=True)) == ["en"]
    assert result["results"][0]["metadata"]["identifier"] == ["HORIZON-FICTIONAL-2026-01"]


@pytest.mark.parametrize(("body", "content_type"), [
    (b"x" * (eu.MAX_RESPONSE_BYTES + 1), "application/json"),
    (b"<html>blocked</html>", "text/html"),
    (b"not-json", "application/json"),
], ids=["oversized", "html-shell", "malformed-json"])
def test_transport_invalid_response_is_recoverable(monkeypatch, body, content_type):
    mock_transport(monkeypatch, body=body, content_type=content_type)

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert any("unavailable" in notice for notice in result.notices)


def test_compressed_response_also_has_decoded_size_bound(monkeypatch):
    response, _ = mock_transport(monkeypatch, body=gzip.compress(b"x" * (eu.MAX_RESPONSE_BYTES + 1)))
    response.headers["Content-Encoding"] = "gzip"

    result = eu.fetch_horizon_calls()

    assert result.calls == ()
    assert result.notices


def test_redirects_and_unbounded_pages_are_refused():
    with pytest.raises(ValueError, match="redirects"):
        eu._NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://unofficial.invalid/")
    for number in (0, eu.MAX_PAGES + 1, True):
        with pytest.raises(ValueError, match="bounded search"):
            eu._page_url(number)


def test_trusted_ca_configuration_preserves_tls_validation():
    context = eu._tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
