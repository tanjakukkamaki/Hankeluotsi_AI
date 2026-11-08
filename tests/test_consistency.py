import json
from pathlib import Path

import pytest

from hankeluotsi.consistency import (
    ConsistencyFinding,
    FindingCode,
    FindingSeverity,
    check_concept_consistency,
)
from hankeluotsi.schemas import ConceptPaper


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "concept_paper.json"


def load_concept() -> ConceptPaper:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return ConceptPaper.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "code", "identifier"),
    [
        ("objectives", FindingCode.DUPLICATE_OBJECTIVE_ID, "O1"),
        ("preliminary_activities", FindingCode.DUPLICATE_ACTIVITY_ID, "A1"),
        ("expected_results", FindingCode.DUPLICATE_RESULT_ID, "R1"),
        ("proposed_indicators", FindingCode.DUPLICATE_INDICATOR_ID, "I1"),
    ],
)
def test_duplicate_ids_are_reported_as_errors(collection, code, identifier):
    concept = load_concept()
    original = getattr(concept, collection)[0]
    updated = list(getattr(concept, collection)) + [original.model_copy()]

    findings = check_concept_consistency(concept.model_copy(update={collection: updated}))
    finding = next(item for item in findings if item.code == code)

    assert finding.severity == FindingSeverity.ERROR
    assert finding.element_id == identifier
    assert identifier in finding.message


def test_valid_fictional_concept_has_no_findings():
    assert check_concept_consistency(load_concept()) == []


def test_unresolved_objective_activity_and_result_references_are_reported():
    concept = load_concept()
    activities = list(concept.preliminary_activities)
    activities[0] = activities[0].model_copy(update={"objective_ids": ["O99"]})
    results = list(concept.expected_results)
    results[0] = results[0].model_copy(update={"activity_ids": ["A99"]})
    indicators = list(concept.proposed_indicators)
    indicators[0] = indicators[0].model_copy(update={"result_ids": ["R99"]})
    mutated = concept.model_copy(
        update={
            "preliminary_activities": activities,
            "expected_results": results,
            "proposed_indicators": indicators,
        }
    )

    findings = check_concept_consistency(mutated)
    unresolved = [
        item
        for item in findings
        if item.code
        in {
            FindingCode.UNRESOLVED_OBJECTIVE_REFERENCE,
            FindingCode.UNRESOLVED_ACTIVITY_REFERENCE,
            FindingCode.UNRESOLVED_RESULT_REFERENCE,
        }
    ]

    assert {(item.code, item.element_id, item.related_ids) for item in unresolved} == {
        (FindingCode.UNRESOLVED_OBJECTIVE_REFERENCE, "A1", ("O99",)),
        (FindingCode.UNRESOLVED_ACTIVITY_REFERENCE, "R1", ("A99",)),
        (FindingCode.UNRESOLVED_RESULT_REFERENCE, "I1", ("R99",)),
    }
    assert all(item.severity == FindingSeverity.ERROR for item in unresolved)


def test_duplicate_relationship_references_are_reported():
    concept = load_concept()
    activities = list(concept.preliminary_activities)
    activities[0] = activities[0].model_copy(update={"objective_ids": ["O1", "O1"]})

    findings = check_concept_consistency(
        concept.model_copy(update={"preliminary_activities": activities})
    )
    duplicate = next(item for item in findings if item.code == FindingCode.DUPLICATE_REFERENCE)

    assert duplicate.severity == FindingSeverity.ERROR
    assert duplicate.element_id == "A1"
    assert duplicate.related_ids == ("O1",)


def test_disconnected_objectives_activities_and_results_are_warnings():
    concept = load_concept()
    objectives = list(concept.objectives) + [concept.objectives[0].model_copy(update={"id": "O3"})]
    activities = list(concept.preliminary_activities) + [
        concept.preliminary_activities[0].model_copy(update={"id": "A4"})
    ]
    results = list(concept.expected_results) + [
        concept.expected_results[0].model_copy(update={"id": "R3"})
    ]
    mutated = concept.model_copy(
        update={
            "objectives": objectives,
            "preliminary_activities": activities,
            "expected_results": results,
        }
    )

    findings = check_concept_consistency(mutated)
    disconnected = {
        (item.code, item.element_id)
        for item in findings
        if item.code
        in {
            FindingCode.OBJECTIVE_WITHOUT_ACTIVITY,
            FindingCode.ACTIVITY_WITHOUT_RESULT,
            FindingCode.RESULT_WITHOUT_INDICATOR,
        }
    }

    assert disconnected == {
        (FindingCode.OBJECTIVE_WITHOUT_ACTIVITY, "O3"),
        (FindingCode.ACTIVITY_WITHOUT_RESULT, "A4"),
        (FindingCode.RESULT_WITHOUT_INDICATOR, "R3"),
    }
    assert all(
        item.severity == FindingSeverity.WARNING
        for item in findings
        if (item.code, item.element_id) in disconnected
    )


def test_empty_relationship_lists_are_reported():
    concept = load_concept()
    activities = list(concept.preliminary_activities)
    activities[0] = activities[0].model_copy(update={"objective_ids": []})
    results = list(concept.expected_results)
    results[0] = results[0].model_copy(update={"activity_ids": []})
    indicators = list(concept.proposed_indicators)
    indicators[0] = indicators[0].model_copy(update={"result_ids": []})
    mutated = concept.model_copy(
        update={
            "preliminary_activities": activities,
            "expected_results": results,
            "proposed_indicators": indicators,
        }
    )

    findings = check_concept_consistency(mutated)
    missing_links = {
        (item.code, item.element_id)
        for item in findings
        if item.code
        in {
            FindingCode.ACTIVITY_WITHOUT_OBJECTIVE,
            FindingCode.RESULT_WITHOUT_ACTIVITY,
            FindingCode.INDICATOR_WITHOUT_RESULT,
        }
    }

    assert missing_links == {
        (FindingCode.ACTIVITY_WITHOUT_OBJECTIVE, "A1"),
        (FindingCode.RESULT_WITHOUT_ACTIVITY, "R1"),
        (FindingCode.INDICATOR_WITHOUT_RESULT, "I1"),
    }


def test_findings_are_deterministic_and_serializable():
    concept = load_concept()
    objectives = list(concept.objectives) + [concept.objectives[0].model_copy(update={"id": "O3"})]
    mutated = concept.model_copy(update={"objectives": objectives})

    first = check_concept_consistency(mutated)
    second = check_concept_consistency(mutated)

    assert first == second
    assert all(isinstance(item, ConsistencyFinding) for item in first)
    assert all(
        set(item.to_dict()) == {"code", "severity", "message", "element_id", "related_ids"}
        for item in first
    )