"""Offline checks for truthful research results and local project comparison."""

import gzip
import ssl
from collections import Counter
from datetime import datetime, timezone
from email.message import Message
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from hankeluotsi import funding
from hankeluotsi.schemas import ProjectIdea


PROGRAMME_HTML = (
    "<html><head><title>Official programme information</title>"
    '<meta name="description" content="Public information about innovation, '
    'training and research support. Individual calls have separate conditions.">'
    "</head><body>Public programme overview.</body></html>"
)


def fictional_idea(**changes):
    payload = {
        "title": "Fictional neighbourhood learning pilot",
        "development_need": "Fictional volunteers need new practices.",
        "target_groups": ["Fictional volunteers"],
        "expected_change": "Volunteers apply a new practice.",
        "geography": "Fictional Finland",
    }
    payload.update(changes)
    return ProjectIdea.model_validate(payload)


def test_default_results_are_six_programme_guides_without_claiming_calls(monkeypatch):
    fetch = Mock(side_effect=AssertionError("Offline research must not fetch pages"))
    monkeypatch.setattr(funding, "_fetch_public_page", fetch)

    records = funding.retrieve_funding_opportunities()

    assert {record.record_id for record in records} == {
        "eakr", "esr", "jtf", "aurora", "portal", "business_finland"
    }
    assert len(records) == 6
    fetch.assert_not_called()
    for record in records:
        assert record.record_kind == "programme_guidance"
        assert record.call_title is None
        assert record.application_dates is None
        assert record.status == "unknown"
        assert record.information_retrieved_at is None
        assert record.retrieved_from_url is None
        assert record.retrieval_state == "not_requested"
        assert record.objectives_and_priorities
        assert record.geographic_eligibility
        assert record.applicant_requirements
        assert record.official_source_url.startswith("https://")
        assert record.guidance_urls
        assert record.guidance_verified_on == funding.VERIFIED_ON
        assert any("no individual call" in item for item in record.uncertainty)


def test_live_retrieval_requests_only_four_fixed_sources_and_preserves_guidance():
    fetch = Mock(return_value=PROGRAMME_HTML)
    before = funding.programme_guidance()
    started = datetime.now(timezone.utc)

    records = funding.retrieve_funding_opportunities(retrieve_live=True, fetch_page=fetch)

    assert Counter(call.args[0] for call in fetch.call_args_list) == Counter({
        funding.EURA_URL: 1,
        funding.AURORA_URL: 1,
        funding.PORTAL_URL: 1,
        funding.BUSINESS_FINLAND_URL: 1,
    })
    for original, record in zip(before, records):
        assert record.retrieval_state == "retrieved"
        assert started <= record.information_retrieved_at <= datetime.now(timezone.utc)
        assert record.information_retrieved_at.utcoffset().total_seconds() == 0
        assert record.retrieved_from_url in funding.PUBLIC_PAGE_URLS
        assert "Official programme information" in record.source_excerpt
        assert record.status == "unknown"
        assert record.call_title is None
        assert record.application_dates is None
        assert record.objectives_and_priorities == original.objectives_and_priorities
        assert record.applicant_requirements == original.applicant_requirements
        assert record.geographic_eligibility == original.geographic_eligibility
        assert record.guidance_verified_on == original.guidance_verified_on
    assert all(record.retrieved_from_url == funding.EURA_URL for record in records[:3])


