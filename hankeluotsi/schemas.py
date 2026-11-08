from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ObjectiveId = Annotated[str, StringConstraints(pattern=r"^O[1-9]\d*$")]
ActivityId = Annotated[str, StringConstraints(pattern=r"^A[1-9]\d*$")]
ResultId = Annotated[str, StringConstraints(pattern=r"^R[1-9]\d*$")]
IndicatorId = Annotated[str, StringConstraints(pattern=r"^I[1-9]\d*$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionedModel(StrictModel):
    schema_version: Literal[1] = 1


class ProjectIdea(VersionedModel):
    title: NonBlank
    development_need: NonBlank
    target_groups: list[NonBlank] = Field(min_length=1)
    expected_change: NonBlank
    geography: NonBlank
    partners: list[NonBlank] | None = None
    funding_context: NonBlank | None = None


class Objective(StrictModel):
    id: ObjectiveId
    description: NonBlank


class PreliminaryActivity(StrictModel):
    id: ActivityId
    description: NonBlank
    objective_ids: list[ObjectiveId] = Field(min_length=1)


class ExpectedResult(StrictModel):
    id: ResultId
    description: NonBlank
    activity_ids: list[ActivityId] = Field(min_length=1)


class ProposedIndicator(StrictModel):
    id: IndicatorId
    description: NonBlank
    result_ids: list[ResultId] = Field(min_length=1)
    measurement_method: NonBlank


class ConceptPaper(VersionedModel):
    background_need: NonBlank
    objectives: list[Objective] = Field(min_length=1)
    target_groups: list[NonBlank] = Field(min_length=1)
    preliminary_activities: list[PreliminaryActivity] = Field(min_length=1)
    expected_results: list[ExpectedResult] = Field(min_length=1)
    proposed_indicators: list[ProposedIndicator] = Field(min_length=1)
    assumptions: list[NonBlank] = Field(default_factory=list)
    open_questions: list[NonBlank] = Field(default_factory=list)
