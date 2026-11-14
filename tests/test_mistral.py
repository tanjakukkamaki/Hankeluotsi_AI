"""No paid requests: exercise official HTTP contract using isolated transport mocks."""

import json
from pathlib import Path
from unittest.mock import Mock

import httpx2 as httpx
import pytest

from hankeluotsi import model_quality as q
from hankeluotsi import mistral_client as m
from hankeluotsi import mistral_benchmark as benchmark
from hankeluotsi.i18n import localize
from hankeluotsi.model_quality_review import prepare, verify_report
from hankeluotsi.schemas import ConceptPaper


KEY = "fictional-test-credential-never-real"
CONSENT = m.CloudConsent(True, True)


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-mistral-model")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-key")
    # Fail closed if a test forgets to install its mock transport.
    monkeypatch.setattr(httpx.Client, "send", Mock(side_effect=AssertionError("No live calls in tests")))


def concept():
    return json.loads((Path(__file__).parent / "fixtures/concept_paper.json").read_text())


def payload(text=None, finish="stop", **extra):
    return {"model": "fictional-mistral-model", "choices": [{"message": {"content":
        json.dumps(concept()) if text is None else text}, "finish_reason": finish}], **extra}


def transport(monkeypatch, *, body=None, status=200, error=None):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    response = Mock(status_code=status, content=b"{}")
    response.json.return_value = payload() if body is None else body
    client.post = Mock(side_effect=error, return_value=response)
    factory = Mock(return_value=client)
    monkeypatch.setattr(m.httpx, "Client", factory)
    return factory, client


def generate():
    return m.select_client("mistral", consent=CONSENT).generate("concept", "Fictional idea", ConceptPaper)


@pytest.mark.parametrize("consent", [m.CloudConsent(), m.CloudConsent(True, False), m.CloudConsent(False, True), m.CloudConsent(1, True)])
def test_cloud_requires_both_explicit_boolean_confirmations(monkeypatch, consent):
    _, client = transport(monkeypatch)
    with pytest.raises(m.CloudError, match="Confirm fictional"):
        m.select_client("mistral", consent=consent)
    client.post.assert_not_called()


@pytest.mark.parametrize("variable,code", [("MISTRAL_API_KEY", "missing_key"), ("MISTRAL_MODEL", "missing_model")])
def test_missing_configuration_prevents_network(monkeypatch, variable, code):
    monkeypatch.delenv(variable)
    _, client = transport(monkeypatch)
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code
    client.post.assert_not_called()


def test_official_contract_defaults_validation_and_no_ambient_credentials(monkeypatch):
    factory, client = transport(monkeypatch, body=payload(usage={"prompt_tokens": 10,
        "completion_tokens": 20, "total_tokens": 30, "prompt_tokens_details": {"cached_tokens": 0}}))
    result = generate()
    assert result.data == ConceptPaper.model_validate(concept())
    assert result.provider == "mistral" and result.prompt_version == "concept_v2"
    assert result.finish_reason == "stop" and not result.incomplete_output and result.attempt_count == 1
    assert factory.call_count == 1
    settings = dict(factory.call_args.kwargs)
    assert isinstance(settings.pop("transport"), httpx.HTTPTransport)
    assert settings == dict(timeout=120, follow_redirects=False, trust_env=False)
    args, kwargs = client.post.call_args
    assert args == (m.ENDPOINT,)
    assert kwargs["headers"] == {"Authorization": "Bearer " + KEY}
    assert kwargs["json"]["model"] == "fictional-mistral-model"
    assert kwargs["json"]["response_format"]["json_schema"]["schema"] == ConceptPaper.model_json_schema()
    assert kwargs["json"]["max_tokens"] == 512
    assert kwargs["json"]["temperature"] == 0.2 and not kwargs["json"]["stream"]
    assert client.post.call_count == 1
    client.__exit__.assert_called_once()


