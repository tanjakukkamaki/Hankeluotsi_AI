import json
import os
from pathlib import Path
from datetime import date
import subprocess
import sys
from unittest.mock import Mock

import pytest
import httpx2 as httpx

from hankeluotsi import model_quality as q
from hankeluotsi import mistral_smoke as smoke
from hankeluotsi.mistral_client import CloudError, MistralTransport


KEY = "fictional-smoke-key-not-real"


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "ROOT", tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-model")
    call = Mock(return_value=q.Reply(text=(Path(__file__).parent / "fixtures/concept_paper.json").read_text(),
        reported_model="fictional-model", finish_reason="stop", usage=q.Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)))
    monkeypatch.setattr(MistralTransport, "complete", call)
    return tmp_path / ".benchmark-private" / "single", call


def test_default_and_missing_configuration_preflight_never_calls_a_provider(configured, monkeypatch, capsys):
    output, call = configured
    assert smoke.main(["--preflight"]) == 0
    assert KEY not in capsys.readouterr().out
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert smoke.main([]) == 2
    status = json.loads(capsys.readouterr().out)
    assert status["network_calls"] == 0 and status["error_code"] == "missing_key"
    call.assert_not_called()
    assert not output.exists()


@pytest.mark.parametrize("flags", [{}, {"execute_cloud": True}, {"execute_cloud": True, "fictional_only": True}])
def test_smoke_requires_every_explicit_execution_authorization(configured, flags):
    output, call = configured
    with pytest.raises(ValueError):
        smoke.smoke(output, **flags)
    call.assert_not_called()


def test_single_success_preserves_usage_and_will_not_overwrite_or_repeat(configured):
    output, call = configured
    receipt = smoke.smoke(output, execute_cloud=True, fictional_only=True, accept_costs=True)
    assert receipt["success"] and receipt["usage"]["total_tokens"] == 30
    assert receipt["estimated_standard_uncached_cost"] is None and receipt["actual_billed_cost"] is None
    assert call.call_count == 1 and call.call_args.kwargs["max_tokens"] == 512
    assert receipt["automatic_retries"] == 0
    assert KEY not in (output / "receipt.json").read_text()
    with pytest.raises(ValueError):
        smoke.smoke(output, execute_cloud=True, fictional_only=True, accept_costs=True)
    assert call.call_count == 1


def test_failed_single_call_has_safe_category_and_no_automatic_retry(configured):
    output, call = configured
    call.side_effect = CloudError("billing_required", http_status=402)
    receipt = smoke.smoke(output, execute_cloud=True, fictional_only=True, accept_costs=True)
    assert receipt["success"] is False and receipt["error_code"] == "billing_required" and receipt["http_status"] == 402
    assert receipt["usage"] is None and not (output / "concept.json").exists()
    call.assert_called_once()


def test_real_child_receives_only_its_launching_shell_configuration_without_printing_it():
    environment = os.environ.copy()
    environment.update(MISTRAL_API_KEY=KEY, MISTRAL_MODEL="fictional-model", PYTHONDONTWRITEBYTECODE="1")
    # The child cannot inherit pytest's monkeypatch fixture, so install its own
    # network guard before importing/running the CLI (including import side effects).
    bootstrap = """
import runpy, socket, sys
def denied(*args, **kwargs):
    raise AssertionError('Network disabled in offline child')
socket.create_connection = socket.getaddrinfo = denied
socket.socket.connect = socket.socket.connect_ex = socket.socket.sendto = denied
sys.argv = ['hankeluotsi.mistral_smoke', '--preflight']
runpy.run_module('hankeluotsi.mistral_smoke', run_name='__main__')
"""
    child = subprocess.run([sys.executable, "-c", bootstrap],
        env=environment, capture_output=True, text=True, timeout=20)
    assert child.returncode == 0 and json.loads(child.stdout)["configured"]
    assert KEY not in child.stdout + child.stderr and "fictional-model" not in child.stdout


def test_usage_cost_requires_matching_reported_model_and_verified_price_record(configured):
    output, call = configured
    price = q.Pricing(provider="mistral", model="fictional-model", currency="EUR",
        input_per_million="1", output_per_million="2", source_url="https://example.invalid/fictional-prices",
        verified_on=date(2026, 11, 13), billing_basis="standard_uncached")
    receipt = smoke.smoke(output, execute_cloud=True, fictional_only=True, accept_costs=True, pricing=price)
    assert float(receipt["estimated_standard_uncached_cost"]) == pytest.approx(0.00005)
    assert receipt["actual_billed_cost"] is None
    call.assert_called_once()


