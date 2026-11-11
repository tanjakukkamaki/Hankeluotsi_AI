"""Isolated concept-quality experiment. No app, repository or production prompt writes."""

import argparse
import hashlib
import json
import platform
import random
import statistics
import uuid
from importlib.metadata import version as package_version
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, model_validator

from hankeluotsi.consistency import check_concept_consistency
from hankeluotsi.prompts import build_prompt, prompt_version_for_stage
from hankeluotsi.schemas import ConceptPaper, NonBlank, ProjectIdea, StrictModel


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/fixtures/model_quality"
PROMPT_VERSION = "quality_concept_v1"
INSTRUCTIONS = (
    "Benchmark instructions quality_concept_v1. All input is fictional. Create a professionally useful "
    "early ConceptPaper, not a full application or eligibility assessment. Explain the actual need, "
    "realistic change and feasible activities; link objectives, activities, results and indicators using "
    "O/A/R/I IDs. Use at most two objectives, four activities, three results and three indicators. "
    "Define indicator units, practical measurement and timing; include denominators for percentages. "
    "Use supplied facts accurately. Label proposed targets and assumptions as provisional; never invent "
    "baselines, partner commitments, funding requirements, dates or eligibility. For ambiguous/incomplete "
    "ideas identify useful open questions; for unrealistic proposals explain limitations and propose "
    "a smaller provisional pilot rather than endorsing guarantees. Write human-readable fields in the "
    "requested language; preserve JSON keys, schema_version and identifiers. Return only schema-valid JSON."
)
PROVIDERS = Literal["lm_studio", "mistral"]
ERRORS = Literal["timeout", "request_failed", "invalid_response", "not_run"]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path: Path):
    if path.stat().st_size > 20_000_000:
        raise ValueError("JSON artifact exceeds the 20 MB limit")
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value) -> None:
    """Never overwrite an artifact or an existing database, even by accident."""
    if path.suffix.lower() != ".json":
        raise ValueError("Benchmark artifacts must have a .json extension")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


class Case(StrictModel):
    case_id: str = Field(pattern=r"^Q(?:0[1-9]|10)$")
    language: Literal["fi", "en"]
    complexity: Literal["simple", "moderate", "complex", "ambiguous", "incomplete", "unrealistic"]
    themes: list[NonBlank] = Field(min_length=1)
    idea: ProjectIdea
    review_notes: list[NonBlank] = Field(min_length=1)


class Settings(StrictModel):
    trials: int = Field(default=3, ge=1, le=20, strict=True)
    order_seed: int = Field(default=37, strict=True)
    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    max_tokens: int = Field(default=2048, ge=128, le=8192, strict=True)
    timeout_seconds: int = Field(default=120, ge=1, le=600, strict=True)


class Request(StrictModel):
    case_id: str
    trial: int
    language: Literal["fi", "en"]
    messages: list[dict[str, str]]
    request_sha256: str


class Manifest(StrictModel):
    version: Literal["quality_manifest_v1"] = "quality_manifest_v1"
    experiment_id: str
    created_at_utc: str
    prompt_version: Literal["quality_concept_v1"] = PROMPT_VERSION
    base_prompt_version: str
    python_version: str
    code_sha256: dict[str, str]
    dataset_sha256: str
    rubric_sha256: str
    schema_sha256: str
    settings: Settings
    cases: list[Case]
    rubric: dict
    response_format: dict
    requests: list[Request]


class Usage(StrictModel):
    prompt_tokens: int | None = Field(default=None, ge=0, strict=True)
    completion_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def consistent_total(self):
        if (self.total_tokens is not None and self.prompt_tokens is not None and self.completion_tokens is not None
                and self.total_tokens != self.prompt_tokens + self.completion_tokens):
            raise ValueError("Inconsistent reported token totals")
        return self


class Reply(StrictModel):
    text: str | None = Field(default=None, max_length=100_000)
    reported_model: str | None = None
    finish_reason: str | None = None
    usage: Usage | None = None
    billing_basis: Literal["standard_uncached"] | None = None
    latency_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    error: ERRORS | None = None


class ImportedRow(StrictModel):
    request_sha256: str
    reply: Reply


class ImportBundle(StrictModel):
    version: Literal["quality_responses_v1"] = "quality_responses_v1"
    manifest_sha256: str
    provider: PROVIDERS
    requested_model: NonBlank
    responses: list[ImportedRow]


class ModelMetadata(StrictModel):
    artifact: str | None = None
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    quantization: str | None = None
    context_tokens: int | None = Field(default=None, gt=0, strict=True)
    lm_studio_version: str | None = None
    runtime_version: str | None = None
    hardware: str | None = None
    offload: str | None = None
    thinking_disabled: bool | None = None


