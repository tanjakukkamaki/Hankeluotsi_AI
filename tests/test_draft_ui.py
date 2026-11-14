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
    if app.radio(key=prefix + "-finalization-choice").value != "approve":
        app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
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
        app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
        assert app.button(key=prefix + "-approve").disabled
        approval_checkbox(app, prefix).check().run()
        app.button(key=prefix + "-approve").click().run()
        assert not app.exception
        approved = repo.load_project(original.project_id)
        assert approved.state == ProjectState.APPROVED
        selector = "open_project_id" + ("_fi" if language == "fi" else "")
        assert app.selectbox(key=selector).value == original.project_id
        assert any(x.proto.label == localize("Download approved draft", language) for x in app.get("download_button"))
        app.run()
        app.selectbox(key="ui_language").select("en" if language == "fi" else "fi").run()
        selector = "open_project_id" + ("_fi" if language == "en" else "")
        assert app.selectbox(key=selector).value == original.project_id
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


def reviewed_project(tmp_path, monkeypatch, language="en"):
    app, repo, project, prefix = open_project(tmp_path, monkeypatch, language)
    app.button(key=prefix + "-draft").click().run()
    app.button(key=prefix + "-review").click().run()
    assert not app.exception
    return app, repo, project, prefix


@pytest.mark.parametrize("language", ["fi", "en"])
def test_finalization_summary_and_technical_options_have_clear_boundaries(tmp_path, monkeypatch, language):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, project, prefix = reviewed_project(tmp_path, monkeypatch, language)
        before = repo.load_project(project.project_id)
        tr = lambda text: localize(text, language)
        panel = app.tabs[3]
        advanced = next(x for x in panel.expander if x.label == tr("Advanced options"))
        details = next(x for x in panel.expander if x.label == tr("Review details and evidence"))
        assert not advanced.proto.expanded and not details.proto.expanded
        assert advanced.selectbox(key=prefix + "-provider")
        assert advanced.button(key=prefix + "-draft").disabled
        assert advanced.button(key=prefix + "-review").disabled
        assert any("No draft history" in x.value or "Luonnoshistoriaa" in x.value for x in advanced.warning)
        assert any(x.value == tr("AI review summary") for x in panel.subheader)
        assert any(x.value == before.review["overall_assessment"] for x in details.text)
        assert any(x.value == before.review["findings"][0]["evidence_quote"] for x in details.text)
        assert not details.radio and not advanced.radio
        assert app.radio(key=prefix + "-finalization-choice").options == [tr("Improve the draft"), tr("Approve and export")]
        assert any("editing is not available" in x.value or "suora muokkaus" in x.value for x in panel.info)
        assert not any(x.label in ("Edit", "Edit draft", "Muokkaa", "Muokkaa luonnosta") for x in panel.button)
        app.run()
        assert model.call_count == 2 and repo.load_project(project.project_id) == before


@pytest.mark.parametrize("language", ["fi", "en"])
def test_approval_choice_survives_navigation_but_leaving_it_requires_new_confirmation(tmp_path, monkeypatch, language):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, project, prefix = reviewed_project(tmp_path, monkeypatch, language)
        approval_checkbox(app, prefix).check().run()
        before = repo.load_project(project.project_id)
        for stage, index in (("concept", 1), ("idea", 0), ("explore", 2), ("draft", 3)):
            app.session_state["workflow_stage"] = stage
            app.run()
            assert app.get("tab_container")[0].proto.tab_container.default_tab_index == index
            assert app.radio(key=prefix + "-finalization-choice").value == "approve"
            assert approval_checkbox(app, prefix).value
            assert repo.load_project(project.project_id) == before
        app.selectbox(key="ui_language").select("en" if language == "fi" else "fi").run()
        assert app.radio(key=prefix + "-finalization-choice").value == "approve"
        assert approval_checkbox(app, prefix).value
        app.radio(key=prefix + "-finalization-choice").set_value("improve").run()
        app.run()
        assert not any(str(x.key).startswith(prefix + "-approve-consent-") for x in app.checkbox)
        assert repo.load_project(project.project_id) == before
        app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
        assert not approval_checkbox(app, prefix).value
        assert app.button(key=prefix + "-approve").disabled
        approval_checkbox(app, prefix).check().run()
        app.button(key=prefix + "-approve").click().run()
        assert not app.exception
        approved = repo.load_project(project.project_id)
        assert approved.state == ProjectState.APPROVED
        assert approved.draft == before.draft and approved.review == before.review
        assert not any(x.key in (prefix + "-draft", prefix + "-review", prefix + "-approve") for x in app.button)
        assert not any(x.label == localize("Advanced options", app.selectbox(key="ui_language").value) for x in app.tabs[3].expander)
        assert any(x.proto.label == localize("Download approved draft", app.selectbox(key="ui_language").value) for x in app.tabs[3].get("download_button"))
        app.run()
        assert repo.load_project(project.project_id) == approved and model.call_count == 2


