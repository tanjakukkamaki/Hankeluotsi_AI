import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hankeluotsi.benchmark import (
    BenchmarkReport,
    load_fixtures,
    run_benchmark,
    write_report,
)
from hankeluotsi.llm_client import GenerationError, GenerationResult
from hankeluotsi.prompts import prompt_version_for_stage


class FakeClient:
    base_url = "http://127.0.0.1:1234/v1"
    default_model = "fake-local-model"
    timeout_seconds = 60
    stage_to_model = {"concept": "fake-local-model", "draft": "fake-local-model", "review": "fake-local-model"}

    def __init__(self, fail_stage: str | None = None, unknown_stage: str | None = None):
        self.fail_stage = fail_stage
        self.unknown_stage = unknown_stage
        self.calls = []

    def generate(self, stage, user_input, response_model, *, max_attempts):
        self.calls.append((stage, user_input, response_model, max_attempts))
        if stage == self.fail_stage:
            raise GenerationError(
                "truncated response (finish_reason=length)",
                stage=stage,
                model=self.default_model,
                prompt_version=prompt_version_for_stage(stage),
                finish_reason="length",
                truncated=True,
                incomplete_output=True,
                response_time_seconds=0.25,
                json_valid=True,
                pydantic_valid=False,
                attempt_count=1,
            )
        finish_reason = "unknown" if stage == self.unknown_stage else "stop"
        return GenerationResult(
            stage=stage,
            model=self.default_model,
            prompt_version=prompt_version_for_stage(stage),
            data=SimpleNamespace(),
            finish_reason=finish_reason,
            truncated=False,
            incomplete_output=finish_reason != "stop",
            response_time_seconds=0.5,
            json_valid=True,
            pydantic_valid=True,
            attempt_count=1,
        )


def test_load_fixtures_contains_all_three_fictional_stages():
    fixtures = load_fixtures()

    assert set(fixtures) == {"concept", "draft", "review"}
    assert all(fixture.fixture_id.startswith("fictional_") for fixture in fixtures.values())
    assert all("fictional" in fixture.user_input.lower() for fixture in fixtures.values())


def test_benchmark_records_first_attempt_metadata_for_each_stage():
    client = FakeClient()

    report = run_benchmark(2, client=client)

    assert len(report.attempts) == 6
    assert all(call[3] == 1 for call in client.calls)
    assert all(attempt.first_attempt_success for attempt in report.attempts)
    assert {attempt.prompt_version for attempt in report.attempts} == {
        "concept_v1",
        "draft_v1",
        "review_v1",
    }
    assert report.stage_summaries()["concept"] == {
        "attempts": 2,
        "first_attempt_successes": 2,
        "first_attempt_success_rate": 1.0,
        "mean_response_time_seconds": 0.5,
    }


def test_benchmark_records_truncation_and_validation_failure():
    report = run_benchmark(1, client=FakeClient(fail_stage="draft"))

    draft_attempt = next(attempt for attempt in report.attempts if attempt.stage == "draft")
    assert draft_attempt.json_valid is True
    assert draft_attempt.pydantic_valid is False
    assert draft_attempt.finish_reason == "length"
    assert draft_attempt.truncated is True
    assert draft_attempt.incomplete_output is True
    assert draft_attempt.first_attempt_success is False
    assert draft_attempt.response_time_seconds == 0.25


def test_unknown_finish_reason_is_incomplete_and_not_a_success():
    report = run_benchmark(1, client=FakeClient(unknown_stage="review"))

    review_attempt = next(attempt for attempt in report.attempts if attempt.stage == "review")
    assert review_attempt.finish_reason == "unknown"
    assert review_attempt.incomplete_output is True
    assert review_attempt.first_attempt_success is False


def test_benchmark_rejects_non_local_endpoint():
    client = FakeClient()
    client.base_url = "https://example.invalid/v1"

    with pytest.raises(ValueError, match="localhost"):
        run_benchmark(1, client=client)

    assert client.calls == []


def test_report_writes_json_with_attempts_and_summaries(tmp_path: Path):
    report = run_benchmark(1, client=FakeClient(), enable_thinking=False)
    output_path = tmp_path / "benchmark" / "results.json"

    write_report(report, output_path)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(saved["attempts"]) == 3
    assert saved["stage_summaries"]["review"]["first_attempt_success_rate"] == 1.0
    assert saved["model_metadata"]["artifact"] is None
    assert saved["model_metadata"]["enable_thinking"] is False


@pytest.mark.parametrize("attempts", [0, -1])
def test_benchmark_requires_positive_attempt_count(attempts):
    with pytest.raises(ValueError, match="at least 1"):
        run_benchmark(attempts, client=FakeClient())