@pytest.mark.parametrize("status,code", [(401, "authentication"), (403, "authorization"),
    (429, "rate_limit"), (301, "http_error"), (400, "bad_request"), (500, "service_unavailable"),
    (402, "billing_required"), (404, "model_unavailable"), (408, "timeout"),
    (413, "request_too_large"), (422, "bad_request"), (503, "service_unavailable"), (504, "timeout")])
def test_http_failures_are_safe_and_not_retried(monkeypatch, caplog, status, code):
    _, client = transport(monkeypatch, status=status, body={"error": KEY})
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code and KEY not in str(e.value)
    assert e.value.http_status == status
    assert KEY not in caplog.text and client.post.call_count == 1
    client.post.return_value.json.assert_called_once()
    assert e.value.diagnostic["http_status"] == status
    assert KEY not in json.dumps(e.value.__dict__)


@pytest.mark.parametrize("error,code", [(httpx.ReadTimeout(KEY), "timeout"),
    (httpx.ConnectError(KEY), "connection"), (httpx.RemoteProtocolError(KEY), "connection"),
    (RuntimeError(KEY), "invalid_response")])
def test_transport_errors_hide_exception_detail(monkeypatch, error, code):
    _, client = transport(monkeypatch, error=error)
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code and KEY not in str(e.value)
    assert e.value.http_status is None
    assert e.value.__suppress_context__ and client.post.call_count == 1


@pytest.mark.parametrize("body,code", [(payload("{"), "invalid_json"), (payload(""), "invalid_json"),
    (payload('{"untrusted":NaN}'), "invalid_json"),
    (payload('{"untrusted":Infinity}'), "invalid_json"),
    (payload("{}"), "invalid_schema"), (payload(finish="length"), "incomplete"),
    (payload(finish=None), "incomplete"), (payload(finish="model_length"), "incomplete"),
    ({"choices": []}, "invalid_response"), (payload(text=[]), "invalid_response"),
    (payload(usage={"prompt_tokens": -1}), "invalid_response")])
def test_bad_or_incomplete_output_never_becomes_valid_concept(monkeypatch, body, code):
    transport(monkeypatch, body=body)
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code


def test_echoed_credential_redacted_and_all_cloud_errors_translated(monkeypatch):
    transport(monkeypatch, body=payload(text=KEY))
    reply = m.MistralTransport(m.configured_model(), CONSENT).complete([], {}, temperature=0.2, max_tokens=128)
    assert KEY not in reply.model_dump_json()
    for message in m.ERROR_MESSAGES.values():
        assert localize(message, "fi") != message


