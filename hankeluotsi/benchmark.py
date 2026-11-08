import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Type
from urllib.parse import urlsplit

from pydantic import Field

from hankeluotsi.config import LOCAL_LM_STUDIO_BASE_URL, MAX_TOKENS
from hankeluotsi.llm_client import GenerationError, LLMClient
from hankeluotsi.prompts import prompt_version_for_stage
from hankeluotsi.schemas import ConceptPaper, NonBlank, StrictModel


class DraftBenchmarkOutput(StrictModel):
    background: NonBlank
    objectives: list[NonBlank] = Field(min_length=1)
    activities: list[NonBlank] = Field(min_length=1)
    results: list[NonBlank] = Field(min_length=1)
    indicators: list[NonBlank] = Field(min_length=1)


class ReviewBenchmarkFinding(StrictModel):
    issue: NonBlank
    suggestion: NonBlank


class ReviewBenchmarkOutput(StrictModel):
    strengths: list[NonBlank] = Field(min_length=1)
    findings: list[ReviewBenchmarkFinding] = Field(default_factory=list)
    missing_information: list[NonBlank] = Field(default_factory=list)
    overall_assessment: NonBlank
    uncertainties: list[NonBlank] = Field(default_factory=list)


@dataclass(frozen=True)
class BenchmarkFixture:
    stage: str
    fixture_id: str
    user_input: str


@dataclass
class BenchmarkAttempt:
    timestamp_utc: str
    stage: str
    attempt_number: int
    fixture_id: str
    model_id: str
    prompt_version: str
    json_valid: bool
    pydantic_valid: bool | None
    finish_reason: str
    truncated: bool
    incomplete_output: bool
    response_time_seconds: float
    first_attempt_success: bool
    quality_score: int | None = None
    error: str | None = None


@dataclass
class BenchmarkReport:
    created_at_utc: str
    endpoint: str
    attempts_per_stage: int
    generation_parameters: dict[str, Any]
    model_metadata: dict[str, Any]
    attempts: list[BenchmarkAttempt]

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at_utc": self.created_at_utc,
            "endpoint": self.endpoint,
            "attempts_per_stage": self.attempts_per_stage,
            "generation_parameters": self.generation_parameters,
            "model_metadata": self.model_metadata,
            "attempts": [asdict(attempt) for attempt in self.attempts],
            "stage_summaries": self.stage_summaries(),
        }

    def stage_summaries(self) -> dict[str, dict[str, Any]]:
        summaries: dict[str, dict[str, Any]] = {}
        for stage in ("concept", "draft", "review"):
            stage_attempts = [attempt for attempt in self.attempts if attempt.stage == stage]
            successes = sum(attempt.first_attempt_success for attempt in stage_attempts)
            timed_attempts = [attempt.response_time_seconds for attempt in stage_attempts]
            summaries[stage] = {
                "attempts": len(stage_attempts),
                "first_attempt_successes": successes,
                "first_attempt_success_rate": (
                    successes / len(stage_attempts) if stage_attempts else None
                ),
                "mean_response_time_seconds": (
                    sum(timed_attempts) / len(timed_attempts) if timed_attempts else None
                ),
            }
        return summaries


DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "benchmark"
RESPONSE_MODELS: dict[str, Type[StrictModel]] = {
    "concept": ConceptPaper,
    "draft": DraftBenchmarkOutput,
    "review": ReviewBenchmarkOutput,
}


def _ensure_local_endpoint(endpoint: str) -> None:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Benchmark endpoint must be a localhost URL")


