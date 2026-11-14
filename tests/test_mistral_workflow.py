"""Real client/service/UI paths over mocked HTTP only; no model-performance claims."""

import json
from pathlib import Path

import httpx2
import pytest
from streamlit.testing.v1 import AppTest

from hankeluotsi.i18n import localize
from hankeluotsi.repository import ProjectRepository, ProjectState
from hankeluotsi.draft_exporter import export_approved_markdown
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from test_app import APP_PATH


DATA = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("language,case_index", [("en", 0), ("fi", 1)])
def test_actual_mistral_adapter_all_stages_switching_approval_export_and_reruns(tmp_path, monkeypatch, language, case_index):
    path = tmp_path / "cloud-fictional.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    monkeypatch.setenv("MISTRAL_API_KEY", "fictional-full-workflow-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-large-4")
    case = json.loads((DATA / "planning_quality_cases_v1.json").read_text(encoding="utf-8"))["cases"][case_index]
    requests = []

    def handle(request):
        assert str(request.url) == "https://api.mistral.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer fictional-full-workflow-key"
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "mistral-large-4"
        name = body["response_format"]["json_schema"]["name"]
        if name == "conceptpaper":
            content = case["concept"]
        elif name == "applicationdraft":
            content = case["draft"]
        else:
            assert name == "reviewselection"
            packet = json.loads(body["messages"][1]["content"].split("\nSOURCE_PACKET:\n", 1)[1])
            entry = next(e for e in packet["evidence_catalogue"]["entries"] if e["location"].endswith("measurement_method"))
            content = dict(schema_version=1, strengths=["Rajattu pilotti" if language == "fi" else "A bounded pilot"],
                findings=[dict(evidence_id=entry["evidence_id"], observation="Tavoite pitää vahvistaa." if language == "fi" else "The target needs confirmation.",
                    suggestion="Sovi tavoite ja lähtötaso." if language == "fi" else "Agree the target and baseline.", severity="question")],
                missing_information=[], overall_assessment="Luonnos vaatii ihmisen tarkistuksen." if language == "fi" else "The draft needs human verification.",
                uncertainties=["Resursseja ei ole vahvistettu." if language == "fi" else "Resources are unconfirmed."])
        return httpx2.Response(200, json={"model": body["model"], "choices": [{"message": {"content": [{"type": "text", "text": json.dumps(content)}]}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}})

    original_client = httpx2.Client

    def mocked_client(**kwargs):
        configured_transport = kwargs.pop("transport", None)
        if configured_transport is not None:
            configured_transport.close()
        return original_client(transport=httpx2.MockTransport(handle), **kwargs)

    monkeypatch.setattr(httpx2, "Client", mocked_client)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert app.selectbox(key="generation_provider").value == "local" and not requests
    app.selectbox(key="ui_language").select(language).run()
    app.selectbox(key="generation_provider").select("mistral").run()
    idea = case["idea"]
    for key, value in (("idea_title", idea["title"]), ("idea_geography", idea["geography"])):
        app.text_input(key=key).set_value(value)
    for key, value in (("idea_development_need", idea["development_need"]), ("idea_target_groups", ", ".join(idea["target_groups"])),
                       ("idea_expected_change", idea["expected_change"]), ("idea_partners", ", ".join(idea.get("partners") or []))):
        app.text_area(key=key).set_value(value)
    app.checkbox(key="cloud_consent").check().run()
    next(button for button in app.button if str(button.key).startswith("FormSubmitter:project_idea_form-")).click().run()
    assert not app.exception and len(requests) == 1
    selector = "open_project_id" + ("_fi" if language == "fi" else "")
    project_id = app.selectbox(key=selector).value
    prefix = "workflow-" + project_id
    repo = ProjectRepository(path)
    initial = repo.load_project(project_id)
    app.session_state["workflow_stage"] = "draft"
    app.run()
    app.selectbox(key=prefix + "-provider").select("mistral").run()
    app.selectbox(key=prefix + "-provider").select("local").run()
    app.selectbox(key=prefix + "-provider").select("mistral").run()
    assert repo.load_project(project_id) == initial and len(requests) == 1
    assert app.button(key=prefix + "-draft").disabled
    next(c for c in app.checkbox if str(c.key).startswith(prefix + "-cloud-consent-")).check().run()
    app.button(key=prefix + "-draft").click().run()
    assert not app.exception and repo.load_project(project_id).state == ProjectState.DRAFT_READY
    assert app.button(key=prefix + "-review").disabled  # fresh stage cloud consent is required
    next(c for c in app.checkbox if str(c.key).startswith(prefix + "-cloud-consent-")).check().run()
    app.button(key=prefix + "-review").click().run()
    assert not app.exception and repo.load_project(project_id).state == ProjectState.REVIEWED
    assert [body["max_tokens"] for body in requests] == [512, 4096, 2048]
    assert all(("Finnish" if language == "fi" else "English") in body["messages"][1]["content"] for body in requests)
    app.radio(key=prefix + "-finalization-choice").set_value("approve").run()
    next(c for c in app.checkbox if str(c.key).startswith(prefix + "-approve-consent-")).check().run()
    app.button(key=prefix + "-approve").click().run()
    assert not app.exception
    approved = repo.load_project(project_id)
    assert approved.state == ProjectState.APPROVED and approved.draft["generation_metadata"]["provider"] == "mistral"
    assert approved.draft["generation_metadata"]["prompt_version"] == "draft_workflow_v2"
    assert approved.review["generation_metadata"]["prompt_version"] == "review_workflow_v3"
    assert any(x.proto.label == localize("Download approved draft", language) for x in app.tabs[3].get("download_button"))
    assert "AI-generated draft." in export_approved_markdown(repo, project_id, language=language)
    app.selectbox(key="generation_provider").select("local").run()
    app.selectbox(key="generation_provider").select("mistral").run()
    app.run()
    app.selectbox(key=selector).select(None).run()
    app.selectbox(key=selector).select(project_id).run()
    assert not app.exception and repo.load_project(project_id) == approved and len(requests) == 3


@pytest.mark.parametrize("language", ["en", "fi"])
def test_new_planning_observations_are_read_only_for_preexisting_approved_projects(tmp_path, monkeypatch, language):
    path = tmp_path / "old-approved.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    case = json.loads((DATA / "planning_quality_cases_v1.json").read_text(encoding="utf-8"))["cases"][0]
    draft = ApplicationDraft.model_validate(case["draft"])
    draft.timeline[0].period = "2024-05-01"
    draft.partner_roles = draft.partner_roles * 2
    repo = ProjectRepository(path)
    project = repo.create_project(case["idea"], operation_id="old-idea")
    repo.save_concept(project.project_id, case["concept"], operation_id="old-concept")
    repo.save_draft(project.project_id, draft, model_type=ApplicationDraft, operation_id="old-draft")
    review = ReviewReport.model_validate_json((DATA / "review_report.json").read_text())
    repo.save_review(project.project_id, review, model_type=ReviewReport, deterministic_findings=[], operation_id="old-review")
    before = repo.approve_project(project.project_id, operation_id="old-owner-approval")
    original = export_approved_markdown(repo, project.project_id, language=language)
    # No provider should be contacted just to display fresh advisory observations.
    monkeypatch.setattr(httpx2.Client, "send", lambda *a, **k: pytest.fail("Unexpected network request"))
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    app.selectbox(key="open_project_id").select(project.project_id).run()
    app.selectbox(key="ui_language").select(language).run()
    assert not app.exception
    assert any(x.label == localize("Planning observations (advisory)", language) for x in app.tabs[3].expander)
    assert any(x.proto.label == localize("Download approved draft", language) for x in app.tabs[3].get("download_button"))
    assert repo.load_project(project.project_id) == before
    assert export_approved_markdown(repo, project.project_id, language=language) == original
