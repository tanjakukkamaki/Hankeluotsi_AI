import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from hankeluotsi.repository import (
    ApprovedProjectLocked,
    ExportNotApproved,
    IdempotencyConflict,
    InvalidTransition,
    ProjectNotFound,
    ProjectRepository,
    ProjectState,
    UnsupportedSchemaVersion,
)
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class DraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str


class ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths: list[str]
    overall_assessment: str


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def idea_payload() -> dict:
    return load_fixture("project_idea.json")


def concept_payload() -> dict:
    return load_fixture("concept_paper.json")


def make_repository(tmp_path: Path) -> ProjectRepository:
    return ProjectRepository(tmp_path / "test-projects.sqlite3")


def create_project(repository: ProjectRepository, operation_id: str = "create-1"):
    return repository.create_project(idea_payload(), operation_id=operation_id)


def save_concept(repository: ProjectRepository, project_id: str, operation_id: str = "concept-1"):
    return repository.save_concept(
        project_id, concept_payload(), operation_id=operation_id
    )


def save_draft(repository: ProjectRepository, project_id: str, operation_id: str = "draft-1", summary="Fictional draft"):
    return repository.save_draft(
        project_id,
        DraftPayload(title="Digital practice labs", summary=summary),
        model_type=DraftPayload,
        operation_id=operation_id,
    )


def save_review(repository: ProjectRepository, project_id: str, operation_id: str = "review-1"):
    return repository.save_review(
        project_id,
        ReviewPayload(strengths=["Clear fictional objective"], overall_assessment="Promising draft"),
        model_type=ReviewPayload,
        deterministic_findings=[{"code": "MISSING_DETAIL", "message": "Clarify follow-up timing."}],
        operation_id=operation_id,
    )


def move_to_reviewed(repository: ProjectRepository):
    project = create_project(repository)
    project = save_concept(repository, project.project_id)
    project = save_draft(repository, project.project_id)
    return save_review(repository, project.project_id)


def test_create_load_and_list_projects_use_fictional_validated_data(tmp_path):
    repository = make_repository(tmp_path)

    created = create_project(repository)
    loaded = repository.load_project(created.project_id)

    assert created.state == ProjectState.CREATED
    assert created.schema_version == 1
    assert isinstance(loaded.idea, ProjectIdea)
    assert loaded.idea.title == idea_payload()["title"]
    assert loaded.concept is None
    assert [item.project_id for item in repository.list_projects()] == [created.project_id]


def test_create_is_idempotent_for_repeated_operation_id(tmp_path):
    repository = make_repository(tmp_path)

    first = create_project(repository, operation_id="same-create")
    repeated = repository.create_project(idea_payload(), operation_id="same-create")

    assert repeated.project_id == first.project_id
    assert len(repository.list_projects()) == 1


def test_reusing_operation_id_for_different_payload_is_rejected(tmp_path):
    repository = make_repository(tmp_path)
    create_project(repository, operation_id="create-key")
    changed_idea = idea_payload()
    changed_idea["title"] = "Different fictional project"

    with pytest.raises(IdempotencyConflict):
        repository.create_project(changed_idea, operation_id="create-key")

    assert len(repository.list_projects()) == 1


def test_invalid_idea_does_not_create_project(tmp_path):
    repository = make_repository(tmp_path)
    invalid_idea = idea_payload()
    invalid_idea["target_groups"] = []

    with pytest.raises(ValidationError):
        repository.create_project(invalid_idea, operation_id="invalid-create")

    assert repository.list_projects() == []


def test_invalid_concept_cannot_overwrite_saved_valid_concept(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)
    valid_record = save_concept(repository, project.project_id)
    invalid_concept = concept_payload()
    invalid_concept["objectives"] = []

    with pytest.raises(ValidationError):
        repository.save_concept(
            project.project_id, invalid_concept, operation_id="invalid-concept"
        )

    unchanged = repository.load_project(project.project_id)
    assert unchanged.state == ProjectState.CONCEPT_READY
    assert unchanged.concept == valid_record.concept


def test_stage_transitions_require_prior_valid_stages(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)

    with pytest.raises(InvalidTransition):
        save_draft(repository, project.project_id)
    with pytest.raises(InvalidTransition):
        save_review(repository, project.project_id)
    with pytest.raises(InvalidTransition):
        repository.approve_project(project.project_id, operation_id="early-approval")

    concept = save_concept(repository, project.project_id)
    draft = save_draft(repository, project.project_id)
    reviewed = save_review(repository, project.project_id)

    assert concept.state == ProjectState.CONCEPT_READY
    assert draft.state == ProjectState.DRAFT_READY
    assert reviewed.state == ProjectState.REVIEWED


