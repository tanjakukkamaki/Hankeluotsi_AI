"""Atomic source guards without migrating or touching existing project databases."""

import json
from pathlib import Path

import pytest

from hankeluotsi.repository import IdempotencyConflict, ProjectRepository, StaleProjectError
from test_repository import DraftPayload, create_project, move_to_reviewed, save_concept


def test_stale_generation_does_not_overwrite_new_concept(tmp_path):
    repo = ProjectRepository(tmp_path / "test.sqlite3")
    project = save_concept(repo, create_project(repo).project_id)
    before = repo.source_fingerprint(project.project_id)
    changed = project.concept.model_copy(update={"background_need": "New fictional need"})
    repo.save_concept(project.project_id, changed, operation_id="new-concept")
    with pytest.raises(StaleProjectError):
        repo.save_draft(project.project_id, DraftPayload(title="Old", summary="Stale"),
            model_type=DraftPayload, operation_id="stale-draft", expected_source=before)
    assert repo.load_project(project.project_id).concept == changed
    assert repo.load_project(project.project_id).draft is None
    assert not repo.operation_completed(project.project_id, "stale-draft", "save_draft")


def test_completed_action_lookup_cannot_cross_project_or_action(tmp_path):
    repo = ProjectRepository(tmp_path / "test.sqlite3")
    first = create_project(repo)
    second = create_project(repo, "create-2")
    assert repo.operation_completed(first.project_id, "create-1", "create_project")
    for project, action in ((second.project_id, "create_project"), (first.project_id, "save_draft")):
        with pytest.raises(IdempotencyConflict):
            repo.operation_completed(project, "create-1", action)


def test_approval_requires_exact_reviewed_snapshot(tmp_path):
    repo = ProjectRepository(tmp_path / "test.sqlite3")
    project = move_to_reviewed(repo)
    fingerprint = repo.source_fingerprint(project.project_id)
    repo.save_draft(project.project_id, DraftPayload(title="new", summary="new"),
        model_type=DraftPayload, operation_id="new-draft")
    with pytest.raises(StaleProjectError):
        repo.approve_project(project.project_id, operation_id="approve-stale", expected_source=fingerprint)
    assert repo.load_project(project.project_id).approved_at is None


def test_fractional_stored_version_is_not_coerced_to_supported_version(tmp_path):
    import sqlite3
    from hankeluotsi.repository import UnsupportedSchemaVersion
    path = tmp_path / "test.sqlite3"
    repo = ProjectRepository(path)
    project = create_project(repo)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE projects SET schema_version=1.9 WHERE project_id=?", (project.project_id,))
    with pytest.raises(UnsupportedSchemaVersion):
        repo.load_project(project.project_id)
