"""All evidence here is explicitly labelled offline_mock, never real model performance."""

from copy import deepcopy
from datetime import date
import json

import pytest

from hankeluotsi import model_quality as q
from hankeluotsi import planning_benchmark as b


def bundle(plan, provider="lm_studio", model="model-alpha"):
    cases = {case["case_id"]: case for case in plan["cases"]}
    rows = []
    for request in plan["requests"]:
        case = cases[request["case_id"]]
        if request["stage"] == "review":
            entry = next(e for e in request["review_catalogue"]["entries"] if e["reference"] == "longer_term_impact")
            data = dict(schema_version=1, strengths=["Fictional pilot structure"], findings=[dict(
                evidence_id=entry["evidence_id"], observation="Compare this impact claim with A1 and its short delivery period.",
                suggestion="Clarify follow-up and narrow unsupported claims.", severity="major")],
                missing_information=["Implementation capacity needs confirmation"], overall_assessment="Unverified mock review for tests only.",
                uncertainties=["No independent content assessment"])
        else:
            data = case[request["stage"]]
        rows.append({"request_sha256": request["request_sha256"], "reply": {
            "text": json.dumps(data, ensure_ascii=False), "reported_model": model, "finish_reason": "stop"}})
    return dict(version="planning_responses_v1", plan_sha256=plan["plan_sha256"], provider=provider,
        requested_model=model, execution_kind="offline_mock", responses=rows)


@pytest.fixture
def plan():
    return b.create_plan(date(2026, 11, 13))


@pytest.mark.parametrize("case_id", ["P02", "P04"])
def test_finnish_benchmark_text_preserves_unicode_and_question_punctuation(case_id):
    dataset = q.read_json(b.DATA / "planning_quality_cases_v1.json")
    case = next(case for case in dataset["cases"] if case["case_id"] == case_id)
    assert case["language"] == "fi"

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    for text in strings(case):
        assert not any(marker in text for marker in ("\ufffd", "\u00c3", "\u00c2")), text
        assert "?" not in text.rstrip("?"), text
    assert all(question.endswith("?") for question in case["concept"]["open_questions"])
    assert "tekoälyosaaminen" in case["concept"]["background_need"]


def test_plan_contains_actual_contracts_frozen_versions_and_no_results(plan):
    assert len(plan["requests"]) == 8
    assert {r["stage"] for r in plan["requests"]} == {"concept", "draft", "review"}
    assert {r["language"] for r in plan["requests"]} == {"fi", "en"}
    assert {r["prompt_version"] for r in plan["requests"]} == {"concept_v2", "draft_workflow_v2", "review_workflow_v3"}
    assert plan["human_assessment"] is None and plan["status"] == "not_run"
    assert b.verify_plan(plan) == plan
    with pytest.raises(ValueError, match="complete labelled"):
        b.import_run(plan, b.response_template(plan))


def test_changed_source_packet_cannot_be_rehashed_into_the_reviewed_protocol(plan):
    plan["requests"][0]["messages"][1]["content"] = "Unreviewed arbitrary project text"
    original = dict(plan)
    original.pop("plan_sha256")
    plan["plan_sha256"] = q.digest(original)
    with pytest.raises(ValueError, match="Frozen planning"):
        b.verify_plan(plan)


def test_import_checks_all_stages_exact_evidence_and_keeps_quality_and_cost_unscored(plan):
    report = b.import_run(plan, bundle(plan))
    assert report["execution_kind"] == "offline_mock"
    assert report["summary"]["pydantic_valid"] == 8
    assert report["summary"]["human_quality"] is None and report["summary"]["critical_review_quality"] is None
    assert report["summary"]["mean_latency_seconds"] is None
    assert report["summary"]["known_token_totals"]["total_tokens"] is None
    assert all(item["actual_billed_cost"] is None and item["estimated_api_cost"] is None for item in report["attempts"])
    assert all(item["review_evidence_valid"] for item in report["attempts"] if item["stage"] == "review")


