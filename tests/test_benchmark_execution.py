"""Isolated execution repair: fake credentials and mocked network only."""

import json
import os
import subprocess
import sys
from unittest.mock import Mock

import httpx2
import pytest

from hankeluotsi import benchmark_execution as e, model_quality as q
from hankeluotsi.model_quality_review import verify_report


SECRET = "fictional-subprocess-test-key"


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", SECRET)
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-model")
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=AssertionError("No real HTTP in tests")))


def mock_http(monkeypatch, payload, status=200):
    response = Mock(status_code=status)
    response.json.return_value = payload
    response.raise_for_status = Mock()
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get.return_value = response
    client.post.return_value = response
    monkeypatch.setattr(e.httpx, "Client", Mock(return_value=client))
    return client


def local_inventory(loaded=True):
    return {"models": [{"key": "qwen3.5-4b", "loaded_instances":
        [{"config": {"context_length": 8192}}] if loaded else [],
        "capabilities": {"reasoning": {"default": "on"}}}]}


def test_local_preflight_requires_loaded_exact_model(monkeypatch):
    mock_http(monkeypatch, local_inventory())
    info = e.preflight("local", "qwen3.5-4b")
    assert info["context_length"] == 8192 and info["availability_verified"]
    assert info["catalogue_reasoning_default"] == "on"
    with pytest.raises(e.PreflightError, match="not loaded"):
        e.preflight("local", "other-model")
    mock_http(monkeypatch, local_inventory(False))
    with pytest.raises(e.PreflightError, match="not loaded"):
        e.preflight("local")


@pytest.mark.parametrize("variable", ["MISTRAL_API_KEY", "MISTRAL_MODEL"])
def test_cloud_missing_config_no_request(monkeypatch, variable):
    client = mock_http(monkeypatch, {})
    monkeypatch.delenv(variable)
    with pytest.raises(ValueError):
        e.preflight("mistral", verify_cloud=True)
    client.get.assert_not_called()


def test_cloud_configuration_check_has_no_network_and_model_check_is_read_only(monkeypatch, capsys):
    client = mock_http(monkeypatch, {"data": [{"id": "fictional-model"}]})
    info = e.preflight("mistral")
    assert not info["availability_verified"] and not info["billing_verified"]
    client.get.assert_not_called()
    assert e.preflight("mistral", verify_cloud=True)["availability_verified"]
    client.post.assert_not_called()
    e.main(["preflight", "--provider", "mistral"])
    output = capsys.readouterr().out
    assert SECRET not in output and "fictional-model" not in output
    assert "Balance/pricing/cost cap" in output


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_inventory_failure_is_sanitized(monkeypatch, status):
    mock_http(monkeypatch, {"error": SECRET}, status)
    with pytest.raises(e.PreflightError) as error:
        e.preflight("mistral", verify_cloud=True)
    assert SECRET not in str(error.value)


def test_unavailable_cloud_model_rejected(monkeypatch):
    mock_http(monkeypatch, {"data": [{"id": "different"}]})
    with pytest.raises(e.PreflightError, match="not available"):
        e.preflight("mistral", verify_cloud=True)