def load_fixtures(fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> dict[str, BenchmarkFixture]:
    fixtures: dict[str, BenchmarkFixture] = {}
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        fixture = BenchmarkFixture(
            stage=payload["stage"],
            fixture_id=payload["fixture_id"],
            user_input=payload["user_input"],
        )
        if fixture.stage not in RESPONSE_MODELS:
            raise ValueError(f"Unsupported benchmark stage in {path.name}: {fixture.stage}")
        if fixture.stage in fixtures:
            raise ValueError(f"More than one fixture configured for stage {fixture.stage}")
        fixtures[fixture.stage] = fixture

    missing_stages = set(RESPONSE_MODELS) - fixtures.keys()
    if missing_stages:
        raise ValueError(f"Missing benchmark fixtures for stages: {', '.join(sorted(missing_stages))}")
    return fixtures


def _is_first_attempt_success(
    *,
    json_valid: bool,
    pydantic_valid: bool | None,
    finish_reason: str,
    truncated: bool,
    incomplete_output: bool,
) -> bool:
    return (
        json_valid
        and pydantic_valid is True
        and finish_reason not in {"unknown", "length"}
        and not truncated
        and not incomplete_output
    )


def run_benchmark(
    attempts_per_stage: int,
    *,
    client: LLMClient | None = None,
    fixture_dir: Path = DEFAULT_FIXTURE_DIR,
    model_artifact: str | None = None,
    quantization: str | None = None,
    context_length: int | None = None,
    runtime_version: str | None = None,
    enable_thinking: bool | None = None,
) -> BenchmarkReport:
    if attempts_per_stage < 1:
        raise ValueError("attempts_per_stage must be at least 1")

    llm_client = client or LLMClient(base_url=LOCAL_LM_STUDIO_BASE_URL)
    _ensure_local_endpoint(llm_client.base_url)
    fixtures = load_fixtures(fixture_dir)
    attempts: list[BenchmarkAttempt] = []

    for stage, response_model in RESPONSE_MODELS.items():
        fixture = fixtures[stage]
        model_id = llm_client.stage_to_model.get(stage, llm_client.default_model)
        prompt_version = prompt_version_for_stage(stage)
        for attempt_number in range(1, attempts_per_stage + 1):
            started_at = perf_counter()
            timestamp = datetime.now(timezone.utc).isoformat()
            try:
                result = llm_client.generate(
                    stage,
                    fixture.user_input,
                    response_model=response_model,
                    max_attempts=1,
                )
            except GenerationError as error:
                json_valid = error.json_valid
                pydantic_valid = error.pydantic_valid
                finish_reason = error.finish_reason
                truncated = error.truncated
                incomplete_output = error.incomplete_output
                response_time_seconds = error.response_time_seconds
                model_id = error.model
                prompt_version = error.prompt_version
                error_message = str(error)
            except Exception as error:
                json_valid = False
                pydantic_valid = False
                finish_reason = "unknown"
                truncated = False
                incomplete_output = True
                response_time_seconds = perf_counter() - started_at
                error_message = f"{type(error).__name__}: {error}"
            else:
                json_valid = result.json_valid
                pydantic_valid = result.pydantic_valid
                finish_reason = result.finish_reason
                truncated = result.truncated
                incomplete_output = result.incomplete_output
                response_time_seconds = result.response_time_seconds
                model_id = result.model
                prompt_version = result.prompt_version
                error_message = None

            attempts.append(
                BenchmarkAttempt(
                    timestamp_utc=timestamp,
                    stage=stage,
                    attempt_number=attempt_number,
                    fixture_id=fixture.fixture_id,
                    model_id=model_id,
                    prompt_version=prompt_version,
                    json_valid=json_valid,
                    pydantic_valid=pydantic_valid,
                    finish_reason=finish_reason,
                    truncated=truncated,
                    incomplete_output=incomplete_output,
                    response_time_seconds=response_time_seconds,
                    first_attempt_success=_is_first_attempt_success(
                        json_valid=json_valid,
                        pydantic_valid=pydantic_valid,
                        finish_reason=finish_reason,
                        truncated=truncated,
                        incomplete_output=incomplete_output,
                    ),
                    error=error_message,
                )
            )

    return BenchmarkReport(
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        endpoint=llm_client.base_url,
        attempts_per_stage=attempts_per_stage,
        generation_parameters={
            "temperature": 0.2,
            "max_tokens": MAX_TOKENS,
            "timeout_seconds": llm_client.timeout_seconds,
            "attempt_policy": "one request per attempt; no retries",
        },
        model_metadata={
            "model_ids": {
                stage: llm_client.stage_to_model.get(stage, llm_client.default_model)
                for stage in RESPONSE_MODELS
            },
            "artifact": model_artifact,
            "quantization": quantization,
            "context_length": context_length,
            "runtime_version": runtime_version,
            "enable_thinking": enable_thinking,
        },
        attempts=attempts,
    )


def write_report(report: BenchmarkReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local fictional-data model benchmarks.")
    parser.add_argument("--attempts-per-stage", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-artifact")
    parser.add_argument("--quantization")
    parser.add_argument("--context-length", type=int)
    parser.add_argument("--runtime-version")
    parser.add_argument("--enable-thinking-disabled", action="store_true")
    args = parser.parse_args()

    report = run_benchmark(
        args.attempts_per_stage,
        model_artifact=args.model_artifact,
        quantization=args.quantization,
        context_length=args.context_length,
        runtime_version=args.runtime_version,
        enable_thinking=False if args.enable_thinking_disabled else None,
    )
    write_report(report, args.output)
    print(f"Wrote {len(report.attempts)} benchmark attempts to {args.output}")


if __name__ == "__main__":
    main()