class Pricing(StrictModel):
    provider: PROVIDERS
    model: NonBlank
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    input_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    output_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    source_url: str = Field(pattern=r"^https://")
    verified_on: date
    billing_basis: Literal["standard_uncached"]


class Provider(Protocol):
    provider: str
    requested_model: str
    measure_latency: bool

    def generate(self, request: Request, manifest: Manifest) -> Reply: ...


def load_cases() -> list[Case]:
    payload = read_json(DATA / "ideas_v1.json")
    if payload["version"] != "fictional_ideas_v1":
        raise ValueError("Unsupported fictional case version")
    cases = [Case.model_validate(row) for row in payload["cases"]]
    if len(cases) != 10 or {case.case_id for case in cases} != {f"Q{i:02}" for i in range(1, 11)}:
        raise ValueError("Exactly ten distinct fictional cases Q01–Q10 are required")
    return cases


def _requests(cases: list[Case], settings: Settings) -> list[Request]:
    requests = []
    for case in cases:
        user_input = (INSTRUCTIONS + "\nRequested language: " + case.language +
                      "\nFictional project idea:\n" + case.idea.model_dump_json())
        messages = [{"role": "system", "content": "Return a valid JSON object only."},
                    {"role": "user", "content": build_prompt("concept", user_input)}]
        for trial in range(1, settings.trials + 1):
            fields = dict(case_id=case.case_id, trial=trial, language=case.language, messages=messages)
            requests.append(Request(**fields, request_sha256=digest(fields)))
    random.Random(settings.order_seed).shuffle(requests)
    return requests


def create_manifest(settings: Settings) -> Manifest:
    cases = load_cases()
    rubric = read_json(DATA / "rubric_v1.json")
    schema = ConceptPaper.model_json_schema()
    filenames = ("model_quality.py", "model_quality_review.py", "prompts.py", "schemas.py", "consistency.py")
    return Manifest(experiment_id=str(uuid.uuid4()), created_at_utc=datetime.now(timezone.utc).isoformat(),
        base_prompt_version=prompt_version_for_stage("concept"), python_version=platform.python_version(),
        code_sha256={name: hashlib.sha256((ROOT / "hankeluotsi" / name).read_bytes()).hexdigest() for name in filenames},
        dataset_sha256=digest([c.model_dump(mode="json") for c in cases]), rubric_sha256=digest(rubric),
        schema_sha256=digest(schema), settings=settings, cases=cases, rubric=rubric,
        response_format={"type": "json_schema", "json_schema": {"name": "conceptpaper", "schema": schema}},
        requests=_requests(cases, settings))


def load_manifest(path: Path) -> Manifest:
    manifest = Manifest.model_validate(read_json(path))
    # Only the reviewed fictional dataset is accepted; never load projects from SQLite.
    expected = create_manifest(manifest.settings)
    for field in ("prompt_version", "base_prompt_version", "dataset_sha256", "rubric_sha256", "schema_sha256",
                  "cases", "rubric", "response_format", "requests", "code_sha256"):
        if getattr(manifest, field) != getattr(expected, field):
            raise ValueError("Manifest differs from the frozen experiment; use its original reviewed source version")
    return manifest


