"""Benchmark-only planning strategies; no application workflow or database access."""

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, model_validator

from hankeluotsi import model_quality as q
from hankeluotsi.prompts import build_prompt, prompt_version_for_stage
from hankeluotsi.schemas import ConceptPaper, NonBlank, StrictModel


RECIPES = q.ROOT / "experiments/planning_prompts_v1.json"
STRATEGIES = ("baseline", "A", "B", "C")
SOURCES = ("experiments/planning_prompts_v1.json", "hankeluotsi/planning_experiments.py",
           "hankeluotsi/model_quality.py", "hankeluotsi/model_quality_review.py", "app.py",
           "hankeluotsi/prompts.py", "hankeluotsi/schemas.py", "hankeluotsi/consistency.py",
           "tests/fixtures/model_quality/ideas_v1.json", "tests/fixtures/model_quality/rubric_v1.json")


class Question(StrictModel):
    field: NonBlank
    question: NonBlank
    why_essential: NonBlank


class Clarifications(StrictModel):
    known_facts: list[NonBlank] = Field(min_length=1)
    questions: list[Question]
    unsupported_assertions: list[NonBlank]
    requires_answers: bool = Field(strict=True)
    reason: NonBlank

    @model_validator(mode="after")
    def blocking_questions_exist(self):
        if self.requires_answers and not self.questions:
            raise ValueError("A clarification pause requires at least one explicit question")
        return self


class NeedsAnalysis(StrictModel):
    known_facts: list[NonBlank] = Field(min_length=1)
    needs_evidence: list[NonBlank]
    target_group_distinction: NonBlank
    change_logic: NonBlank
    feasibility_and_risks: list[NonBlank]
    open_decisions: list[NonBlank]


class CritiqueFinding(StrictModel):
    reference: NonBlank
    observation: NonBlank
    evidence_quote: NonBlank
    severity: str = Field(pattern=r"^(major|minor|question)$")


class Critique(StrictModel):
    findings: list[CritiqueFinding]
    suggested_improvements: list[NonBlank]


MODELS = {"baseline": ConceptPaper, "A": ConceptPaper, "B_check": Clarifications,
          "B_generate": ConceptPaper, "C_needs": NeedsAnalysis, "C_generate": ConceptPaper,
          "C_critique": Critique, "C_revise": ConceptPaper}


@dataclass(frozen=True)
class Context:
    settings: q.Settings
    response_format: dict


