"""Bounded execution diagnostics over the existing fictional benchmark/review contracts."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx2 as httpx

from hankeluotsi import model_quality as q
from hankeluotsi.mistral_client import CloudConsent, CloudError, check_configuration
from hankeluotsi.mistral_benchmark import MistralProvider


class PreflightError(ValueError):
    pass


def private_output(path):
    root = (q.ROOT / ".benchmark-private").resolve()
    path = Path(path).resolve()
    if not root.is_relative_to(q.ROOT.resolve()) or not path.is_relative_to(root) or path == root:
        raise PreflightError("Output must be a new directory below .benchmark-private/.")
    if path.exists():
        raise PreflightError("Output already exists. Choose a new directory; no evidence is overwritten.")
    return path


def preflight(provider, model=None, endpoint="http://127.0.0.1:1234/v1", *, verify_cloud=False):
    if provider == "mistral":
        # Only presence and validated model ID leave this function, never the key.
        selected = check_configuration()
        if model and model != selected:
            raise PreflightError("Requested model differs from MISTRAL_MODEL.")
        result = {"provider": provider, "model": selected, "key_available": True,
                  "availability_verified": False, "billing_verified": False}
        if not verify_cloud:
            return result
        url = "https://api.mistral.ai/v1/models"
        headers = {"Authorization": "Bearer " + os.environ["MISTRAL_API_KEY"].strip()}
    elif provider == "local":
        selected = model or "qwen3.5-4b"
        url = q.local_endpoint(endpoint).removesuffix("/v1") + "/api/v1/models"
        headers = {}
    else:
        raise PreflightError("Choose local or mistral explicitly.")
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.get(url, headers=headers)
            if response.status_code in (401, 403):
                raise PreflightError("Model inventory authentication failed. No generation was attempted.")
            if response.status_code != 200:
                raise PreflightError("Model inventory unavailable. No generation was attempted.")
            payload = response.json()
        if provider == "local":
            match = next((x for x in payload["models"] if x.get("key") == selected), None)
            instances = match.get("loaded_instances", []) if match else []
            if not instances:
                raise PreflightError("Local model is not loaded. Load the exact model in LM Studio first.")
            return {"provider": provider, "model": selected, "availability_verified": True,
                "context_length": instances[0].get("config", {}).get("context_length"),
                "quantization": match.get("quantization"),
                "catalogue_reasoning_default": match.get("capabilities", {}).get("reasoning", {}).get("default"),
                "thinking_setting": "UI value not exposed; inspect returned reasoning counters, never assume off"}
        if not any(x.get("id") == selected for x in payload["data"]):
            raise PreflightError("Configured Mistral model is not available to this key.")
        result["availability_verified"] = True
        return result
    except PreflightError:
        raise
    except Exception:
        raise PreflightError("Could not safely inspect model inventory. Check server/network/configuration.") from None


def failure_type(attempt):
    if attempt["reply"]["finish_reason"] == "length":
        return "token_limit: no automatic retry; verify thinking and budget in a new run"
    if attempt["reply"]["error"]:
        return attempt["reply"]["error"]
    if attempt["incomplete_output"]:
        return "incomplete_finish"
    if not attempt["json_valid"]:
        return "empty_or_invalid_json"
    if not attempt["pydantic_valid"]:
        return "invalid_schema"
    return None


class DiagnosticLocalProvider:
    provider = "lm_studio"
    measure_latency = True

    def __init__(self, model, endpoint, output):
        self.requested_model = model
        self.endpoint = q.local_endpoint(endpoint)
        self.output = output
        self.diagnostics = {}

    def generate(self, request, manifest):
        body = {"model": self.requested_model, "messages": request.messages,
            "temperature": manifest.settings.temperature, "max_tokens": manifest.settings.max_tokens,
            "response_format": manifest.response_format, "stream": False}
        with httpx.Client(timeout=manifest.settings.timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = client.post(self.endpoint + "/chat/completions", json=body)
            payload = response.json()
        q.write_new(self.output / "diagnostics" / (request.request_sha256 + ".json"),
            {"request": body, "http_status": response.status_code, "response": payload})
        response.raise_for_status()
        choice = payload["choices"][0]
        message = choice["message"]
        reasoning = message.get("reasoning_content", message.get("reasoning", ""))
        usage = payload.get("usage")
        self.diagnostics[request.request_sha256] = {"reasoning_requested": "server_default",
            "reasoning_characters": len(reasoning) if isinstance(reasoning, str) else None,
            "reasoning_tokens": (usage or {}).get("completion_tokens_details", {}).get("reasoning_tokens"),
            "message_fields": sorted(message), "content_characters": len(message.get("content") or "")}
        return q.Reply(text=message.get("content"), reported_model=payload.get("model"),
            finish_reason=choice.get("finish_reason"), usage=q.Usage.model_validate({
                k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}) if usage else None)


class NativeLocalProvider(DiagnosticLocalProvider):
    """Opt-in native reasoning control; schema is prompted, then strictly validated locally."""

    def generate(self, request, manifest):
        if [m["role"] for m in request.messages] != ["system", "user"]:
            raise PreflightError("Native diagnostic mode accepts only the frozen single-turn fixture format.")
        body = {"model": self.requested_model, "input": request.messages[1]["content"],
            "system_prompt": request.messages[0]["content"] +
                "\nRequired output JSON schema (native_schema_prompt_v1):\n" +
                json.dumps(manifest.response_format["json_schema"]["schema"], ensure_ascii=False),
            "reasoning": "off", "max_output_tokens": manifest.settings.max_tokens,
            "temperature": manifest.settings.temperature, "stream": False, "store": False,
            "integrations": []}
        with httpx.Client(timeout=manifest.settings.timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = client.post(self.endpoint.removesuffix("/v1") + "/api/v1/chat", json=body)
            payload = response.json()
        q.write_new(self.output / "diagnostics" / (request.request_sha256 + ".json"),
            {"request": body, "http_status": response.status_code, "response": payload})
        response.raise_for_status()
        items = payload["output"]
        text = "\n".join(x["content"] for x in items if x.get("type") == "message")
        reasoning = "\n".join(x["content"] for x in items if x.get("type") == "reasoning")
        stats = payload.get("stats", {})
        input_tokens, output_tokens = stats.get("input_tokens"), stats.get("total_output_tokens")
        # Native API does not document a finish reason: do not invent 'stop'.
        finish = payload.get("finish_reason")
        self.diagnostics[request.request_sha256] = {"reasoning_requested": "off",
            "reasoning_characters": len(reasoning), "reasoning_tokens": stats.get("reasoning_output_tokens"),
            "content_characters": len(text), "schema_delivery": "native_schema_prompt_v1",
            "native_finish_reason": finish, "at_output_cap": output_tokens >= manifest.settings.max_tokens
                if isinstance(output_tokens, int) else None}
        usage = q.Usage(prompt_tokens=input_tokens, completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None)
        return q.Reply(text=text, reported_model=payload.get("model_instance_id"), finish_reason=finish, usage=usage)


def run(provider, case_ids, output, *, model=None, endpoint="http://127.0.0.1:1234/v1",
        max_tokens=4096, execute_cloud=False, fictional_only=False, accept_costs=False, local_api="compatible"):
    output = private_output(output)
    if not case_ids or len(case_ids) > 5 or len(set(case_ids)) != len(case_ids):
        raise PreflightError("Select one to five distinct fictional cases.")
    source = q.create_manifest(q.Settings(trials=1, max_tokens=max_tokens))
    if set(case_ids) - {c.case_id for c in source.cases}:
        raise PreflightError("Unknown fictional case. No requests made.")
    if provider == "mistral" and not (execute_cloud and fictional_only and accept_costs):
        raise PreflightError("Cloud requires --execute-cloud --fictional-only --accept-costs after billing review.")
    if local_api not in ("compatible", "native") or provider == "mistral" and local_api != "compatible":
        raise PreflightError("Native mode is a local-only diagnostic, not a paired cloud comparison.")
    info = preflight(provider, model, endpoint, verify_cloud=provider == "mistral")
    if provider == "local" and info.get("context_length") and max_tokens >= info["context_length"]:
        raise PreflightError("Output token limit leaves no input context. Reduce --max-tokens.")
    selected = source.model_copy(update={"requests": [r for r in source.requests if r.case_id in case_ids]})
    q.write_new(output / "source-manifest.json", source.model_dump(mode="json"))
    q.write_new(output / "preflight.json", info)
    local_class = NativeLocalProvider if local_api == "native" else DiagnosticLocalProvider
    adapter = (local_class(info["model"], endpoint, output) if provider == "local"
               else MistralProvider(CloudConsent(True, True)))
    report = q.run(selected, adapter, checkpoint=output / "attempts")
    report["execution"] = {"version": "execution_repair_v1", "case_ids": case_ids,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "local_api": local_api if provider == "local" else None,
        "schema_delivery": "native_schema_prompt_v1" if local_api == "native" else "server_json_schema",
        "source_manifest_sha256": q.digest(source.model_dump(mode="json")),
        "retries": 0, "reasoning_requested": "off" if local_api == "native" else "server_default" if provider == "local" else "provider_default"}
    for attempt in report["attempts"]:
        attempt["execution_error"] = (adapter.errors.get(attempt["request_sha256"]) if provider == "mistral" else None) or failure_type(attempt)
        if provider == "local":
            attempt["diagnostics"] = adapter.diagnostics.get(attempt["request_sha256"])
            diagnostic = attempt["diagnostics"] or {}
            if local_api == "native":
                if diagnostic.get("reasoning_tokens", 0) or diagnostic.get("reasoning_characters", 0):
                    attempt["execution_error"] = "reasoning_active_despite_off"
                elif diagnostic.get("at_output_cap"):
                    attempt["execution_error"] = "token_limit: native output reached cap; no retry"
    q.write_new(output / "results.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fictional benchmark preflight/smoke; no credentials printed.")
    parser.add_argument("action", choices=("preflight", "run"))
    parser.add_argument("--provider", choices=("local", "mistral"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--verify-model", action="store_true", help="Read model inventory only, no generation.")
    parser.add_argument("--case-ids", nargs="+", default=["Q01"])
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--local-api", choices=("compatible", "native"), default="compatible")
    parser.add_argument("--output", type=Path)
    for flag in ("execute-cloud", "fictional-only", "accept-costs"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "preflight":
            info = preflight(args.provider, args.model, args.endpoint, verify_cloud=args.verify_model)
            print("Configuration present; model availability " + ("verified." if info["availability_verified"] else "not verified (use --verify-model)."))
            if args.provider == "mistral":
                print("No generation. Balance/pricing/cost cap still require owner verification; not inferred from the key.")
            return
        if args.output is None:
            raise PreflightError("--output must be a new private directory.")
        report = run(args.provider, args.case_ids, args.output, model=args.model, endpoint=args.endpoint,
            max_tokens=args.max_tokens, execute_cloud=args.execute_cloud,
            fictional_only=args.fictional_only, accept_costs=args.accept_costs, local_api=args.local_api)
        print(f"Recorded {len(report['attempts'])} attempts; {report['summary']['first_attempt_successes']} valid first attempts. No retries.")
        for attempt in report["attempts"]:
            if attempt["execution_error"]:
                print(attempt["case_id"] + ": " + attempt["execution_error"])
        if report["summary"]["first_attempt_successes"] != len(report["attempts"]):
            parser.exit(1, "One or more attempts failed. Evidence preserved; no automatic retry.\n")
    except (CloudError, PreflightError) as error:
        parser.exit(2, str(error) + "\n")
    except Exception:
        parser.exit(2, "Execution rejected. Check bounded settings and private output path. No exception details printed.\n")


if __name__ == "__main__":
    main()
