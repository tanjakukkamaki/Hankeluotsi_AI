"""Offline experimental orchestration, not an implemented application workflow."""

import ast
import hashlib
import json
import socket
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from hankeluotsi import model_quality as q
from hankeluotsi import planning_experiments as experiment
from hankeluotsi.i18n import language_code
from hankeluotsi.prompts import concept_generation_input


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Experimental test attempted network/database access")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(sqlite3, "connect", blocked)


@pytest.fixture
def plan():
    return experiment.create_plan(q.Settings(trials=1), "fictional-qwen")


class FictionalProvider:
    provider = "lm_studio"
    requested_model = "fictional-qwen"
    measure_latency = False

    def __init__(self, pause=False, fail_stage=None, reason="stop"):
        self.pause, self.fail_stage, self.reason = pause, fail_stage, reason
        self.calls = []

    def generate(self, request, context):
        name = context.response_format["json_schema"]["name"]
        self.calls.append((name, request, context))
        if name == self.fail_stage:
            return q.Reply(text="{", finish_reason="length", reported_model=self.requested_model)
        if name == "clarifications":
            data = {"known_facts": ["Fictional source need"], "questions": [{"field": "expected_change",
                "question": "Which fictional task?", "why_essential": "Scope is not agreed."}],
                "unsupported_assertions": [], "requires_answers": self.pause, "reason": "Fictional test decision."}
        elif name == "needsanalysis":
            data = {"known_facts": ["Fictional source need"], "needs_evidence": ["Baseline missing"],
                "target_group_distinction": "Fictional participants", "change_logic": "Practice then demonstration",
                "feasibility_and_risks": ["Capacity unknown"], "open_decisions": ["Task criteria"]}
        elif name == "critique":
            data = {"findings": [], "suggested_improvements": ["Clarify the fictional assessment task."]}
        else:
            data = json.loads((Path(__file__).parent / "fixtures/concept_paper.json").read_text(encoding="utf-8"))
        return q.Reply(text=json.dumps(data), finish_reason=self.reason, reported_model=self.requested_model, latency_seconds=0.25)


def job(strategy, case="Q01"):
    return {"case_id": case, "strategy": strategy, "trial": 1}


def test_ten_diverse_original_cases_and_all_four_strategies_are_frozen(plan):
    assert len(plan["case_ids"]) == 10 and len(plan["jobs"]) == 40
    assert {j["strategy"] for j in plan["jobs"]} == set(experiment.STRATEGIES)
    assert {c["language"] for c in plan["base_manifest"]["cases"]} == {"fi", "en"}
    assert "app.py" in plan["source_sha256"] and "hankeluotsi/schemas.py" in plan["source_sha256"]
    assert plan["base_manifest"]["rubric"]["version"] == "expert_quality_v1"


@pytest.mark.parametrize("locale", ["fi", "en"])
def test_historical_control_stays_frozen_and_is_distinct_from_current_production_v2(plan, locale):
    tree = ast.parse((q.ROOT / "app.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_concept_generation_input")
    namespace = {"ProjectIdea": q.ProjectIdea, "language_code": language_code,
        "concept_generation_input": concept_generation_input}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "trusted-production-helper", "exec"), namespace)
    case = next(c for c in q.load_cases() if c.language == locale)
    instruction = plan["recipes"]["baseline"]["instruction"]
    assert hashlib.sha256(instruction.encode("utf-8")).hexdigest() == "69f0c90d50b04805ab6da0143683938db30a383cab63947507ee4a57201c5184"
    archived = experiment.baseline_input(case, plan["recipes"])
    current = namespace["_concept_generation_input"](case.idea, locale)
    assert instruction in archived and "Use empty assumptions and open_questions." in archived
    assert current == concept_generation_input(case.idea, locale) and current != archived
    assert "at most one short assumption" in current


@pytest.mark.parametrize("strategy,expected_calls", [("baseline", 1), ("A", 1), ("B", 2), ("C", 4)])
def test_shared_transport_validation_produces_separate_candidates(plan, strategy, expected_calls):
    provider = FictionalProvider()
    result = experiment.run_job(plan, job(strategy), provider)
    assert result["status"] == "candidate_ready" and result["stage_calls"] == expected_calls
    assert result["human_quality"] is None
    assert q.ConceptPaper.model_validate(result["candidate"])
    assert all(r["prompt_version"] and r["request"]["request_sha256"] for r in result["stages"])
    assert result["total_measured_latency_seconds"] == expected_calls * 0.25