def test_concept_regeneration_atomically_invalidates_draft_and_review(tmp_path):
    repository = make_repository(tmp_path)
    reviewed = move_to_reviewed(repository)
    revised_concept = concept_payload()
    revised_concept["background_need"] = "Revised fictional need statement."

    regenerated = repository.save_concept(
        reviewed.project_id,
        revised_concept,
        operation_id="concept-regeneration",
    )

    assert regenerated.state == ProjectState.CONCEPT_READY
    assert regenerated.concept.background_need == revised_concept["background_need"]
    assert regenerated.draft is None
    assert regenerated.review is None
    assert regenerated.deterministic_findings is None


def test_idea_regeneration_invalidates_all_derived_stages(tmp_path):
    repository = make_repository(tmp_path)
    reviewed = move_to_reviewed(repository)
    revised_idea = idea_payload()
    revised_idea["expected_change"] = "A revised fictional expected change."

    updated = repository.save_idea(
        reviewed.project_id, revised_idea, operation_id="idea-regeneration"
    )

    assert updated.state == ProjectState.CREATED
    assert updated.idea.expected_change == revised_idea["expected_change"]
    assert updated.concept is None
    assert updated.draft is None
    assert updated.review is None
    assert updated.deterministic_findings is None


def test_draft_regeneration_invalidates_review_and_findings(tmp_path):
    repository = make_repository(tmp_path)
    reviewed = move_to_reviewed(repository)

    regenerated = save_draft(
        repository,
        reviewed.project_id,
        operation_id="draft-regeneration",
        summary="Revised fictional draft",
    )

    assert regenerated.state == ProjectState.DRAFT_READY
    assert regenerated.draft["summary"] == "Revised fictional draft"
    assert regenerated.review is None
    assert regenerated.deterministic_findings is None


def test_repeated_stage_operation_is_idempotent_and_different_payload_conflicts(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)
    save_concept(repository, project.project_id)
    first = save_draft(repository, project.project_id, operation_id="stable-draft")
    replay = save_draft(repository, project.project_id, operation_id="stable-draft")

    assert replay.draft == first.draft
    with pytest.raises(IdempotencyConflict):
        save_draft(
            repository,
            project.project_id,
            operation_id="stable-draft",
            summary="Different content under same operation key",
        )
    assert repository.load_project(project.project_id).draft == first.draft


def test_review_and_approval_lock_project_and_export_requires_approval(tmp_path):
    repository = make_repository(tmp_path)
    reviewed = move_to_reviewed(repository)

    with pytest.raises(ExportNotApproved):
        repository.load_for_export(reviewed.project_id)

    approved = repository.approve_project(reviewed.project_id, operation_id="approve-1")

    assert approved.state == ProjectState.APPROVED
    assert approved.approved_at is not None
    assert repository.load_for_export(reviewed.project_id) == approved
    with pytest.raises(ApprovedProjectLocked):
        repository.save_concept(
            reviewed.project_id, concept_payload(), operation_id="after-approval"
        )
    with pytest.raises(ApprovedProjectLocked):
        repository.save_idea(
            reviewed.project_id, idea_payload(), operation_id="edit-approved"
        )
    with pytest.raises(ApprovedProjectLocked):
        repository.approve_project(reviewed.project_id, operation_id="approve-again")


def test_repeated_approval_with_same_operation_id_returns_approved_record(tmp_path):
    repository = make_repository(tmp_path)
    reviewed = move_to_reviewed(repository)

    approved = repository.approve_project(reviewed.project_id, operation_id="approve-idempotent")
    replay = repository.approve_project(reviewed.project_id, operation_id="approve-idempotent")

    assert replay == approved


def test_invalid_draft_model_does_not_overwrite_existing_draft(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)
    save_concept(repository, project.project_id)
    existing = save_draft(repository, project.project_id)

    with pytest.raises(ValidationError):
        repository.save_draft(
            project.project_id,
            {"title": "Invalid fictional draft", "unexpected": "extra"},
            model_type=DraftPayload,
            operation_id="invalid-draft",
        )

    assert repository.load_project(project.project_id).draft == existing.draft


def test_failed_sql_update_rolls_back_without_recording_operation(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_concept_update BEFORE UPDATE OF concept_json ON projects
            WHEN NEW.concept_json IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'simulated database failure'); END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="simulated database failure"):
        save_concept(repository, project.project_id, operation_id="rollback-concept")

    unchanged = repository.load_project(project.project_id)
    assert unchanged.state == ProjectState.CREATED
    assert unchanged.concept is None

    with sqlite3.connect(repository.database_path) as connection:
        operation_count = connection.execute(
            "SELECT COUNT(*) FROM operations WHERE operation_id = 'rollback-concept'"
        ).fetchone()[0]
    assert operation_count == 0


def test_unsupported_project_schema_version_is_rejected(tmp_path):
    repository = make_repository(tmp_path)
    project = create_project(repository)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE projects SET schema_version = 2 WHERE project_id = ?",
            (project.project_id,),
        )

    with pytest.raises(UnsupportedSchemaVersion, match="not supported"):
        repository.load_project(project.project_id)


def test_missing_project_raises_clear_error(tmp_path):
    repository = make_repository(tmp_path)

    with pytest.raises(ProjectNotFound, match="project not found"):
        repository.load_project("missing-project")