@pytest.mark.parametrize("failure", [
    TimeoutError("Timed out"),
    URLError("DNS unavailable"),
    ssl.SSLCertVerificationError("Untrusted certificate"),
    HTTPError(funding.AURORA_URL, 403, "Forbidden", None, None),
])
def test_source_failure_keeps_fallback_and_does_not_hide_other_sources(failure):
    def fetch(url):
        if url == funding.AURORA_URL:
            raise failure
        return PROGRAMME_HTML

    records = funding.retrieve_funding_opportunities(retrieve_live=True, fetch_page=fetch)
    aurora = next(record for record in records if record.record_id == "aurora")
    original = next(record for record in funding.programme_guidance() if record.record_id == "aurora")

    assert aurora.retrieval_state == "unavailable"
    assert aurora.source_excerpt is None
    assert aurora.information_retrieved_at is None
    assert aurora.retrieved_from_url is None
    assert aurora.guidance_verified_on == original.guidance_verified_on
    assert aurora.objectives_and_priorities == original.objectives_and_priorities
    assert aurora.official_source_url == original.official_source_url
    assert len(aurora.uncertainty) > len(original.uncertainty)
    assert aurora.call_title is None and aurora.status == "unknown"
    assert all(record.retrieval_state == "retrieved" for record in records if record != aurora)


@pytest.mark.parametrize("unusable_html", [
    "",
    "This is not a programme page",
    "<html><head><title>Portal</title></head><body><script>startApp()</script></body></html>",
    '<html><head><title>Portal</title><meta name="description" content="Portal"></head></html>',
    '<meta name="description" content="A long description without a valid page title is not sufficient evidence.">',
])
def test_empty_unusable_or_javascript_shell_response_is_not_fresh_information(unusable_html):
    fetch = Mock(return_value=unusable_html)

    records = funding.retrieve_funding_opportunities(retrieve_live=True, fetch_page=fetch)

    assert fetch.call_count == 4
    assert all(record.retrieval_state == "unavailable" for record in records)
    assert all(record.information_retrieved_at is None for record in records)
    assert all(record.status == "unknown" and record.call_title is None for record in records)


@pytest.mark.parametrize(("text", "topic", "record_id"), [
    ("Skills training", "skills", "esr"),
    ("Osaaminen ja koulutus", "skills", "esr"),
    ("Työllisyyden parantaminen", "employment", "esr"),
    ("Digitaalinen innovaatio", "digital", "eakr"),
    ("Vihreä siirtymä", "green transition", "aurora"),
    ("Kulttuuri ja matkailu", "tourism", "aurora"),
    ("Tutkimus", "research", "business_finland"),
])
def test_local_comparison_explains_bilingual_shared_topics(text, topic, record_id):
    idea = fictional_idea(title=text)
    original = idea.model_dump()
    record = next(item for item in funding.programme_guidance() if item.record_id == record_id)

    assert topic in funding.compare_locally(idea, record)
    assert idea.model_dump() == original


def test_local_comparison_uses_token_boundaries_and_does_not_infer_geographic_eligibility():
    record = next(item for item in funding.programme_guidance() if item.record_id == "aurora")
    idea = fictional_idea(
        title="Fictional culturalist researchable tourismology",
        geography="Skills training culture tourism Finland Sweden Norway",
        partners=["Research SME innovation"],
    )

    assert funding.compare_locally(idea, record) == ()


def test_comparison_and_network_requests_keep_project_details_local(monkeypatch):
    fetch = Mock(return_value=PROGRAMME_HTML)
    monkeypatch.setattr(funding, "_fetch_public_page", fetch)
    idea = fictional_idea(
        title="FICTIONAL-PRIVATE-TITLE digital skills",
        development_need="FICTIONAL-PRIVATE-NEED",
        funding_context="FICTIONAL-PRIVATE-CONTEXT",
    )
    records = funding.retrieve_funding_opportunities(retrieve_live=True)

    for record in records:
        funding.compare_locally(idea, record)

    assert fetch.call_count == 4
    assert all(call.args[0] in funding.PUBLIC_PAGE_URLS for call in fetch.call_args_list)
    assert "FICTIONAL-PRIVATE" not in str(fetch.call_args_list)


def mocked_response(monkeypatch, *, content=b"<html></html>", content_type="text/html"):
    headers = Message()
    headers["Content-Type"] = content_type
    response = Mock()
    response.headers = headers
    response.read.return_value = content
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    factory = Mock(return_value=opener)
    monkeypatch.setattr(funding, "build_opener", factory)
    return response, opener, factory


