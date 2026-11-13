"""Additive, bounded draft/review contracts; existing concept records are unchanged."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from hankeluotsi.schemas import (
    ActivityId,
    ExpectedResult,
    NonBlank,
    Objective,
    ObjectiveId,
    ProposedIndicator,
    StrictModel,
)


WorkPackageId = Annotated[str, StringConstraints(pattern=r"^WP[1-9]\d*$")]
DraftText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1800)]


class DraftVersionedModel(StrictModel):
    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def supported_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("unsupported draft/review schema version")
        return value


class WorkPackage(StrictModel):
    id: WorkPackageId
    description: DraftText
    objective_ids: list[ObjectiveId] = Field(min_length=1, max_length=3)


class DraftActivity(StrictModel):
    id: ActivityId
    description: DraftText
    objective_ids: list[ObjectiveId] = Field(min_length=1, max_length=3)
    work_package_id: WorkPackageId


class PartnerRole(StrictModel):
    partner: DraftText
    role: DraftText
    status: Literal["provided", "proposed", "unknown"]


class TimelineEntry(StrictModel):
    work_package_id: WorkPackageId
    period: DraftText


class DraftRisk(StrictModel):
    description: DraftText
    mitigation: DraftText


class GenerationMetadata(StrictModel):
    provider: NonBlank
    model: NonBlank
    prompt_version: NonBlank
    finish_reason: str = "unknown"
    incomplete_output: bool = True


class ApplicationDraft(DraftVersionedModel):
    generation_metadata: GenerationMetadata | None = None
    project_summary: DraftText
    background_need: DraftText
    target_groups: list[NonBlank] = Field(min_length=1, max_length=5)
    beneficiaries: list[NonBlank] = Field(min_length=1, max_length=5)
    general_objective: DraftText
    objectives: list[Objective] = Field(min_length=1, max_length=3)
    work_packages: list[WorkPackage] = Field(min_length=1, max_length=3)
    activities: list[DraftActivity] = Field(min_length=1, max_length=6)
    outputs: list[NonBlank] = Field(min_length=1, max_length=6)
    expected_results: list[ExpectedResult] = Field(min_length=1, max_length=4)
    proposed_indicators: list[ProposedIndicator] = Field(min_length=1, max_length=4)
    longer_term_impact: DraftText
    partner_roles: list[PartnerRole] = Field(max_length=5)
    timeline: list[TimelineEntry] = Field(min_length=1, max_length=6)
    risks: list[DraftRisk] = Field(min_length=1, max_length=5)
    assumptions: list[NonBlank] = Field(max_length=6)
    sustainability: DraftText
    open_questions: list[NonBlank] = Field(max_length=8)


class ReviewFinding(StrictModel):
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    evidence_quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
    observation: DraftText
    suggestion: DraftText
    severity: Literal["major", "minor", "question"]


class ReviewReport(DraftVersionedModel):
    generation_metadata: GenerationMetadata | None = None
    strengths: list[NonBlank] = Field(min_length=1, max_length=5)
    findings: list[ReviewFinding] = Field(max_length=12)
    missing_information: list[NonBlank] = Field(max_length=8)
    overall_assessment: DraftText
    uncertainties: list[NonBlank] = Field(min_length=1, max_length=6)
