"""Explicit, fictional-only Mistral transport. No SDK defaults or implicit fallback."""

import json
import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

import httpx2 as httpx
from pydantic import ValidationError

from hankeluotsi.llm_client import GenerationResult, LLMClient
from hankeluotsi.model_quality import Reply, Usage
from hankeluotsi.prompts import build_prompt, prompt_version_for_stage


ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
MAX_ERROR_BODY_BYTES = 65536
MAX_ERROR_MESSAGE_CHARS = 240
ERROR_MESSAGES = {
    "consent_required": "Confirm fictional data and cloud processing before generating with Mistral.",
    "missing_key": "Mistral is unavailable. Configure MISTRAL_API_KEY and restart the app.",
    "missing_model": "Mistral is unavailable. Configure a valid MISTRAL_MODEL and restart the app.",
    "authentication": "Mistral authentication failed. Check the API key and account permissions.",
    "authorization": "Mistral denied access. Check workspace permissions and access to the configured model.",
    "billing_required": "Mistral requires account billing or credits. Check the account before retrying.",
    "bad_request": "Mistral could not accept the request. Verify the model, output schema and request parameters.",
    "model_unavailable": "Mistral could not find the requested resource. Verify the exact configured model identifier and access.",
    "request_too_large": "Mistral rejected the request size. Reduce the input or output budget in a separate attempt.",
    "service_unavailable": "Mistral reported a server failure. Check service status before retrying explicitly.",
    "rate_limit": "Mistral rate or quota limit reached. Check usage limits and credits before retrying.",
    "timeout": "Mistral timed out. No automatic retry was made; check before submitting again.",
    "connection": "Could not connect securely to Mistral. Check the network and try again explicitly.",
    "http_error": "Mistral rejected the request or is unavailable. Check model access and service status.",
    "invalid_response": "Mistral returned an invalid response. The generated document was not saved.",
    "invalid_json": "Mistral returned empty or invalid JSON. The generated document was not saved.",
    "invalid_schema": "Mistral output failed schema validation. The generated document was not saved.",
    "incomplete": "Mistral output was incomplete or truncated. The generated document was not saved.",
}


class CloudError(ValueError):
    def __init__(self, code, *, http_status=None):
        self.code = code
        # Only sanitized primitives may be attached by the HTTP error factory below.
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.diagnostic = None
        self.provider_error_code = None
        self.parameter = None
        self.sanitized_message = None
        super().__init__(ERROR_MESSAGES[code])


def _http_error(status, *, response=None, secret=None):
    codes = {400: "bad_request", 401: "authentication", 402: "billing_required",
        403: "authorization", 404: "model_unavailable", 408: "timeout", 413: "request_too_large",
        422: "bad_request", 429: "rate_limit", 504: "timeout"}
    error = CloudError(codes.get(status, "service_unavailable" if status >= 500 else "http_error"),
        http_status=status)
    if response is not None:
        error.diagnostic = request_error_diagnostic(response, secret=secret)
        error.provider_error_code = error.diagnostic["provider_error_code"]
        error.parameter = error.diagnostic["parameter"]
        error.sanitized_message = error.diagnostic["sanitized_message"]
    return error


def _safe_provider_code(value, secret):
    """Retain known code names or short numeric codes, never arbitrary provider data."""
    known = {"unknown_model", "invalid_model", "model_not_found", "unsupported_model",
        "invalid_parameter", "unsupported_parameter", "invalid_request", "invalid_request_error",
        "context_length_exceeded", "invalid_api_key", "authentication_error", "permission_denied",
        "insufficient_permissions", "insufficient_quota", "rate_limit_exceeded", "validation_error"}
    if type(value) is int and 0 <= value <= 99999:
        value = str(value)
    if not isinstance(value, str) or secret and secret in value:
        return None
    if value in known or re.fullmatch(r"[0-9]{1,5}", value):
        return value
    return None


def _safe_provider_message(messages):
    """Reconstruct only recognized statements; omit every untrusted free-text value."""
    templates = {
        ("invalid model:", "unknown model:", "model not found"): "Model not accepted: [value withheld].",
        ("invalid api key", "invalid api_key", "invalid authentication", "authentication failed"): "API authentication was rejected: [details withheld].",
        ("permission denied", "access denied"): "Access was denied: [details withheld].",
        ("unsupported parameter:", "unknown parameter:"): "Unsupported parameter: [value withheld].",
        ("extra inputs are not permitted",): "Extra inputs are not permitted.",
        ("maximum context length", "this model's maximum context length"): "Model context limit was exceeded: [details withheld].",
    }
    for text in messages:
        for prefixes, message in templates.items():
            if text.startswith(prefixes):
                return message, "template_allowlist"
        limit = re.match(r"^[`'\"]?max_tokens[`'\"]?\s+must be\s+(at least|at most|>=|<=|>|<)\s*([0-9]{1,6})(?![0-9])", text)
        if limit:
            return f"max_tokens must be {limit[1]} {int(limit[2])}: [other details withheld].", "template_allowlist"
        if text.startswith(("max_tokens", "`max_tokens`", "'max_tokens'", '"max_tokens"')):
            return "max_tokens was rejected: [details withheld].", "template_allowlist"
    return ("Unrecognized provider message withheld.", "withheld") if messages else (None, "absent")


