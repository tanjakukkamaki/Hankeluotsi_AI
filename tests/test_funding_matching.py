"""Fictional evidence only: research relevance must never become eligibility."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from hankeluotsi.funding_calls import FundingCall, parse_call_date
from hankeluotsi.funding_eu import _page_url
from hankeluotsi.funding_matching import match_funding_call, rank_funding_calls
from hankeluotsi.schemas import ConceptPaper, Objective, ProjectIdea


NOW = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)


def idea(**changes):
    fields = dict(title="Fictional community arts and digital skills",
        development_need="Fictional community artists need digital training.",
        target_groups=["Fictional community volunteers"],
        expected_change="Better arts skills and participation in community activities.",
        geography="Fictional Finland")
    fields.update(changes)
    return ProjectIdea(**fields)


def call(**changes):
    fields = dict(source="Interreg Aurora", programme="Fictional programme",
        identifier="FICTIONAL-Z-ARTS", title="Fictional community arts and digital skills",
        objectives="Support community cultural activities, digital learning and skills training.",
        opening=parse_call_date("2026-10-01T10:00:00Z"),
        deadline=parse_call_date("2026-12-01T10:00:00Z"), official_status="open",
        source_url="https://www.interregaurora.eu/projects/calls-for-applications-2/",
        evidence_url="https://www.interregaurora.eu/wp-content/uploads/Timetable-of-the-planned-calls-for-proposals-fictional.csv",
        retrieved_at=NOW)
    fields.update(changes)
    return FundingCall(**fields)


def solar_call():
    return call(identifier="FICTIONAL-A-SOLAR", title="Fictional Solar Radiation Modification research",
        objectives="Research atmospheric climate effects using solar radiation modelling and digital research methods.")


@pytest.mark.parametrize("project", [
    idea(),
    idea(title="Fictional creative industry learning", development_need="Creative industries need skills training."),
    idea(title="Fictional community development", development_need="Community volunteers need inclusive learning."),
])
def test_specific_community_creative_and_skills_calls_rank_before_unrelated_research(project):
    result = rank_funding_calls(project, (solar_call(), call()), now=NOW)
    assert result[0].call.identifier == "FICTIONAL-Z-ARTS"
    assert result[0].category in ("High", "Medium")
    assert result[1].category == "Low"
    assert result[0].score > result[1].score


def test_broad_research_and_digital_overlap_alone_cannot_promote_unrelated_call():
    project = idea(development_need="Community arts research and digital training.")
    result = match_funding_call(project, solar_call(), now=NOW)
    assert result.category == "Low"
    assert set(result.matched_topics) == {"digital", "research"}


def test_generic_project_wording_cannot_produce_a_high_numeric_score():
    project = idea(title="Fictional digital research", development_need="Research innovation is needed.",
        target_groups=["Fictional researchers"], expected_change="Digital research improves.")
    result = match_funding_call(project, solar_call(), now=NOW)
    assert result.category == "Low" and result.thematic_points <= 24


@pytest.mark.parametrize("phrase", ["state-of-the-art research equipment", "innovation culture", "bacterial culture"])
def test_non_art_uses_of_art_and_culture_are_not_cultural_matches(phrase):
    result = match_funding_call(idea(), call(title="Fictional technology facilities",
        objectives="Fictional facilities support " + phrase + " for industrial research."), now=NOW)
    assert "culture & creative work" not in result.matched_topics
    assert result.category == "Low"


@pytest.mark.parametrize("title", ["Fictional sedimentary reservoir assessment", "Fictional nature restoration science"])
def test_incidental_community_mentions_do_not_promote_an_unrelated_specialist_title(title):
    result = match_funding_call(idea(), call(title=title,
        objectives="Scientific methods will be developed; local communities may benefit from the resulting systems."), now=NOW)
    assert "community development" in result.matched_topics
    assert result.category == "Low" and result.thematic_points <= 24
    assert any("specialist title" in item for item in result.cautions)


def test_concept_objectives_are_used_without_changing_project_or_call():
    project = idea(title="Fictional local programme", development_need="Fictional participants need support.",
                   target_groups=["Fictional participants"], expected_change="Participants improve their practice.")
    concept = ConceptPaper.model_validate(json.loads((Path(__file__).parent / "fixtures/concept_paper.json").read_text(encoding="utf-8")))
    concept = concept.model_copy(update={"objectives": [Objective(id="O1", description="Develop community arts learning and digital skills.")]})
    record = call()
    before = (project.model_dump_json(), concept.model_dump_json(), record.model_dump_json())
    assert match_funding_call(project, record, now=NOW).category == "Insufficient Information"
    assert match_funding_call(project, record, now=NOW).confidence == "Limited"
    assert match_funding_call(project, record, concept=concept, now=NOW).category == "High"
    assert before == (project.model_dump_json(), concept.model_dump_json(), record.model_dump_json())


def test_missing_description_caps_a_specific_title_and_leaves_generic_title_unscored():
    specific = match_funding_call(idea(), call(objectives=None), now=NOW)
    generic = match_funding_call(idea(), call(title="Fictional Call 7", objectives=None), now=NOW)
    assert specific.category == "Medium" and specific.confidence == "Limited"
    assert generic.category == "Insufficient Information" and generic.score is None
    assert any("missing" in item for item in specific.cautions)


def test_missing_geography_and_applicant_requirements_never_establish_compatibility():
    result = match_funding_call(idea(), call(), now=NOW)
    assert result.geography_points == result.applicant_points == 0
    assert result.confidence != "Stronger"
    assert any("no compatibility assumed" in item for item in result.reasons)
    assert any("applicant requirements are missing" in item for item in result.cautions)


def test_target_groups_are_not_mistaken_for_applicant_organisations():
    result = match_funding_call(idea(target_groups=["Fictional NGOs and universities"]),
                                call(applicant_requirements="Universities and NGOs may apply."), now=NOW)
    assert result.applicant_points == 0
    assert any("target groups are not treated as applicants" in item for item in result.reasons)


def test_explicit_source_region_and_partner_type_are_small_context_clues():
    result = match_funding_call(idea(geography="Fictional Lapland, Finland", partners=["Fictional NGO partner"]),
        call(geographic_area="Lapland, Finland", applicant_requirements="NGOs and public authorities may apply."), now=NOW)
    assert result.geography_points == result.applicant_points == 10
    assert result.score == 100 and result.confidence == "Stronger"
    assert any("does not confirm eligibility" in item for item in result.reasons)


def test_country_overlap_does_not_establish_subregional_coverage():
    result = match_funding_call(idea(), call(geographic_area="Northern Finland"), now=NOW)
    assert result.geography_points == 5
    unknown = match_funding_call(idea(), call(geographic_area="EU Member States"), now=NOW)
    assert unknown.geography_points == 0


def test_differing_named_conditions_are_advisory_and_do_not_remove_the_call():
    record = call(geographic_area="Sweden only", applicant_requirements="Universities may apply.")
    result = rank_funding_calls(idea(partners=["Fictional NGO"]), (record,), now=NOW)[0]
    assert result.category == "Medium"
    assert result.geography_points == result.applicant_points == -5
    assert any("not an exclusion decision" in item for item in result.reasons)
    assert result.call == record


def test_explicit_negation_does_not_create_positive_context_or_theme_points():
    record = call(title="Fictional research", objectives="Research not for arts or training; atmospheric climate effects only.",
                  geographic_area="Finland is not eligible", applicant_requirements="NGOs are not eligible")
    result = match_funding_call(idea(partners=["Fictional NGO"]), record, now=NOW)
    assert result.geography_points == result.applicant_points == 0
    assert "culture & creative work" not in result.matched_topics
    assert "skills & learning" not in result.matched_topics


@pytest.mark.parametrize("changes", [
    {"source_url": "https://www.interregaurora.eu/unconfirmed-call"},
    {"evidence_url": "https://www.interregaurora.eu/unconfirmed.csv"},
    {"source_url": "https://ec.europa.eu/incorrect-source"},
])
def test_unconfirmed_source_records_are_unscored_and_never_verified_open(changes):
    result = match_funding_call(idea(), call(**changes), now=NOW)
    assert not result.source_reference_confirmed
    assert result.score is None and result.category == "Insufficient Information"
    assert result.status == "unknown" and result.confidence == "Limited"
    assert result.call.official_status == "open"


def test_eu_topic_identifier_must_match_official_url_and_evidence_endpoint():
    identifier = "HORIZON-FICTIONAL-2026-ARTS"
    record = call(source="EU Funding & Tenders Portal", programme="Horizon Europe", identifier=identifier,
        source_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/" + identifier,
        evidence_url=_page_url(1))
    assert match_funding_call(idea(), record, now=NOW).source_reference_confirmed
    explicit_port = record.model_copy(update={"source_url": record.source_url.replace("ec.europa.eu/", "ec.europa.eu:443/")})
    assert match_funding_call(idea(), explicit_port, now=NOW).source_reference_confirmed
    mismatched = record.model_copy(update={"identifier": "HORIZON-FICTIONAL-OTHER"})
    assert not match_funding_call(idea(), mismatched, now=NOW).source_reference_confirmed


@pytest.mark.parametrize("changes", [
    {"retrieved_at": NOW - timedelta(hours=7)},
    {"opening": parse_call_date("2027-01-01"), "deadline": parse_call_date("2026-01-01")},
])
def test_stale_or_conflicting_dates_preserve_facts_and_separate_status_from_relevance(changes):
    record = call(**changes)
    before = record.model_dump_json()
    result = match_funding_call(idea(), record, now=NOW)
    assert result.status == "unknown" and result.confidence == "Limited"
    assert result.category == "High"  # Theme relevance is not confirmation of an open call.
    assert any("status is unknown" in item for item in result.cautions)
    assert record.model_dump_json() == before


def test_ranking_is_deterministic_local_and_keeps_unmatched_records():
    records = (solar_call(), call(), call(identifier="FICTIONAL-UNKNOWN", objectives=None, title="Fictional Call 3"))
    with patch("urllib.request.build_opener", side_effect=AssertionError("No network allowed")):
        first = rank_funding_calls(idea(), records, now=NOW)
        second = rank_funding_calls(idea(), tuple(reversed(records)), now=NOW)
    assert first == second
    assert {item.call.identifier for item in first} == {item.identifier for item in records}
    assert [item.category for item in first] == ["High", "Low", "Insufficient Information"]
