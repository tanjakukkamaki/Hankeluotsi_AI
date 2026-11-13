"""Source-selected review citations. Models select IDs; application copies exact text."""

import hashlib
from itertools import zip_longest
from typing import Annotated

from pydantic import Field, StringConstraints

from hankeluotsi.draft_checks import validate_review_evidence
from hankeluotsi.draft_schemas import ApplicationDraft, DraftText, ReviewFinding, ReviewReport
from hankeluotsi.schemas import NonBlank, StrictModel


class EvidenceSelection(StrictModel):
    evidence_id: Annotated[str, StringConstraints(pattern=r"^E[1-9]\d*$")]
    observation: DraftText
    suggestion: DraftText
    severity: Annotated[str, StringConstraints(pattern=r"^(major|minor|question)$")]


class ReviewSelection(ReviewReport):
    findings: list[EvidenceSelection] = Field(max_length=12)
    uncertainties: list[NonBlank] = Field(min_length=1, max_length=5)


def _digest(draft):
    return hashlib.sha256(draft.model_dump_json().encode("utf-8")).hexdigest()


def _leaves(value, path=""):
    if isinstance(value, str):
        if value.strip():
            yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, path + "." + str(index))
    elif isinstance(value, dict):
        for field, item in value.items():
            if field not in {"id", "objective_ids", "activity_ids", "result_ids", "work_package_id", "status"}:
                yield from _leaves(item, path + "." + field)


def build_evidence_catalog(draft: ApplicationDraft, *, max_entries=48, max_characters=6000, max_excerpt=240):
    if not (1 <= max_entries <= 64 and 1 <= max_characters <= 12000 and 1 <= max_excerpt <= 500):
        raise ValueError("Evidence catalogue limits are out of bounds")
    groups = []
    entities = {"objectives", "work_packages", "activities", "expected_results", "proposed_indicators"}
    for field, value in draft.model_dump(mode="json").items():
        if field in {"schema_version", "generation_metadata"}:
            continue
        if field in entities:
            for item in value:
                groups.append([(item["id"], path, text) for path, text in _leaves(item, field + "." + item["id"])])
        else:
            groups.append([(field, path, text) for path, text in _leaves(value, field)])
    # Breadth first gives each section/entity an initial citation before extra detail.
    candidates = [item for row in zip_longest(*groups) for item in row if item is not None]
    entries, size, partial = [], 0, False
    for reference, location, text in candidates:
        quote = text[:max_excerpt].rstrip()
        if len(entries) >= max_entries or size + len(quote) > max_characters:
            partial = True
            continue
        partial = partial or len(quote) < len(text)
        entries.append({"evidence_id": "E" + str(len(entries) + 1), "reference": reference,
            "location": location, "quote": quote})
        size += len(quote)
    return {"version": "review_evidence_v1", "draft_sha256": _digest(draft), "partial": partial, "entries": entries}


def resolve_review_selection(draft: ApplicationDraft, selection: ReviewSelection, catalogue, *, language="en"):
    if language not in ("fi", "en") or catalogue.get("draft_sha256") != _digest(draft):
        raise ValueError("Evidence catalogue does not match the current source")
    entries = catalogue["entries"]
    index = {item["evidence_id"]: item for item in entries}
    if len(index) != len(entries):
        raise ValueError("Evidence catalogue has duplicate selectors")
    findings = []
    for item in selection.findings:
        if item.evidence_id not in index:
            raise ValueError("Review selected evidence outside the supplied catalogue")
        source = index[item.evidence_id]
        findings.append(ReviewFinding(reference=source["reference"], evidence_quote=source["quote"],
            observation=item.observation, suggestion=item.suggestion, severity=item.severity))
    notice = ("Sovellus poimi lainaukset lähteestä; AI-havaintojen oikeellisuutta ei ole vahvistettu."
        if language == "fi" else "The application copied source quotations; AI observations remain unverified suggestions.")
    if catalogue["partial"]:
        notice += (" Arvio perustuu rajattuihin otteisiin eikä välttämättä kata kaikkea tekstiä."
            if language == "fi" else " Review used bounded excerpts and may not cover all source text.")
    payload = selection.model_dump(mode="json", exclude={"findings"})
    payload["findings"] = [f.model_dump(mode="json") for f in findings]
    payload["uncertainties"] = [*selection.uncertainties, notice]
    review = ReviewReport.model_validate(payload)
    # This exact, field-scoped validation is retained, including after application resolution.
    validate_review_evidence(draft, review)
    return review