def safe_response_metadata(response):
    """Only fixed MIME/protocol categories and presence/size facts, never header values."""
    metadata = {"content_type": None, "http_version": None, "buffered_body_bytes": None,
        "request_id_present": False, "redirect_location_present": False,
        "authentication_challenge_present": False}
    try:
        mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        metadata["content_type"] = mime if mime in {
            "application/json", "application/problem+json", "text/html", "text/plain",
            "application/octet-stream"} else "other" if mime else None
        protocol = response.http_version
        metadata["http_version"] = protocol if protocol in ("HTTP/1.0", "HTTP/1.1", "HTTP/2", "HTTP/3") else None
        metadata["buffered_body_bytes"] = len(response.content)
        metadata["request_id_present"] = any(name in response.headers for name in ("x-request-id", "request-id", "x-correlation-id"))
        metadata["redirect_location_present"] = "location" in response.headers
        metadata["authentication_challenge_present"] = "www-authenticate" in response.headers
    except Exception:
        pass
    return metadata


def request_error_diagnostic(response, *, secret=None):
    """Capture bounded allowlisted error fields; never return raw provider text."""
    reason, field, evidence, provider_type = "request_rejected", None, "http_status_only", None
    provider_code, parameter, sanitized_message, message_sanitization = None, None, None, "absent"
    body_format, withheld_fields = "not_parsed", []
    code_present, parameter_present = False, False
    if secret is None:
        secret = os.environ.get("MISTRAL_API_KEY", "").strip()
    fields = {"model", "messages", "max_tokens", "stream", "response_format", "temperature", "reasoning_effort"}
    known_types = {"invalid_model", "model_not_found", "unsupported_model", "context_length_exceeded",
        "unsupported_parameter", "invalid_request_error", "invalid_request_invalid_args", "validation_error",
        "authentication_error", "permission_error", "rate_limit_error", "server_error"}
    try:
        if len(response.content) > MAX_ERROR_BODY_BYTES:
            body_format = "not_parsed_oversized"
            raise ValueError("Diagnostic body limit")
        body_format = "non_json"
        payload = response.json()
        body_format = "json_object" if isinstance(payload, dict) else "json_other"
        nodes = [payload] if isinstance(payload, dict) else []
        if nodes and isinstance(payload.get("error"), dict):
            nodes.append(payload["error"])
        # Handle flat errors and bounded validation details, including message.detail.
        for node in list(nodes):
            containers = [node]
            if isinstance(node.get("message"), dict):
                containers.append(node["message"])
            for container in containers:
                details = container.get("detail")
                if isinstance(details, list):
                    nodes.extend(item for item in details[:16] if isinstance(item, dict))
                elif isinstance(details, str):
                    nodes.append({"message": details})
            if isinstance(node.get("error"), str):
                nodes.append({"message": node["error"]})
        messages = []
        for node in nodes:
            value = node.get("type")
            if isinstance(value, str) and value in known_types and provider_type is None and not (secret and secret in value):
                provider_type = value
            if provider_code is None:
                provider_code = _safe_provider_code(node.get("code"), secret)
            code_present = code_present or node.get("code") is not None
            candidates = [node.get("param")]
            parameter_present = parameter_present or node.get("param") is not None or isinstance(node.get("loc"), list)
            if isinstance(node.get("loc"), list):
                candidates.extend(node["loc"][:8])
            if field is None:
                field = next((item for item in candidates if isinstance(item, str) and item in fields
                    and not (secret and secret in item)), None)
            for name in ("message", "msg"):
                if isinstance(node.get(name), str):
                    text = node[name].replace(secret, "[REDACTED]") if secret else node[name]
                    messages.append(text[:2048].casefold())
        parameter = field
        sanitized_message, message_sanitization = _safe_provider_message(messages)
        if provider_type in {"authentication_error", "permission_error"} or provider_code in {
                "invalid_api_key", "authentication_error", "permission_denied", "insufficient_permissions"}:
            reason, evidence = "authentication_context_rejected", "provider_error"
        elif provider_type == "context_length_exceeded" or provider_code == "context_length_exceeded":
            reason, evidence = "context_limit_rejected", "provider_error"
        elif any(text.startswith(("maximum context length", "this model's maximum context length")) for text in messages):
            reason, evidence = "context_limit_rejected", "provider_message_pattern"
        elif provider_type in {"invalid_model", "model_not_found", "unsupported_model"} or provider_code in {
                "unknown_model", "invalid_model", "model_not_found", "unsupported_model"} or field == "model":
            reason, field, evidence = "model_rejected", "model", "provider_error"
        elif field == "max_tokens":
            reason, evidence = "token_budget_rejected", "provider_error"
        elif field == "messages":
            reason, evidence = "message_format_rejected", "provider_error"
        elif field or provider_type == "unsupported_parameter" or provider_code in {"invalid_parameter", "unsupported_parameter"}:
            reason, evidence = "parameter_rejected", "provider_error"
        elif any(text.startswith(("invalid model:", "unknown model:", "model not found")) for text in messages):
            reason, field, evidence = "model_rejected", "model", "provider_message_pattern"
        elif any(text.startswith(("max_tokens", "`max_tokens`", "'max_tokens'", '"max_tokens"')) for text in messages):
            reason, field, evidence = "token_budget_rejected", "max_tokens", "provider_message_pattern"
        elif any(text.startswith(("invalid api key", "invalid api_key", "authentication failed", "permission denied", "access denied")) for text in messages):
            reason, evidence = "authentication_context_rejected", "provider_message_pattern"
    except Exception:
        pass
    hints = {
        "request_rejected": ("The server rejected the request; the retained safe evidence does not identify a field.",
            "Compare safe response metadata for catalogue and chat; check the existing key/workspace context. Do not repeat calls without approval."),
        "model_rejected": ("The server identified a model problem; identifier, availability, chat support or workspace access needs checking.",
            "Verify the exact configured model in your Mistral workspace. Do not guess a replacement or retry automatically."),
        "token_budget_rejected": ("The server identified max_tokens as a rejected field; check the requested output cap against the selected model constraints.",
            "Check the selected model's documented token constraints. Do not raise the cap or retry without approval."),
        "message_format_rejected": ("The server identified the messages field as invalid.",
            "Compare the local --diagnose preview with the chat API's role/content message format before approving a new request."),
        "parameter_rejected": ("The server identified a parameter problem.",
            "Compare the indicated field and --diagnose preview with this model's supported parameters; do not change models or retry automatically."),
        "context_limit_rejected": ("The server reported a context-length problem.",
            "Check the model context limit against input plus the requested output cap before approving any revised request."),
        "authentication_context_rejected": ("The server reported an authentication or access-context problem.",
            "Check the existing inference API key's active workspace and model permissions in the console. Do not display the key or retry."),
    }
    if code_present and provider_code is None:
        withheld_fields.append("provider_error_code")
    if parameter_present and parameter is None:
        withheld_fields.append("parameter")
    if message_sanitization == "withheld":
        withheld_fields.append("message")
    explanation, next_step = hints[reason]
    return {"reason": reason, "field": field, "evidence": evidence,
        "http_status": response.status_code, "provider_error_type": provider_type,
        "provider_error_code": provider_code, "parameter": parameter,
        "sanitized_message": sanitized_message[:MAX_ERROR_MESSAGE_CHARS] if sanitized_message else None,
        "message_sanitization": message_sanitization,
        "body_format": body_format, "withheld_fields": withheld_fields,
        "diagnostic_information": "recognized" if reason != "request_rejected" or provider_code else "insufficient",
        "response_metadata": safe_response_metadata(response),
        "explanation": explanation, "next_step": next_step}