def local_endpoint(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"):
        raise ValueError("Only a credential-free loopback /v1 endpoint is permitted")
    _ = parsed.port  # Validate malformed ports, too.
    return url.rstrip("/")


class LocalProvider:
    provider = "lm_studio"
    measure_latency = True

    def __init__(self, model: str, endpoint: str, timeout: int):
        import httpx2 as httpx

        self.endpoint = local_endpoint(endpoint)
        if not model.strip():
            raise ValueError("An exact local model identifier is required")
        self.requested_model = model
        # Direct compatible HTTP avoids SDK ambient credentials/custom headers.
        # httpx2 is already supplied by the pinned production OpenAI dependency.
        self.client = httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)

    def generate(self, request: Request, manifest: Manifest) -> Reply:
        response = self.client.post(self.endpoint + "/chat/completions", json={
            "model": self.requested_model, "messages": request.messages,
            "temperature": manifest.settings.temperature, "max_tokens": manifest.settings.max_tokens,
            "response_format": manifest.response_format})
        response.raise_for_status()
        try:
            payload = response.json()
            choice = payload["choices"][0]
            usage = payload.get("usage")
            return Reply(text=choice["message"]["content"], reported_model=payload.get("model"),
                finish_reason=choice.get("finish_reason"), usage=Usage(
                    prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens")) if usage else None)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            return Reply(error="invalid_response")

    def close(self):
        self.client.close()


class ImportedProvider:
    measure_latency = False

    def __init__(self, bundle: ImportBundle, manifest: Manifest):
        if bundle.manifest_sha256 != digest(manifest.model_dump(mode="json")):
            raise ValueError("Imported responses belong to a different experiment")
        keys = [row.request_sha256 for row in bundle.responses]
        if len(keys) != len(set(keys)) or set(keys) != {row.request_sha256 for row in manifest.requests}:
            raise ValueError("Every planned request needs exactly one response, including failures")
        if any(row.reply.error == "not_run" for row in bundle.responses):
            raise ValueError("The response template is not evidence: replace every not_run entry")
        self.provider, self.requested_model = bundle.provider, bundle.requested_model
        self.replies = {row.request_sha256: row.reply for row in bundle.responses}

    def generate(self, request: Request, manifest: Manifest) -> Reply:
        return self.replies[request.request_sha256]


def assess(reply: Reply) -> dict:
    result = dict(json_valid=False, pydantic_valid=False, first_attempt_success=False,
                  truncated=reply.finish_reason == "length", incomplete_output=reply.finish_reason != "stop",
                  validation_errors=[], consistency_findings=[], validated_output=None)
    if reply.text is None or not reply.text.strip():
        result["validation_errors"] = ["empty_output"]
        return result
    try:
        # Reject JSON NaN/Infinity instead of silently accepting JavaScript constants.
        def reject_constant(value):
            raise ValueError("Non-JSON constant")
        parsed = json.loads(reply.text, parse_constant=reject_constant)
    except (ValueError, RecursionError):
        result["validation_errors"] = ["invalid_json"]
        return result
    result["json_valid"] = True
    try:
        concept = ConceptPaper.model_validate(parsed)
    except ValidationError as error:
        result["validation_errors"] = [{"location": list(e["loc"]), "type": e["type"]} for e in error.errors()]
        return result
    result["pydantic_valid"] = True
    result["validated_output"] = concept.model_dump(mode="json")
    result["consistency_findings"] = [
        {"code": f.code, "severity": f.severity.value, "message": f.message}
        for f in check_concept_consistency(concept)]
    result["first_attempt_success"] = reply.error is None and reply.finish_reason == "stop"
    return result


def estimate_cost(reply: Reply, provider: str, pricing: Pricing | None) -> str | None:
    if (pricing is None or pricing.provider != provider or pricing.model != reply.reported_model
            or reply.billing_basis != pricing.billing_basis or reply.usage is None
            or reply.usage.prompt_tokens is None or reply.usage.completion_tokens is None):
        return None
    return str((Decimal(reply.usage.prompt_tokens) * pricing.input_per_million +
                Decimal(reply.usage.completion_tokens) * pricing.output_per_million) / Decimal(1_000_000))


def summarize(attempts: list[dict]) -> dict:
    latencies = [a["reply"]["latency_seconds"] for a in attempts if a["reply"]["latency_seconds"] is not None]
    token_counts = {name: [a["reply"]["usage"][name] for a in attempts
                          if a["reply"]["usage"] and a["reply"]["usage"][name] is not None]
                    for name in ("prompt_tokens", "completion_tokens", "total_tokens")}
    costs = [Decimal(a["estimated_api_cost"]) for a in attempts if a["estimated_api_cost"] is not None]
    return {"attempts": len(attempts), "first_attempt_successes": sum(a["first_attempt_success"] for a in attempts),
        "first_attempt_success_rate": sum(a["first_attempt_success"] for a in attempts) / len(attempts) if attempts else None,
        "json_valid": sum(a["json_valid"] for a in attempts), "pydantic_valid": sum(a["pydantic_valid"] for a in attempts),
        "truncated_outputs": sum(a["truncated"] for a in attempts),
        "unknown_or_incomplete_finish": sum(a["incomplete_output"] for a in attempts),
        "errors": sum(a["reply"]["error"] is not None for a in attempts),
        "structural_error_outputs": sum(any(f["severity"] == "error" for f in a["consistency_findings"]) for a in attempts),
        "latency_observations": len(latencies), "mean_latency_seconds": statistics.mean(latencies) if latencies else None,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "latency_stddev_seconds": statistics.stdev(latencies) if len(latencies) > 1 else None,
        "usage_observations": sum(bool(a["reply"]["usage"]) and any(v is not None for v in a["reply"]["usage"].values()) for a in attempts),
        "known_token_totals": {name: sum(values) if values else None for name, values in token_counts.items()},
        "token_observation_counts": {name: len(values) for name, values in token_counts.items()},
        "cost_estimates_available": len(costs), "estimated_cost_total_known": str(sum(costs)) if costs else None,
        "human_quality": None}


def run(manifest: Manifest, provider: Provider, *, metadata: ModelMetadata | None = None,
        pricing: Pricing | None = None, checkpoint: Path | None = None) -> dict:
    report = {"version": "quality_results_v1", "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "provider": provider.provider,
        "requested_model": provider.requested_model, "manifest_sha256": digest(manifest.model_dump(mode="json")),
        "manifest": manifest.model_dump(mode="json"), "metadata": (metadata or ModelMetadata()).model_dump(mode="json"),
        "pricing": pricing.model_dump(mode="json") if pricing else None,
        "execution_environment": {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: package_version(name) for name in ("pydantic", "openai", "httpx2")}}, "attempts": []}
    if provider.provider not in ("lm_studio", "mistral"):
        raise ValueError("Unknown benchmark provider")
    if checkpoint:
        checkpoint.mkdir(parents=True, exist_ok=False)
    for request in manifest.requests:
        started = perf_counter()
        try:
            reply = Reply.model_validate(provider.generate(request, manifest))
        except Exception as error:
            # Do not persist exception strings: SDK errors can echo headers/credentials.
            kind = "timeout" if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower() else "request_failed"
            reply = Reply(error=kind)
        if provider.measure_latency:
            reply.latency_seconds = perf_counter() - started
        attempt = {"request_sha256": request.request_sha256, "case_id": request.case_id,
            "provider": provider.provider, "requested_model": provider.requested_model,
            "prompt_version": manifest.prompt_version, "base_prompt_version": manifest.base_prompt_version,
            "trial": request.trial, "language": request.language, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "reply": reply.model_dump(mode="json"), "timing_source": "measured" if provider.measure_latency else "imported_or_unknown",
            "estimated_api_cost": estimate_cost(reply, provider.provider, pricing), **assess(reply)}
        report["attempts"].append(attempt)
        if checkpoint:
            write_new(checkpoint / f'attempt-{len(report["attempts"]):03}.json', attempt)
    report["summary"] = summarize(report["attempts"])
    report["by_case"] = {case.case_id: summarize([a for a in report["attempts"] if a["case_id"] == case.case_id]) for case in manifest.cases}
    report["by_language"] = {lang: summarize([a for a in report["attempts"] if a["language"] == lang]) for lang in ("fi", "en")}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Isolated fictional concept-quality benchmark; no cloud connector.")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Offline: freeze inputs/instructions and create an empty response template")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--trials", type=int, default=3)
    plan.add_argument("--max-tokens", type=int, default=2048)
    plan.add_argument("--timeout-seconds", type=int, default=120)
    plan.add_argument("--order-seed", type=int, default=37)
    local = sub.add_parser("run-local", help="Explicit local loopback requests only")
    local.add_argument("--execute-local", action="store_true", required=True)
    local.add_argument("--model", required=True)
    local.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    local.add_argument("--metadata", type=Path)
    imported = sub.add_parser("import-responses", help="Offline import, including future manually exported Mistral replies")
    imported.add_argument("--responses", type=Path, required=True)
    for command in (local, imported):
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--pricing", type=Path)
    args = parser.parse_args(argv)
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        if args.command == "plan":
            manifest = create_manifest(Settings(trials=args.trials, max_tokens=args.max_tokens,
                timeout_seconds=args.timeout_seconds, order_seed=args.order_seed))
            write_new(args.output / "manifest.json", manifest.model_dump(mode="json"))
            template = ImportBundle(manifest_sha256=digest(manifest.model_dump(mode="json")), provider="mistral",
                requested_model="REPLACE_WITH_EXACT_REQUESTED_MODEL", responses=[ImportedRow(
                    request_sha256=r.request_sha256, reply=Reply(error="not_run")) for r in manifest.requests])
            write_new(args.output / "responses-template.json", template.model_dump(mode="json"))
            print(f"Prepared {len(manifest.requests)} requests; no model contacted.")
            return
        manifest = load_manifest(args.manifest)
        pricing = Pricing.model_validate(read_json(args.pricing)) if args.pricing else None
        metadata = ModelMetadata.model_validate(read_json(args.metadata)) if args.command == "run-local" and args.metadata else None
        provider = (LocalProvider(args.model, args.endpoint, manifest.settings.timeout_seconds) if args.command == "run-local"
                    else ImportedProvider(ImportBundle.model_validate(read_json(args.responses)), manifest))
        try:
            report = run(manifest, provider, metadata=metadata, pricing=pricing, checkpoint=args.output / "attempts")
        finally:
            if isinstance(provider, LocalProvider):
                provider.close()
        write_new(args.output / "results.json", report)
        print(f"Recorded {len(report['attempts'])} attempts; human quality remains unscored.")
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, "Benchmark input/output rejected; check versions, paths, permissions and required fields. No credentials are printed.\n")


if __name__ == "__main__":
    main()
