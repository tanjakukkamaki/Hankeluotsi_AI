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
    assert result.provider == "mistral" and result.prompt_version == "concept_v1"
    assert result.finish_reason == "stop" and not result.incomplete_output and result.attempt_count == 1
    factory.assert_called_once_with(timeout=120, follow_redirects=False, trust_env=False)
    args, kwargs = client.post.call_args
    assert args == (m.ENDPOINT,)
    assert kwargs["headers"] == {"Authorization": "Bearer " + KEY}
    assert kwargs["json"]["model"] == "fictional-mistral-model"
    assert kwargs["json"]["response_format"]["json_schema"]["schema"] == ConceptPaper.model_json_schema()
    assert kwargs["json"]["max_tokens"] == 512
    assert kwargs["json"]["temperature"] == 0.2 and not kwargs["json"]["stream"]
    assert client.post.call_count == 1
    client.__exit__.assert_called_once()


@pytest.mark.parametrize("status,code", [(401, "authentication"), (403, "authentication"),
    (429, "rate_limit"), (301, "http_error"), (400, "http_error"), (500, "http_error")])
def test_http_failures_are_safe_and_not_retried(monkeypatch, caplog, status, code):
    _, client = transport(monkeypatch, status=status, body={"error": KEY})
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code and KEY not in str(e.value)
    assert KEY not in caplog.text and client.post.call_count == 1


@pytest.mark.parametrize("error,code", [(httpx.ReadTimeout(KEY), "timeout"),
    (httpx.ConnectError(KEY), "connection"), (httpx.RemoteProtocolError(KEY), "connection"),
    (RuntimeError(KEY), "invalid_response")])
def test_transport_errors_hide_exception_detail(monkeypatch, error, code):
    _, client = transport(monkeypatch, error=error)
    with pytest.raises(m.CloudError) as e:
        generate()
    assert e.value.code == code and KEY not in str(e.value)
    assert e.value.__suppress_context__ and client.post.call_count == 1


@pytest.mark.parametrize("body,code", [(payload("{"), "invalid_json"), (payload(""), "invalid_json"),
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
