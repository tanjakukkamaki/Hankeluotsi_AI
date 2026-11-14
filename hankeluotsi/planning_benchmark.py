"""Offline-only planning pilot: freeze requests, import evidence, prepare blinded review."""

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import platform

from hankeluotsi import model_quality as q
from hankeluotsi.benchmark_execution import private_output
from hankeluotsi.draft_checks import check_draft_consistency
from hankeluotsi.draft_schemas import ApplicationDraft
from hankeluotsi.draft_workflow import PROMPT_VERSIONS, draft_input, review_input
from hankeluotsi.mistral_client import ERROR_MESSAGES
from hankeluotsi.planning_quality import check_planning_advisories
from hankeluotsi.prompts import build_prompt, concept_generation_input, prompt_version_for_stage
from hankeluotsi.review_evidence import ReviewSelection, resolve_review_selection
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "fixtures"
MODELS = {"concept": ConceptPaper, "draft": ApplicationDraft, "review": ReviewSelection}
SOURCE_FILES = (
    "hankeluotsi/planning_benchmark.py", "hankeluotsi/prompts.py", "hankeluotsi/draft_workflow.py",
    "hankeluotsi/planning_quality.py", "hankeluotsi/draft_checks.py", "hankeluotsi/review_evidence.py",
    "hankeluotsi/mistral_client.py", "hankeluotsi/schemas.py", "hankeluotsi/draft_schemas.py",
    "hankeluotsi/llm_client.py", "hankeluotsi/config.py", "hankeluotsi/benchmark_execution.py",
    "hankeluotsi/model_quality.py", "tests/fixtures/planning_quality_cases_v1.json",
    "tests/fixtures/planning_rubric_v1.json",
)


def create_plan(reference_date):
    if type(reference_date) is not date:
        raise ValueError("An explicit planning reference date is required")
    dataset = q.read_json(DATA / "planning_quality_cases_v1.json")
    rubric = q.read_json(DATA / "planning_rubric_v1.json")
    requests = []
    for case in dataset["cases"]:
        idea, concept, draft = ProjectIdea.model_validate(case["idea"]), ConceptPaper.model_validate(case["concept"]), ApplicationDraft.model_validate(case["draft"])
        for stage in case["stages"]:
            catalogue = None
            if stage == "concept":
                user_input = concept_generation_input(idea, case["language"])
            elif stage == "draft":
                user_input = draft_input(idea, concept, case["language"], reference_date=reference_date)
            else:
                user_input, catalogue = review_input(idea, draft, case["language"], reference_date=reference_date)
            request = {"case_id": case["case_id"], "stage": stage, "language": case["language"], "trial": 1,
                "prompt_version": prompt_version_for_stage(stage) if stage == "concept" else PROMPT_VERSIONS[stage],
                "wrapper_prompt_version": prompt_version_for_stage(stage),
                "messages": [{"role": "system", "content": "Return a valid JSON object only."},
                    {"role": "user", "content": build_prompt(stage, user_input)}],
                "response_format": {"type": "json_schema", "json_schema": {"name": MODELS[stage].__name__.lower(), "schema": MODELS[stage].model_json_schema()}},
                "temperature": 0.2, "max_output_tokens": {"concept": 512, "draft": 4096, "review": 2048}[stage],
                "timeout_seconds": 120 if stage == "concept" else 180, "automatic_retries": 0,
                "review_catalogue": catalogue}
            request["request_sha256"] = q.digest(request)
            requests.append(request)
    plan = {"version": "planning_comparison_plan_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_date": reference_date.isoformat(), "fictional_only": True,
        "preparation_environment": {"python": platform.python_version(),
            "packages": {name: q.package_version(name) for name in ("pydantic", "openai", "httpx2")}},
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        "cases": dataset["cases"], "rubric": rubric, "requests": requests,
        "status": "not_run", "human_assessment": None, "ai_assisted_assessment": None,
        "protocol_notes": ["Fixed stage-isolation pilot, not a complete reliability gate or generated end-to-end pipeline.",
            "Concepts/drafts supplied to later stages are hand-authored controls, not outputs attributed to either model.",
            "Use these same canonical messages for both providers; record native schema delivery/reasoning controls separately.",
            "No network collector is part of this offline command. No model access or prices are assumed."]}
    plan["plan_sha256"] = q.digest(plan)
    return plan


