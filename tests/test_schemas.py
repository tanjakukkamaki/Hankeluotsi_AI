import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hankeluotsi.schemas import ConceptPaper, ProjectIdea


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def project_idea_data() -> dict:
    return load_fixture("project_idea.json")


def concept_paper_data() -> dict:
    return load_fixture("concept_paper.json")


def test_fictional_project_idea_fixture_parses():
    idea = ProjectIdea.model_validate(project_idea_data())

    assert idea.schema_version == 1
    assert "Fictional" in idea.geography
    assert len(idea.target_groups) == 1
    assert len(idea.partners) == 2


def test_fictional_concept_paper_fixture_parses_with_explicit_references():
    concept = ConceptPaper.model_validate(concept_paper_data())

    assert concept.schema_version == 1
    assert len(concept.objectives) == 2
    assert len(concept.preliminary_activities) == 3
    assert concept.preliminary_activities[1].objective_ids == ["O1", "O2"]
    assert concept.expected_results[0].activity_ids == ["A1", "A2"]
    assert concept.proposed_indicators[0].result_ids == ["R1"]


@pytest.mark.parametrize(
    "field",
    ["title", "development_need", "target_groups", "expected_change", "geography"],
)
def test_project_idea_requires_core_fields(field):
    payload = project_idea_data()
    payload.pop(field)

    with pytest.raises(ValidationError):
        ProjectIdea.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [
        "background_need",
        "objectives",
        "target_groups",
        "preliminary_activities",
        "expected_results",
        "proposed_indicators",
    ],
)
def test_concept_paper_requires_core_fields(field):
    payload = concept_paper_data()
    payload.pop(field)

    with pytest.raises(ValidationError):
        ConceptPaper.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "index", "field"),
    [
        ("objectives", 0, "id"),
        ("objectives", 0, "description"),
        ("preliminary_activities", 0, "id"),
        ("preliminary_activities", 0, "description"),
        ("preliminary_activities", 0, "objective_ids"),
        ("expected_results", 0, "id"),
        ("expected_results", 0, "description"),
        ("expected_results", 0, "activity_ids"),
        ("proposed_indicators", 0, "id"),
        ("proposed_indicators", 0, "description"),
        ("proposed_indicators", 0, "result_ids"),
        ("proposed_indicators", 0, "measurement_method"),
    ],
)
def test_nested_concept_objects_require_fields(collection, index, field):
    payload = concept_paper_data()
    payload[collection][index].pop(field)

    with pytest.raises(ValidationError):
        ConceptPaper.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload_factory", "field"),
    [
        (ProjectIdea, project_idea_data, "title"),
        (ProjectIdea, project_idea_data, "development_need"),
        (ProjectIdea, project_idea_data, "expected_change"),
        (ProjectIdea, project_idea_data, "geography"),
        (ConceptPaper, concept_paper_data, "background_need"),
    ],
)
def test_required_text_fields_reject_blank_strings(model, payload_factory, field):
    payload = payload_factory()
    payload[field] = "  \t "

    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_list_text_fields_reject_blank_strings():
    idea = project_idea_data()
    idea["target_groups"] = ["   "]
    concept = concept_paper_data()
    concept["objectives"][0]["description"] = "  "

    with pytest.raises(ValidationError):
        ProjectIdea.model_validate(idea)
    with pytest.raises(ValidationError):
        ConceptPaper.model_validate(concept)


@pytest.mark.parametrize(
    ("model", "payload_factory", "field"),
    [
        (ProjectIdea, project_idea_data, "target_groups"),
        (ConceptPaper, concept_paper_data, "objectives"),
        (ConceptPaper, concept_paper_data, "target_groups"),
        (ConceptPaper, concept_paper_data, "preliminary_activities"),
        (ConceptPaper, concept_paper_data, "expected_results"),
        (ConceptPaper, concept_paper_data, "proposed_indicators"),
    ],
)
def test_required_collections_cannot_be_empty(model, payload_factory, field):
    payload = payload_factory()
    payload[field] = []

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "field"),
    [
        ("preliminary_activities", "objective_ids"),
        ("expected_results", "activity_ids"),
        ("proposed_indicators", "result_ids"),
    ],
)
def test_required_reference_lists_cannot_be_empty(collection, field):
    payload = concept_paper_data()
    payload[collection][0][field] = []

    with pytest.raises(ValidationError):
        ConceptPaper.model_validate(payload)


def test_optional_project_idea_fields_can_be_omitted_or_null():
    payload = project_idea_data()
    payload.pop("partners")
    payload.pop("funding_context")

    idea = ProjectIdea.model_validate(payload)
    assert idea.partners is None
    assert idea.funding_context is None

    payload["partners"] = None
    payload["funding_context"] = None
    assert ProjectIdea.model_validate(payload).partners is None


def test_concept_assumptions_and_open_questions_default_to_empty_lists():
    payload = concept_paper_data()
    payload.pop("assumptions")
    payload.pop("open_questions")

    concept = ConceptPaper.model_validate(payload)
    assert concept.assumptions == []
    assert concept.open_questions == []


@pytest.mark.parametrize("model,payload_factory", [(ProjectIdea, project_idea_data), (ConceptPaper, concept_paper_data)])
@pytest.mark.parametrize("version", [0, 2])
def test_unsupported_schema_versions_are_rejected(model, payload_factory, version):
    payload = payload_factory()
    payload["schema_version"] = version

    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)

    assert any("schema_version" in str(item["loc"]) for item in error.value.errors())


@pytest.mark.parametrize(
    ("collection", "index", "field", "invalid_value"),
    [
        ("objectives", 0, "id", "A1"),
        ("preliminary_activities", 0, "id", "A0"),
        ("preliminary_activities", 0, "objective_ids", ["WP1"]),
        ("expected_results", 0, "id", "R-1"),
        ("expected_results", 0, "activity_ids", ["O1"]),
        ("proposed_indicators", 0, "id", "I01"),
        ("proposed_indicators", 0, "result_ids", ["A1"]),
    ],
)
def test_malformed_concept_ids_and_reference_ids_are_rejected(
    collection, index, field, invalid_value
):
    payload = concept_paper_data()
    payload[collection][index][field] = invalid_value

    with pytest.raises(ValidationError):
        ConceptPaper.model_validate(payload)


def test_unexpected_fields_are_rejected():
    payload = project_idea_data()
    payload["budget"] = "not part of this project scope"

    with pytest.raises(ValidationError):
        ProjectIdea.model_validate(payload)


def test_schema_version_defaults_to_supported_version():
    idea = project_idea_data()
    concept = concept_paper_data()
    idea.pop("schema_version")
    concept.pop("schema_version")

    assert ProjectIdea.model_validate(idea).schema_version == 1
    assert ConceptPaper.model_validate(concept).schema_version == 1
