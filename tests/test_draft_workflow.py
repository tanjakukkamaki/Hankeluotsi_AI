"""Fictional-only service, state, stale-write and cross-process operation regressions."""

import json
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
import pytest

from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.draft_workflow import (
    PROMPT_VERSIONS, StageClient, WorkflowBusyError, WorkflowError, WorkflowService, project_operation_guard,
)
from hankeluotsi.mistral_client import CloudConsent, CloudError
from hankeluotsi.repository import ApprovedProjectLocked, InvalidTransition, ProjectRepository, ProjectState, StaleProjectError
from review_selection_fixture import selected_review_fixture


DATA = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=AssertionError("No real model calls in tests")))


@pytest.fixture
def ready(tmp_path):
    repository = ProjectRepository(tmp_path / "fictional.sqlite3")
    project = repository.create_project(fixture("project_idea.json"), operation_id="idea")
    project = repository.save_concept(project.project_id, fixture("concept_paper.json"), operation_id="concept")
    return repository, project


class Client:
    def __init__(self, data=None, effect=None, finish="stop"):
        self.data, self.effect, self.finish = data, effect, finish
        self.calls = []

    def generate(self, stage, user_input, response_model, *, max_attempts):
        self.calls.append((stage, user_input, response_model, max_attempts))
        if self.effect:
            self.effect()
        data = self.data if self.data is not None else fixture("application_draft.json" if stage == "draft" else "review_report.json")
        if stage == "review" and self.data is None:
            data = selected_review_fixture(data, user_input)
        return SimpleNamespace(data=data, model="fictional-qwen", provider="local", prompt_version=PROMPT_VERSIONS[stage],
            finish_reason=self.finish, incomplete_output=self.finish != "stop", truncated=self.finish == "length")


def service(repository, client=None):
    client = client or Client()
    return WorkflowService(repository, lambda provider, consent: client), client


@pytest.mark.parametrize("language,requested", [("fi", "Finnish"), ("en", "English")])
def test_generate_reopen_and_provenance_then_review_human_approval(ready, language, requested):
    repository, project = ready
    workflow, client = service(repository)
    saved = workflow.generate_draft(project.project_id, language=language, operation_id="draft")
    assert saved.state == ProjectState.DRAFT_READY
    draft = ApplicationDraft.model_validate(saved.draft)
    assert draft.generation_metadata.provider == "local" and draft.generation_metadata.model == "fictional-qwen"
    assert requested in client.calls[0][1]
    assert "Never invent" in client.calls[0][1] and "proposals and unknowns" in client.calls[0][1]
    assert client.calls[0][3] == 1
    reopened = ProjectRepository(repository.database_path).load_project(project.project_id)
    assert reopened.draft == saved.draft
    reviewed = workflow.review_draft(project.project_id, language=language, operation_id="review")
    assert reviewed.state == ProjectState.REVIEWED and reviewed.review is not None
    assert "deterministic_findings" in client.calls[1][1]
    approved = workflow.approve(project.project_id, operation_id="approve", expected_source=repository.source_fingerprint(project.project_id))
    assert approved.state == ProjectState.APPROVED
    for action in (workflow.generate_draft, workflow.review_draft):
        with pytest.raises(ApprovedProjectLocked):
            action(project.project_id, operation_id="blocked")
    assert len(client.calls) == 2


def test_unknown_native_finish_is_saved_as_unknown_not_benchmark_success(ready):
    repository, project = ready
    workflow, _ = service(repository, Client(finish="unknown"))
    saved = workflow.generate_draft(project.project_id, operation_id="draft")
    assert saved.draft["generation_metadata"]["finish_reason"] == "unknown"
    assert saved.draft["generation_metadata"]["incomplete_output"] is True


@pytest.mark.parametrize("finish", ["content_filter", "tool_calls", "unexpected_provider_status"])
def test_explicit_nonstop_completion_is_not_saved(ready, finish):
    repository, project = ready
    workflow, _ = service(repository, Client(finish=finish))
    with pytest.raises(WorkflowError, match="incomplete completion"):
        workflow.generate_draft(project.project_id, operation_id="filtered")
    assert repository.load_project(project.project_id) == project


def test_model_supplied_generation_provenance_is_overwritten(ready):
    repository, project = ready
    data = fixture("application_draft.json")
    data["generation_metadata"] = {"provider": "fake-approved-provider", "model": "fake", "prompt_version": "fake", "finish_reason": "stop", "incomplete_output": False}
    workflow, _ = service(repository, Client(data=data, finish="unknown"))
    saved = workflow.generate_draft(project.project_id, operation_id="draft")
    assert saved.draft["generation_metadata"] == {"provider": "local", "model": "fictional-qwen", "prompt_version": "draft_workflow_v2", "finish_reason": "unknown", "incomplete_output": True}