@dataclass(frozen=True)
class CloudConsent:
    fictional_data: bool = False
    cloud_processing: bool = False

    def require(self):
        if self.fictional_data is not True or self.cloud_processing is not True:
            raise CloudError("consent_required")


def configured_model():
    model = os.getenv("MISTRAL_MODEL", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model):
        raise CloudError("missing_model")
    return model


def check_configuration():
    key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not key:
        raise CloudError("missing_key")
    model = configured_model()
    if key in model:
        raise CloudError("missing_model")
    return model


def _answer_text(content):
    """Only documented final text; never concatenate thinking/tools into JSON."""
    if content is None or isinstance(content, str):
        return content
    if not isinstance(content, list) or not content or len(content) > 256:
        raise CloudError("invalid_response")
    parts = []
    for part in content:
        if not isinstance(part, dict):
            raise CloudError("invalid_response")
        if part.get("type") == "thinking":
            continue
        if part.get("type") != "text" or not isinstance(part.get("text"), str):
            raise CloudError("invalid_response")
        parts.append(part["text"])
    return "".join(parts)


class ConceptClient(Protocol):
    def generate(self, stage, user_input, response_model=None, *, max_attempts=1) -> GenerationResult: ...


class MistralTransport:
    """One bounded HTTPS request. No redirects, proxies, retries, tools or logging."""

    def __init__(self, model, consent, *, timeout=120):
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("Cloud timeout must be an integer between 1 and 600 seconds")
        self.model, self.consent, self.timeout = model, consent, timeout

    def complete(self, messages, response_format, *, temperature, max_tokens):
        self.consent.require()
        if type(max_tokens) is not int or not 128 <= max_tokens <= 8192:
            raise ValueError("Cloud output budget must be an integer between 128 and 8192 tokens")
        check_configuration()
        # Model must be the explicit environment choice, never a hidden default.
        if self.model != configured_model():
            raise CloudError("missing_model")
        key = os.environ["MISTRAL_API_KEY"].strip()
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False,
                              transport=httpx.HTTPTransport(retries=0, trust_env=False)) as client:
                response = client.post(ENDPOINT, headers={"Authorization": "Bearer " + key}, json={
                    "model": self.model, "messages": messages, "temperature": temperature,
                    "max_tokens": max_tokens, "response_format": response_format, "stream": False,
                })
                if not 200 <= response.status_code < 300:
                    raise _http_error(response.status_code, response=response, secret=key) from None
                if len(response.content) > 1_000_000:
                    raise CloudError("invalid_response")
                payload = response.json()
                choice = payload["choices"][0]
                # Do not persist even a server-echoed credential in output or metadata.
                text = _answer_text(choice["message"]["content"])
                model = payload.get("model")
                finish = choice.get("finish_reason")
                if (model is not None and not isinstance(model, str)
                        or finish is not None and not isinstance(finish, str)):
                    raise CloudError("invalid_response")
                usage = payload.get("usage")
                return Reply(text=text.replace(key, "[REDACTED]") if text is not None else None,
                    reported_model=model.replace(key, "[REDACTED]") if model else None,
                    finish_reason=finish.replace(key, "[REDACTED]") if finish else None,
                    usage=Usage.model_validate({name: usage.get(name) for name in
                        ("prompt_tokens", "completion_tokens", "total_tokens")}) if usage is not None else None)
        except CloudError:
            raise
        except httpx.TimeoutException:
            raise CloudError("timeout") from None
        except httpx.RequestError:
            raise CloudError("connection") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise CloudError("invalid_response") from None
        except Exception:
            # Unknown transport/library errors must not expose credentials or response bodies.
            raise CloudError("invalid_response") from None