def test_clarification_gate_pauses_without_inventing_answers_or_generating(plan):
    provider = FictionalProvider(pause=True)
    result = experiment.run_job(plan, job("B", "Q08"), provider)
    assert result["status"] == "awaiting_clarification" and result["candidate"] is None
    assert len(provider.calls) == 1
    assert result["stages"][0]["validated_output"]["questions"]


@pytest.mark.parametrize("stage,calls", [("needsanalysis", 1), ("conceptpaper", 2), ("critique", 3)])
def test_invalid_intermediate_output_stops_dependents_and_preserves_raw(plan, stage, calls):
    provider = FictionalProvider(fail_stage=stage)
    result = experiment.run_job(plan, job("C"), provider)
    assert result["status"] == "stage_failed" and result["candidate"] is None
    assert len(provider.calls) == calls
    assert result["stages"][-1]["reply"]["text"] == "{"
    assert result["stages"][-1]["truncated"]


def test_critique_has_fresh_context_and_revision_does_not_overwrite_initial(plan):
    provider = FictionalProvider()
    result = experiment.run_job(plan, job("C"), provider)
    critique = result["stages"][2]["request"]["messages"][1]["content"]
    assert "provisional_model_analysis" not in critique
    assert "not an independent human expert" in critique
    assert result["stages"][1]["stage"] == "C_generate"
    assert result["stages"][3]["stage"] == "C_revise"
    assert result["stages"][1]["reply"]["text"] == result["stages"][3]["reply"]["text"]


def test_existing_output_is_rejected_before_generation(plan, tmp_path):
    provider = FictionalProvider()
    with pytest.raises(FileExistsError):
        experiment.run_plan(plan, provider, tmp_path)
    assert provider.calls == []


def test_plan_changes_or_model_mismatch_are_rejected(plan, tmp_path):
    path = tmp_path / "plan.json"
    q.write_new(path, plan)
    assert experiment.load_plan(path)["jobs"] == plan["jobs"]
    plan["recipes"]["A"]["instruction"] += "tampered"
    other = tmp_path / "altered.json"
    q.write_new(other, plan)
    with pytest.raises(ValueError, match="Frozen"):
        experiment.load_plan(other)
    plan["model"] = "another-model"
    with pytest.raises(ValueError, match="model"):
        experiment.run_plan(plan, FictionalProvider(), tmp_path / "run")


def test_blocking_decision_needs_an_explicit_question():
    with pytest.raises(ValidationError):
        experiment.Clarifications(known_facts=["Fictional need"], questions=[], unsupported_assertions=[],
            requires_answers=True, reason="Unspecified")


def test_offline_complete_experiment_and_coverage_denominators(tmp_path):
    plan = experiment.create_plan(q.Settings(trials=1), "fictional-qwen", ["Q01", "Q08"])
    provider = FictionalProvider(pause=True)
    report = experiment.run_plan(plan, provider, tmp_path / "run")
    assert len(report["jobs"]) == 8
    assert report["summary"]["B"]["planned_jobs"] == 2
    assert report["summary"]["B"]["candidate_ready"] == 0
    assert report["summary"]["B"]["awaiting_clarification"] == 2
    assert report["summary"]["C"]["stage_calls"] == 8
    assert report["human_quality"] is None
    assert len(list((tmp_path / "run").glob("*.json"))) == 9


def test_live_cli_requires_explicit_opt_in(tmp_path):
    with pytest.raises(SystemExit) as error:
        experiment.main(["run-local", "--plan", str(tmp_path / "missing.json"), "--output", str(tmp_path / "run")])
    assert error.value.code == 2 and not (tmp_path / "run").exists()


def test_critical_trial_and_case_selection_bounds():
    for cases in ([], ["Q99"], ["Q01", "Q01"]):
        with pytest.raises(ValueError):
            experiment.create_plan(q.Settings(trials=1), "fictional-qwen", cases)
