import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hankeluotsi.draft_schemas import ApplicationDraft, GenerationMetadata, ReviewReport
from hankeluotsi.schemas import ConceptPaper


FIXTURES = Path(__file__).parent / "fixtures"


def draft_data():
    return json.loads((FIXTURES / "application_draft.json").read_text(encoding="utf-8"))


def review_data():
    return json.loads((FIXTURES / "review_report.json").read_text(encoding="utf-8"))


def test_fictional_draft_and_review_round_trip_without_changing_concept_contract():
    draft = ApplicationDraft.model_validate(draft_data())
    review = ReviewReport.model_validate(review_data())
    assert ApplicationDraft.model_validate_json(draft.model_dump_json()) == draft
    assert ReviewReport.model_validate_json(review.model_dump_json()) == review
    assert draft.schema_version == review.schema_version == 1
    assert "work_packages" not in ConceptPaper.model_fields
    assert draft.generation_metadata is None and review.generation_metadata is None


@pytest.mark.parametrize("field", ["project_summary", "background_need", "general_objective",
    "longer_term_impact", "sustainability"])
def test_blank_required_draft_sections_rejected(field):
    data = draft_data()
    data[field] = " \n "
    with pytest.raises(ValidationError):
        ApplicationDraft.model_validate(data)


@pytest.mark.parametrize("field", ["target_groups", "beneficiaries", "objectives", "work_packages", "activities",
    "outputs", "expected_results", "proposed_indicators", "timeline", "risks"])
def test_empty_required_draft_lists_rejected(field):
    data = draft_data()
    data[field] = []
    with pytest.raises(ValidationError):
        ApplicationDraft.model_validate(data)


def test_unknown_partner_roles_and_missing_information_are_explicit_and_allowed():
    data = draft_data()
    data["partner_roles"] = [{"partner": "Unknown", "role": "Requires owner clarification", "status": "unknown"}]
    data["timeline"][0]["period"] = "Unknown; confirm timing before implementation"
    assert ApplicationDraft.model_validate(data).partner_roles[0].status == "unknown"
    data["partner_roles"] = []
    assert ApplicationDraft.model_validate(data).partner_roles == []


@pytest.mark.parametrize("version", [0, 2, "1", True, None])
@pytest.mark.parametrize("model,data_fn", [(ApplicationDraft, draft_data), (ReviewReport, review_data)])
def test_unsupported_versions_are_not_silently_coerced(version, model, data_fn):
    data = data_fn()
    data["schema_version"] = version
    with pytest.raises(ValidationError, match="unsupported"):
        model.model_validate(data)


@pytest.mark.parametrize("field,limit", [("objectives", 3), ("work_packages", 3), ("activities", 6),
    ("expected_results", 4), ("proposed_indicators", 4)])
def test_generation_bounds_are_enforced(field, limit):
    data = draft_data()
    data[field] *= limit + 1
    with pytest.raises(ValidationError):
        ApplicationDraft.model_validate(data)


@pytest.mark.parametrize("section,field,value", [("work_packages", "id", "W1"),
    ("activities", "id", "A0"), ("activities", "work_package_id", "WP0")])
def test_work_package_and_activity_ids_are_typed(section, field, value):
    data = draft_data()
    data[section][0][field] = value
    with pytest.raises(ValidationError):
        ApplicationDraft.model_validate(data)


def test_review_cannot_authorize_approval_or_silently_include_a_replacement_draft():
    data = review_data()
    data["approved"] = True
    data["replacement_draft"] = draft_data()
    with pytest.raises(ValidationError):
        ReviewReport.model_validate(data)


def test_review_requires_explicit_uncertainty_and_evidence():
    data = review_data()
    data["uncertainties"] = []
    with pytest.raises(ValidationError):
        ReviewReport.model_validate(data)
    data = review_data()
    data["findings"][0]["evidence_quote"] = " "
    with pytest.raises(ValidationError):
        ReviewReport.model_validate(data)


def test_metadata_is_optional_versioned_output_information_not_a_human_approval():
    data = draft_data()
    data["generation_metadata"] = GenerationMetadata(provider="local", model="fictional-qwen",
        prompt_version="draft_v2").model_dump()
    model = ApplicationDraft.model_validate(data)
    assert model.generation_metadata.finish_reason == "unknown"
    assert model.generation_metadata.incomplete_output
    data["generation_metadata"]["approved"] = True
    with pytest.raises(ValidationError):
        ApplicationDraft.model_validate(data)
