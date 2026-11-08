"""Offline checks using fictional call evidence, never real funding opportunities."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hankeluotsi.funding_calls import (
    CallDate,
    FundingCall,
    assess_call_status,
    compare_call_locally,
    parse_call_date,
)
from hankeluotsi.schemas import ProjectIdea


UTC = timezone.utc
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def fictional_call(*, retrieved_at=NOW, **changes):
    payload = {
        "source": "Interreg Aurora",
        "programme": "Fictional fixture programme",
        "identifier": "FICTIONAL-2026-01",
        "title": "Fictional digital skills call",
        "objectives": "Fictional education and innovation activities.",
        "opening": parse_call_date("2026-11-07T12:00:00Z"),
        "deadline": parse_call_date("2026-11-09T12:00:00Z"),
        "official_status": "open",
        "source_url": "https://www.interregaurora.eu/projects/calls-for-applications-2/",
        "evidence_url": "https://www.interregaurora.eu/fictional-test-evidence.csv",
        "retrieved_at": retrieved_at,
    }
    payload.update(changes)
    return FundingCall.model_validate(payload)


def fictional_idea(**changes):
    payload = {
        "title": "Fictional learning idea",
        "development_need": "Fictional volunteers need practice.",
        "target_groups": ["Fictional volunteers"],
        "expected_change": "Volunteers apply a new practice.",
        "geography": "Fictional district",
    }
    payload.update(changes)
    return ProjectIdea.model_validate(payload)


@pytest.mark.parametrize(("raw", "expected"), [
    ("2026-11-08", date(2026, 11, 8)),
    ("2028-02-29", date(2028, 2, 29)),
    ("2026-11-08T12:00:00Z", datetime(2026, 11, 8, 12, tzinfo=UTC)),
    ("2026-11-08T14:00:00+02:00", datetime(2026, 11, 8, 14, tzinfo=timezone(timedelta(hours=2)))),
    ("2026-11-08T07:00:00-05:00", datetime(2026, 11, 8, 7, tzinfo=timezone(timedelta(hours=-5)))),
    ("2026-11-08T12:00:00.000+0000", datetime(2026, 11, 8, 12, tzinfo=UTC)),
], ids=["date-only", "leap-day", "utc-z", "positive-offset", "negative-offset", "compact-offset"])
def test_call_dates_preserve_original_evidence_and_date_precision(raw, expected):
    parsed = parse_call_date(raw)

    assert parsed.raw == raw
    assert parsed.value == expected
    assert isinstance(parsed.value, datetime) == isinstance(expected, datetime)
    if isinstance(expected, datetime):
        assert parsed.value.utcoffset() == expected.utcoffset()
        assert "date only" not in parsed.display
    else:
        assert "date only; exact time/timezone unverified" in parsed.display


@pytest.mark.parametrize("raw", [
    None, "", "not-a-date", "2026-02-29", "2026-13-01",
    "2026-11-08T12:00:00", "2026-11-08T25:00:00Z", 12345,
], ids=["missing", "empty", "invalid", "invalid-leap-day", "invalid-month", "naive-time", "invalid-hour", "wrong-type"])
def test_invalid_or_naive_dates_remain_unknown_without_an_invented_timezone(raw):
    assert parse_call_date(raw) is None


def test_midnight_api_placeholders_are_date_only_only_when_explicitly_requested():
    raw = "2026-11-08T00:00:00.000+0200"

    assert isinstance(parse_call_date(raw).value, datetime)
    placeholder = parse_call_date(raw, midnight_is_date=True)
    assert type(placeholder.value) is date
    assert placeholder.value == date(2026, 11, 8)
    assert placeholder.raw == raw
    assert "exact time/timezone unverified" in placeholder.display
    assert isinstance(parse_call_date("2026-11-08T00:00:01Z", midnight_is_date=True).value, datetime)
    assert parse_call_date("2026-11-08T00:00:00", midnight_is_date=True) is None


def test_call_date_and_retrieval_models_reject_naive_exact_times():
    with pytest.raises(ValidationError):
        CallDate(raw="Fictional unzoned timestamp", value=datetime(2026, 11, 8, 12))
    with pytest.raises(ValidationError):
        fictional_call(retrieved_at=datetime(2026, 11, 8, 12))
    with pytest.raises(ValueError, match="aware current time"):
        assess_call_status(fictional_call(), now=datetime(2026, 11, 8, 12))


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, "open"),
    ({"opening": parse_call_date("2026-11-09T12:00:00Z"), "deadline": parse_call_date("2026-11-10T12:00:00Z"), "official_status": "upcoming"}, "upcoming"),
    ({"deadline": parse_call_date("2026-11-08T11:00:00Z")}, "closed"),
    ({"opening": None, "deadline": None, "official_status": "unknown"}, "unknown"),
    ({"official_status": "unknown"}, "unknown"),
    ({"official_status": "upcoming"}, "unknown"),
    ({"opening": None}, "unknown"),
    ({"deadline": None}, "unknown"),
    ({"opening": None, "deadline": None, "official_status": "closed"}, "closed"),
], ids=["verified-open", "future-opening", "deadline-passed", "no-dates", "no-official-open", "upcoming-conflicts", "missing-opening", "missing-deadline", "explicitly-closed"])
def test_status_requires_consistent_source_and_date_evidence(changes, expected):
    status, explanation = assess_call_status(fictional_call(**changes), now=NOW)

    assert status == expected
    assert explanation


@pytest.mark.parametrize(("now", "expected"), [
    (datetime(2026, 11, 8, 11, 59, tzinfo=UTC), "upcoming"),
    (datetime(2026, 11, 8, 12, tzinfo=UTC), "open"),
    (datetime(2026, 11, 8, 14, 59, tzinfo=UTC), "open"),
    (datetime(2026, 11, 8, 15, tzinfo=UTC), "closed"),
], ids=["before-opening", "opening-instant", "before-deadline", "deadline-instant"])
def test_explicit_offsets_are_compared_as_instants_in_utc(now, expected):
    call = fictional_call(
        retrieved_at=now,
        opening=parse_call_date("2026-11-08T14:00:00+02:00"),
        deadline=parse_call_date("2026-11-08T17:00:00+02:00"),
        official_status="unknown" if expected == "upcoming" else "open",
    )

    assert assess_call_status(call, now=now)[0] == expected


@pytest.mark.parametrize(("now", "expected"), [
    (datetime(2026, 11, 8, 9, 59, tzinfo=UTC), "upcoming"),
    (datetime(2026, 11, 8, 10, tzinfo=UTC), "unknown"),
    (datetime(2026, 11, 9, 12, tzinfo=UTC), "unknown"),
    (datetime(2026, 11, 10, 11, 59, tzinfo=UTC), "unknown"),
    (datetime(2026, 11, 10, 12, tzinfo=UTC), "open"),
    (datetime(2026, 11, 14, 9, 59, tzinfo=UTC), "open"),
    (datetime(2026, 11, 14, 10, tzinfo=UTC), "unknown"),
    (datetime(2026, 11, 16, 11, 59, tzinfo=UTC), "unknown"),
    (datetime(2026, 11, 16, 12, tzinfo=UTC), "closed"),
], ids=["before-earliest-opening", "opening-boundary", "opening-time-unknown", "before-latest-opening", "after-latest-opening", "before-earliest-closing", "closing-boundary", "before-latest-closing", "after-all-timezones-closed"])
def test_date_only_bounds_do_not_invent_timezone_or_precise_closing_time(now, expected):
    # 9 Nov opening could begin as early as 8 Nov 10:00 UTC (+14),
    # or as late as the end of 9 Nov in UTC-12 (10 Nov 12:00 UTC).
    # A 15 Nov deadline could be
    # anywhere on that day, ending no later than 16 Nov 12:00 UTC.
    call = fictional_call(
        retrieved_at=now,
        opening=parse_call_date("2026-11-09"),
        deadline=parse_call_date("2026-11-15"),
        official_status="unknown" if expected == "upcoming" else "open",
    )

    assert assess_call_status(call, now=now)[0] == expected
    assert type(call.deadline.value) is date


def test_api_midnight_placeholder_cannot_confirm_opening_late_on_the_given_day():
    now = datetime(2026, 11, 9, 20, tzinfo=UTC)
    opening = parse_call_date("2026-11-09T00:00:00+0000", midnight_is_date=True)
    call = fictional_call(
        retrieved_at=now,
        opening=opening,
        deadline=parse_call_date("2026-11-15"),
        official_status="open",
    )

    status, explanation = assess_call_status(call, now=now)

    assert status == "unknown"
    assert "boundary" in explanation
    assert opening.raw == "2026-11-09T00:00:00+0000"
    assert type(opening.value) is date


@pytest.mark.parametrize(("field", "raw"), [
    ("opening", "0001-01-01"),
    ("deadline", "9999-12-31"),
    ("opening", "0001-01-01T00:00:00+14:00"),
    ("deadline", "9999-12-31T23:59:59-12:00"),
], ids=["earliest-date", "latest-date", "earliest-offset-instant", "latest-offset-instant"])
def test_valid_calendar_extremes_produce_unknown_instead_of_overflow(field, raw):
    parsed = parse_call_date(raw)
    assert parsed is not None
    call = fictional_call(**{field: parsed})

    status, explanation = assess_call_status(call, now=NOW)

    assert status == "unknown"
    assert "supported calendar range" in explanation


def test_open_label_with_a_verified_future_opening_is_unknown():
    call = fictional_call(
        opening=parse_call_date("2026-11-09T12:00:00Z"),
        deadline=parse_call_date("2026-11-10T12:00:00Z"),
    )

    status, explanation = assess_call_status(call, now=NOW)
    assert status == "unknown"
    assert "conflict" in explanation


def test_impossible_date_range_is_unknown_even_when_source_label_is_closed():
    call = fictional_call(
        opening=parse_call_date("2026-11-10T12:00:00Z"),
        deadline=parse_call_date("2026-11-07T12:00:00Z"),
        official_status="closed",
    )

    status, explanation = assess_call_status(call, now=NOW)
    assert status == "unknown"
    assert "inconsistent" in explanation


@pytest.mark.parametrize("official_status", ["open", "closed"])
def test_snapshots_older_than_six_hours_cannot_claim_current_status(official_status):
    call = fictional_call(
        retrieved_at=NOW - timedelta(hours=6, microseconds=1),
        official_status=official_status,
    )

    status, explanation = assess_call_status(call, now=NOW)
    assert status == "unknown"
    assert "stale" in explanation


def test_snapshot_age_boundary_and_implausible_future_retrieval_time():
    assert assess_call_status(fictional_call(retrieved_at=NOW - timedelta(hours=6)), now=NOW)[0] == "open"
    status, explanation = assess_call_status(
        fictional_call(retrieved_at=NOW + timedelta(minutes=6)), now=NOW
    )
    assert status == "unknown"
    assert "inconsistent" in explanation


@pytest.mark.parametrize("bad_url", [
    "http://www.interregaurora.eu/fictional-call",
    "https://unofficial.invalid/fictional-call",
    "https://www.interregaurora.eu.unofficial.invalid/fictional-call",
    "https://www.interregaurora.eu@unofficial.invalid/fictional-call",
    "https://user:password@www.interregaurora.eu/fictional-call",
    "https://www.interregaurora.eu:8443/fictional-call",
], ids=["http", "foreign-host", "lookalike-host", "userinfo-lookalike", "credentials", "unexpected-port"])
def test_call_evidence_requires_official_https_urls(bad_url):
    for field in ("source_url", "evidence_url"):
        with pytest.raises(ValidationError):
            fictional_call(**{field: bad_url})


def test_versioned_call_preserves_valid_official_evidence_and_rejects_unknown_versions():
    call = fictional_call(
        source="EU Funding & Tenders Portal",
        source_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/FICTIONAL-2026-01",
        evidence_url="https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA",
    )

    assert call.schema_version == 1
    assert call.identifier == "FICTIONAL-2026-01"
    assert call.retrieved_at.utcoffset() == timedelta(0)
    with pytest.raises(ValidationError):
        fictional_call(schema_version=2)
    with pytest.raises(ValidationError):
        call.title = "Changed fictional title"


@pytest.mark.parametrize(("idea_title", "expected_topic"), [
    ("Fictional digital training", "digital"),
    ("Fictional koulutus ja osaaminen", "skills"),
    ("Fictional innovaatio", "innovation"),
], ids=["english-digital", "finnish-skills", "finnish-innovation"])
def test_local_matching_explains_vocabulary_topics_without_network_or_mutation(idea_title, expected_topic):
    idea = fictional_idea(title=idea_title)
    call = fictional_call()
    original_idea = idea.model_dump()
    original_call = call.model_dump()

    with patch("urllib.request.urlopen", side_effect=AssertionError("Project data must stay local")):
        topics = compare_call_locally(idea, call)

    assert expected_topic in topics
    assert isinstance(topics, tuple)
    assert idea.model_dump() == original_idea
    assert call.model_dump() == original_call


def test_local_matching_does_not_treat_substrings_geography_or_partners_as_eligibility():
    idea = fictional_idea(
        title="Fictional digitalist skillsology innovationary",
        geography="Digital skills innovation Finland Sweden Norway",
        partners=["Digital education innovation"],
    )

    assert compare_call_locally(idea, fictional_call()) == ()


def test_missing_call_objectives_or_private_project_context_does_not_become_a_verdict():
    idea = fictional_idea(funding_context="FICTIONAL-PRIVATE-CONTEXT research")
    call = fictional_call(title="Fictional research call", objectives=None)

    assert compare_call_locally(idea, call) == ("research",)
    assert compare_call_locally(idea, fictional_call(title="Fictional unrelated call", objectives=None)) == ()