def test_invalid_review_selector_and_unknown_finish_are_not_successes(plan):
    data = bundle(plan)
    row = next(row for row, request in zip(data["responses"], plan["requests"]) if request["stage"] == "review")
    content = json.loads(row["reply"]["text"])
    content["findings"][0]["evidence_id"] = "E999"
    row["reply"]["text"] = json.dumps(content)
    data["responses"][0]["reply"]["finish_reason"] = None
    report = b.import_run(plan, data)
    assert report["attempts"][0]["pydantic_valid"] and not report["attempts"][0]["first_attempt_success"]
    review = next(a for a in report["attempts"] if a["stage"] == "review")
    assert review["pydantic_valid"] and review["review_evidence_valid"] is False
    assert not review["first_attempt_success"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "not_run"])
def test_incomplete_duplicate_or_unexecuted_rows_cannot_become_a_completed_run(plan, mutation):
    data = bundle(plan)
    if mutation == "missing":
        data["responses"].pop()
    elif mutation == "duplicate":
        data["responses"].append(data["responses"][0])
    else:
        data["responses"][0]["reply"] = {"error": "not_run"}
    with pytest.raises(ValueError):
        b.import_run(plan, data)


def test_blinded_packet_hides_identity_and_separates_human_from_ai_ratings(plan, tmp_path, monkeypatch):
    monkeypatch.setattr(q, "ROOT", tmp_path)
    first = b.import_run(plan, bundle(plan))
    second = b.import_run(plan, bundle(plan, "mistral", "model-beta"))
    output = tmp_path / ".benchmark-private" / "blind"
    packet = b.blind([first, second], output)
    assert len(packet["items"]) == 16 and {item["label"] for item in packet["items"]} == {"A", "B"}
    assert packet["execution_kind"] == "offline_mock"
    encoded = json.dumps(packet).lower()
    assert all(value not in encoded for value in ("model-alpha", "model-beta", "mistral", "qwen"))
    assert all(set(item["source_material"]) == {"idea"} for item in packet["items"] if item["stage"] == "concept")
    for kind in ("human", "ai-assisted"):
        ratings = q.read_json(output / (kind + "-ratings-template.json"))
        assert ratings["assessment_kind"] == kind
        assert all(value is None for rating in ratings["ratings"] for value in rating["scores"].values())
    assert (output / "PRIVATE-model-map.json").exists()
    with pytest.raises(ValueError):
        b.blind([first, second], output)


def test_model_self_identification_and_tampered_validation_block_blinding(plan, tmp_path, monkeypatch):
    monkeypatch.setattr(q, "ROOT", tmp_path)
    first = b.import_run(plan, bundle(plan))
    second = b.import_run(plan, bundle(plan, "mistral", "model-beta"))
    modified = deepcopy(second)
    modified["attempts"][0]["first_attempt_success"] = False
    with pytest.raises(ValueError, match="Validation evidence"):
        b.blind([first, modified], tmp_path / ".benchmark-private" / "tampered")
    data = bundle(plan, "mistral", "model-beta")
    content = json.loads(data["responses"][0]["reply"]["text"])
    content["background_need"] = "I am Mistral and identify this model."
    data["responses"][0]["reply"]["text"] = json.dumps(content)
    with pytest.raises(ValueError, match="model identity"):
        b.blind([first, b.import_run(plan, data)], tmp_path / ".benchmark-private" / "identity")


def test_recorded_token_cost_estimate_is_separate_from_unknown_actual_billing(plan):
    data = bundle(plan, "mistral", "model-beta")
    for row in data["responses"]:
        row["reply"].update(usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            billing_basis="standard_uncached", latency_seconds=1.25)
    pricing = q.Pricing(provider="mistral", model="model-beta", currency="EUR", input_per_million="1",
        output_per_million="2", source_url="https://example.invalid/fictional-prices",
        verified_on=date(2026, 11, 13), billing_basis="standard_uncached")
    report = b.import_run(plan, data, pricing=pricing)
    assert report["pricing"] == pricing.model_dump(mode="json")
    assert report["summary"]["mean_latency_seconds"] == 1.25
    assert report["summary"]["known_token_totals"]["total_tokens"] == 240
    assert float(report["summary"]["estimated_cost_total_known"]) == pytest.approx(0.0004)
    assert all(item["actual_billed_cost"] is None for item in report["attempts"])
    assert report["execution_kind"] == "offline_mock"