def test_invented_partner_cannot_be_persisted_as_provided_fact(ready):
    repository, project = ready
    data = fixture("application_draft.json")
    data["partner_roles"][0] = {"partner": "Invented confirmed partner", "role": "Invented confirmed delivery", "status": "provided"}
    workflow, client = service(repository, Client(data=data))
    with pytest.raises(WorkflowError, match="unknown partner"):
        workflow.generate_draft(project.project_id, operation_id="bad-provided-partner")
    assert repository.load_project(project.project_id) == project
    assert "name alone does not establish" in client.calls[0][1]


def test_supplied_partner_name_guard_is_not_a_claim_of_role_verification(ready):
    repository, project = ready
    idea = project.idea.model_dump(mode="json")
    idea["partners"] = ["Fictional supplied partner"]
    repository.save_idea(project.project_id, idea, operation_id="partner-clarification")
    repository.save_concept(project.project_id, fixture("concept_paper.json"), operation_id="new-concept")
    data = fixture("application_draft.json")
    data["partner_roles"][0] = {"partner": "Fictional supplied partner", "role": "The source names this partner; responsibility still needs confirmation.", "status": "provided"}
    workflow, _ = service(repository, Client(data=data))
    assert workflow.generate_draft(project.project_id, operation_id="known-name").state == ProjectState.DRAFT_READY


@pytest.mark.parametrize("data,finish", [({}, "stop"), (fixture("application_draft.json"), "length")])
def test_invalid_or_truncated_generation_preserves_last_valid_draft(ready, data, finish):
    repository, project = ready
    workflow, _ = service(repository)
    valid = workflow.generate_draft(project.project_id, operation_id="draft")
    invalid, _ = service(repository, Client(data=data, finish=finish))
    with pytest.raises(WorkflowError):
        invalid.generate_draft(project.project_id, operation_id="invalid")
    assert repository.load_project(project.project_id) == valid


def test_network_failure_preserves_data_and_releases_operation_guard(ready):
    repository, project = ready
    def failed():
        raise TimeoutError("fictional-secret-error-detail")
    workflow, _ = service(repository, Client(effect=failed))
    with pytest.raises(WorkflowError) as error:
        workflow.generate_draft(project.project_id, operation_id="retryable")
    assert "fictional-secret" not in str(error.value)
    assert repository.load_project(project.project_id) == project
    good, _ = service(repository)
    assert good.generate_draft(project.project_id, operation_id="retryable").state == ProjectState.DRAFT_READY


def test_no_cloud_call_or_save_without_fictional_and_processing_consent(ready):
    repository, project = ready
    factory = Mock()
    workflow = WorkflowService(repository, factory)
    with pytest.raises(CloudError, match="Confirm fictional"):
        workflow.generate_draft(project.project_id, provider="mistral", operation_id="cloud")
    factory.assert_not_called()
    assert repository.load_project(project.project_id) == project


def test_cloud_selection_is_explicit_and_rechecks_consent_at_service_boundary(ready):
    repository, project = ready
    client = Client()
    factory = Mock(return_value=client)
    workflow = WorkflowService(repository, factory)
    workflow.generate_draft(project.project_id, provider="mistral", consent=CloudConsent(True, True), operation_id="cloud")
    factory.assert_called_once_with("mistral", CloudConsent(True, True))
    assert repository.load_project(project.project_id).draft["generation_metadata"]["provider"] == "mistral"


def test_replayed_submission_across_services_never_regenerates(ready):
    repository, project = ready
    first, client = service(repository)
    saved = first.generate_draft(project.project_id, operation_id="stable-request")
    later, unused = service(ProjectRepository(repository.database_path))
    assert later.generate_draft(project.project_id, operation_id="stable-request") == saved
    assert len(client.calls) == 1 and not unused.calls


def test_generation_cannot_overwrite_changed_upstream_source(ready):
    repository, project = ready
    newer = fixture("concept_paper.json")
    newer["background_need"] = "New fictional owner clarification while the model was running."
    def changed():
        repository.save_concept(project.project_id, newer, operation_id="new-concept")
    workflow, client = service(repository, Client(effect=changed))
    with pytest.raises(StaleProjectError):
        workflow.generate_draft(project.project_id, operation_id="old-draft")
    saved = repository.load_project(project.project_id)
    assert saved.concept.background_need == newer["background_need"] and saved.draft is None
    assert len(client.calls) == 1


