"""Fictional data only; no live model, cloud, or application database calls."""

import copy
import json
import socket
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from hankeluotsi import model_quality as q
from hankeluotsi.model_quality_review import FLAGS, CRITERIA
from hankeluotsi.repository import ProjectRepository


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline test attempted a network connection")
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def manifest():
    return q.create_manifest(q.Settings(trials=1))


@pytest.fixture
def valid_text():
    return (Path(__file__).parent / "fixtures/concept_paper.json").read_text(encoding="utf-8")


class FictionalProvider:
    provider = "lm_studio"
    requested_model = "fictional-qwen-id"
    measure_latency = False

    def __init__(self, text, error=None):
        self.text, self.error, self.calls = text, error, []

    def generate(self, request, manifest):
        self.calls.append(request.request_sha256)
        if self.error:
            raise self.error
        return q.Reply(text=self.text, reported_model=self.requested_model, finish_reason="stop",
            usage=q.Usage(prompt_tokens=12, completion_tokens=34, total_tokens=46), latency_seconds=0.5)


def test_ten_diverse_cases_are_valid_fictional_and_rubric_has_all_anchors(manifest):
    assert len(manifest.cases) == 10 and len(manifest.requests) == 10
    assert {c.language for c in manifest.cases} == {"fi", "en"}
    assert {c.complexity for c in manifest.cases} >= {"simple", "complex", "ambiguous", "incomplete", "unrealistic"}
    assert set(manifest.rubric["criteria"]) == set(CRITERIA)
    assert set(manifest.rubric["flags"]) == set(FLAGS)
    for criterion in manifest.rubric["criteria"].values():
        assert set(criterion["anchors"]) == set("12345")
        assert criterion["weak_example"] and criterion["strong_example"]
    for request in manifest.requests:
        assert "review_notes" not in json.dumps(request.messages)
        assert "quality_concept_v1" in request.messages[1]["content"]
        assert "concept_v2" in request.messages[1]["content"]
    assert "Å" in json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False)


def test_repeated_trials_have_stable_unique_requests_and_frozen_instructions():
    first = q.create_manifest(q.Settings(trials=3))
    second = q.create_manifest(q.Settings(trials=3))
    assert first.requests == second.requests
    assert len({r.request_sha256 for r in first.requests}) == 30
    assert all(sum(r.case_id == c.case_id for r in first.requests) == 3 for c in first.cases)


@pytest.mark.parametrize("text", [None, "", "{", '{"background_need":', "not JSON", "```json\n{}\n```", '{"value": NaN}'])
def test_malformed_and_incomplete_outputs_do_not_pass(text):
    result = q.assess(q.Reply(text=text, finish_reason="stop"))
    assert not result["json_valid"] and not result["first_attempt_success"]


@pytest.mark.parametrize("payload", [{}, [], {"background_need": "Fictional need"},
    {"tausta": "Kuvitteellinen tarve"}, {"schema_version": 99}])
def test_missing_fields_or_invalid_schema_are_recorded(payload):
    result = q.assess(q.Reply(text=json.dumps(payload), finish_reason="stop"))
    assert result["json_valid"] and not result["pydantic_valid"]
    assert result["validation_errors"]


@pytest.mark.parametrize("reason", [None, "length", "content_filter", "unknown"])
def test_valid_but_nonstop_or_unknown_finish_is_not_first_attempt_success(valid_text, reason):
    result = q.assess(q.Reply(text=valid_text, finish_reason=reason))
    assert result["pydantic_valid"] and not result["first_attempt_success"]


def test_schema_valid_does_not_hide_structural_or_human_quality_problems(valid_text):
    data = json.loads(valid_text)
    data["preliminary_activities"][0]["objective_ids"] = ["O99"]
    result = q.assess(q.Reply(text=json.dumps(data), finish_reason="stop"))
    assert result["first_attempt_success"]  # Structural reliability is recorded separately.
    assert any(f["code"] == "UNRESOLVED_OBJECTIVE_REFERENCE" for f in result["consistency_findings"])


