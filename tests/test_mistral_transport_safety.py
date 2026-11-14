"""Hermetic transport checks: only in-memory responses and unconnected TLS contexts."""

import json
import ssl
from unittest.mock import Mock

import httpcore2
import httpx2
import pytest
from openai import DefaultHttpxClient, OpenAI

from hankeluotsi import mistral_client as cloud
from hankeluotsi import mistral_smoke as smoke


KEY = "fictional-transport-test-key-never-real"
MODEL = "fictional-transport-model"
SCHEMA_FORMAT = {"type": "json_schema", "json_schema": {"name": "fictional",
    "schema": {"type": "object", "properties": {}, "additionalProperties": False}}}


def _reply():
    return httpx2.Response(200, json={"model": MODEL,
        "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})


def _invoke(kind):
    if kind == "production":
        return cloud.MistralTransport(MODEL, cloud.CloudConsent(True, True)).complete(
            [{"role": "user", "content": "Fictional transport fixture"}], SCHEMA_FORMAT,
            temperature=0.2, max_tokens=512)
    if kind == "connectivity":
        return smoke.live_connectivity()
    return smoke.model_access()


def _assert_success(kind, result):
    if kind == "production":
        assert result.finish_reason == "stop" and result.text == "{}"
    elif kind == "connectivity":
        assert result["success"] is True
    else:
        assert result["http_status"] == 200 and result["mistral_large_4_listed"] is True


@pytest.fixture
def isolated_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    monkeypatch.setenv("MISTRAL_MODEL", MODEL)
    monkeypatch.setenv("OPENAI_API_KEY", "fictional-unrelated-key")
    monkeypatch.setenv("HTTP_PROXY", "http://fictional-proxy.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://fictional-proxy.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://fictional-proxy.invalid:8080")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "nonexistent-ca.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "nonexistent-ca-directory"))
    proxy_lookup = Mock(side_effect=AssertionError("Environment proxy lookup is forbidden"))
    monkeypatch.setattr("httpx2._client.get_environment_proxies", proxy_lookup)
    return proxy_lookup


@pytest.mark.parametrize("kind", ["production", "connectivity", "models"])
def test_all_mistral_constructors_ignore_tls_environment_without_disabling_verification(
        monkeypatch, isolated_environment, kind):
    contexts, clients = [], []
    real_client = httpx2.Client

    def make_context(*, _trust_env=True):
        assert _trust_env is False
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexts.append(context)
        return context

    def make_client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        client = real_client(**kwargs)
        clients.append(client)
        # Do not send on this real pool: these methods return in-memory responses.
        client.post = Mock(return_value=_reply())
        client.get = Mock(return_value=httpx2.Response(200, json={"data": [{"id": "mistral-large-4"}]}))
        client.send = Mock(side_effect=AssertionError("Real HTTP send is forbidden"))
        return client

    monkeypatch.setattr(httpcore2, "default_ssl_context", make_context)
    monkeypatch.setattr(httpx2, "Client", make_client)
    _assert_success(kind, _invoke(kind))
    assert len(contexts) == 1 and len(clients) == 1
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED and contexts[0].check_hostname
    client = clients[0]
    assert not client._mounts  # No environment proxy routes were created.
    assert client._transport._pool._retries == 0
    assert client._transport._pool._http1 is True and client._transport._pool._http2 is False
    assert client._transport._pool._ssl_context is contexts[0]
    client.send.assert_not_called()
    isolated_environment.assert_not_called()
    assert client.get.call_count + client.post.call_count == 1


@pytest.mark.parametrize("kind", ["production", "connectivity", "models"])
def test_actual_serialization_uses_one_correct_request_over_mock_transport(
        monkeypatch, isolated_environment, kind):
    requests, options = [], []

    def handle(request):
        requests.append(request)
        assert len(request.headers.get_list("authorization")) == 1
        assert request.headers["authorization"] == "Bearer " + KEY
        assert request.headers["host"] == "api.mistral.ai" and not request.url.query
        if kind == "models":
            assert request.method == "GET" and request.url.path == "/v1/models"
            assert not request.content and "content-type" not in request.headers
            return httpx2.Response(200, json={"data": [{"id": "mistral-large-4"}]})
        assert request.method == "POST" and request.url.path == "/v1/chat/completions"
        assert request.headers["content-type"] == "application/json"
        assert int(request.headers["content-length"]) == len(request.content)
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == MODEL and body["stream"] is False
        assert isinstance(body["max_tokens"], int)
        if kind == "production":
            assert body["temperature"] == 0.2 and body["max_tokens"] == 512
            assert body["response_format"] == SCHEMA_FORMAT
        else:
            assert body["max_tokens"] == 256 and "response_format" not in body
            assert set(body) == {"model", "messages", "max_tokens", "stream"}
        return _reply()

    def make_transport(**kwargs):
        options.append(kwargs)
        return httpx2.MockTransport(handle)

    monkeypatch.setattr(httpx2, "HTTPTransport", make_transport)
    _assert_success(kind, _invoke(kind))
    assert options == [{"retries": 0, "trust_env": False}]
    assert len(requests) == 1
    isolated_environment.assert_not_called()


def test_sdk_defaults_are_a_separate_contract_without_any_request():
    def never_send(request):
        pytest.fail("SDK comparison must not issue even a mocked request")

    with DefaultHttpxClient(transport=httpx2.MockTransport(never_send), trust_env=False) as http_client:
        assert http_client.follow_redirects is True
        with OpenAI(api_key="fictional-sdk-key", base_url="http://localhost:1234/v1",
                    http_client=http_client) as sdk:
            assert sdk.max_retries == 2
            assert sdk._client is http_client
    # The unchanged local integration selects these SDK defaults, unlike explicit Mistral settings.


@pytest.mark.parametrize("kind", ["production", "connectivity", "models"])
def test_real_http1_codec_encodes_requests_and_replays_safe_400_without_network(
        monkeypatch, isolated_environment, kind):
    """Exercise HTTPTransport/httpcore2/h11; the network and TLS handshake are fake."""
    error_body = json.dumps({"object": "error", "type": "invalid_request_error",
        "message": "Unknown model: " + KEY, "param": "model", "code": "unknown_model"}).encode()
    response_bytes = (b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n"
        + b"Content-Length: " + str(len(error_body)).encode() + b"\r\nConnection: close\r\n\r\n" + error_body)

    class MemoryStream(httpcore2.NetworkStream):
        def __init__(self):
            self.incoming = response_bytes
            self.outgoing = bytearray()
            self.tls_calls = []

        def read(self, max_bytes, timeout=None):
            data, self.incoming = self.incoming[:max_bytes], self.incoming[max_bytes:]
            return data

        def write(self, buffer, timeout=None):
            self.outgoing.extend(buffer)

        def close(self):
            pass

        def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            self.tls_calls.append((server_hostname, ssl_context))
            return self  # No socket, encryption or handshake occurs.

    class MemoryBackend(httpcore2.NetworkBackend):
        def __init__(self):
            self.stream = MemoryStream()
            self.connections = []

        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            self.connections.append((host, port))
            return self.stream

        def connect_unix_socket(self, *args, **kwargs):
            pytest.fail("No Unix socket is allowed in this in-memory codec check")

        def sleep(self, seconds):
            pytest.fail("No connection retry is allowed")

    backend = MemoryBackend()
    real_transport = httpx2.HTTPTransport

    def make_transport(**kwargs):
        assert kwargs == {"retries": 0, "trust_env": False}
        transport = real_transport(**kwargs)
        transport._pool._network_backend = backend
        return transport

    monkeypatch.setattr(httpcore2, "default_ssl_context", lambda **kwargs: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    monkeypatch.setattr(httpx2, "HTTPTransport", make_transport)
    if kind == "production":
        with pytest.raises(cloud.CloudError) as raised:
            cloud.MistralTransport(MODEL, cloud.CloudConsent(True, True)).complete(
                [{"role": "user", "content": "Kuvitteellinen työpaja"}], SCHEMA_FORMAT,
                temperature=0.2, max_tokens=512)
        assert raised.value.code == "bad_request" and raised.value.http_status == 400
        diagnostic = raised.value.diagnostic
    elif kind == "connectivity":
        result = smoke.live_connectivity()
        assert result["http_status"] == 400 and result["error_code"] == "bad_request"
        diagnostic = result["diagnostic"]
    else:
        result = smoke.model_access(include_diagnostics=True)
        assert result["http_status"] == 400 and result["mistral_large_4_listed"] is None
        diagnostic = result["diagnostic"]
    assert diagnostic["provider_error_code"] == "unknown_model" and diagnostic["parameter"] == "model"
    assert diagnostic["response_metadata"]["http_version"] == "HTTP/1.1"
    assert KEY not in json.dumps(diagnostic)
    assert backend.connections == [("api.mistral.ai", 443)]
    assert len(backend.stream.tls_calls) == 1
    hostname, context = backend.stream.tls_calls[0]
    assert hostname == "api.mistral.ai" and context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    head, separator, body = bytes(backend.stream.outgoing).partition(b"\r\n\r\n")
    assert separator
    lines = head.split(b"\r\n")
    expected_line = b"GET /v1/models HTTP/1.1" if kind == "models" else b"POST /v1/chat/completions HTTP/1.1"
    assert lines[0] == expected_line
    headers = [(name.lower(), value.strip()) for name, value in (line.split(b":", 1) for line in lines[1:])]
    assert [value for name, value in headers if name == b"host"] == [b"api.mistral.ai"]
    assert [value for name, value in headers if name == b"authorization"] == [("Bearer " + KEY).encode()]
    if kind == "models":
        assert body == b"" and not any(name == b"content-type" for name, _ in headers)
    else:
        assert dict(headers)[b"content-type"] == b"application/json"
        assert int(dict(headers)[b"content-length"]) == len(body)
        parsed = json.loads(body.decode("utf-8"))
        assert parsed["stream"] is False and parsed["model"] == MODEL
        if kind == "production":
            assert parsed["messages"][0]["content"] == "Kuvitteellinen työpaja"
            assert b"ty\xc3\xb6paja" in body and parsed["max_tokens"] == 512
        else:
            assert parsed["max_tokens"] == 256 and "response_format" not in parsed
    isolated_environment.assert_not_called()