@pytest.fixture
def connectivity(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-model")
    real_client, real_transport = httpx.Client, httpx.HTTPTransport
    requests = []
    reply = {"status": 200, "payload": {"choices": [{"message": {"content": "OK"},
        "finish_reason": "stop"}], "usage": {"prompt_tokens": 17, "completion_tokens": 1, "total_tokens": 18}}}

    def handler(request):
        requests.append(request)
        if "exception" in reply:
            raise reply["exception"]
        if "raw" in reply:
            return httpx.Response(reply["status"], content=reply["raw"])
        return httpx.Response(reply["status"], json=reply["payload"])

    def client(**kwargs):
        assert kwargs["timeout"] == 60
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    transport = Mock(wraps=real_transport)
    monkeypatch.setattr(smoke.httpx, "HTTPTransport", transport)
    monkeypatch.setattr(smoke.httpx, "Client", client)
    return requests, reply, transport


def test_live_is_one_minimal_configured_request_and_does_not_save_files(connectivity, tmp_path, monkeypatch, capsys):
    requests, reply, transport = connectivity
    monkeypatch.chdir(tmp_path)
    # Even a provider echo must not appear in the diagnostic output.
    reply["payload"]["choices"][0]["message"]["content"] = KEY
    reply["payload"]["choices"][0]["finish_reason"] = KEY
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert KEY not in output
    assert result["authentication_verified"] and result["model_access_verified"]
    assert result["response_generated"] and result["finish_reason"] == "unknown"
    assert result["usage"]["total_tokens"] == 18
    assert result["estimated_cost"] is None and result["actual_billed_cost"] is None
    assert result["requests_attempted"] == 1 and result["automatic_retries"] == 0
    transport.assert_called_once_with(retries=0, trust_env=False)
    assert len(requests) == 1 and not list(tmp_path.iterdir())
    assert requests[0].url == smoke.ENDPOINT and requests[0].method == "POST"
    assert requests[0].headers["content-type"] == "application/json"
    assert json.loads(requests[0].content) == {"model": "fictional-model",
        "messages": [{"role": "user", "content": "Fictional project: Meadow. Reply only OK."}],
        "max_tokens": 256, "stream": False}


def test_live_success_reports_usage_and_returns_zero(connectivity, capsys):
    requests, _, _ = connectivity
    assert smoke.main(["--live"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["success"] and result["finish_reason"] == "stop"
    assert result["response_generated"] and result["max_output_tokens"] == 256
    assert len(requests) == 1


def test_reported_32_token_limit_is_api_success_but_incomplete_generation(connectivity, capsys):
    requests, reply, _ = connectivity
    reply["payload"] = {"choices": [{"message": {"content": None}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 26, "completion_tokens": 32, "total_tokens": 58}}
    assert smoke.main(["--live", "--max-output-tokens", "32"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["api_request_succeeded"] and result["authentication_verified"] and result["model_access_verified"]
    assert not result["success"] and result["outcome"] == result["error_code"] == "output_token_limit"
    assert result["completion_truncated"] and result["output_token_limit_reached"]
    assert result["usage"] == {"prompt_tokens": 26, "completion_tokens": 32, "total_tokens": 58}
    assert "not an HTTP/API failure" in result["explanation"]
    assert len(requests) == 1 and json.loads(requests[0].content)["max_tokens"] == 32


@pytest.mark.parametrize("cap", [32, 128, 256, 512])
def test_live_uses_only_explicit_bounded_cap_without_automatic_retry(connectivity, capsys, cap):
    requests, _, _ = connectivity
    assert smoke.main(["--live", "--max-output-tokens", str(cap)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["success"] and result["outcome"] == "complete" and result["api_request_succeeded"]
    assert result["completion_truncated"] is False and result["automatic_retries"] == 0
    assert result["max_output_tokens"] == cap and json.loads(requests[0].content)["max_tokens"] == cap
    assert len(requests) == 1


@pytest.mark.parametrize("finish,expected,error,truncated", [
    ("length", "output_token_limit", "output_token_limit", True),
    ("model_length", "context_limit", "context_limit", True),
    (None, "incomplete_response", "incomplete", None),
    ("stop", "complete", None, False),
])
def test_token_usage_at_cap_does_not_override_explicit_or_unknown_finish(connectivity, capsys, finish, expected, error, truncated):
    requests, reply, _ = connectivity
    reply["payload"] = {"choices": [{"message": {"content": "OK"}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 26, "completion_tokens": 256, "total_tokens": 282}}
    assert smoke.main(["--live"]) == (0 if finish == "stop" else 1)
    result = json.loads(capsys.readouterr().out)
    assert result["api_request_succeeded"] and result["output_token_limit_reached"]
    assert result["outcome"] == expected and result["error_code"] == error
    assert result["completion_truncated"] is truncated
    assert len(requests) == 1


@pytest.mark.parametrize("cap", [True, None, 0, -1, 64, 1024, "256"])
def test_programmatic_invalid_budget_is_rejected_before_client_creation(connectivity, cap):
    requests, _, transport = connectivity
    with pytest.raises(ValueError):
        smoke.live_connectivity(max_output_tokens=cap)
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("mode", [[], ["--diagnose"], ["--models"], ["--preflight"], ["--execute-cloud"]])
def test_budget_flag_cannot_start_generation_or_modify_other_modes(connectivity, mode):
    requests, _, transport = connectivity
    with pytest.raises(SystemExit):
        smoke.main([*mode, "--max-output-tokens", "256"])
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("variable,code", [("MISTRAL_API_KEY", "missing_key"), ("MISTRAL_MODEL", "missing_model")])
def test_live_missing_configuration_makes_no_request(connectivity, monkeypatch, capsys, variable, code):
    requests, _, transport = connectivity
    monkeypatch.delenv(variable)
    assert smoke.main(["--live"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["error_code"] == code and result["requests_attempted"] == 0
    assert result["authentication_verified"] is None and result["model_access_verified"] is None
    assert KEY not in output and not requests
    transport.assert_not_called()


@pytest.mark.parametrize("status,code", [(401, "authentication"), (402, "billing_required"),
    (403, "authorization"), (404, "model_unavailable"), (429, "rate_limit"), (400, "bad_request"),
    (500, "service_unavailable"), (307, "http_error")])
def test_live_http_failure_is_safe_and_never_retried(connectivity, capsys, status, code):
    requests, reply, _ = connectivity
    reply.update(status=status, raw=KEY.encode())
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["error_code"] == code and result["http_status"] == status
    assert result["outcome"] == "http_api_error" and result["api_request_succeeded"] is False
    assert result["completion_truncated"] is None and result["output_token_limit_reached"] is None
    assert result["success"] is False and KEY not in output and len(requests) == 1


@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout(KEY), "timeout"),
    (httpx.ConnectError(KEY), "connection"), (ValueError(KEY), "invalid_response")])
def test_live_transport_failure_never_retries_or_displays_exception(connectivity, capsys, failure, code):
    requests, reply, _ = connectivity
    reply["exception"] = failure
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error_code"] == code and KEY not in output
    assert len(requests) == 1


@pytest.mark.parametrize("payload,code", [
    ({"choices": [{"message": {"content": None}, "finish_reason": "length"}]}, "output_token_limit"),
    ({"choices": [{"message": {"content": []}, "finish_reason": "stop"}]}, "invalid_response"),
    ({"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}, "invalid_response"),
    ({"choices": [{"message": {"content": [{"type": "thinking", "thinking": "hidden"}]}, "finish_reason": "stop"}]}, "invalid_response"),
    ({"choices": []}, "invalid_response"),
])
def test_live_empty_reasoning_or_truncated_response_is_not_success(connectivity, capsys, payload, code):
    requests, reply, _ = connectivity
    reply["payload"] = payload
    assert smoke.main(["--live"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["success"] and result["error_code"] == code
    assert result["authentication_verified"] and result["model_access_verified"]
    assert len(requests) == 1


def test_live_malformed_json_is_safe(connectivity, capsys):
    requests, reply, _ = connectivity
    reply["raw"] = KEY.encode()
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error_code"] == "invalid_response" and KEY not in output
    assert len(requests) == 1


@pytest.mark.parametrize("flags", [["--preflight"], ["--execute-cloud"], ["--fictional-only"],
    ["--accept-costs"], ["--output", "unused"], ["--pricing", "unused"], ["--diagnose"], ["--models"]])
def test_live_rejects_conflicting_modes_before_network(connectivity, flags):
    requests, _, transport = connectivity
    with pytest.raises(SystemExit) as error:
        smoke.main(["--live", *flags])
    assert error.value.code == 2 and not requests
    transport.assert_not_called()


def test_default_remains_offline_even_when_live_configuration_exists(connectivity, capsys):
    requests, _, transport = connectivity
    assert smoke.main([]) == 0
    assert json.loads(capsys.readouterr().out)["network_calls"] == 0
    assert not requests
    transport.assert_not_called()


def test_diagnose_previews_the_exact_configured_request_without_network_or_key(connectivity, monkeypatch, capsys):
    requests, _, transport = connectivity
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-large-latest")
    assert smoke.main(["--diagnose"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert KEY not in output
    assert result["configured"] and result["network_calls"] == 0
    assert not result["model_access_verified"] and not result["billing_verified"]
    request = result["request"]
    assert request["model"] == "mistral-large-latest" and request["max_output_tokens"] == 256
    assert request["message_count"] == 1 and request["message_roles"] == ["user"]
    assert "body" not in request and "content" not in request and "Meadow" not in output
    assert request["parameter_names"] == ["max_tokens", "messages", "model", "stream"]
    assert request["endpoint"] == smoke.ENDPOINT and request["content_type"] == "application/json"
    assert request["authorization"] == "configured; not displayed"
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("variable", ["MISTRAL_API_KEY", "MISTRAL_MODEL"])
def test_diagnose_missing_configuration_never_looks_up_models(connectivity, monkeypatch, capsys, variable):
    requests, _, transport = connectivity
    monkeypatch.delenv(variable)
    assert smoke.main(["--diagnose"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert not result["configured"] and "request" not in result and result["network_calls"] == 0
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("flags", [["--preflight"], ["--execute-cloud"], ["--fictional-only"],
    ["--accept-costs"], ["--output", "unused"], ["--pricing", "unused"], ["--models"]])
def test_diagnose_rejects_combined_modes_offline(connectivity, flags):
    requests, _, transport = connectivity
    with pytest.raises(SystemExit) as error:
        smoke.main(["--diagnose", *flags])
    assert error.value.code == 2 and not requests
    transport.assert_not_called()


@pytest.mark.parametrize("status,payload,reason,field,evidence", [
    (400, {"type": "invalid_model", "message": "Invalid model: " + KEY, "code": "1500"},
        "model_rejected", "model", "provider_error"),
    (400, {"error": {"type": "invalid_request_error", "param": "max_tokens", "message": KEY}},
        "token_budget_rejected", "max_tokens", "provider_error"),
    (422, {"message": {"detail": [{"loc": ["body", "messages", 0, "content"], "msg": KEY, "input": KEY}]}},
        "message_format_rejected", "messages", "provider_error"),
    (422, {"detail": [{"loc": ["body", "max_tokens"], "msg": "must be >=128 " + KEY}]},
        "token_budget_rejected", "max_tokens", "provider_error"),
    (400, {"error": {"param": "stream", "message": KEY}},
        "parameter_rejected", "stream", "provider_error"),
    (400, {"type": "context_length_exceeded", "message": KEY},
        "context_limit_rejected", None, "provider_error"),
    (400, {"message": "Invalid model: " + KEY},
        "model_rejected", "model", "provider_message_pattern"),
    (400, {"message": "max_tokens must be at least 128 " + KEY},
        "token_budget_rejected", "max_tokens", "provider_message_pattern"),
    (400, {"message": "This model's maximum context length was exceeded " + KEY},
        "context_limit_rejected", None, "provider_message_pattern"),
    (400, {"message": KEY, "param": KEY, "type": KEY, "code": KEY, "sensitive": KEY},
        "request_rejected", None, "http_status_only"),
])
def test_bad_request_classifies_only_safe_evidence_without_retry_or_parameter_changes(
        connectivity, capsys, status, payload, reason, field, evidence):
    requests, reply, _ = connectivity
    reply.update(status=status, payload=payload)
    assert smoke.main(["--live"]) == 1
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err
    result = json.loads(captured.out)
    assert result["error_code"] == "bad_request" and result["http_status"] == status
    diagnostic = result["diagnostic"]
    assert diagnostic["reason"] == reason and diagnostic["field"] == field and diagnostic["evidence"] == evidence
    assert diagnostic["explanation"] and diagnostic["next_step"]
    assert result["actual_billed_cost"] is None and "null does not mean zero" in result["billing_note"]
    assert result["authentication_verified"] is None and result["model_access_verified"] is None
    assert len(requests) == 1 and json.loads(requests[0].content)["max_tokens"] == 256


@pytest.mark.parametrize("raw", [b"not-json", b"<html>private response</html>", b"x" * 65537,
    b"[]", b'{"error": null}', b'{"message":{"detail":[null,17,[]]}}'],
    ids=["non-json", "html", "oversized", "array", "empty-error", "invalid-detail"])
def test_unknown_or_large_bad_request_body_retains_safe_fallback(connectivity, capsys, raw):
    requests, reply, _ = connectivity
    reply.update(status=400, raw=raw)
    assert smoke.main(["--live"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["diagnostic"]["reason"] == "request_rejected"
    assert result["diagnostic"]["evidence"] == "http_status_only" and len(requests) == 1


def test_diagnose_rejects_key_misconfigured_as_model_without_printing_it(connectivity, monkeypatch, capsys):
    requests, _, _ = connectivity
    monkeypatch.setenv("MISTRAL_MODEL", KEY)
    assert smoke.main(["--diagnose"]) == 2
    output = capsys.readouterr().out
    assert KEY not in output and json.loads(output)["error_code"] == "missing_model"
    assert not requests


@pytest.mark.parametrize("model", ["mistral-large-latest", "mistral-large-4"])
def test_both_owner_model_ids_use_documented_wire_format_without_implicit_parameters(
        connectivity, monkeypatch, capsys, model):
    requests, _, transport = connectivity
    monkeypatch.setenv("MISTRAL_MODEL", model)
    assert smoke.main(["--live"]) == 0
    request = requests[0]
    assert len(requests) == 1 and request.method == "POST"
    assert str(request.url) == "https://api.mistral.ai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer " + KEY
    assert request.headers["content-type"] == "application/json"
    body = json.loads(request.content)
    assert body == {"model": model, "messages": [{"role": "user",
        "content": "Fictional project: Meadow. Reply only OK."}], "max_tokens": 256, "stream": False}
    transport.assert_called_once_with(retries=0, trust_env=False)
    assert KEY not in capsys.readouterr().out


def test_diagnose_explains_authentication_scope_without_claiming_it_verified(connectivity, capsys):
    requests, _, transport = connectivity
    assert smoke.main(["--diagnose"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["authentication_context"] == {"key_source": "MISTRAL_API_KEY", "scheme": "Bearer",
        "workspace_access": "not_verified", "credential_validity": "not_verified"}
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("nested", [False, True])
def test_official_error_envelope_captures_safe_code_parameter_and_sanitized_message(connectivity, capsys, nested):
    requests, reply, _ = connectivity
    private = "Private project Meadow; partner@example.invalid; C:/private/project.sqlite3"
    error = {"object": "error", "type": "invalid_request_error", "code": "unknown_model", "param": "model",
        "message": "Unknown model: " + private + " Bearer " + KEY}
    reply.update(status=400, payload={"error": error} if nested else error)
    assert smoke.main(["--live"]) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    diagnostic = result["diagnostic"]
    assert result["error_code"] == "bad_request" and result["http_status"] == 400
    assert diagnostic["http_status"] == 400 and diagnostic["provider_error_code"] == "unknown_model"
    assert diagnostic["parameter"] == "model" and diagnostic["provider_error_type"] == "invalid_request_error"
    assert diagnostic["reason"] == "model_rejected" and diagnostic["message_sanitization"] == "template_allowlist"
    assert diagnostic["sanitized_message"] == "Model not accepted: [value withheld]."
    assert KEY not in captured.out + captured.err and private not in captured.out + captured.err
    assert result["authentication_verified"] is None and result["model_access_verified"] is None
    assert len(requests) == 1


@pytest.mark.parametrize("code,expected", [("1500", "1500"), (1500, "1500"),
    ("unknown_model", "unknown_model"), ("customer@example.invalid", None), (KEY, None),
    ("1234567890123456", None), (True, None), (None, None), ({"secret": KEY}, None)])
def test_provider_codes_preserve_bounded_machine_values_and_withhold_private_data(connectivity, capsys, code, expected):
    requests, reply, _ = connectivity
    reply.update(status=400, payload={"code": code, "message": "Private partner information", "param": "model"})
    assert smoke.main(["--live"]) == 1
    captured = capsys.readouterr()
    diagnostic = json.loads(captured.out)["diagnostic"]
    assert diagnostic["provider_error_code"] == expected
    assert diagnostic["sanitized_message"] == "Unrecognized provider message withheld."
    assert KEY not in captured.out + captured.err and "Private partner information" not in captured.out + captured.err
    assert "customer@example.invalid" not in captured.out and len(requests) == 1


def test_safe_token_constraint_is_retained_without_increasing_budget_or_leaking_details(connectivity, capsys):
    requests, reply, _ = connectivity
    reply.update(status=400, payload={"param": "max_tokens", "message":
        "max_tokens must be at least 512; employer Alice, secret=" + KEY})
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    diagnostic = json.loads(output)["diagnostic"]
    assert diagnostic["parameter"] == "max_tokens" and diagnostic["reason"] == "token_budget_rejected"
    assert diagnostic["sanitized_message"] == "max_tokens must be at least 512: [other details withheld]."
    assert "Alice" not in output and KEY not in output
    assert len(requests) == 1 and json.loads(requests[0].content)["max_tokens"] == 256


def test_reported_parameter_is_not_invented_from_an_inferred_model_field(connectivity, capsys):
    _, reply, _ = connectivity
    reply.update(status=400, payload={"type": "invalid_model", "param": None, "code": "1500"})
    assert smoke.main(["--live"]) == 1
    diagnostic = json.loads(capsys.readouterr().out)["diagnostic"]
    assert diagnostic["field"] == "model" and diagnostic["parameter"] is None
    assert diagnostic["sanitized_message"] is None and diagnostic["message_sanitization"] == "absent"


@pytest.mark.parametrize("code", ["invalid_api_key", "permission_denied", "insufficient_permissions"])
def test_reported_authentication_context_problem_is_not_confused_with_model_typo(connectivity, capsys, code):
    requests, reply, _ = connectivity
    reply.update(status=400, payload={"code": code, "message": KEY})
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["diagnostic"]["reason"] == "authentication_context_rejected"
    assert result["diagnostic"]["provider_error_code"] == code
    assert result["authentication_verified"] is None and result["model_access_verified"] is None
    assert KEY not in output and len(requests) == 1


def test_numeric_secret_is_redacted_before_reconstructing_message_or_code(connectivity, monkeypatch, capsys):
    _, reply, _ = connectivity
    monkeypatch.setenv("MISTRAL_API_KEY", "1500")
    monkeypatch.setattr(smoke, "perf_counter", lambda: 0)
    reply.update(status=400, payload={"code": "1500", "param": "max_tokens",
        "message": "max_tokens must be at least 1500"})
    assert smoke.main(["--live"]) == 1
    output = capsys.readouterr().out
    assert "1500" not in output
    assert json.loads(output)["diagnostic"]["provider_error_code"] is None


@pytest.fixture
def catalogue(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    requests = []
    reply = {"status": 200, "payload": {"object": "list", "data": [
        {"id": "mistral-large-4"}, {"id": "mistral-large-latest"}]}}
    real_client, real_transport = httpx.Client, httpx.HTTPTransport

    def handler(request):
        requests.append(request)
        assert request.method == "GET" and str(request.url) == smoke.MODELS_ENDPOINT
        assert request.headers["authorization"] == "Bearer " + os.environ["MISTRAL_API_KEY"]
        assert not request.content and not request.url.query
        if "exception" in reply:
            raise reply["exception"]
        if "raw" in reply:
            return httpx.Response(reply["status"], content=reply["raw"])
        return httpx.Response(reply["status"], json=reply["payload"])

    def client(**kwargs):
        assert kwargs["timeout"] == 30 and kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    transport = Mock(wraps=real_transport)
    monkeypatch.setattr(smoke.httpx, "HTTPTransport", transport)
    monkeypatch.setattr(smoke.httpx, "Client", client)
    return requests, reply, transport


@pytest.mark.parametrize("bare_array", [False, True])
def test_models_is_one_get_without_model_setting_and_only_safe_large_ids(catalogue, tmp_path, monkeypatch, capsys, bare_array):
    requests, reply, transport = catalogue
    monkeypatch.chdir(tmp_path)
    private = "Private employer confidential project"
    entries = [{"id": identifier, "description": private, "owner": KEY} for identifier in (
        "mistral-large-latest", "mistral-large-4", "mistral-large-4", "mistral-large-2512",
        "mistral-small-latest", "ft:mistral-large-4:private", "mistral-large-private-employer",
        "mistral-large-" + KEY, "mistral-large-4\nAuthorization: " + KEY)]
    reply["payload"] = entries if bare_array else {"object": "list", "data": entries, "private": private}
    assert smoke.main(["--models"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result == {"http_status": 200, "mistral_large_model_ids": [
        "mistral-large-2512", "mistral-large-4", "mistral-large-latest"], "mistral_large_4_listed": True}
    assert all(text not in captured.out + captured.err for text in (KEY, private, "Authorization", "ft:"))
    assert len(requests) == 1 and not list(tmp_path.iterdir())
    transport.assert_called_once_with(retries=0, trust_env=False)


@pytest.mark.parametrize("identifiers", [[], ["mistral-small-latest"], ["mistral-large-latest"], ["mistral-large-4-0"]])
def test_models_exact_id_absence_is_false_only_for_valid_catalogue(catalogue, capsys, identifiers):
    requests, reply, _ = catalogue
    reply["payload"] = {"data": [{"id": identifier} for identifier in identifiers]}
    assert smoke.main(["--models"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mistral_large_4_listed"] is False and result["mistral_large_model_ids"] is not None
    assert len(requests) == 1


def test_each_catalogue_call_uses_current_key_without_caching_previous_credential(catalogue, monkeypatch, capsys):
    requests, reply, _ = catalogue
    reply.update(status=400, payload={"code": "invalid_request", "message": "Unspecified fictional request rejection"})
    keys = ("fictional-previous-catalogue-key", "fictional-replacement-catalogue-key")
    for key in keys:
        monkeypatch.setenv("MISTRAL_API_KEY", key)
        assert smoke.main(["--models"]) == 1
        result = json.loads(capsys.readouterr().out)
        assert result == {"http_status": 400, "mistral_large_model_ids": None, "mistral_large_4_listed": None}
        assert requests[-1].headers["authorization"] == "Bearer " + key
    assert len(requests) == 2  # One explicit attempt per separate invocation, no retries.
    assert requests[0].headers["authorization"] != requests[1].headers["authorization"]


def test_catalogue_does_not_send_or_validate_generation_model_setting(catalogue, monkeypatch, capsys):
    requests, _, _ = catalogue
    monkeypatch.setenv("MISTRAL_MODEL", "invalid model setting that is irrelevant to catalogue GET")
    assert smoke.main(["--models"]) == 0
    assert json.loads(capsys.readouterr().out)["mistral_large_4_listed"] is True
    assert len(requests) == 1 and not requests[0].content and not requests[0].url.query
    assert "model" not in requests[0].headers


def test_models_missing_key_does_not_construct_client(catalogue, monkeypatch, capsys):
    requests, _, transport = catalogue
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert smoke.main(["--models"]) == 2
    assert json.loads(capsys.readouterr().out) == {"http_status": None, "mistral_large_model_ids": None,
        "mistral_large_4_listed": None}
    assert not requests
    transport.assert_not_called()


def test_models_credential_echo_matching_numeric_model_form_is_withheld(catalogue, monkeypatch, capsys):
    requests, reply, _ = catalogue
    monkeypatch.setenv("MISTRAL_API_KEY", "2512")
    reply["payload"] = {"data": [{"id": "mistral-large-4"}, {"id": "mistral-large-2512"}]}
    assert smoke.main(["--models"]) == 1
    output = capsys.readouterr().out
    assert "2512" not in output and json.loads(output)["mistral_large_model_ids"] is None
    assert len(requests) == 1


@pytest.mark.parametrize("identifiers", [["mistral-small-latest"] * 10001,
    ["mistral-large-" + str(index) for index in range(257)]], ids=["card-limit", "large-id-limit"])
def test_models_excessive_catalogue_stays_unknown_not_partially_listed(catalogue, capsys, identifiers):
    requests, reply, _ = catalogue
    reply["payload"] = {"data": [{"id": identifier} for identifier in identifiers]}
    assert smoke.main(["--models"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["mistral_large_model_ids"] is None and result["mistral_large_4_listed"] is None
    assert len(requests) == 1


def test_catalogue_is_never_queried_by_default(catalogue, capsys):
    requests, _, transport = catalogue
    assert smoke.main([]) == 2  # Key exists but the model setting is intentionally absent.
    assert json.loads(capsys.readouterr().out)["network_calls"] == 0
    assert not requests
    transport.assert_not_called()


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404, 429, 500])
def test_models_http_errors_never_show_response_or_retry(catalogue, capsys, caplog, status):
    requests, reply, _ = catalogue
    reply.update(status=status, raw=("Authorization: Bearer " + KEY + " private project").encode())
    assert smoke.main(["--models"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"http_status": status, "mistral_large_model_ids": None,
        "mistral_large_4_listed": None}
    assert KEY not in captured.out + captured.err + caplog.text
    assert "private project" not in captured.out + captured.err and len(requests) == 1


@pytest.mark.parametrize("raw", [b"not-json", b"<html>private</html>", b"x" * 1000001,
    b'{}', b'{"data":null}', b'{"data":[null]}', b'{"data":[{"id":17}]}'],
    ids=["malformed", "html", "oversized", "no-data", "null-data", "null-entry", "bad-id"])
def test_models_invalid_response_means_unknown_not_absent(catalogue, capsys, raw):
    requests, reply, _ = catalogue
    reply["raw"] = raw
    assert smoke.main(["--models"]) == 1
    assert json.loads(capsys.readouterr().out) == {"http_status": 200, "mistral_large_model_ids": None,
        "mistral_large_4_listed": None}
    assert len(requests) == 1


@pytest.mark.parametrize("failure", [httpx.ReadTimeout(KEY), httpx.ConnectError(KEY), RuntimeError(KEY)])
def test_models_transport_exception_is_sanitized_without_retry(catalogue, capsys, failure):
    requests, reply, _ = catalogue
    reply["exception"] = failure
    assert smoke.main(["--models"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"http_status": None, "mistral_large_model_ids": None,
        "mistral_large_4_listed": None}
    assert KEY not in captured.out + captured.err and len(requests) == 1


@pytest.mark.parametrize("flags", [["--live"], ["--diagnose"], ["--preflight"], ["--execute-cloud"],
    ["--fictional-only"], ["--accept-costs"], ["--output", "unused"], ["--pricing", "unused"]])
def test_models_rejects_other_modes_without_any_request(catalogue, flags):
    requests, _, transport = catalogue
    with pytest.raises(SystemExit) as error:
        smoke.main(["--models", *flags])
    assert error.value.code == 2 and not requests
    transport.assert_not_called()


@pytest.mark.parametrize("status", [400, 401, 403, 429])
def test_opt_in_models_diagnostics_preserves_safe_error_from_same_get(catalogue, capsys, status):
    requests, reply, _ = catalogue
    reply.update(status=status, payload={"message": "Invalid API Key " + KEY,
        "param": None, "code": "invalid_api_key", "type": "authentication_error"})
    assert smoke.main(["--models", "--diagnostics"]) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["http_status"] == status and result["mistral_large_4_listed"] is None
    assert result["diagnostic"]["provider_error_code"] == "invalid_api_key"
    assert result["diagnostic"]["sanitized_message"] and result["diagnostic"]["next_step"]
    assert KEY not in captured.out + captured.err and len(requests) == 1


def test_models_diagnostics_html_explains_missing_error_evidence(catalogue, capsys):
    requests, reply, _ = catalogue
    reply.update(status=400, raw=("<html>" + KEY + " private content</html>").encode())
    assert smoke.main(["--models", "--diagnostics"]) == 1
    output = capsys.readouterr().out
    detail = json.loads(output)["diagnostic"]
    assert detail["body_format"] == "non_json" and detail["diagnostic_information"] == "insufficient"
    assert KEY not in output and "private content" not in output and len(requests) == 1


@pytest.mark.parametrize("failure", ["missing_key", "timeout", "invalid_catalogue", "success"])
def test_models_verbose_local_and_response_outcomes_are_safe(catalogue, monkeypatch, capsys, failure):
    requests, reply, _ = catalogue
    if failure == "missing_key":
        monkeypatch.delenv("MISTRAL_API_KEY")
    elif failure == "timeout":
        reply["exception"] = httpx.ReadTimeout(KEY)
    elif failure == "invalid_catalogue":
        reply["payload"] = {"unrelated": KEY}
    code = smoke.main(["--models", "--diagnostics"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["diagnostic"]["next_step"] and KEY not in captured.out + captured.err
    assert len(requests) == (0 if failure == "missing_key" else 1)
    assert code == (0 if failure == "success" else 2 if failure in {"missing_key", "timeout"} else 1)


@pytest.mark.parametrize("flags", [[], ["--diagnose"], ["--live"], ["--preflight"], ["--execute-cloud"]])
def test_diagnostics_flag_cannot_start_request_without_models(catalogue, flags):
    requests, _, transport = catalogue
    with pytest.raises(SystemExit):
        smoke.main(["--diagnostics", *flags])
    assert not requests
    transport.assert_not_called()


def test_offline_diagnose_flags_suspect_key_shape_without_displaying_values(connectivity, monkeypatch, capsys):
    requests, _, transport = connectivity
    suspect = "'Bearer " + KEY + "'"
    monkeypatch.setenv("MISTRAL_API_KEY", suspect)
    monkeypatch.setenv("HTTPS_PROXY", "https://user:" + KEY + "@proxy.invalid:8080")
    monkeypatch.setenv("SSL_CERT_FILE", "C:/private/" + KEY + ".pem")
    assert smoke.main(["--diagnose"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["key_shape_flags"]["has_surrounding_quotes"]
    assert result["key_shape_flags"]["has_internal_whitespace"]
    assert result["transport"]["environment_presence_only"]["HTTPS_PROXY"]
    assert result["transport"]["transport_trust_env"] is False and result["transport"]["verify_tls"] is True
    assert KEY not in output and "proxy.invalid" not in output and "C:/private" not in output
    assert not requests
    transport.assert_not_called()