class MistralClient:
    def __init__(self, consent):
        self.consent = consent

    def generate(self, stage, user_input, response_model=None, *, max_attempts=1,
                 max_tokens=512, timeout_seconds=120):
        self.consent.require()
        if type(max_attempts) is not int or max_attempts != 1 or response_model is None:
            raise ValueError("Cloud generation requires one attempt and a response schema")
        model = check_configuration()
        version = prompt_version_for_stage(stage)
        started = perf_counter()
        reply = MistralTransport(model, self.consent, timeout=timeout_seconds).complete([
            {"role": "system", "content": "Return a valid JSON object only."},
            {"role": "user", "content": build_prompt(stage, user_input)},
        ], {"type": "json_schema", "json_schema": {
            "name": response_model.__name__.lower(), "schema": response_model.model_json_schema(),
        }}, temperature=0.2, max_tokens=max_tokens)
        elapsed = perf_counter() - started
        if reply.finish_reason != "stop":
            raise CloudError("incomplete")
        try:
            def reject_constant(value):
                raise ValueError("Non-JSON numeric constant")
            parsed = json.loads(reply.text or "", parse_constant=reject_constant)
        except ValueError:
            raise CloudError("invalid_json") from None
        try:
            data = response_model.model_validate(parsed)
        except ValidationError:
            raise CloudError("invalid_schema") from None
        return GenerationResult(stage=stage, model=model, prompt_version=version, data=data,
            finish_reason=reply.finish_reason, response_time_seconds=elapsed,
            pydantic_valid=True, provider="mistral", reported_model=reply.reported_model,
            usage=reply.usage.model_dump() if reply.usage else None)


def select_client(provider="local", *, consent=None) -> ConceptClient:
    if provider == "local":
        return LLMClient()
    if provider == "mistral":
        consent = consent or CloudConsent()
        consent.require()
        check_configuration()
        return MistralClient(consent)
    raise ValueError("Unknown provider")