def test_local_selection_does_not_require_cloud_configuration(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert isinstance(m.select_client(), m.LLMClient)
    with pytest.raises(ValueError, match="Unknown provider"):
        m.select_client("automatic")


def test_direct_transport_and_client_cannot_bypass_consent(monkeypatch):
    _, client = transport(monkeypatch)
    with pytest.raises(m.CloudError, match="Confirm fictional"):
        m.MistralTransport(m.configured_model(), m.CloudConsent()).complete([], {}, temperature=0.2, max_tokens=128)
    with pytest.raises(m.CloudError, match="Confirm fictional"):
        m.MistralClient(m.CloudConsent()).generate("concept", "Fictional", ConceptPaper)
    client.post.assert_not_called()


@pytest.mark.parametrize("nested", [False, True])
def test_production_http400_preserves_only_safe_provider_fields(monkeypatch, caplog, capsys, nested):
    private = "Confidential partner Alice alice@example.invalid C:/private/project.json"
    error = {"object": "error", "message": "Unknown model: " + private + " Bearer " + KEY,
        "type": "invalid_request_error", "param": "model", "code": "unknown_model",
        "request": {"Authorization": "Bearer " + KEY, "body": private}}
    _, client = transport(monkeypatch, status=400, body={"error": error} if nested else error)
    with pytest.raises(m.CloudError) as raised:
        generate()
    failure = raised.value
    assert failure.code == "bad_request" and failure.http_status == 400
    assert failure.provider_error_code == "unknown_model" and failure.parameter == "model"
    assert failure.sanitized_message == "Model not accepted: [value withheld]."
    assert len(failure.sanitized_message) <= m.MAX_ERROR_MESSAGE_CHARS
    assert failure.diagnostic["message_sanitization"] == "template_allowlist"
    captured = capsys.readouterr()
    exposed = json.dumps(failure.__dict__) + str(failure) + repr(failure) + repr(failure.args) + caplog.text + captured.out + captured.err
    assert all(text not in exposed for text in (KEY, private, "alice@example.invalid", "Authorization", "Fictional idea"))
    assert str(failure) == m.ERROR_MESSAGES["bad_request"] and failure.__suppress_context__
    assert not hasattr(failure, "response") and not hasattr(failure, "request")
    client.post.assert_called_once()
    client.post.return_value.json.assert_called_once()


@pytest.mark.parametrize("kind", ["malformed", "html", "non-object", "oversized", "parser-error"])
def test_production_bad_error_bodies_keep_original_http_status_safely(monkeypatch, kind):
    _, client = transport(monkeypatch, status=400, body=[] if kind == "non-object" else {"message": KEY})
    response = client.post.return_value
    if kind in {"malformed", "html"}:
        response.content = ("<html>" + KEY + "</html>").encode()
        response.json.side_effect = ValueError(KEY)
    elif kind == "oversized":
        response.content = b"x" * (m.MAX_ERROR_BODY_BYTES + 1)
    elif kind == "parser-error":
        response.json.side_effect = RuntimeError(KEY)
    with pytest.raises(m.CloudError) as raised:
        generate()
    failure = raised.value
    assert failure.code == "bad_request" and failure.http_status == 400
    assert failure.diagnostic["reason"] == "request_rejected"
    assert failure.provider_error_code is None and failure.parameter is None
    assert KEY not in json.dumps(failure.__dict__)
    client.post.assert_called_once()
    if kind == "oversized":
        response.json.assert_not_called()
    else:
        response.json.assert_called_once()


def test_production_diagnostics_use_captured_key_even_if_environment_changes(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "1500")
    _, client = transport(monkeypatch, status=400, body={"code": "1500", "param": "max_tokens",
        "message": "max_tokens must be at least 1500"})
    response = client.post.return_value

    def post(*args, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer 1500"
        monkeypatch.setenv("MISTRAL_API_KEY", "rotated-fictional-key")
        return response

    client.post.side_effect = post
    with pytest.raises(m.CloudError) as raised:
        generate()
    assert "1500" not in json.dumps(raised.value.__dict__)
    assert raised.value.provider_error_code is None and raised.value.parameter == "max_tokens"
    assert raised.value.sanitized_message == "max_tokens was rejected: [details withheld]."
    client.post.assert_called_once()


def test_production_redacts_credential_before_clipping_provider_message(monkeypatch):
    numeric_key = "8726451093" * 4
    monkeypatch.setenv("MISTRAL_API_KEY", numeric_key)
    prefix = "max_tokens must be at least "
    # Leave five key digits before the diagnostic clip boundary.
    text = prefix + " " * (2048 - len(prefix) - 5) + numeric_key
    _, client = transport(monkeypatch, status=400, body={"message": text, "param": "max_tokens"})
    with pytest.raises(m.CloudError) as raised:
        generate()
    assert raised.value.sanitized_message == "max_tokens was rejected: [details withheld]."
    assert numeric_key[:5] not in json.dumps(raised.value.__dict__)


def test_production_http_transport_explicitly_disables_retries(monkeypatch):
    factory, client = transport(monkeypatch)
    http_transport = Mock(return_value=object())
    monkeypatch.setattr(m.httpx, "HTTPTransport", http_transport)
    generate()
    http_transport.assert_called_once_with(retries=0, trust_env=False)
    assert factory.call_args.kwargs["transport"] is http_transport.return_value
    client.post.assert_called_once()


@pytest.mark.parametrize("body", [{"detail": "Invalid API Key " + KEY},
    {"error": "Invalid API Key " + KEY}, {"message": {"detail": "Invalid API Key " + KEY}}])
def test_error_detail_strings_are_sanitized_without_losing_recognizable_reason(body):
    response = httpx.Response(400, json=body)
    error = m._http_error(400, response=response, secret=KEY)
    assert error.code == "bad_request" and error.diagnostic["reason"] == "authentication_context_rejected"
    assert error.diagnostic["diagnostic_information"] == "recognized"
    assert error.sanitized_message == "API authentication was rejected: [details withheld]."
    assert KEY not in json.dumps(error.__dict__)


def test_safe_response_metadata_never_preserves_header_values_or_private_message():
    private = "Confidential employer plan alice@example.invalid"
    response = httpx.Response(400, headers={"content-type": "application/json; charset=utf-8",
        "x-request-id": KEY, "location": "https://private.invalid/?key=" + KEY,
        "www-authenticate": "Bearer secret=" + KEY, "server": private},
        extensions={"http_version": b"HTTP/2"},
        json={"message": private, "code": "unknown-private-" + KEY, "param": private})
    detail = m.request_error_diagnostic(response, secret=KEY)
    assert detail["body_format"] == "json_object" and detail["diagnostic_information"] == "insufficient"
    assert set(detail["withheld_fields"]) == {"provider_error_code", "parameter", "message"}
    meta = detail["response_metadata"]
    assert meta == {"content_type": "application/json", "http_version": "HTTP/2",
        "buffered_body_bytes": len(response.content), "request_id_present": True,
        "redirect_location_present": True, "authentication_challenge_present": True}
    assert KEY not in json.dumps(detail) and private not in json.dumps(detail)


@pytest.mark.parametrize("content_type,raw,body_format", [
    ("text/html", b"<html>private project</html>", "non_json"),
    ("text/plain", b"x" * (m.MAX_ERROR_BODY_BYTES + 1), "not_parsed_oversized")], ids=["html", "oversized"])
def test_non_json_and_large_responses_state_diagnostic_limits(content_type, raw, body_format):
    detail = m.request_error_diagnostic(httpx.Response(400, content=raw, headers={"content-type": content_type}))
    assert detail["body_format"] == body_format and detail["diagnostic_information"] == "insufficient"
    assert detail["response_metadata"]["content_type"] == content_type
    assert detail["http_status"] == 400 and detail["next_step"]


@pytest.mark.parametrize("model", ["bad model", "https://private.invalid/model", "model\nheader", ""])
def test_malformed_model_identifier_stops_production_before_request(monkeypatch, model):
    monkeypatch.setenv("MISTRAL_MODEL", model)
    _, client = transport(monkeypatch)
    with pytest.raises(m.CloudError) as error:
        generate()
    assert error.value.code == "missing_model" and not client.post.called


def test_direct_runtime_dependencies_are_declared_and_verified_offline():
    import ast
    from importlib.metadata import version
    import sys

    root = Path(__file__).resolve().parents[1]
    declarations = dict(line.strip().split("==", 1) for line in
        (root / "requirements.txt").read_text(encoding="utf-8").splitlines() if "==" in line)
    for name in ("httpx2", "certifi"):
        assert declarations[name] == version(name)
    imported = set()
    for path in [root / "app.py", *(root / "hankeluotsi").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                imported.add(node.module.split(".")[0])
    external = imported - sys.stdlib_module_names - {"hankeluotsi"}
    assert external <= declarations.keys(), external - declarations.keys()


def test_invalid_http_json_and_response_size_are_rejected(monkeypatch):
    _, client = transport(monkeypatch)
    response = client.post.return_value
    response.json.side_effect = ValueError(KEY)
    with pytest.raises(m.CloudError) as error:
        generate()
    assert error.value.code == "invalid_response" and KEY not in str(error.value)
    response.content = b"x" * 1_000_001
    response.json.reset_mock()
    with pytest.raises(m.CloudError) as error:
        generate()
    assert error.value.code == "invalid_response"
    response.json.assert_not_called()


def test_benchmark_reuses_exact_requests_usage_and_blinded_review(monkeypatch, tmp_path):
    _, client = transport(monkeypatch, body=payload(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}))
    manifest = q.create_manifest(q.Settings(trials=1))
    report = benchmark.collect(manifest, tmp_path / "run", CONSENT)
    assert verify_report(report) == manifest
    assert client.post.call_count == 10
    assert [c.kwargs["json"]["messages"] for c in client.post.call_args_list] == [r.messages for r in manifest.requests]
    assert all(a["reply"]["usage"]["total_tokens"] == 30 and a["error_type"] is None for a in report["attempts"])
    assert report["summary"]["human_quality"] is None and report["summary"]["cost_estimates_available"] == 0
    assert {a["language"] for a in report["attempts"]} == {"fi", "en"}
    assert all(a["estimated_api_cost"] is None for a in report["attempts"])
    prepare([report], tmp_path / "blind")
    packet = q.read_json(tmp_path / "blind/review-packet.json")
    assert "fictional-mistral-model" not in json.dumps(packet)
    with pytest.raises(FileExistsError):
        benchmark.collect(manifest, tmp_path / "run", CONSENT)
    assert client.post.call_count == 10

    class FictionalLocal:
        provider = "lm_studio"
        requested_model = "fictional-qwen"
        measure_latency = False

        def generate(self, request, manifest):
            return q.Reply(text=json.dumps(concept()), reported_model=self.requested_model, finish_reason="stop")

    local_report = q.run(manifest, FictionalLocal())
    prepare([local_report, report], tmp_path / "comparison")
    packet = q.read_json(tmp_path / "comparison/review-packet.json")
    assert len(packet["items"]) == 20
    assert "fictional-qwen" not in json.dumps(packet) and "fictional-mistral-model" not in json.dumps(packet)
    ratings = q.read_json(tmp_path / "comparison/ratings-template.json")
    assert all(all(score is None for score in rating["scores"].values()) for rating in ratings["ratings"])


def test_benchmark_failure_records_specific_error_without_leakage(monkeypatch, tmp_path):
    transport(monkeypatch, status=429)
    report = benchmark.collect(q.create_manifest(q.Settings(trials=1)), tmp_path / "run", CONSENT)
    assert all(a["error_type"] == "rate_limit" and not a["first_attempt_success"] for a in report["attempts"])
    assert KEY not in json.dumps(report)
    verify_report(report)


@pytest.mark.parametrize("body,code", [(payload("{"), "invalid_json"), (payload("{}"), "invalid_schema"),
    (payload(finish="length"), "incomplete")])
def test_benchmark_validation_error_categories(monkeypatch, tmp_path, body, code):
    transport(monkeypatch, body=body)
    report = benchmark.collect(q.create_manifest(q.Settings(trials=1)), tmp_path / "run", CONSENT)
    assert all(a["error_type"] == code and not a["first_attempt_success"] for a in report["attempts"])
    verify_report(report)


def test_benchmark_rejects_project_text_and_cli_without_opt_in(monkeypatch, tmp_path):
    _, client = transport(monkeypatch)
    manifest = q.create_manifest(q.Settings(trials=1))
    manifest.requests[0].messages[0]["content"] = "Unreviewed project data"
    with pytest.raises(ValueError, match="frozen fictional"):
        benchmark.collect(manifest, tmp_path / "run", CONSENT)
    with pytest.raises(SystemExit):
        benchmark.main(["--manifest", "missing", "--output", str(tmp_path / "run")])
    client.post.assert_not_called()


def test_cloud_stage_budgets_are_explicit_and_leave_concept_defaults_unchanged(monkeypatch):
    factory, client = transport(monkeypatch)
    result = m.MistralClient(CONSENT).generate("draft", "Fictional draft instructions",
        ConceptPaper, max_attempts=1, max_tokens=4096, timeout_seconds=180)
    assert result.prompt_version == "draft_v1" and result.stage == "draft"
    assert factory.call_count == 1
    settings = dict(factory.call_args.kwargs)
    assert isinstance(settings.pop("transport"), httpx.HTTPTransport)
    assert settings == dict(timeout=180, follow_redirects=False, trust_env=False)
    assert client.post.call_args.kwargs["json"]["max_tokens"] == 4096
    assert client.post.call_count == 1


@pytest.mark.parametrize("kwargs", [{"max_tokens": 0}, {"max_tokens": 8193}, {"max_tokens": True},
    {"timeout_seconds": 0}, {"timeout_seconds": 601}, {"timeout_seconds": True}])
def test_invalid_stage_limits_rejected_before_network(monkeypatch, kwargs):
    _, client = transport(monkeypatch)
    with pytest.raises(ValueError):
        m.MistralClient(CONSENT).generate("draft", "Fictional", ConceptPaper, **kwargs)
    client.post.assert_not_called()


def test_numeric_status_diagnostic_cannot_echo_untrusted_data():
    assert m.CloudError("http_error", http_status=KEY).http_status is None
    assert m.CloudError("http_error", http_status=True).http_status is None
    assert m.CloudError("http_error", http_status=999).http_status is None


@pytest.mark.parametrize("content", [
    [{"type": "text", "text": json.dumps(concept())}],
    [{"type": "thinking", "thinking": [{"type": "text", "text": KEY}]},
     {"type": "text", "text": json.dumps(concept())[:40]},
     {"type": "text", "text": json.dumps(concept())[40:]}],
])
def test_documented_content_chunks_keep_only_final_text_and_usage(monkeypatch, content):
    _, client = transport(monkeypatch, body=payload(content, usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}))
    result = generate()
    assert result.data == ConceptPaper.model_validate(concept())
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    assert result.reported_model == "fictional-mistral-model"
    assert KEY not in result.data.model_dump_json() and client.post.call_count == 1


@pytest.mark.parametrize("content,finish,expected", [
    (None, "length", "incomplete"), (None, "stop", "invalid_json"),
    ([{"type": "thinking", "thinking": [{"type": "text", "text": json.dumps(concept())}]}], "stop", "invalid_json"),
    ([{"type": "tool_call", "text": json.dumps(concept())}], "stop", "invalid_response"),
    ([{"type": "text", "text": 42}], "stop", "invalid_response"),
])
def test_incomplete_or_nonanswer_content_is_not_promoted_to_a_concept(monkeypatch, content, finish, expected):
    body = payload(finish=finish)
    body["choices"][0]["message"]["content"] = content
    _, client = transport(monkeypatch, body=body)
    with pytest.raises(m.CloudError) as error:
        generate()
    assert error.value.code == expected and client.post.call_count == 1


def test_boolean_attempt_count_is_not_an_execution_budget(monkeypatch):
    _, client = transport(monkeypatch)
    with pytest.raises(ValueError):
        m.MistralClient(CONSENT).generate("concept", "Fictional", ConceptPaper, max_attempts=True)
    client.post.assert_not_called()


def test_credential_cannot_be_misconfigured_as_logged_model_metadata(monkeypatch):
    monkeypatch.setenv("MISTRAL_MODEL", KEY)
    _, client = transport(monkeypatch)
    with pytest.raises(m.CloudError) as error:
        generate()
    assert error.value.code == "missing_model" and KEY not in str(error.value)
    client.post.assert_not_called()