def verify_plan(plan):
    supplied = dict(plan)
    fingerprint = supplied.pop("plan_sha256")
    if q.digest(supplied) != fingerprint or plan["version"] != "planning_comparison_plan_v1":
        raise ValueError("Plan integrity/version mismatch")
    expected = create_plan(date.fromisoformat(plan["reference_date"]))
    for field in ("source_sha256", "cases", "rubric", "requests", "fictional_only", "protocol_notes", "status", "human_assessment", "ai_assisted_assessment"):
        if plan[field] != expected[field]:
            raise ValueError("Frozen planning sources changed; use the recorded revision or prepare a new study")
    return plan


def response_template(plan):
    verify_plan(plan)
    return {"version": "planning_responses_v1", "plan_sha256": plan["plan_sha256"],
        "provider": None, "requested_model": None, "execution_kind": "not_run",
        "responses": [{"request_sha256": item["request_sha256"], "reply": {"error": "not_run"},
            "error_code": None, "http_status": None} for item in plan["requests"]]}


def _assess(plan, request, reply):
    model = MODELS[request["stage"]]
    facts = q.assess(reply, response_model=model)
    facts["review_evidence_valid"] = None
    facts["planning_observations"] = []
    facts["schema_complete"] = facts["pydantic_valid"]
    if not facts["pydantic_valid"]:
        return facts
    case = next(case for case in plan["cases"] if case["case_id"] == request["case_id"])
    if request["stage"] == "draft":
        draft = ApplicationDraft.model_validate(facts["validated_output"])
        facts["consistency_findings"] = [item.to_dict() for item in check_draft_consistency(draft)]
        facts["planning_observations"] = [item.to_dict() for item in check_planning_advisories(draft,
            reference_date=date.fromisoformat(plan["reference_date"]))]
    elif request["stage"] == "review":
        try:
            selection = ReviewSelection.model_validate(facts["validated_output"]).model_copy(update={"generation_metadata": None})
            resolved = resolve_review_selection(ApplicationDraft.model_validate(case["draft"]), selection,
                request["review_catalogue"], language=case["language"])
            facts["validated_output"] = resolved.model_dump(mode="json")
            facts["review_evidence_valid"] = True
        except ValueError:
            facts["review_evidence_valid"] = False
            facts["first_attempt_success"] = False
            facts["validation_errors"].append("unsupported_review_evidence")
    return facts


def import_run(plan, bundle, *, pricing=None):
    verify_plan(plan)
    if (bundle["version"] != "planning_responses_v1" or bundle["plan_sha256"] != plan["plan_sha256"]
            or bundle["provider"] not in ("lm_studio", "mistral")
            or not isinstance(bundle["requested_model"], str) or not bundle["requested_model"].strip()
            or bundle["execution_kind"] not in ("recorded_live", "offline_mock")):
        raise ValueError("A complete labelled live/mock evidence bundle is required; placeholders are not results")
    rows = bundle["responses"]
    mapping = {row["request_sha256"]: row for row in rows}
    if len(mapping) != len(rows) or set(mapping) != {item["request_sha256"] for item in plan["requests"]}:
        raise ValueError("Record every planned attempt exactly once, including failures")
    attempts = []
    for request in plan["requests"]:
        row = mapping[request["request_sha256"]]
        reply = q.Reply.model_validate(row["reply"])
        if reply.error == "not_run" or row.get("error_code") not in {*ERROR_MESSAGES, None}:
            raise ValueError("Unexecuted rows or arbitrary error text are not evidence")
        status = row.get("http_status")
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise ValueError("Only a safe numeric HTTP status may be imported")
        attempts.append({"request_sha256": request["request_sha256"], "case_id": request["case_id"],
            "stage": request["stage"], "language": request["language"], "reply": reply.model_dump(mode="json"),
            "error_code": row.get("error_code"), "http_status": status,
            "estimated_api_cost": q.estimate_cost(reply, bundle["provider"], pricing),
            "actual_billed_cost": None, "human_scores": None, "ai_assisted_scores": None,
            **_assess(plan, request, reply)})
    return {"version": "planning_results_v1", "plan": plan, "plan_sha256": plan["plan_sha256"],
        "provider": bundle["provider"], "requested_model": bundle["requested_model"],
        "model_metadata": q.ModelMetadata.model_validate(bundle.get("model_metadata", {})).model_dump(mode="json"),
        "pricing": pricing.model_dump(mode="json") if pricing else None,
        "execution_kind": bundle["execution_kind"], "attempts": attempts,
        "summary": {**q.summarize(attempts), "critical_review_quality": None,
            "unsupported_facts_quality": None, "semantic_completeness": None}}


