"""Offline by default; explicit commands permit one fictional connectivity or concept call."""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import httpx2 as httpx

from hankeluotsi import model_quality as q
from hankeluotsi.benchmark_execution import private_output
from hankeluotsi.mistral_client import (
    ENDPOINT, CloudConsent, CloudError, MistralClient, _answer_text, _http_error,
    check_configuration, request_error_diagnostic, safe_response_metadata,
)
from hankeluotsi.prompts import build_prompt, concept_generation_input, prompt_version_for_stage
from hankeluotsi.schemas import ConceptPaper


MODELS_ENDPOINT = "https://api.mistral.ai/v1/models"
CONNECTIVITY_MAX_OUTPUT_TOKENS = 256
CONNECTIVITY_TOKEN_LIMITS = (32, 128, 256, 512)


def _catalogue_diagnostic(result, response, key, code):
    if response is not None:
        if result["mistral_large_model_ids"] is not None:
            return {"error_code": None, "http_status": result["http_status"],
                "response_metadata": safe_response_metadata(response),
                "next_step": "Catalogue received; listing does not authorize or prove generation."}
        detail = request_error_diagnostic(response, secret=key)
        if 200 <= result["http_status"] < 300:
            detail.update(reason="invalid_catalogue", explanation="The HTTP response did not contain a usable bounded model catalogue.",
                next_step="Review safe metadata and existing console records; do not repeat requests without approval.")
        detail["error_code"] = code
        return detail
    return {"error_code": code, "http_status": None, "provider_error_code": None,
        "parameter": None, "sanitized_message": None, "response_metadata": None,
        "explanation": str(CloudError(code)),
        "next_step": "Run offline --diagnose in the existing configured shell. Do not repeat requests without approval."}


def model_access(*, include_diagnostics=False):
    """One explicit catalogue GET; expose only status and bounded public Large IDs."""
    result = {"http_status": None, "mistral_large_model_ids": None, "mistral_large_4_listed": None}
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        if include_diagnostics:
            result["diagnostic"] = _catalogue_diagnostic(result, None, key, "missing_key")
        return result
    response, failure_code = None, "invalid_response"
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False,
                          transport=httpx.HTTPTransport(retries=0, trust_env=False)) as client:
            response = client.get(MODELS_ENDPOINT, headers={"Authorization": "Bearer " + key})
            result["http_status"] = response.status_code
            if not 200 <= response.status_code < 300:
                failure_code = _http_error(response.status_code).code
                return result
            if len(response.content) > 1_000_000:
                return result
            payload = response.json()
            # The official schema uses data; its example also shows a bare array.
            entries = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(entries, list) or len(entries) > 10000:
                return result
            models = set()
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                    return result
                identifier = entry["id"]
                if len(identifier) <= 128 and re.fullmatch(
                        r"mistral-large(?:-(?:latest|[0-9]+(?:[.-][0-9]+)*(?:-(?:latest|preview))?))?", identifier):
                    if key in identifier:
                        return result
                    models.add(identifier)
            if len(models) > 256:
                return result
            result.update(mistral_large_model_ids=sorted(models), mistral_large_4_listed="mistral-large-4" in models)
    except httpx.TimeoutException:
        failure_code = "timeout"
    except httpx.RequestError:
        failure_code = "connection"
    except Exception:
        # Never print provider error bodies, headers, exception text or arbitrary IDs.
        pass
    finally:
        if include_diagnostics:
            result["diagnostic"] = _catalogue_diagnostic(result, response, key, failure_code)
    return result


def configuration_status():
    try:
        check_configuration()
    except CloudError as error:
        return {"configured": False, "error_code": error.code, "network_calls": 0,
            "model_access_verified": False, "billing_verified": False}
    return {"configured": True, "error_code": None, "network_calls": 0,
        "model_access_verified": False, "billing_verified": False}


def connectivity_request(model, *, max_output_tokens=CONNECTIVITY_MAX_OUTPUT_TOKENS):
    if type(max_output_tokens) is not int or max_output_tokens not in CONNECTIVITY_TOKEN_LIMITS:
        raise ValueError("Connectivity token limit must be one of 32, 128, 256 or 512")
    return {"model": model, "messages": [{"role": "user",
        "content": "Fictional project: Meadow. Reply only OK."}],
        "max_tokens": max_output_tokens, "stream": False}


