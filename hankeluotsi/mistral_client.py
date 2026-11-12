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
ERROR_MESSAGES = {
    "consent_required": "Confirm fictional data and cloud processing before generating with Mistral.",
    "missing_key": "Mistral is unavailable. Configure MISTRAL_API_KEY and restart the app.",
    "missing_model": "Mistral is unavailable. Configure a valid MISTRAL_MODEL and restart the app.",
    "authentication": "Mistral authentication failed. Check the API key and account permissions.",
    "rate_limit": "Mistral rate limit reached. Wait before submitting again.",
    "timeout": "Mistral timed out. No automatic retry was made; check before submitting again.",
    "connection": "Could not connect securely to Mistral. Check the network and try again explicitly.",
    "http_error": "Mistral rejected the request or is unavailable. Check model access and service status.",
    "invalid_response": "Mistral returned an invalid response. The concept was not saved.",
    "invalid_json": "Mistral returned empty or invalid JSON. The concept was not saved.",
    "invalid_schema": "Mistral output failed schema validation. The concept was not saved.",
    "incomplete": "Mistral output was incomplete or truncated. The concept was not saved.",
}


class CloudError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(ERROR_MESSAGES[code])


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
    if not os.getenv("MISTRAL_API_KEY", "").strip():
        raise CloudError("missing_key")
    return configured_model()


class ConceptClient(Protocol):
    def generate(self, stage, user_input, response_model=None, *, max_attempts=1) -> GenerationResult: ...


class MistralTransport:
    """One bounded HTTPS request. No redirects, proxies, retries, tools or logging."""

    def __init__(self, model, consent, *, timeout=120):
        self.model, self.consent, self.timeout = model, consent, timeout

    def complete(self, messages, response_format, *, temperature, max_tokens):
        self.consent.require()
        check_configuration()
        # Model must be the explicit environment choice, never a hidden default.
        if self.model != configured_model():
            raise CloudError("missing_model")
        key = os.environ["MISTRAL_API_KEY"].strip()
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                response = client.post(ENDPOINT, headers={"Authorization": "Bearer " + key}, json={
                    "model": self.model, "messages": messages, "temperature": temperature,
                    "max_tokens": max_tokens, "response_format": response_format, "stream": False,
                })
                if response.status_code in (401, 403):
                    raise CloudError("authentication")
                if response.status_code == 429:
                    raise CloudError("rate_limit")
                if not 200 <= response.status_code < 300:
                    raise CloudError("http_error")
                if len(response.content) > 1_000_000:
                    raise CloudError("invalid_response")
                payload = response.json()
                choice = payload["choices"][0]
                # Do not persist even a server-echoed credential in output or metadata.
                text = choice["message"]["content"]
                model = payload.get("model")
                finish = choice.get("finish_reason")
                if (not isinstance(text, str) or model is not None and not isinstance(model, str)
                        or finish is not None and not isinstance(finish, str)):
                    raise CloudError("invalid_response")
                usage = payload.get("usage")
                return Reply(text=text.replace(key, "[REDACTED]"),
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

    def generate(self, stage, user_input, response_model=None, *, max_attempts=1):
        self.consent.require()
        if max_attempts != 1 or response_model is None:
            raise ValueError("Cloud generation requires one attempt and a response schema")
        model = check_configuration()
        version = prompt_version_for_stage(stage)
        started = perf_counter()
        reply = MistralTransport(model, self.consent).complete([
            {"role": "system", "content": "Return a valid JSON object only."},
            {"role": "user", "content": build_prompt(stage, user_input)},
        ], {"type": "json_schema", "json_schema": {
            "name": response_model.__name__.lower(), "schema": response_model.model_json_schema(),
        }}, temperature=0.2, max_tokens=512)
        elapsed = perf_counter() - started
        if reply.finish_reason != "stop":
            raise CloudError("incomplete")
        try:
            parsed = json.loads(reply.text or "")
        except ValueError:
            raise CloudError("invalid_json") from None
        try:
            data = response_model.model_validate(parsed)
        except ValidationError:
            raise CloudError("invalid_schema") from None
        return GenerationResult(stage=stage, model=model, prompt_version=version, data=data,
            finish_reason=reply.finish_reason, response_time_seconds=elapsed,
            pydantic_valid=True, provider="mistral")


def select_client(provider="local", *, consent=None) -> ConceptClient:
    if provider == "local":
        return LLMClient()
    if provider == "mistral":
        consent = consent or CloudConsent()
        consent.require()
        check_configuration()
        return MistralClient(consent)
    raise ValueError("Unknown provider")
