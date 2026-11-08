from collections import Counter
from dataclasses import dataclass
from enum import Enum

from hankeluotsi.schemas import ConceptPaper


class FindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class FindingCode(str, Enum):
    DUPLICATE_OBJECTIVE_ID = "DUPLICATE_OBJECTIVE_ID"
    DUPLICATE_ACTIVITY_ID = "DUPLICATE_ACTIVITY_ID"
    DUPLICATE_RESULT_ID = "DUPLICATE_RESULT_ID"
    DUPLICATE_INDICATOR_ID = "DUPLICATE_INDICATOR_ID"
    DUPLICATE_REFERENCE = "DUPLICATE_REFERENCE"
    UNRESOLVED_OBJECTIVE_REFERENCE = "UNRESOLVED_OBJECTIVE_REFERENCE"
    UNRESOLVED_ACTIVITY_REFERENCE = "UNRESOLVED_ACTIVITY_REFERENCE"
    UNRESOLVED_RESULT_REFERENCE = "UNRESOLVED_RESULT_REFERENCE"
    ACTIVITY_WITHOUT_OBJECTIVE = "ACTIVITY_WITHOUT_OBJECTIVE"
    RESULT_WITHOUT_ACTIVITY = "RESULT_WITHOUT_ACTIVITY"
    INDICATOR_WITHOUT_RESULT = "INDICATOR_WITHOUT_RESULT"
    OBJECTIVE_WITHOUT_ACTIVITY = "OBJECTIVE_WITHOUT_ACTIVITY"
    ACTIVITY_WITHOUT_RESULT = "ACTIVITY_WITHOUT_RESULT"
    RESULT_WITHOUT_INDICATOR = "RESULT_WITHOUT_INDICATOR"


@dataclass(frozen=True)
class ConsistencyFinding:
    code: FindingCode
    severity: FindingSeverity
    message: str
    element_id: str | None = None
    related_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, str | list[str] | None]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "element_id": self.element_id,
            "related_ids": list(self.related_ids),
        }


def _duplicate_ids(identifiers: list[str]) -> list[tuple[str, int]]:
    counts = Counter(identifiers)
    return [(identifier, count) for identifier, count in counts.items() if count > 1]


def _append_duplicate_id_findings(findings, items, code: FindingCode, label: str) -> None:
    for identifier, count in _duplicate_ids([item.id for item in items]):
        findings.append(
            ConsistencyFinding(
                code=code,
                severity=FindingSeverity.ERROR,
                element_id=identifier,
                message=f"{label} identifier {identifier} is used {count} times.",
            )
        )


def _append_reference_findings(
    findings: list[ConsistencyFinding],
    *,
    owner_id: str,
    owner_label: str,
    references: list[str],
    valid_ids: set[str],
    unresolved_code: FindingCode,
    target_label: str,
) -> None:
    for reference in dict.fromkeys(references):
        if reference not in valid_ids:
            findings.append(
                ConsistencyFinding(
                    code=unresolved_code,
                    severity=FindingSeverity.ERROR,
                    element_id=owner_id,
                    related_ids=(reference,),
                    message=(
                        f"{owner_label} {owner_id} refers to {target_label} {reference}, "
                        f"which is not defined in this concept."
                    ),
                )
            )


def _append_duplicate_reference_findings(
    findings: list[ConsistencyFinding],
    *,
    owner_id: str,
    owner_label: str,
    references: list[str],
    target_label: str,
) -> None:
    for reference, count in _duplicate_ids(references):
        findings.append(
            ConsistencyFinding(
                code=FindingCode.DUPLICATE_REFERENCE,
                severity=FindingSeverity.ERROR,
                element_id=owner_id,
                related_ids=(reference,),
                message=(
                    f"{owner_label} {owner_id} links to {target_label} {reference} "
                    f"{count} times."
                ),
            )
        )