def test_approval_requires_a_review_and_structural_errors_disable_it(tmp_path, monkeypatch):
    def invalid_links(stage, user_input, response_model, **kwargs):
        result = generate(stage, user_input, response_model, **kwargs)
        if stage == "draft":
            activity = result.data.activities[0].model_copy(update={"objective_ids": ["O99"]})
            result.data = result.data.model_copy(update={"activities": [activity]})
        return result

    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=invalid_links) as model:
        app, repo, project, prefix = open_project(tmp_path, monkeypatch)
        app.button(key=prefix + "-draft").click().run()
        app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
        assert approval_checkbox(app, prefix).disabled and app.button(key=prefix + "-approve").disabled
        assert repo.load_project(project.project_id).state == ProjectState.DRAFT_READY
        app.radio(key=prefix + "-finalization-choice").set_value("improve").run()
        app.button(key=prefix + "-review").click().run()
        app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
        before = repo.load_project(project.project_id)
        assert before.state == ProjectState.REVIEWED
        assert approval_checkbox(app, prefix).disabled and app.button(key=prefix + "-approve").disabled
        assert any("Approval is blocked by" in x.value for x in app.error)
        app.run()
        assert repo.load_project(project.project_id) == before and model.call_count == 2
        assert not any(x.key == prefix + "-export" for x in app.tabs[3].get("download_button"))


def test_review_replacement_requires_advanced_confirmation_and_revokes_approval_consent(tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate):
        app, repo, project, prefix = reviewed_project(tmp_path, monkeypatch)
    approval_checkbox(app, prefix).check().run()
    before = repo.load_project(project.project_id)
    assert app.button(key=prefix + "-review").disabled
    replace = next(x for x in app.checkbox if str(x.key).startswith(prefix + "-replace-review-"))
    replace.check().run()

    def replacement(stage, user_input, response_model, **kwargs):
        result = generate(stage, user_input, response_model, **kwargs)
        result.data = result.data.model_copy(update={"strengths": ["A new fictional review assessment"]})
        return result

    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=replacement) as model:
        app.button(key=prefix + "-review").click().run()
        assert not app.exception
        after = repo.load_project(project.project_id)
        assert after.draft == before.draft and after.review != before.review
        assert after.state == ProjectState.REVIEWED and not approval_checkbox(app, prefix).value
        assert app.button(key=prefix + "-review").disabled and app.button(key=prefix + "-approve").disabled
        app.run()
        model.assert_called_once()


def test_unconfigured_generation_provider_does_not_block_approval_of_existing_review(tmp_path, monkeypatch):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, project, prefix = reviewed_project(tmp_path, monkeypatch)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        app.selectbox(key=prefix + "-provider").select("mistral").run()
        assert cloud_checkbox(app, prefix).disabled
        approval_checkbox(app, prefix).check().run()
        assert not app.button(key=prefix + "-approve").disabled
        app.button(key=prefix + "-approve").click().run()
        assert repo.load_project(project.project_id).state == ProjectState.APPROVED
        assert model.call_count == 2


@pytest.mark.parametrize("language", ["fi", "en"])
def test_approval_status_label_change_cannot_reset_project_but_explicit_deselection_can(tmp_path, monkeypatch, language):
    with patch("hankeluotsi.draft_workflow.StageClient.generate", side_effect=generate) as model:
        app, repo, project, prefix = reviewed_project(tmp_path, monkeypatch, language)
        approval_checkbox(app, prefix).check().run()
        app.button(key=prefix + "-approve").click().run()
        before = repo.load_project(project.project_id)
        selector = "open_project_id" + ("_fi" if language == "fi" else "")
        assert app.selectbox(key=selector).value == project.project_id
        # Emulate a recreated status-labelled selectbox delivering its empty
        # default without an actual user-selection callback.
        app.session_state[selector] = None
        app.run()
        assert not app.exception
        assert app.selectbox(key=selector).value == project.project_id
        assert any(x.proto.label == localize("Download approved draft", language) for x in app.tabs[3].get("download_button"))
        app.selectbox(key=selector).select(None).run()
        assert app.selectbox(key=selector).value is None
        app.run()
        assert app.selectbox(key=selector).value is None
        assert repo.load_project(project.project_id) == before and model.call_count == 2