def test_snapshot_pair_prevents_old_prompt_new_fingerprint_race(ready, monkeypatch):
    repository, project = ready
    original_snapshot = repository.load_snapshot
    new = fixture("concept_paper.json")
    new["background_need"] = "Changed immediately after the atomic source snapshot."
    def racing_snapshot(project_id):
        pair = original_snapshot(project_id)
        repository.save_concept(project_id, new, operation_id="snapshot-race")
        return pair
    monkeypatch.setattr(repository, "load_snapshot", racing_snapshot)
    workflow, client = service(repository)
    with pytest.raises(StaleProjectError):
        workflow.generate_draft(project.project_id, operation_id="draft")
    assert repository.load_project(project.project_id).draft is None
    assert new["background_need"] not in client.calls[0][1]


def test_stale_displayed_cloud_source_never_contacts_provider(ready):
    repository, project = ready
    displayed = repository.source_fingerprint(project.project_id)
    new = fixture("concept_paper.json")
    new["background_need"] = "New owner material was not part of the displayed cloud consent."
    repository.save_concept(project.project_id, new, operation_id="changed-source")
    factory = Mock()
    workflow = WorkflowService(repository, factory)
    with pytest.raises(StaleProjectError, match="form was shown"):
        workflow.generate_draft(project.project_id, provider="mistral", consent=CloudConsent(True, True),
            operation_id="cloud", expected_source=displayed)
    factory.assert_not_called()


def test_untrusted_review_quote_preserves_review_and_draft(ready):
    repository, project = ready
    workflow, _ = service(repository)
    workflow.generate_draft(project.project_id, operation_id="draft")
    reviewed = workflow.review_draft(project.project_id, operation_id="review")
    fake = fixture("review_report.json")
    fake["findings"][0] = {"evidence_id": "E9999", "observation": "Unsupported citation",
        "suggestion": "Check the original source", "severity": "question"}
    bad, _ = service(repository, Client(data=fake))
    with pytest.raises(WorkflowError, match="unsupported evidence"):
        bad.review_draft(project.project_id, operation_id="bad-review")
    assert repository.load_project(project.project_id) == reviewed


def test_unsupported_existing_draft_is_not_silently_replaced(ready):
    from pydantic import BaseModel
    class LegacyDraft(BaseModel):
        schema_version: int
        summary: str
    repository, project = ready
    legacy = repository.save_draft(project.project_id, {"schema_version": 99, "summary": "Uninterpreted old data"},
        model_type=LegacyDraft, operation_id="legacy")
    workflow, client = service(repository)
    with pytest.raises(WorkflowError, match="unsupported contract"):
        workflow.generate_draft(project.project_id, operation_id="replacement")
    assert not client.calls and repository.load_project(project.project_id) == legacy


def test_unsupported_existing_review_blocks_regeneration_without_model_call(ready):
    from pydantic import BaseModel
    class LegacyReview(BaseModel):
        schema_version: int
        assessment: str
    repository, project = ready
    workflow, client = service(repository)
    workflow.generate_draft(project.project_id, operation_id="draft")
    legacy = repository.save_review(project.project_id, {"schema_version": 99, "assessment": "Old review"},
        model_type=LegacyReview, deterministic_findings=[], operation_id="legacy-review")
    before = len(client.calls)
    with pytest.raises(WorkflowError, match="unsupported contract"):
        workflow.review_draft(project.project_id, operation_id="new-review")
    assert len(client.calls) == before and repository.load_project(project.project_id) == legacy


def test_deterministic_errors_remain_separate_and_block_approval(ready):
    repository, project = ready
    invalid = fixture("application_draft.json")
    invalid["proposed_indicators"][0]["result_ids"] = ["R99"]
    workflow, _ = service(repository, Client(data=invalid))
    workflow.generate_draft(project.project_id, operation_id="draft")
    review = fixture("review_report.json")
    review["findings"] = []
    reviewer, _ = service(repository, Client(data=review))
    saved = reviewer.review_draft(project.project_id, operation_id="review")
    assert any(f["code"] == "UNRESOLVED_RESULT_REFERENCE" for f in saved.deterministic_findings)
    with pytest.raises(WorkflowError, match="deterministic errors"):
        reviewer.approve(project.project_id, operation_id="approve", expected_source=repository.source_fingerprint(project.project_id))
    assert repository.load_project(project.project_id).state == ProjectState.REVIEWED


def test_review_regeneration_invalidates_stale_human_approval(ready):
    repository, project = ready
    workflow, _ = service(repository)
    workflow.generate_draft(project.project_id, operation_id="draft")
    workflow.review_draft(project.project_id, operation_id="review")
    stale = repository.source_fingerprint(project.project_id)
    changed_review = fixture("review_report.json")
    changed_review["findings"] = []
    changed_review["overall_assessment"] = "Revised assessment includes newly identified uncertainty requiring another human decision."
    new_reviewer, _ = service(repository, Client(data=changed_review))
    new_reviewer.review_draft(project.project_id, operation_id="review-again")
    with pytest.raises(StaleProjectError):
        workflow.approve(project.project_id, operation_id="approve", expected_source=stale)
    assert repository.load_project(project.project_id).state == ProjectState.REVIEWED


