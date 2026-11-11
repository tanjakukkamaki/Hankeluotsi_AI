"""Offline integration of planning, response import, blinding and human-score summaries."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hankeluotsi import model_quality as q
from hankeluotsi import model_quality_review as review


@pytest.fixture
def manifest():
    return q.create_manifest(q.Settings(trials=1))


def report_for(manifest, provider="lm_studio", failed=False):
    text = (Path(__file__).parent / "fixtures/concept_paper.json").read_text(encoding="utf-8")
    bundle = q.ImportBundle(manifest_sha256=q.digest(manifest.model_dump(mode="json")), provider=provider,
        requested_model="fictional-" + provider, responses=[q.ImportedRow(request_sha256=r.request_sha256,
            reply=q.Reply(text=None if failed else text, error="timeout" if failed else None,
                reported_model="fictional-" + provider, finish_reason=None if failed else "stop")) for r in manifest.requests])
    return q.run(manifest, q.ImportedProvider(bundle, manifest))


def scored_template(directory, score=4, flagged=None):
    payload = q.read_json(directory / "ratings-template.json")
    for item in payload["ratings"]:
        item["scores"] = {criterion: score for criterion in review.CRITERIA}
        item["flags"] = {flag: flag == flagged for flag in review.FLAGS}
        item["evidence"] = "Synthetic test rating only: O1/A1/R1/I1 reviewed. Not a human study result."
    return review.Ratings.model_validate(payload)


def test_blinding_removes_provider_metadata_but_keeps_input_and_all_failures(tmp_path, manifest):
    reports = [report_for(manifest), report_for(manifest, "mistral", failed=True)]
    output = tmp_path / "blind"
    review.prepare(reports, output)
    packet = q.read_json(output / "review-packet.json")
    key = q.read_json(output / "PRIVATE-key.json")
    assert len(packet["items"]) == 20 and len(key["items"]) == 20
    assert "fictional-lm_studio" not in json.dumps(packet)
    assert "fictional-mistral" not in json.dumps(packet)
    assert sum(item["output"] is None for item in packet["items"]) == 10
    assert all("provider" not in item and "trial" not in item for item in packet["items"])
    assert {item["provider"] for item in key["items"]} == {"lm_studio", "mistral"}
    result = review.analyze(key, review.Ratings.model_validate(q.read_json(output / "ratings-template.json")))
    assert all(item["case_macro_mean"] is None and item["rating_coverage"] == 0 for item in result["providers"].values())


def test_human_scores_flags_and_structural_success_remain_separate(tmp_path, manifest):
    output = tmp_path / "blind"
    review.prepare([report_for(manifest), report_for(manifest, "mistral", failed=True)], output)
    key = q.read_json(output / "PRIVATE-key.json")
    ratings = scored_template(output)
    result = review.analyze(key, ratings)
    local = result["providers"]["lm_studio:fictional-lm_studio"]
    failed = result["providers"]["mistral:fictional-mistral"]
    assert local["case_macro_mean"] == 4 and local["usable_fraction_of_all_planned"] == 1
    assert failed["fully_scored_outputs"] == 10 and failed["candidate_usable_outputs"] == 0
    flagged = review.analyze(key, scored_template(output, flagged="invented_funding_requirements"))
    assert flagged["providers"]["lm_studio:fictional-lm_studio"]["candidate_usable_outputs"] == 0
    assert flagged["providers"]["lm_studio:fictional-lm_studio"]["flags_present"]["invented_funding_requirements"] == 10


def test_missing_flags_are_unknown_not_absent_and_completed_scores_need_evidence(tmp_path, manifest):
    output = tmp_path / "blind"
    review.prepare([report_for(manifest)], output)
    key = q.read_json(output / "PRIVATE-key.json")
    payload = q.read_json(output / "ratings-template.json")
    payload["ratings"][0]["scores"] = {criterion: 5 for criterion in review.CRITERIA}
    with pytest.raises(ValueError, match="evidence"):
        review.analyze(key, review.Ratings.model_validate(payload))
    payload["ratings"][0]["evidence"] = "Fictional test evidence for O1."
    result = review.analyze(key, review.Ratings.model_validate(payload))["providers"]["lm_studio:fictional-lm_studio"]
    assert result["fully_scored_outputs"] == 1 and result["fully_scored_cases"] == 1
    assert result["rating_coverage"] == 0.1 and result["usability_unassessed"] == 10


@pytest.mark.parametrize("score", [0, 6, True, "4", 3.5])
def test_human_score_bounds_and_types_are_strict(score):
    with pytest.raises(ValidationError):
        review.Scores(development_need=score)


def test_ratings_with_unknown_duplicate_or_missing_ids_are_rejected(tmp_path, manifest):
    output = tmp_path / "blind"
    review.prepare([report_for(manifest)], output)
    key = q.read_json(output / "PRIVATE-key.json")
    original = q.read_json(output / "ratings-template.json")
    for change in ("missing", "duplicate", "unknown"):
        payload = copy.deepcopy(original)
        if change == "missing":
            payload["ratings"].pop()
        elif change == "duplicate":
            payload["ratings"].append(payload["ratings"][0])
        else:
            payload["ratings"][0]["review_id"] = "UNKNOWN"
        with pytest.raises(ValueError):
            review.analyze(key, review.Ratings.model_validate(payload))


def test_blinding_rejects_different_settings_duplicate_runs_and_tampered_facts(tmp_path, manifest):
    report = report_for(manifest)
    other = report_for(q.create_manifest(q.Settings(trials=2)), "mistral")
    with pytest.raises(ValueError, match="same frozen"):
        review.prepare([report, other], tmp_path / "different")
    with pytest.raises(ValueError, match="Duplicate"):
        review.prepare([report, report], tmp_path / "duplicate")
    report["attempts"][0]["pydantic_valid"] = False
    with pytest.raises(ValueError, match="modified"):
        review.prepare([report], tmp_path / "tampered")


def test_scores_from_a_different_blinded_packet_are_not_silently_reassigned(tmp_path, manifest):
    output = tmp_path / "blind"
    review.prepare([report_for(manifest)], output)
    key = q.read_json(output / "PRIVATE-key.json")
    ratings = scored_template(output)
    ratings.packet_sha256 = "wrong-packet-with-the-same-R0001-style-identifiers"
    with pytest.raises(ValueError, match="different blinded"):
        review.analyze(key, ratings)


def test_a_flag_alone_also_requires_evidence(tmp_path, manifest):
    output = tmp_path / "blind"
    review.prepare([report_for(manifest)], output)
    payload = q.read_json(output / "ratings-template.json")
    payload["ratings"][0]["flags"]["invented_funding_requirements"] = True
    with pytest.raises(ValueError, match="evidence"):
        review.analyze(q.read_json(output / "PRIVATE-key.json"), review.Ratings.model_validate(payload))


def test_complete_cli_flow_imports_and_reviews_without_network_or_database(tmp_path):
    plan = tmp_path / "plan"
    q.main(["plan", "--trials", "1", "--output", str(plan)])
    manifest = q.load_manifest(plan / "manifest.json")
    text = (Path(__file__).parent / "fixtures/concept_paper_fi.json").read_text(encoding="utf-8")
    bundle = q.read_json(plan / "responses-template.json")
    bundle["requested_model"] = "fictional-mistral-offline-fixture"
    for row in bundle["responses"]:
        row["reply"] = q.Reply(text=text, finish_reason="stop", reported_model=bundle["requested_model"]).model_dump(mode="json")
    responses = tmp_path / "fictional-responses.json"
    q.write_new(responses, bundle)
    result_dir = tmp_path / "results"
    blind = tmp_path / "blind"
    with patch("sqlite3.connect", side_effect=AssertionError("No database access")), patch(
            "socket.create_connection", side_effect=AssertionError("No network access")):
        q.main(["import-responses", "--manifest", str(plan / "manifest.json"), "--responses", str(responses), "--output", str(result_dir)])
        review.main(["prepare", "--reports", str(result_dir / "results.json"), "--output", str(blind)])
        review.main(["analyze", "--key", str(blind / "PRIVATE-key.json"), "--ratings", str(blind / "ratings-template.json"),
                     "--output", str(tmp_path / "summary.json")])
    result = q.read_json(result_dir / "results.json")
    assert result["summary"]["first_attempt_successes"] == 10
    assert q.read_json(tmp_path / "summary.json")["providers"]["mistral:fictional-mistral-offline-fixture"]["case_macro_mean"] is None
    assert result["attempts"][0]["reply"]["text"] == text
    assert len(list((result_dir / "attempts").glob("*.json"))) == 10


def test_no_credential_fields_are_accepted_or_results_overwritten(tmp_path, manifest):
    with pytest.raises(ValidationError):
        q.ModelMetadata(api_key="fictional-secret")
    with pytest.raises(ValidationError):
        q.ImportBundle(manifest_sha256="unused", provider="mistral", requested_model="fictional",
                       responses=[], api_key="fictional-secret")
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "preserve.json"
    sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        q.main(["plan", "--output", str(output)])
    assert error.value.code == 2 and sentinel.read_text(encoding="utf-8") == "unchanged"
