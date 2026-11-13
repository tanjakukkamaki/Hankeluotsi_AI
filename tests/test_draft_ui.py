"""Complete draft/review UI with fictional data, fake providers and temporary SQLite."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
import pytest
from streamlit.testing.v1 import AppTest

from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.i18n import localize
from hankeluotsi.repository import ProjectState
from test_app import APP_PATH, create_saved_concept
from review_selection_fixture import selected_review_fixture


@pytest.fixture(autouse=True)
def prevent_live_calls(monkeypatch):
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=AssertionError("No network in workflow UI tests")))


def data(name):
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))


def generate(stage, user_input, response_model, **kwargs):
    payload = data("application_draft.json" if stage == "draft" else "review_report.json")
    if stage == "review":
        payload = selected_review_fixture(payload, user_input)
    return SimpleNamespace(data=response_model.model_validate(payload), provider="local", model="fictional-local",
        prompt_version="fixture_" + stage, finish_reason="unknown", incomplete_output=True)


def open_project(tmp_path, monkeypatch, language="en"):
    db = tmp_path / "workflow.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(db))
    repository, project = create_saved_concept(db)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    app.selectbox(key="ui_language").select(language).run()
    selector = "open_project_id" + ("_fi" if language == "fi" else "")
    app.selectbox(key=selector).select(project.project_id).run()
    return app, repository, project, "workflow-" + project.project_id


def approval_checkbox(app, prefix):
    return next(x for x in app.checkbox if str(x.key).startswith(prefix + "-approve-consent-"))


def cloud_checkbox(app, prefix):
    return next(x for x in app.checkbox if str(x.key).startswith(prefix + "-cloud-consent-"))


@pytest.mark.parametrize("language", ["fi", "en"])
def test_full_workflow_human_approval_export_and_rerun(language, tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, original, prefix = open_project(tmp_path, monkeypatch, language)
        assert not app.exception
        assert app.button(key=prefix + "-draft").label == localize("Generate draft", language)
        model.assert_not_called()
        app.button(key=prefix + "-draft").click().run()
        assert not app.exception
        current = repo.load_project(original.project_id)
        assert current.state == ProjectState.DRAFT_READY and current.concept == original.concept
        assert ApplicationDraft.model_validate(current.draft)
        assert app.button(key=prefix + "-draft").disabled
        app.run()
        assert model.call_count == 1
        app.button(key=prefix + "-review").click().run()
        assert not app.exception
        assert repo.load_project(original.project_id).state == ProjectState.REVIEWED
        assert app.button(key=prefix + "-approve").disabled
        approval_checkbox(app, prefix).check().run()
        app.button(key=prefix + "-approve").click().run()
        assert not app.exception
        approved = repo.load_project(original.project_id)
        assert approved.state == ProjectState.APPROVED
        assert any(x.proto.label == localize("Download approved Markdown", language) for x in app.get("download_button"))
        app.run()
        app.selectbox(key="ui_language").select("en" if language == "fi" else "fi").run()
        assert repo.load_project(original.project_id) == approved
        assert model.call_count == 2
        assert not any(x.key == prefix + "-draft" for x in app.button)


def test_missing_cloud_key_and_stale_cloud_consent_cannot_generate(tmp_path, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with patch("hankeluotsi.draft_workflow.StageClient.generate") as model:
        app, repo, project, prefix = open_project(tmp_path, monkeypatch)
        app.selectbox(key=prefix + "-provider").select("mistral").run()
        assert cloud_checkbox(app, prefix).disabled and app.button(key=prefix + "-draft").disabled
        monkeypatch.setenv("MISTRAL_API_KEY", "fictional-ui-key")
        monkeypatch.setenv("MISTRAL_MODEL", "fictional-ui-model")
        app.run()
        cloud_checkbox(app, prefix).check().run()
        changed = project.concept.model_copy(update={"background_need": "New fictional source"})
        repo.save_concept(project.project_id, changed, operation_id="external-change")
        app.button(key=prefix + "-draft").click().run()
        assert not app.exception and not cloud_checkbox(app, prefix).value
        model.assert_not_called()
        assert repo.load_project(project.project_id).draft is None


def test_new_review_revokes_old_human_approval_consent(tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate):
        app, repo, project, prefix = open_project(tmp_path, monkeypatch)
        app.button(key=prefix + "-draft").click().run()
        app.button(key=prefix + "-review").click().run()
        approval_checkbox(app, prefix).check().run()
        latest = repo.load_project(project.project_id)
        review = ReviewReport.model_validate(latest.review).model_copy(update={"strengths": ["Changed review"]})
        repo.save_review(project.project_id, review, model_type=ReviewReport,
            deterministic_findings=latest.deterministic_findings, operation_id="external-review")
        app.button(key=prefix + "-approve").click().run()
        assert not app.exception
        assert repo.load_project(project.project_id).state == ProjectState.REVIEWED
        assert not approval_checkbox(app, prefix).value


def test_generation_timeout_preserves_reviewed_draft_and_requires_explicit_replacement(tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate):
        app, repo, project, prefix = open_project(tmp_path, monkeypatch)
        app.button(key=prefix + "-draft").click().run()
        app.button(key=prefix + "-review").click().run()
    before = repo.load_project(project.project_id)
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=TimeoutError("untrusted error detail")) as model:
        assert app.button(key=prefix + "-draft").disabled
        next(x for x in app.checkbox if str(x.key).startswith(prefix + "-replace-") and "review" not in str(x.key)).check().run()
        app.button(key=prefix + "-draft").click().run()
        assert not app.exception and repo.load_project(project.project_id) == before
        assert any("previous saved document was preserved" in x.value for x in app.error)
        assert all("untrusted error detail" not in x.value for x in app.error)
        app.run()
        model.assert_called_once()


def test_successful_regeneration_requires_fresh_replacement_confirmation(tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, project, prefix = open_project(tmp_path, monkeypatch)
        app.button(key=prefix + "-draft").click().run()
        app.button(key=prefix + "-review").click().run()
        next(x for x in app.checkbox if str(x.key).startswith(prefix + "-replace-") and "review" not in str(x.key)).check().run()
        app.button(key=prefix + "-draft").click().run()
        assert not app.exception and model.call_count == 3
        current = repo.load_project(project.project_id)
        assert current.state == ProjectState.DRAFT_READY and current.review is None
        assert app.button(key=prefix + "-draft").disabled
        from streamlit.testing.v1.errors import AppTestError
        with pytest.raises(AppTestError, match="disabled"):
            app.button(key=prefix + "-draft").click()
        app.run()
        assert model.call_count == 3