def test_forged_persisted_deterministic_results_cannot_be_approved(ready):
    repository, project = ready
    workflow, _ = service(repository)
    workflow.generate_draft(project.project_id, operation_id="draft")
    repository.save_review(project.project_id, fixture("review_report.json"), model_type=ReviewReport,
        deterministic_findings=[{"code": "FAKE", "severity": "warning", "message": "Incorrect saved checks"}], operation_id="manual")
    with pytest.raises(WorkflowError, match="no longer match"):
        workflow.approve(project.project_id, operation_id="approve", expected_source=repository.source_fingerprint(project.project_id))


def test_same_project_concurrent_click_is_rejected_without_second_model_call(ready):
    repository, project = ready
    started, release = Event(), Event()
    errors = []
    def blocked():
        started.set()
        assert release.wait(5)
    first, client = service(repository, Client(effect=blocked))
    def run_first():
        try:
            first.generate_draft(project.project_id, operation_id="first")
        except Exception as error:
            errors.append(error)
    thread = Thread(target=run_first)
    thread.start()
    try:
        assert started.wait(5)
        second, unused = service(repository)
        with pytest.raises(WorkflowBusyError):
            second.generate_draft(project.project_id, operation_id="second")
        assert not unused.calls
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors and len(client.calls) == 1


def test_kernel_guard_rejects_separate_process_and_releases_after_context(ready):
    repository, project = ready
    code = """from pathlib import Path
import sys
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.draft_workflow import project_operation_guard, WorkflowBusyError
r=ProjectRepository(Path(sys.argv[1]))
try:
    with project_operation_guard(r,sys.argv[2]):
        print('acquired')
except WorkflowBusyError:
    print('busy')
"""
    with project_operation_guard(repository, project.project_id):
        result = subprocess.run([sys.executable, "-c", code, str(repository.database_path), project.project_id],
            capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and result.stdout.strip() == "busy"
    with project_operation_guard(repository, project.project_id):
        pass


def test_native_stage_contract_reasoning_off_schema_validation_and_unknown_finish(monkeypatch):
    response = Mock(content=b"{}")
    response.json.return_value = {"model_instance_id": "fictional-qwen", "output": [
        {"type": "message", "content": json.dumps(fixture("application_draft.json"))}],
        "stats": {"reasoning_output_tokens": 0, "total_output_tokens": 800}}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    factory = Mock(return_value=client)
    monkeypatch.setattr(httpx2, "Client", factory)
    result = StageClient().generate("draft", "Fictional idea", ApplicationDraft)
    body = client.post.call_args.kwargs["json"]
    assert body["reasoning"] == "off" and body["max_output_tokens"] == 4096
    assert not body["store"] and body["integrations"] == []
    assert "project_summary" in body["system_prompt"]
    assert "Do not return the schema itself" in body["system_prompt"]
    assert result.finish_reason == "unknown" and result.incomplete_output
    factory.assert_called_once_with(timeout=180, follow_redirects=False, trust_env=False)


def test_native_stage_rejects_reasoning_despite_off_and_no_retries(monkeypatch):
    response = Mock(content=b"{}")
    response.json.return_value = {"output": [], "stats": {"reasoning_output_tokens": 4000}}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    monkeypatch.setattr(httpx2, "Client", Mock(return_value=client))
    with pytest.raises(WorkflowError, match="thinking remained active"):
        StageClient().generate("draft", "Fictional idea", ApplicationDraft)
    assert client.post.call_count == 1


def test_local_stage_rejects_nonlocal_endpoint_before_request(monkeypatch):
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "https://example.invalid/v1")
    with pytest.raises(WorkflowError, match="loopback"):
        StageClient().generate("draft", "Fictional idea", ApplicationDraft)


def test_local_schema_echo_is_rejected_with_specific_safe_error(monkeypatch):
    response = Mock(content=b"{}")
    response.json.return_value = {"output": [{"type": "message", "content":
        json.dumps(ApplicationDraft.model_json_schema())}], "stats": {"reasoning_output_tokens": 0}}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    monkeypatch.setattr(httpx2, "Client", Mock(return_value=client))
    with pytest.raises(WorkflowError, match="JSON schema instead of a document"):
        StageClient().generate("draft", "Fictional idea", ApplicationDraft)
    client.post.assert_called_once()