@pytest.mark.parametrize("error,kind", [(TimeoutError("fictional-secret-token"), "timeout"),
    (ConnectionError("fictional-secret-token"), "request_failed"), (RuntimeError("fictional-secret-token"), "request_failed")])
def test_failed_requests_count_once_continue_and_never_log_exception_secrets(manifest, valid_text, error, kind):
    provider = FictionalProvider(valid_text, error)
    report = q.run(manifest, provider)
    assert len(provider.calls) == 10 and len(set(provider.calls)) == 10
    assert report["summary"]["errors"] == 10
    assert report["summary"]["first_attempt_success_rate"] == 0
    assert all(a["reply"]["error"] == kind for a in report["attempts"])
    assert "fictional-secret-token" not in json.dumps(report)


def test_results_preserve_outputs_usage_unknown_cost_and_statistics(manifest, valid_text):
    report = q.run(manifest, FictionalProvider(valid_text))
    assert report["summary"]["first_attempt_success_rate"] == 1
    assert report["summary"]["mean_latency_seconds"] == 0.5
    assert report["summary"]["usage_observations"] == 10
    assert report["summary"]["cost_estimates_available"] == 0
    assert report["summary"]["human_quality"] is None
    assert all(a["reply"]["text"] == valid_text for a in report["attempts"])
    assert len(report["by_case"]) == 10 and report["by_language"]["fi"]["attempts"] == 5


def test_cost_requires_explicit_model_specific_pricing_and_complete_usage():
    pricing = q.Pricing(provider="mistral", model="fictional-model", currency="EUR", input_per_million="1",
        output_per_million="2", source_url="https://example.invalid/fictional-price", verified_on="2026-11-11",
        billing_basis="standard_uncached")
    reply = q.Reply(reported_model="fictional-model", billing_basis="standard_uncached",
                    usage=q.Usage(prompt_tokens=100, completion_tokens=50))
    assert q.estimate_cost(reply, "mistral", pricing) == "0.0002"
    assert q.estimate_cost(reply, "lm_studio", pricing) is None
    assert q.estimate_cost(reply.model_copy(update={"reported_model": "different-model"}), "mistral", pricing) is None
    assert q.estimate_cost(q.Reply(reported_model="fictional-model"), "mistral", pricing) is None
    assert q.estimate_cost(reply.model_copy(update={"billing_basis": None}), "mistral", pricing) is None
    with pytest.raises(ValidationError):
        q.Usage(prompt_tokens=1, completion_tokens=2, total_tokens=4)


@pytest.mark.parametrize("endpoint", ["https://api.mistral.ai/v1", "https://example.invalid/v1",
    "http://localhost.evil.invalid/v1", "http://user:secret@localhost/v1", "http://localhost/v1?key=secret",
    "http://localhost/not-v1", "http://localhost/v1#fragment"])
def test_live_transport_rejects_nonlocal_or_credential_urls(endpoint):
    with pytest.raises(ValueError):
        q.local_endpoint(endpoint)