def test_fetch_refuses_user_urls_before_any_network_connection(monkeypatch):
    factory = Mock(side_effect=AssertionError("No connection permitted"))
    monkeypatch.setattr(funding, "build_opener", factory)

    with pytest.raises(ValueError, match="fixed official programme pages"):
        funding._fetch_public_page("https://example.test/?project=fictional-private-data")

    factory.assert_not_called()


def test_fetch_uses_bounded_read_timeout_and_official_url(monkeypatch):
    response, opener, _ = mocked_response(monkeypatch, content=b"<html>Public page</html>")

    assert funding._fetch_public_page(funding.EURA_URL) == "<html>Public page</html>"

    request = opener.open.call_args.args[0]
    assert request.full_url == funding.EURA_URL
    assert request.get_method() == "GET"
    assert request.data is None
    assert 0 < opener.open.call_args.kwargs["timeout"] <= 10
    response.read.assert_called_once_with(funding.MAX_PAGE_BYTES + 1)


@pytest.mark.parametrize(("content", "content_type", "message"), [
    (b"a" * (funding.MAX_PAGE_BYTES + 1), "text/html", "size limit"),
    (b"{}", "application/json", "HTML programme page"),
], ids=["oversized-html", "wrong-content-type"])
def test_fetch_rejects_oversized_or_wrong_content_type(monkeypatch, content, content_type, message):
    mocked_response(monkeypatch, content=content, content_type=content_type)

    with pytest.raises(ValueError, match=message):
        funding._fetch_public_page(funding.EURA_URL)


def test_redirect_cannot_forward_requests_to_another_host():
    with pytest.raises(ValueError, match="redirected"):
        funding._NoRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://example.test/unapproved"
        )


def test_unknown_page_charset_preserves_fallback_without_a_false_retrieval_date(monkeypatch):
    mocked_response(
        monkeypatch,
        content=PROGRAMME_HTML.encode("utf-8"),
        content_type="text/html; charset=not-a-real-encoding",
    )

    records = funding.retrieve_funding_opportunities(retrieve_live=True)

    assert len(records) == 6
    assert all(record.retrieval_state == "unavailable" for record in records)
    assert all(record.information_retrieved_at is None for record in records)
    assert all(record.guidance_verified_on == funding.VERIFIED_ON for record in records)
    assert all(record.call_title is None and record.status == "unknown" for record in records)


def test_malformed_meta_attributes_do_not_hide_a_usable_open_graph_description():
    page = (
        "<html><head><title>Official source</title><meta name><meta property>"
        '<meta property="og:description" content="Public programme information '
        'with enough detail to distinguish this page from an empty shell.">'
        "</head></html>"
    )

    records = funding.retrieve_funding_opportunities(
        retrieve_live=True, fetch_page=Mock(return_value=page)
    )

    assert all(record.retrieval_state == "retrieved" for record in records)
    assert all("Public programme information" in record.source_excerpt for record in records)
    assert all(record.status == "unknown" for record in records)


def test_gzip_programme_page_decodes_as_html(monkeypatch):
    response, _, _ = mocked_response(
        monkeypatch, content=gzip.compress(PROGRAMME_HTML.encode("utf-8"))
    )
    response.headers["Content-Encoding"] = "gzip"

    assert funding._fetch_public_page(funding.EURA_URL) == PROGRAMME_HTML


def test_small_compressed_page_cannot_exceed_decoded_size_limit(monkeypatch):
    compressed = gzip.compress(b"a" * (funding.MAX_PAGE_BYTES + 1))
    assert len(compressed) < funding.MAX_PAGE_BYTES
    response, _, _ = mocked_response(monkeypatch, content=compressed)
    response.headers["Content-Encoding"] = "gzip"

    with pytest.raises(ValueError, match="Decoded source page exceeds"):
        funding._fetch_public_page(funding.EURA_URL)


