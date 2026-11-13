"""Citation selection improves transport reliability without relaxing source validation."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from hankeluotsi.draft_checks import validate_review_evidence
from hankeluotsi.draft_schemas import ApplicationDraft
from hankeluotsi.review_evidence import ReviewSelection, build_evidence_catalog, resolve_review_selection


@pytest.fixture
def draft():
    return ApplicationDraft.model_validate_json((Path(__file__).parent / "fixtures/application_draft.json").read_text(encoding="utf-8"))


def selected(evidence_id):
    return ReviewSelection(strengths=["A relevant fictional need"], findings=[dict(evidence_id=evidence_id,
        observation="The proposed measurement needs human verification.", suggestion="Check the assessment criterion.",
        severity="question")], missing_information=[], overall_assessment="Suggestions only.", uncertainties=["No expert review."])


@pytest.mark.parametrize("language", ["en", "fi"])
def test_quotes_are_copied_from_source_and_old_validator_still_passes(draft, language):
    catalog = build_evidence_catalog(draft)
    entry = next(x for x in catalog["entries"] if x["reference"] == "I1" and "measurement_method" in x["location"])
    review = resolve_review_selection(draft, selected(entry["evidence_id"]), catalog, language=language)
    finding = review.findings[0]
    assert finding.reference == "I1" and finding.evidence_quote == entry["quote"]
    assert finding.evidence_quote in draft.proposed_indicators[0].measurement_method
    validate_review_evidence(draft, review)
    assert len(review.uncertainties) == 2
    assert ("Sovellus" if language == "fi" else "application") in review.uncertainties[-1]


def test_fabricated_selection_is_not_repaired_or_saved(draft):
    with pytest.raises(ValueError, match="outside"):
        resolve_review_selection(draft, selected("E9999"), build_evidence_catalog(draft))


def test_old_model_written_quote_contract_is_not_silently_accepted():
    old = json.loads((Path(__file__).parent / "fixtures/review_report.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        ReviewSelection.model_validate(old)


def test_different_source_catalogue_rejected(draft):
    catalog = build_evidence_catalog(draft)
    changed = draft.model_copy(update={"project_summary": "Changed by the owner"})
    with pytest.raises(ValueError, match="current source"):
        resolve_review_selection(changed, selected("E1"), catalog)


def test_tampered_quote_and_wrong_reference_still_rejected_by_strict_validator(draft):
    catalog = build_evidence_catalog(draft)
    for changes in ({"quote": "Fabricated evidence absent from source"}, {"reference": "generation_metadata"}):
        tampered = deepcopy(catalog)
        tampered["entries"][0].update(changes)
        with pytest.raises(ValueError):
            resolve_review_selection(draft, selected("E1"), tampered)


def test_catalogue_is_deterministic_bounded_and_excludes_metadata(draft):
    catalog = build_evidence_catalog(draft, max_entries=5, max_characters=100, max_excerpt=30)
    assert catalog == build_evidence_catalog(draft, max_entries=5, max_characters=100, max_excerpt=30)
    assert len(catalog["entries"]) <= 5 and sum(len(e["quote"]) for e in catalog["entries"]) <= 100
    assert catalog["partial"]
    assert all(len(e["quote"]) <= 30 and e["reference"] not in {"generation_metadata", "schema_version"} for e in catalog["entries"])
    review = resolve_review_selection(draft, selected("E1"), catalog)
    assert "bounded excerpts" in review.uncertainties[-1]


def test_all_catalogue_quotes_are_valid_in_their_original_fields(draft):
    catalog = build_evidence_catalog(draft)
    for entry in catalog["entries"]:
        review = resolve_review_selection(draft, selected(entry["evidence_id"]), catalog)
        validate_review_evidence(draft, review)


def test_duplicate_catalogue_ids_and_unbounded_settings_fail(draft):
    catalog = build_evidence_catalog(draft)
    catalog["entries"].append(catalog["entries"][0])
    with pytest.raises(ValueError, match="duplicate"):
        resolve_review_selection(draft, selected("E1"), catalog)
    for options in ({"max_entries": 0}, {"max_entries": 999}, {"max_excerpt": 0}, {"max_characters": 99999}):
        with pytest.raises(ValueError):
            build_evidence_catalog(draft, **options)
