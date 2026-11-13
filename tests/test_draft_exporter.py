"""Approved-only Markdown preserves human-reviewed content without executable markup."""

import json
from pathlib import Path

import pytest

from hankeluotsi.draft_exporter import DISCLAIMER, export_approved_markdown
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.draft_workflow import WorkflowService
from hankeluotsi.repository import ExportNotApproved, ProjectRepository


DATA = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def reviewed(tmp_path, draft=None):
    repository = ProjectRepository(tmp_path / "export.sqlite3")
    project = repository.create_project(fixture("project_idea.json"), operation_id="idea")
    repository.save_concept(project.project_id, fixture("concept_paper.json"), operation_id="concept")
    repository.save_draft(project.project_id, draft or fixture("application_draft.json"),
        model_type=ApplicationDraft, operation_id="draft")
    repository.save_review(project.project_id, fixture("review_report.json"), model_type=ReviewReport,
        deterministic_findings=[], operation_id="review")
    return repository, project


def test_unapproved_export_is_blocked_before_document_rendering(tmp_path):
    repository, project = reviewed(tmp_path)
    with pytest.raises(ExportNotApproved):
        export_approved_markdown(repository, project.project_id)


@pytest.mark.parametrize("language,heading", [("fi", "## Hankkeen yhteenveto"), ("en", "## Project summary")])
def test_approved_export_contains_full_document_review_disclaimer_and_ids(tmp_path, language, heading):
    repository, project = reviewed(tmp_path)
    WorkflowService(repository).approve(project.project_id, operation_id="approve",
        expected_source=repository.source_fingerprint(project.project_id))
    before = repository.load_project(project.project_id)
    markdown = export_approved_markdown(repository, project.project_id, language=language)
    assert DISCLAIMER in markdown and heading in markdown
    for expected in ("O1", "A1", "R1", "I1", "WP1", "Facilitator"):
        assert expected in markdown
    assert "denominator is defined" in markdown
    assert "Longer-term impact" in markdown if language == "en" else "Pitkän aikavälin vaikutukset" in markdown
    assert repository.load_project(project.project_id) == before


def test_export_escapes_html_and_active_markdown_in_generated_text(tmp_path):
    draft = fixture("application_draft.json")
    draft["project_summary"] = '<script>alert("fictional")</script> [run](javascript:alert(1))\n# forged heading\n```html'
    repository, project = reviewed(tmp_path, draft)
    WorkflowService(repository).approve(project.project_id, operation_id="approve",
        expected_source=repository.source_fingerprint(project.project_id))
    markdown = export_approved_markdown(repository, project.project_id)
    assert "<script>" not in markdown and "&lt;script&gt;" in markdown
    assert "[run](javascript:" not in markdown and "\\[run\\]\\(javascript:" in markdown
    assert "\n# forged heading" not in markdown and "\n\\# forged heading" in markdown
    assert "```html" not in markdown


def test_export_rechecks_persisted_findings_even_if_generic_approval_was_used(tmp_path):
    repository, project = reviewed(tmp_path)
    repository.save_review(project.project_id, fixture("review_report.json"), model_type=ReviewReport,
        deterministic_findings=[{"code": "FORGED", "message": "Not the actual deterministic result"}], operation_id="forged")
    repository.approve_project(project.project_id, operation_id="generic-approval")
    with pytest.raises(ValueError, match="Current validated draft"):
        export_approved_markdown(repository, project.project_id)