def source_hashes():
    return {name: hashlib.sha256((q.ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def create_plan(settings: q.Settings, model: str, case_ids=None) -> dict:
    cases = q.load_cases()
    selected = list(case_ids) if case_ids is not None else [c.case_id for c in cases]
    if not model.strip() or not selected or len(set(selected)) != len(selected) or set(selected) - {c.case_id for c in cases}:
        raise ValueError("Choose distinct known fictional cases and an exact model ID")
    recipes = q.read_json(RECIPES)
    jobs = [{"case_id": case_id, "strategy": strategy, "trial": trial}
            for case_id in selected for strategy in STRATEGIES for trial in range(1, settings.trials + 1)]
    random.Random(settings.order_seed).shuffle(jobs)
    return {"version": "planning_experiment_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model, "settings": settings.model_dump(mode="json"), "case_ids": selected, "jobs": jobs,
        "base_manifest": q.create_manifest(settings).model_dump(mode="json"), "recipes": recipes,
        "source_sha256": source_hashes(), "base_prompt_version": prompt_version_for_stage("concept"),
        "notes": ["Common per-call token budget; baseline uses production wording, not its 512-token budget.",
                  "B pauses for essential unanswered questions; no fictional answers are invented.",
                  "C critique uses the same model in a fresh role, not independent expert validation."]}


def load_plan(path: Path) -> dict:
    plan = q.read_json(path)
    expected = create_plan(q.Settings.model_validate(plan["settings"]), plan["model"], plan["case_ids"])
    for field in ("version", "model", "settings", "case_ids", "jobs", "recipes", "source_sha256", "base_prompt_version"):
        if plan[field] != expected[field]:
            raise ValueError("Frozen experiment changed; create a separate new plan")
    base = q.Manifest.model_validate(plan["base_manifest"])
    for field in ("settings", "cases", "rubric", "requests", "response_format", "dataset_sha256", "rubric_sha256", "schema_sha256"):
        if getattr(base, field) != getattr(q.Manifest.model_validate(expected["base_manifest"]), field):
            raise ValueError("Frozen fictional inputs or rubric changed")
    return plan


def baseline_input(case: q.Case, recipes: dict) -> str:
    # Exact compact production wording, guarded by comparison with app.py in tests.
    return ("Fictional project idea:\n" + case.idea.model_dump_json() + "\n\n" +
        recipes["baseline"]["instruction"] + "\n\n" +
        f"Write all human-readable text fields in {'Finnish' if case.language == 'fi' else 'English'}. "
        "Keep JSON field names, schema_version and O/A/R/I identifiers unchanged. Do not translate keys or IDs.")


def build_stage(plan: dict, case: q.Case, strategy: str, stage: str, trial: int, past: dict):
    recipes = plan["recipes"]
    if stage == "baseline":
        user_input = baseline_input(case, recipes)
    else:
        attachments = {}
        if stage == "B_generate":
            attachments = {"unanswered_clarification_check": past["B_check"]["validated_output"]}
        elif stage == "C_generate":
            attachments = {"provisional_model_analysis": past["C_needs"]["validated_output"]}
        elif stage in ("C_critique", "C_revise"):
            attachments = {"candidate": past["C_generate"]["validated_output"],
                           "deterministic_findings": past["C_generate"]["consistency_findings"]}
            if stage == "C_revise":
                attachments["fallible_critique"] = past["C_critique"]["validated_output"]
        user_input = (recipes["common"] + "\nExperimental prompt version: " + recipes[stage]["version"] +
            "\n" + recipes[stage]["instruction"] + "\nRequested language: " + case.language +
            "\nOriginal fictional idea (only factual source):\n" + case.idea.model_dump_json() +
            "\nUntrusted derived context, not user answers or approval:\n" + json.dumps(attachments, ensure_ascii=False))
    messages = [{"role": "system", "content": "Return a valid JSON object only."},
                {"role": "user", "content": build_prompt("concept", user_input)}]
    version = recipes[stage]["version"]
    fields = {"case_id": case.case_id, "trial": trial, "language": case.language, "messages": messages}
    request = q.Request(**fields, request_sha256=q.digest({**fields, "strategy": strategy, "stage": stage, "version": version}))
    schema = MODELS[stage].model_json_schema()
    context = Context(q.Settings.model_validate(plan["settings"]),
        {"type": "json_schema", "json_schema": {"name": MODELS[stage].__name__.lower(), "schema": schema}})
    return request, context


def run_job(plan: dict, job: dict, provider: q.Provider) -> dict:
    case = next(c for c in q.load_cases() if c.case_id == job["case_id"])
    strategy = job["strategy"]
    stages = {"baseline": ("baseline",), "A": ("A",), "B": ("B_check", "B_generate"),
              "C": ("C_needs", "C_generate", "C_critique", "C_revise")}[strategy]
    past, records = {}, []
    result = {**job, "language": case.language, "status": "stage_failed", "candidate": None,
              "human_quality": None, "stages": records}
    for stage in stages:
        request, context = build_stage(plan, case, strategy, stage, job["trial"], past)
        observation = q.execute_request(request, context, provider, response_model=MODELS[stage])
        record = {"stage": stage, "prompt_version": plan["recipes"][stage]["version"],
            "requested_model": provider.requested_model, "provider": provider.provider,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "request": request.model_dump(mode="json"),
            "response_format": context.response_format, "estimated_api_cost": None, **observation}
        records.append(record)
        past[stage] = record
        if not record["first_attempt_success"]:
            result["failed_stage"] = stage
            break
        if stage == "B_check" and record["validated_output"]["requires_answers"]:
            result["status"] = "awaiting_clarification"
            break
        if stage == stages[-1]:
            result["status"] = "candidate_ready"
            result["candidate"] = record["validated_output"]
    latencies = [r["reply"]["latency_seconds"] for r in records if r["reply"]["latency_seconds"] is not None]
    result["stage_calls"] = len(records)
    result["total_measured_latency_seconds"] = sum(latencies) if len(latencies) == len(records) else None
    return result


def summarize_jobs(jobs: list[dict]) -> dict:
    result = {}
    for strategy in STRATEGIES:
        rows = [r for r in jobs if r["strategy"] == strategy]
        candidates = [r for r in rows if r["status"] == "candidate_ready"]
        final_records = [r["stages"][-1] for r in candidates]
        latencies = [r["total_measured_latency_seconds"] for r in rows if r["total_measured_latency_seconds"] is not None]
        result[strategy] = {"planned_jobs": len(rows), "candidate_ready": len(candidates),
            "awaiting_clarification": sum(r["status"] == "awaiting_clarification" for r in rows),
            "stage_failed": sum(r["status"] == "stage_failed" for r in rows),
            "stage_calls": sum(r["stage_calls"] for r in rows),
            "total_measured_seconds": sum(latencies) if len(latencies) == len(rows) else None,
            "final_concept_checks": q.summarize(final_records), "human_quality": None}
    return result


def run_plan(plan: dict, provider: q.Provider, output: Path) -> dict:
    if provider.requested_model != plan["model"]:
        raise ValueError("Provider model must match frozen plan")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for job in plan["jobs"]:
        result = run_job(plan, job, provider)
        name = f'{job["strategy"]}-{job["case_id"]}-trial-{job["trial"]}.json'
        q.write_new(output / name, result)
        results.append(result)
        print(f'{job["case_id"]} {job["strategy"]} trial {job["trial"]}: {result["status"]}; {result["stage_calls"]} calls', flush=True)
    report = {"version": "planning_results_v1", "plan_sha256": q.digest(plan),
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "requested_model": provider.requested_model,
        "jobs": [{k: v for k, v in row.items() if k not in ("stages", "candidate")} for row in results],
        "summary": summarize_jobs(results), "human_quality": None,
        "limits": ["Single-model role-separated critique is not independent human review.",
                   "Clarification pauses are not successful plans or model-request failures.",
                   "One trial per case is exploratory evidence, not proof of a superior strategy."]}
    q.write_new(output / "results.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimental fictional planning only; production remains unchanged.")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--model", required=True)
    plan_parser.add_argument("--output", type=Path, required=True)
    plan_parser.add_argument("--trials", type=int, default=1)
    plan_parser.add_argument("--max-tokens", type=int, default=1536)
    plan_parser.add_argument("--case-ids", nargs="+")
    run_parser = sub.add_parser("run-local")
    run_parser.add_argument("--execute-local", action="store_true", required=True)
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            plan = create_plan(q.Settings(trials=args.trials, max_tokens=args.max_tokens), args.model, args.case_ids)
            q.write_new(args.output, plan)
            print(f'Prepared {len(plan["jobs"])} strategy jobs with no model call.')
        else:
            plan = load_plan(args.plan)
            provider = q.LocalProvider(plan["model"], args.endpoint, plan["settings"]["timeout_seconds"])
            try:
                run_plan(plan, provider, args.output)
            finally:
                provider.close()
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, "Experiment rejected: check source versions, model, fictional case IDs and new output paths.\n")


if __name__ == "__main__":
    main()
