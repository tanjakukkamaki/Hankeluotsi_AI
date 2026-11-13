"""Deterministic draft references and exact, field-scoped review evidence checks."""

from collections import Counter
from dataclasses import dataclass

from hankeluotsi.consistency import FindingSeverity, check_concept_consistency
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.schemas import ConceptPaper, PreliminaryActivity


@dataclass(frozen=True)
class DraftFinding:
    code: str
    severity: FindingSeverity
    message: str
    element_id: str | None = None
    related_ids: tuple[str, ...] = ()

    def to_dict(self):
        return {"code": self.code, "severity": self.severity.value, "message": self.message,
                "element_id": self.element_id, "related_ids": list(self.related_ids)}


def check_draft_consistency(draft: ApplicationDraft) -> list[DraftFinding]:
    # Reuse the tested O -> A -> R -> I graph rules, retaining their stable codes.
    concept = ConceptPaper(
        background_need=draft.background_need, objectives=draft.objectives,
        target_groups=draft.target_groups,
        preliminary_activities=[PreliminaryActivity(id=a.id, description=a.description,
            objective_ids=a.objective_ids) for a in draft.activities],
        expected_results=draft.expected_results, proposed_indicators=draft.proposed_indicators,
        assumptions=draft.assumptions, open_questions=draft.open_questions,
    )
    findings = [DraftFinding(f.code.value, f.severity, f.message.replace("this concept", "this draft"),
        f.element_id, f.related_ids) for f in check_concept_consistency(concept)]
    ids = {wp.id for wp in draft.work_packages}
    objectives = {o.id for o in draft.objectives}
    used = {a.work_package_id for a in draft.activities}
    timed = {entry.work_package_id for entry in draft.timeline}
    for identifier, count in Counter(wp.id for wp in draft.work_packages).items():
        if count > 1:
            findings.append(DraftFinding("DUPLICATE_WORK_PACKAGE_ID", FindingSeverity.ERROR,
                f"Work-package identifier {identifier} is used {count} times.", identifier))
    for wp in draft.work_packages:
        for identifier, count in Counter(wp.objective_ids).items():
            if count > 1:
                findings.append(DraftFinding("DUPLICATE_REFERENCE", FindingSeverity.ERROR,
                    f"Work package {wp.id} repeats objective {identifier}.", wp.id, (identifier,)))
            if identifier not in objectives:
                findings.append(DraftFinding("UNRESOLVED_OBJECTIVE_REFERENCE", FindingSeverity.ERROR,
                    f"Work package {wp.id} refers to undefined objective {identifier}.", wp.id, (identifier,)))
        if wp.id not in used:
            findings.append(DraftFinding("WORK_PACKAGE_WITHOUT_ACTIVITY", FindingSeverity.WARNING,
                f"Work package {wp.id} has no activity.", wp.id))
        if wp.id not in timed:
            findings.append(DraftFinding("WORK_PACKAGE_WITHOUT_TIMELINE", FindingSeverity.WARNING,
                f"Work package {wp.id} has no preliminary timeline entry.", wp.id))
    for activity in draft.activities:
        if activity.work_package_id not in ids:
            findings.append(DraftFinding("UNRESOLVED_WORK_PACKAGE_REFERENCE", FindingSeverity.ERROR,
                f"Activity {activity.id} refers to undefined work package {activity.work_package_id}.",
                activity.id, (activity.work_package_id,)))
        else:
            wp = next(wp for wp in draft.work_packages if wp.id == activity.work_package_id)
            if not set(activity.objective_ids) <= set(wp.objective_ids):
                findings.append(DraftFinding("ACTIVITY_WORK_PACKAGE_OBJECTIVE_MISMATCH", FindingSeverity.WARNING,
                    f"Activity {activity.id} links objectives outside its work package {wp.id}.", activity.id,
                    tuple(identifier for identifier in activity.objective_ids if identifier not in wp.objective_ids)))
    for entry in draft.timeline:
        if entry.work_package_id not in ids:
            findings.append(DraftFinding("UNRESOLVED_WORK_PACKAGE_REFERENCE", FindingSeverity.ERROR,
                f"Timeline refers to undefined work package {entry.work_package_id}.",
                "timeline", (entry.work_package_id,)))
    if not draft.partner_roles:
        findings.append(DraftFinding("PARTNER_ROLES_UNCONFIRMED", FindingSeverity.WARNING,
            "Partner roles are not supplied. Clarify relevant responsibilities; this is not a funding requirement.",
            "partner_roles"))
    return findings


def _human_text(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for child in value for text in _human_text(child)]
    if isinstance(value, dict):
        return [text for key, child in value.items()
            if key not in {"id", "objective_ids", "activity_ids", "result_ids", "work_package_id", "status"}
            for text in _human_text(child)]
    return []


def _reference_value(draft: ApplicationDraft, reference: str):
    values = draft.model_dump(mode="json")
    if reference in values and reference not in {"schema_version", "generation_metadata"}:
        return values[reference]
    entity_id, separator, field = reference.partition(".")
    candidates = [item for section in ("objectives", "work_packages", "activities", "expected_results",
        "proposed_indicators") for item in values[section] if item["id"] == entity_id]
    if len(candidates) != 1:
        raise ValueError("Review reference does not identify one unambiguous draft section or ID")
    candidate = candidates[0]
    if separator:
        if field not in candidate or field in {"id", "objective_ids", "activity_ids", "result_ids", "work_package_id"}:
            raise ValueError("Review reference does not identify a human-readable draft field")
        return candidate[field]
    return candidate


def evidence_text(draft: ApplicationDraft, reference: str) -> str:
    """Resolve one exact top-level section, entity ID, or ID.text_field reference."""
    return "\n".join(_human_text(_reference_value(draft, reference)))


def validate_review_evidence(draft: ApplicationDraft, review: ReviewReport) -> None:
    for finding in review.findings:
        fragments = _human_text(_reference_value(draft, finding.reference))
        if not any(finding.evidence_quote in source for source in fragments):
            raise ValueError("Review evidence quote is not an exact excerpt of the cited draft field")