def test_real_local_adapter_with_mock_http_has_no_hidden_retries_or_redirects(manifest, valid_text, monkeypatch):
    captured = []
    status = [200]
    def handle(request):
        captured.append(request)
        if status[0] != 200:
            return httpx.Response(status[0], headers={"location": "https://example.invalid/forbidden"}, json={"error": "fictional"})
        return httpx.Response(200, json={"id": "fictional", "object": "chat.completion", "created": 1,
            "model": "fictional-qwen-id", "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}})
    real_client = httpx.Client
    class IsolatedClient(real_client):
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
            super().__init__(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(httpx, "Client", IsolatedClient)
    monkeypatch.setenv("OPENAI_API_KEY", "fictional-never-use-this")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer fictional-never-use-this\nX-Secret: fictional-never-use-this")
    provider = q.LocalProvider("fictional-qwen-id", "http://127.0.0.1:1234/v1", 1)
    try:
        reply = provider.generate(manifest.requests[0], manifest)
        assert reply.usage.total_tokens == 46 and reply.text == valid_text
        assert "authorization" not in captured[0].headers and "x-secret" not in captured[0].headers
        body = json.loads(captured[0].content)
        assert body["messages"] == manifest.requests[0].messages
        assert body["response_format"] == manifest.response_format
        for code in (302, 500):
            status[0] = code
            before = len(captured)
            with pytest.raises(Exception):
                provider.generate(manifest.requests[0], manifest)
            assert len(captured) == before + 1
    finally:
        provider.close()


def test_import_preserves_manifest_model_and_latency_without_any_connector(manifest, valid_text):
    bundle = q.ImportBundle(manifest_sha256=q.digest(manifest.model_dump(mode="json")), provider="mistral",
        requested_model="fictional-exact-model", responses=[q.ImportedRow(request_sha256=r.request_sha256,
            reply=q.Reply(text=valid_text, reported_model="fictional-exact-model", finish_reason="stop")) for r in manifest.requests])
    provider = q.ImportedProvider(bundle, manifest)
    report = q.run(manifest, provider)
    assert report["summary"]["latency_observations"] == 0
    assert report["requested_model"] == "fictional-exact-model" and report["provider"] == "mistral"
    for broken in (bundle.model_copy(update={"responses": bundle.responses[:-1]}),
                   bundle.model_copy(update={"responses": bundle.responses + [bundle.responses[0]]}),
                   bundle.model_copy(update={"manifest_sha256": "incorrect"})):
        with pytest.raises(ValueError):
            q.ImportedProvider(broken, manifest)


def test_cli_plan_is_offline_frozen_and_not_a_fabricated_result(tmp_path):
    output = tmp_path / "plan"
    q.main(["plan", "--output", str(output), "--trials", "1"])
    manifest = q.load_manifest(output / "manifest.json")
    bundle = q.ImportBundle.model_validate(q.read_json(output / "responses-template.json"))
    with pytest.raises(ValueError, match="not evidence"):
        q.ImportedProvider(bundle, manifest)
    data = manifest.model_dump(mode="json")
    data["requests"][0]["messages"][1]["content"] += "altered"
    altered = tmp_path / "altered.json"
    q.write_new(altered, data)
    with pytest.raises(ValueError, match="frozen"):
        q.load_manifest(altered)


def test_benchmark_has_no_sqlite_dependency_or_existing_file_write_path(tmp_path, manifest, valid_text, monkeypatch):
    path = tmp_path / "existing.sqlite3"
    repo = ProjectRepository(path)
    saved = repo.create_project(q.load_cases()[0].idea, operation_id="fictional")
    before = path.read_bytes()
    def no_sqlite(*args, **kwargs):
        raise AssertionError("Benchmark must not open SQLite")
    monkeypatch.setattr(sqlite3, "connect", no_sqlite)
    report = q.run(manifest, FictionalProvider(valid_text), checkpoint=tmp_path / "artifacts")
    with pytest.raises(ValueError):
        q.write_new(path, report)
    existing_json = tmp_path / "existing.json"
    existing_json.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        q.write_new(existing_json, report)
    assert path.read_bytes() == before and existing_json.read_text(encoding="utf-8") == "preserve"


def test_existing_checkpoint_is_rejected_before_any_generation(tmp_path, manifest, valid_text):
    provider = FictionalProvider(valid_text)
    checkpoint = tmp_path / "existing"
    checkpoint.mkdir()
    with pytest.raises(FileExistsError):
        q.run(manifest, provider, checkpoint=checkpoint)
    assert provider.calls == []


@pytest.mark.parametrize("body", [b'not-json', b'{"choices":[]}', b'{"choices":[{"message":{}}]}'])
def test_malformed_http_responses_are_bounded_failures(manifest, body):
    provider = q.LocalProvider("fictional-qwen-id", "http://127.0.0.1:1234/v1", 1)
    provider.client.close()
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)))
    try:
        reply = provider.generate(manifest.requests[0], manifest)
        assert reply.error == "invalid_response" and reply.text is None
    finally:
        provider.close()


def test_cli_local_generation_requires_explicit_execute_flag(tmp_path):
    with pytest.raises(SystemExit) as error:
        q.main(["run-local", "--model", "fictional", "--manifest", str(tmp_path / "absent.json"),
                "--output", str(tmp_path / "unused")])
    assert error.value.code == 2 and not (tmp_path / "unused").exists()