def diagnose_configuration():
    """Safe local request preview; no model/account lookup or HTTP client."""
    status = configuration_status()
    status["billing_note"] = "Unknown cost is not evidence of zero billing."
    status["authentication_context"] = {"key_source": "MISTRAL_API_KEY", "scheme": "Bearer",
        "workspace_access": "not_verified", "credential_validity": "not_verified"}
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    status["key_shape_flags"] = {"has_bearer_prefix": key.lower().startswith("bearer ") if key else None,
        "has_internal_whitespace": any(char.isspace() for char in key) if key else None,
        "has_surrounding_quotes": key[:1] in ("'", '"') or key[-1:] in ("'", '"') if key else None,
        "has_non_ascii": not key.isascii() if key else None}
    status["transport"] = {"httpx2_version": q.package_version("httpx2"),
        "client_trust_env": False, "transport_trust_env": False, "verify_tls": True,
        "follow_redirects": False, "automatic_retries": 0,
        "environment_presence_only": {name: bool(os.environ.get(name)) for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR")}}
    if status["configured"]:
        body = connectivity_request(check_configuration())
        status["request"] = {"method": "POST", "endpoint": ENDPOINT,
            "content_type": "application/json", "authorization": "configured; not displayed",
            "model": body["model"], "max_output_tokens": body["max_tokens"], "stream": body["stream"],
            "message_count": len(body["messages"]), "message_roles": [item["role"] for item in body["messages"]],
            "parameter_names": sorted(body), "automatic_retries": 0}
        status["next_step"] = "Verify this exact model's chat access in your Mistral workspace; do not run --live again without authorization."
    return status


def live_connectivity(*, max_output_tokens=CONNECTIVITY_MAX_OUTPUT_TOKENS):
    """One owner-authorized minimal request; no document generation, files or retries."""
    # Validate the fixed small budgets before configuration or network work.
    connectivity_request("validation-placeholder", max_output_tokens=max_output_tokens)
    result = {"success": False, "requests_attempted": 0, "http_status": None,
        "api_request_succeeded": None, "outcome": "not_started", "error_code": None,
        "authentication_verified": None, "model_access_verified": None,
        "response_generated": None, "finish_reason": None, "usage": None,
        "completion_truncated": None, "output_token_limit_reached": None,
        "max_output_tokens": max_output_tokens, "automatic_retries": 0,
        "estimated_cost": None, "actual_billed_cost": None,
        "billing_note": "The API did not report an actual billed cost; null does not mean zero."}
    started = perf_counter()
    try:
        model = check_configuration()
        key = os.environ["MISTRAL_API_KEY"].strip()
        # Separate connectivity probe: the concept transport deliberately requires >=128 tokens.
        with httpx.Client(timeout=60, follow_redirects=False, trust_env=False,
                          transport=httpx.HTTPTransport(retries=0, trust_env=False)) as client:
            result["requests_attempted"] = 1
            response = client.post(ENDPOINT,
                headers={"Authorization": "Bearer " + key},
                json=connectivity_request(model, max_output_tokens=max_output_tokens))
            result["http_status"] = response.status_code
            result["api_request_succeeded"] = 200 <= response.status_code < 300
            if not 200 <= response.status_code < 300:
                raise _http_error(response.status_code, response=response, secret=key) from None
            result.update(authentication_verified=True, model_access_verified=True)
            if len(response.content) > 1_000_000:
                raise CloudError("invalid_response")
            payload = response.json()
            choice = payload["choices"][0]
            text = _answer_text(choice["message"]["content"])
            result["response_generated"] = bool(text and text.strip())
            finish = choice.get("finish_reason")
            result["finish_reason"] = finish if finish in ("stop", "length", "model_length") else "unknown"
            usage = payload.get("usage")
            if usage is not None:
                result["usage"] = q.Usage.model_validate({name: usage.get(name) for name in
                    ("prompt_tokens", "completion_tokens", "total_tokens")}).model_dump()
                used = result["usage"]["completion_tokens"]
                if used is not None:
                    result["output_token_limit_reached"] = used >= max_output_tokens
            result["completion_truncated"] = finish in ("length", "model_length") if finish in ("stop", "length", "model_length") else None
            result["success"] = result["response_generated"] and finish == "stop"
            if result["success"]:
                result.update(outcome="complete", explanation="The API request and the short final response completed successfully.")
            elif finish == "length":
                result.update(outcome="output_token_limit", error_code="output_token_limit",
                    output_token_limit_reached=True,
                    explanation="The API request succeeded, but generation stopped at its output-token limit. This is not an HTTP/API failure.")
            elif finish == "model_length":
                result.update(outcome="context_limit", error_code="context_limit",
                    explanation="The API request succeeded, but generation stopped at the model context limit.")
            else:
                result["error_code"] = "incomplete" if finish != "stop" else "invalid_response"
                result.update(outcome="incomplete_response" if finish != "stop" else "response_error",
                    explanation="The API request succeeded, but a complete final response was not verified.")
    except CloudError as error:
        result["error_code"] = error.code
        result["outcome"] = ("http_api_error" if result["api_request_succeeded"] is False else
            "configuration_error" if error.code in ("missing_key", "missing_model") else "response_error")
        result["explanation"] = str(error)
        if error.diagnostic is not None:
            result["diagnostic"] = error.diagnostic
    except httpx.TimeoutException:
        result["error_code"] = "timeout"
        result["outcome"] = "timeout"
    except httpx.RequestError:
        result["error_code"] = "connection"
        result["outcome"] = "connection_error"
    except Exception:
        # Never display provider bodies, generated text, headers or exception details.
        result["error_code"] = "invalid_response"
        result["outcome"] = "response_error"
    result["next_step"] = ("No further request is needed for connectivity; production schema acceptance remains separate."
        if result["success"] else "Review this outcome. Do not retry, raise limits or generate again without explicit approval.")
    result["elapsed_seconds"] = perf_counter() - started
    return result


def smoke(output, *, execute_cloud=False, fictional_only=False, accept_costs=False, pricing=None):
    if any(value is not True for value in (execute_cloud, fictional_only, accept_costs)):
        raise ValueError("Explicit execution, fictional-data and cost authorization are required")
    output = private_output(output)
    model = check_configuration()
    case = next(case for case in q.load_cases() if case.case_id == "Q01")
    user_input = concept_generation_input(case.idea, case.language)
    output.mkdir(parents=True, exist_ok=False)
    prompt = build_prompt("concept", user_input)
    schema = ConceptPaper.model_json_schema()
    source_root = Path(__file__).resolve().parents[1]
    q.write_new(output / "request.json", {"case_id": case.case_id, "language": case.language,
        "requested_model": model, "prompt_version": prompt_version_for_stage("concept"),
        "messages": [{"role": "system", "content": "Return a valid JSON object only."}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "conceptpaper", "schema": schema}},
        "source_sha256": {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in
            ("hankeluotsi/mistral_smoke.py", "hankeluotsi/mistral_client.py", "hankeluotsi/prompts.py", "hankeluotsi/schemas.py")},
        "temperature": 0.2, "max_output_tokens": 512, "http_phase_timeout_seconds": 120,
        "automatic_retries": 0, "fictional_only": True})
    receipt = {"version": "mistral_single_smoke_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": "Q01", "provider": "mistral", "requested_model": model,
        "prompt_version": prompt_version_for_stage("concept"), "client_invocations": 1,
        "automatic_retries": 0, "success": False, "reported_model": None, "usage": None,
        "finish_reason": None, "json_valid": None, "pydantic_valid": None,
        "estimated_standard_uncached_cost": None, "actual_billed_cost": None,
        "pricing": pricing.model_dump(mode="json") if pricing else None,
        "billing_note": "Usage estimate only if exact reported model and owner-verified pricing match; not an invoice."}
    started = perf_counter()
    try:
        result = MistralClient(CloudConsent(True, True)).generate("concept", user_input,
            ConceptPaper, max_attempts=1, max_tokens=512, timeout_seconds=120)
        receipt.update(success=True, reported_model=result.reported_model, usage=result.usage,
            finish_reason=result.finish_reason, json_valid=True, pydantic_valid=True,
            generation_seconds=result.response_time_seconds,
            consistency_findings=[{"code": item.code.value, "severity": item.severity.value}
                for item in q.check_concept_consistency(result.data)])
        if pricing:
            receipt["estimated_standard_uncached_cost"] = q.estimate_cost(q.Reply(
                reported_model=result.reported_model, usage=result.usage,
                billing_basis=pricing.billing_basis), "mistral", pricing)
        q.write_new(output / "concept.json", result.data.model_dump(mode="json"))
    except CloudError as error:
        receipt.update(error_code=error.code, http_status=error.http_status)
        if error.diagnostic is not None:
            receipt["diagnostic"] = error.diagnostic
    except Exception:
        receipt.update(error_code="unexpected", http_status=None)
    receipt["elapsed_seconds"] = perf_counter() - started
    q.write_new(output / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="No network by default. Explicit smoke: one fictional, potentially billed request.")
    parser.add_argument("--live", action="store_true",
        help="Authorize one paid fictional short-response request, default 256 output tokens, no retries or saved files")
    parser.add_argument("--max-output-tokens", type=int, choices=CONNECTIVITY_TOKEN_LIMITS,
        help="With --live only: explicit small output cap (default 256); 32 reproduces the historical limit")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--models", action="store_true",
        help="Authorize one authenticated GET /v1/models; show only status and public Mistral Large IDs, never generate")
    parser.add_argument("--diagnostics", action="store_true",
        help="With --models only: include sanitized failure explanation and safe response metadata from the same GET")
    parser.add_argument("--diagnose", action="store_true",
        help="Offline preview of the configured model and fictional request, without credentials or API calls")
    parser.add_argument("--execute-cloud", action="store_true")
    parser.add_argument("--fictional-only", action="store_true")
    parser.add_argument("--accept-costs", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pricing", type=Path, help="Optional owner-verified existing Pricing JSON; never a credential file")
    args = parser.parse_args(argv)
    if args.max_output_tokens is not None and not args.live:
        parser.error("--max-output-tokens requires --live")
    if args.diagnostics and not args.models:
        parser.error("--diagnostics requires --models; it never starts a request by itself")
    if args.models:
        if args.live or args.diagnose or args.preflight or args.execute_cloud or args.fictional_only or args.accept_costs or args.output or args.pricing:
            parser.error("--models is a standalone one-GET model-access check")
        result = model_access(include_diagnostics=args.diagnostics)
        print(json.dumps(result))
        return 0 if result["mistral_large_model_ids"] is not None else 2 if result["http_status"] is None else 1
    if args.diagnose:
        if args.live or args.preflight or args.execute_cloud or args.fictional_only or args.accept_costs or args.output or args.pricing:
            parser.error("--diagnose is an offline standalone request preview")
        result = diagnose_configuration()
        print(json.dumps(result))
        return 0 if result["configured"] else 2
    if args.live:
        if args.preflight or args.execute_cloud or args.fictional_only or args.accept_costs or args.output or args.pricing:
            parser.error("--live is a standalone one-request connectivity test; do not combine it with other modes")
        result = live_connectivity(max_output_tokens=args.max_output_tokens or CONNECTIVITY_MAX_OUTPUT_TOKENS)
        print(json.dumps(result))
        return 0 if result["success"] else 2 if result["requests_attempted"] == 0 else 1
    if not args.execute_cloud:
        if args.output or args.pricing or args.fictional_only or args.accept_costs:
            parser.error("Preflight needs no output, pricing or execution flags")
        status = configuration_status()
        print(json.dumps(status))
        return 0 if status["configured"] else 2
    if args.preflight or not args.output:
        parser.error("Execution requires a new private output path and cannot be combined with preflight")
    try:
        pricing = q.Pricing.model_validate(q.read_json(args.pricing)) if args.pricing else None
        result = smoke(args.output, execute_cloud=args.execute_cloud, fictional_only=args.fictional_only,
            accept_costs=args.accept_costs, pricing=pricing)
    except (CloudError, ValueError, OSError):
        print("Smoke could not start or finish: check flags/configuration/private files and account usage before any new attempt.")
        return 2
    print("Single smoke passed; private receipt saved." if result["success"] else
          "Single smoke failed; safe error category saved privately. Check account usage before any new attempt.")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