def test_local_diagnostics_keep_reasoning_separate_from_schema_output(monkeypatch, tmp_path):
    data = q.read_json(q.ROOT / "tests/fixtures/concept_paper.json")
    manifest = q.create_manifest(q.Settings(trials=1))
    payload = {"model": "qwen3.5-4b", "choices": [{"message": {"content": json.dumps(data),
        "reasoning_content": ""}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100,
        "completion_tokens": 500, "total_tokens": 600, "completion_tokens_details": {"reasoning_tokens": 0}}}
    client = mock_http(monkeypatch, payload)
    provider = e.DiagnosticLocalProvider("qwen3.5-4b", "http://127.0.0.1:1234/v1", tmp_path)
    selected = manifest.model_copy(update={"requests": manifest.requests[:1]})
    report = q.run(selected, provider)
    assert verify_report(report) == selected
    assert report["summary"]["first_attempt_successes"] == 1
    assert "reasoning_effort" not in client.post.call_args.kwargs["json"]
    assert "reasoning" not in client.post.call_args.kwargs["json"]
    assert client.post.call_args.kwargs["json"]["response_format"] == manifest.response_format
    assert provider.diagnostics[selected.requests[0].request_sha256]["reasoning_tokens"] == 0
    assert len(list((tmp_path / "diagnostics").glob("*.json"))) == 1


def test_reasoning_only_is_never_repaired_into_final_answer(monkeypatch, tmp_path):
    mock_http(monkeypatch, {"model": "qwen3.5-4b", "choices": [{"message": {
        "content": "", "reasoning_content": '{"unsafe_to_treat_as_answer":true}'}, "finish_reason": "length"}]})
    manifest = q.create_manifest(q.Settings(trials=1))
    provider = e.DiagnosticLocalProvider("qwen3.5-4b", "http://127.0.0.1:1234/v1", tmp_path)
    attempt = q.execute_request(manifest.requests[0], manifest, provider)
    assert not attempt["first_attempt_success"] and attempt["reply"]["text"] == ""
    assert e.failure_type(attempt).startswith("token_limit")


def test_private_output_guard_and_cloud_opt_in_before_network(monkeypatch, tmp_path):
    client = mock_http(monkeypatch, {})
    with pytest.raises(e.PreflightError, match="below .benchmark-private"):
        e.private_output(tmp_path / "public")
    monkeypatch.setattr(e, "private_output", lambda value: tmp_path / "new")
    with pytest.raises(e.PreflightError, match="Cloud requires"):
        e.run("mistral", ["Q01"], tmp_path / "new")
    client.get.assert_not_called()
    client.post.assert_not_called()


def test_output_limit_cannot_consume_entire_loaded_context(monkeypatch, tmp_path):
    client = mock_http(monkeypatch, local_inventory())
    monkeypatch.setattr(e, "private_output", lambda value: tmp_path / "new")
    with pytest.raises(e.PreflightError, match="no input context"):
        e.run("local", ["Q01"], tmp_path / "new", max_tokens=8192)
    client.post.assert_not_called()
    assert not (tmp_path / "new").exists()


def test_selected_run_remains_review_compatible_and_does_not_overwrite(monkeypatch, tmp_path):
    data = q.read_json(q.ROOT / "tests/fixtures/concept_paper.json")
    client = mock_http(monkeypatch, {"model": "qwen3.5-4b", "choices": [{"message": {
        "content": json.dumps(data)}, "finish_reason": "stop"}]})
    inventory_response = Mock(status_code=200)
    inventory_response.json.return_value = local_inventory()
    client.get.return_value = inventory_response
    monkeypatch.setattr(e, "private_output", lambda value: tmp_path / "new")
    report = e.run("local", ["Q01"], tmp_path / "new")
    verify_report(report)
    assert len(report["attempts"]) == 1 and report["summary"]["first_attempt_successes"] == 1
    assert report["manifest"]["settings"]["max_tokens"] == 4096
    assert report["execution"]["runner_sha256"]
    assert client.post.call_count == 1
    with pytest.raises(FileExistsError):
        e.run("local", ["Q01"], tmp_path / "new")
    assert client.post.call_count == 1


@pytest.mark.parametrize("cases", [[], ["Q99"], ["Q01", "Q01"], ["Q01", "Q02", "Q03", "Q04", "Q05", "Q06"]])
def test_bounded_case_selection(monkeypatch, tmp_path, cases):
    monkeypatch.setattr(e, "private_output", lambda value: tmp_path / "new")
    with pytest.raises(e.PreflightError):
        e.run("local", cases, tmp_path / "new")


def test_child_python_inherits_launching_environment_without_printing_key():
    # Actual child process, no HTTP and no permanent Windows environment changes.
    result = subprocess.run([sys.executable, "-m", "hankeluotsi.benchmark_execution",
        "preflight", "--provider", "mistral"], capture_output=True, text=True, env=os.environ.copy())
    assert result.returncode == 0
    assert "Configuration present" in result.stdout
    assert SECRET not in result.stdout + result.stderr


def test_cli_reports_failed_generation_as_nonzero_without_retry(monkeypatch, tmp_path, capsys):
    runner = Mock(return_value={"attempts": [{"case_id": "Q01", "execution_error": "token_limit"}],
        "summary": {"first_attempt_successes": 0}})
    monkeypatch.setattr(e, "run", runner)
    with pytest.raises(SystemExit) as error:
        e.main(["run", "--provider", "local", "--output", str(tmp_path / "ignored")])
    assert error.value.code == 1
    runner.assert_called_once()
    assert "token_limit" in capsys.readouterr().out


def test_git_ignores_old_mapping_and_new_runtime_directory():
    paths = ["benchmark-results/example/blind/PRIVATE-model-map.json", ".benchmark-private/example/results.json",
        "benchmark-results/example/local-model-metadata.json"]
    result = subprocess.run(["git", "check-ignore", "--stdin", "-z"], input=("\0".join(paths)+"\0").encode(),
        capture_output=True)
    assert result.returncode == 0 and set(result.stdout.decode().strip("\0").split("\0")) == set(paths)


def test_native_reasoning_off_contract_keeps_unknown_finish_unknown(monkeypatch, tmp_path):
    data = q.read_json(q.ROOT / "tests/fixtures/concept_paper.json")
    client = mock_http(monkeypatch, {"model_instance_id": "qwen3.5-4b", "output": [
        {"type": "message", "content": json.dumps(data)}], "stats": {
        "input_tokens": 1000, "total_output_tokens": 600, "reasoning_output_tokens": 0}})
    manifest = q.create_manifest(q.Settings(trials=1, max_tokens=4096))
    adapter = e.NativeLocalProvider("qwen3.5-4b", "http://127.0.0.1:1234/v1", tmp_path)
    attempt = q.execute_request(manifest.requests[0], manifest, adapter)
    assert attempt["json_valid"] and attempt["pydantic_valid"]
    assert not attempt["first_attempt_success"] and attempt["incomplete_output"]
    assert attempt["reply"]["finish_reason"] is None
    body = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "http://127.0.0.1:1234/api/v1/chat"
    assert body["reasoning"] == "off" and not body["store"] and body["integrations"] == []
    assert body["max_output_tokens"] == 4096 and body["input"] == manifest.requests[0].messages[1]["content"]
    assert "native_schema_prompt_v1" in body["system_prompt"]
    diagnostic = adapter.diagnostics[manifest.requests[0].request_sha256]
    assert diagnostic["reasoning_tokens"] == 0 and diagnostic["reasoning_characters"] == 0
    assert not diagnostic["at_output_cap"]


def test_native_mode_does_not_promote_reasoning_or_allow_cloud(monkeypatch, tmp_path):
    mock_http(monkeypatch, {"model_instance_id": "qwen3.5-4b", "output": [
        {"type": "reasoning", "content": '{"not_a_final_answer":true}'}], "stats": {
        "input_tokens": 1000, "total_output_tokens": 4096, "reasoning_output_tokens": 4000}})
    manifest = q.create_manifest(q.Settings(trials=1, max_tokens=4096))
    adapter = e.NativeLocalProvider("qwen3.5-4b", "http://127.0.0.1:1234/v1", tmp_path)
    attempt = q.execute_request(manifest.requests[0], manifest, adapter)
    assert attempt["reply"]["text"] == "" and not attempt["pydantic_valid"]
    assert adapter.diagnostics[manifest.requests[0].request_sha256]["at_output_cap"]
    monkeypatch.setattr(e, "private_output", lambda p: tmp_path / "new")
    with pytest.raises(e.PreflightError, match="local-only"):
        e.run("mistral", ["Q01"], tmp_path / "new", local_api="native",
            execute_cloud=True, fictional_only=True, accept_costs=True)