def check_concept_consistency(concept: ConceptPaper) -> list[ConsistencyFinding]:
    """Check ID uniqueness and O→A→R→I references without interpreting programme rules."""
    findings: list[ConsistencyFinding] = []

    _append_duplicate_id_findings(
        findings,
        concept.objectives,
        FindingCode.DUPLICATE_OBJECTIVE_ID,
        "Objective",
    )
    _append_duplicate_id_findings(
        findings,
        concept.preliminary_activities,
        FindingCode.DUPLICATE_ACTIVITY_ID,
        "Activity",
    )
    _append_duplicate_id_findings(
        findings,
        concept.expected_results,
        FindingCode.DUPLICATE_RESULT_ID,
        "Result",
    )
    _append_duplicate_id_findings(
        findings,
        concept.proposed_indicators,
        FindingCode.DUPLICATE_INDICATOR_ID,
        "Indicator",
    )

    objective_ids = {item.id for item in concept.objectives}
    activity_ids = {item.id for item in concept.preliminary_activities}
    result_ids = {item.id for item in concept.expected_results}

    for activity in concept.preliminary_activities:
        if not activity.objective_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.ACTIVITY_WITHOUT_OBJECTIVE,
                    FindingSeverity.ERROR,
                    f"Activity {activity.id} is not linked to an objective.",
                    activity.id,
                )
            )
        _append_duplicate_reference_findings(
            findings,
            owner_id=activity.id,
            owner_label="Activity",
            references=activity.objective_ids,
            target_label="objective",
        )
        _append_reference_findings(
            findings,
            owner_id=activity.id,
            owner_label="Activity",
            references=activity.objective_ids,
            valid_ids=objective_ids,
            unresolved_code=FindingCode.UNRESOLVED_OBJECTIVE_REFERENCE,
            target_label="objective",
        )

    for result in concept.expected_results:
        if not result.activity_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.RESULT_WITHOUT_ACTIVITY,
                    FindingSeverity.ERROR,
                    f"Result {result.id} is not linked to an activity.",
                    result.id,
                )
            )
        _append_duplicate_reference_findings(
            findings,
            owner_id=result.id,
            owner_label="Result",
            references=result.activity_ids,
            target_label="activity",
        )
        _append_reference_findings(
            findings,
            owner_id=result.id,
            owner_label="Result",
            references=result.activity_ids,
            valid_ids=activity_ids,
            unresolved_code=FindingCode.UNRESOLVED_ACTIVITY_REFERENCE,
            target_label="activity",
        )

    for indicator in concept.proposed_indicators:
        if not indicator.result_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.INDICATOR_WITHOUT_RESULT,
                    FindingSeverity.ERROR,
                    f"Indicator {indicator.id} is not linked to a result.",
                    indicator.id,
                )
            )
        _append_duplicate_reference_findings(
            findings,
            owner_id=indicator.id,
            owner_label="Indicator",
            references=indicator.result_ids,
            target_label="result",
        )
        _append_reference_findings(
            findings,
            owner_id=indicator.id,
            owner_label="Indicator",
            references=indicator.result_ids,
            valid_ids=result_ids,
            unresolved_code=FindingCode.UNRESOLVED_RESULT_REFERENCE,
            target_label="result",
        )

    linked_objective_ids = {
        objective_id
        for activity in concept.preliminary_activities
        for objective_id in activity.objective_ids
        if objective_id in objective_ids
    }
    linked_activity_ids = {
        activity_id
        for result in concept.expected_results
        for activity_id in result.activity_ids
        if activity_id in activity_ids
    }
    linked_result_ids = {
        result_id
        for indicator in concept.proposed_indicators
        for result_id in indicator.result_ids
        if result_id in result_ids
    }

    for objective in concept.objectives:
        if objective.id not in linked_objective_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.OBJECTIVE_WITHOUT_ACTIVITY,
                    FindingSeverity.WARNING,
                    f"Objective {objective.id} has no activity linked to it.",
                    objective.id,
                )
            )
    for activity in concept.preliminary_activities:
        if activity.id not in linked_activity_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.ACTIVITY_WITHOUT_RESULT,
                    FindingSeverity.WARNING,
                    f"Activity {activity.id} is not linked from an expected result.",
                    activity.id,
                )
            )
    for result in concept.expected_results:
        if result.id not in linked_result_ids:
            findings.append(
                ConsistencyFinding(
                    FindingCode.RESULT_WITHOUT_INDICATOR,
                    FindingSeverity.WARNING,
                    f"Result {result.id} has no proposed indicator linked to it.",
                    result.id,
                )
            )

    return findings