def blind(reports, output, *, seed=91):
    if len(reports) != 2 or {report["provider"] for report in reports} != {"lm_studio", "mistral"}:
        raise ValueError("Exactly one complete run per provider is required")
    plan = verify_plan(reports[0]["plan"])
    if len({report["execution_kind"] for report in reports}) != 1:
        raise ValueError("Do not mix live observations and offline mocks")
    for report in reports:
        verify_plan(report["plan"])
        if report["version"] != "planning_results_v1" or report["plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("Use the same frozen plan for both providers")
        bundle = {"version": "planning_responses_v1", "plan_sha256": plan["plan_sha256"],
            "provider": report["provider"], "requested_model": report["requested_model"],
            "execution_kind": report["execution_kind"], "responses": report["attempts"]}
        recomputed = import_run(plan, bundle, pricing=q.Pricing.model_validate(report["pricing"]) if report.get("pricing") else None)
        for old, checked in zip(report["attempts"], recomputed["attempts"], strict=True):
            if any(old[key] != checked[key] for key in ("request_sha256", "case_id", "stage", "language", "json_valid", "pydantic_valid", "review_evidence_valid", "first_attempt_success", "validated_output", "estimated_api_cost")):
                raise ValueError("Validation evidence was modified")
    order = random.Random(seed).sample(reports, 2)
    items, mapping = [], []
    cases = {case["case_id"]: case for case in plan["cases"]}
    identities = {"qwen", "mistral", "lm studio", "lm_studio", *[report["requested_model"].casefold() for report in reports]}
    identities.update(attempt["reply"]["reported_model"].casefold() for report in reports for attempt in report["attempts"] if attempt["reply"]["reported_model"])
    for request in plan["requests"]:
        for label, report in zip(("A", "B"), order, strict=True):
            attempt = next(item for item in report["attempts"] if item["request_sha256"] == request["request_sha256"])
            content = attempt["validated_output"]
            if isinstance(content, dict):
                content = {key: value for key, value in content.items() if key != "generation_metadata"}
            else:
                content = attempt["reply"]["text"]
            text = json.dumps(content, ensure_ascii=False).casefold()
            if any(re.search(r"(?<!\w)" + re.escape(identity) + r"(?!\w)", text) for identity in identities if identity):
                raise ValueError("Output may reveal model identity; review privately before blinding")
            case = cases[request["case_id"]]
            review_id = request["case_id"] + "-" + request["stage"] + "-" + label
            fields = {"concept": ("idea",), "draft": ("idea", "concept"), "review": ("idea", "draft")}[request["stage"]]
            items.append({"review_id": review_id, "label": label, "stage": request["stage"], "language": request["language"],
                "source_material": {key: case[key] for key in fields}, "output": content})
            mapping.append({"review_id": review_id, "provider": report["provider"], "requested_model": report["requested_model"],
                "source_report_sha256": q.digest(report), "request_sha256": request["request_sha256"]})
    output = private_output(output)
    output.mkdir(parents=True, exist_ok=False)
    packet = {"version": "planning_blind_packet_v1", "execution_kind": reports[0]["execution_kind"], "rubric": plan["rubric"], "items": items}
    q.write_new(output / "review-packet.json", packet)
    template = [{"review_id": item["review_id"], "scores": {key: None for key in plan["rubric"]["criteria"]}, "evidence": "", "notes": ""} for item in items]
    for kind in ("human", "ai-assisted"):
        q.write_new(output / (kind + "-ratings-template.json"), {"assessment_kind": kind, "packet_sha256": q.digest(packet), "ratings": template})
    q.write_new(output / "PRIVATE-model-map.json", {"packet_sha256": q.digest(packet), "seed": seed, "items": mapping})
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline-only planning benchmark preparation/import/blinding; never contacts a provider")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("plan")
    prepare.add_argument("--reference-date", type=date.fromisoformat, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    collect = commands.add_parser("import")
    collect.add_argument("--plan", type=Path, required=True)
    collect.add_argument("--responses", type=Path, required=True)
    collect.add_argument("--pricing", type=Path)
    collect.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("blind")
    review.add_argument("--reports", type=Path, nargs=2, required=True)
    review.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "blind":
        blind([q.read_json(path) for path in args.reports], args.output)
    else:
        output = private_output(args.output)
        if args.command == "plan":
            plan = create_plan(args.reference_date)
            output.mkdir(parents=True, exist_ok=False)
            q.write_new(output / "plan.json", plan)
            q.write_new(output / "responses-template.json", response_template(plan))
        else:
            plan, bundle = q.read_json(args.plan), q.read_json(args.responses)
            pricing = q.Pricing.model_validate(q.read_json(args.pricing)) if args.pricing else None
            report = import_run(plan, bundle, pricing=pricing)
            output.mkdir(parents=True, exist_ok=False)
            q.write_new(output / "results.json", report)
    print("Offline planning artifact saved privately; no network/model requests were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