@pytest.mark.parametrize("invalid_content", [
    b"This is not a gzip stream",
    gzip.compress(PROGRAMME_HTML.encode("utf-8"))[:-8],
], ids=["malformed-gzip", "truncated-gzip"])
def test_invalid_gzip_preserves_only_affected_source_fallback(monkeypatch, invalid_content):
    bad_response, _, _ = mocked_response(monkeypatch, content=invalid_content)
    bad_response.headers["Content-Encoding"] = "gzip"
    good_response, opener, _ = mocked_response(
        monkeypatch, content=PROGRAMME_HTML.encode("utf-8")
    )
    opener.open.side_effect = lambda request, **kwargs: (
        bad_response if request.full_url == funding.EURA_URL else good_response
    )

    records = funding.retrieve_funding_opportunities(retrieve_live=True)

    assert all(record.retrieval_state == "unavailable" for record in records[:3])
    assert all(record.information_retrieved_at is None for record in records[:3])
    assert all(record.guidance_verified_on == funding.VERIFIED_ON for record in records[:3])
    assert all(record.retrieval_state == "retrieved" for record in records[3:])
    assert all(record.status == "unknown" for record in records)


def test_unsupported_content_encoding_produces_honest_fallback(monkeypatch):
    response, _, _ = mocked_response(monkeypatch, content=b"unsupported-compressed-data")
    response.headers["Content-Encoding"] = "br"

    records = funding.retrieve_funding_opportunities(retrieve_live=True)

    assert all(record.retrieval_state == "unavailable" for record in records)
    assert all(record.information_retrieved_at is None for record in records)
    assert all(record.status == "unknown" for record in records)
    assert all(any("unsupported content encoding" in item for item in record.uncertainty) for record in records)


@pytest.mark.parametrize("protocol_error", [
    IncompleteRead(b"untrusted partial protocol content", 20),
    BadStatusLine("untrusted malformed protocol status"),
], ids=["truncated-body", "malformed-status"])
def test_http_protocol_failure_preserves_guidance_and_continues_other_sources(monkeypatch, protocol_error):
    bad_response, _, _ = mocked_response(monkeypatch)
    if isinstance(protocol_error, IncompleteRead):
        bad_response.read.side_effect = protocol_error
    good_response, opener, _ = mocked_response(
        monkeypatch, content=PROGRAMME_HTML.encode("utf-8")
    )

    def open_page(request, **kwargs):
        if request.full_url != funding.EURA_URL:
            return good_response
        if isinstance(protocol_error, BadStatusLine):
            raise protocol_error
        return bad_response

    opener.open.side_effect = open_page
    originals = {record.record_id: record for record in funding.programme_guidance()}

    records = funding.retrieve_funding_opportunities(retrieve_live=True)

    assert tuple(call.args[0].full_url for call in opener.open.call_args_list) == funding.PUBLIC_PAGE_URLS
    assert len(records) == 6
    for record in records[:3]:
        original = originals[record.record_id]
        assert record.retrieval_state == "unavailable"
        assert record.information_retrieved_at is None
        assert record.retrieved_from_url is None
        assert record.source_excerpt is None
        assert record.objectives_and_priorities == original.objectives_and_priorities
        assert record.geographic_eligibility == original.geographic_eligibility
        assert record.applicant_requirements == original.applicant_requirements
        assert record.official_source_url == original.official_source_url
        assert record.guidance_urls == original.guidance_urls
        assert record.guidance_verified_on == original.guidance_verified_on
        assert record.uncertainty[:-1] == original.uncertainty
        assert record.uncertainty[-1] == (
            "Network, certificate or HTTP access failed; open the official source manually."
        )
        assert "untrusted" not in " ".join(record.uncertainty)
        assert type(protocol_error).__name__ not in " ".join(record.uncertainty)
    for record in records[3:]:
        assert record.retrieval_state == "retrieved"
        assert record.information_retrieved_at is not None
        assert record.retrieved_from_url in funding.PUBLIC_PAGE_URLS
        assert "Official programme information" in record.source_excerpt
    assert all(record.call_title is None for record in records)
    assert all(record.application_dates is None for record in records)
    assert all(record.status == "unknown" for record in records)
