"""Offline blinded human review. Scores are supplied by people, never generated."""

import argparse
import json
import random
import statistics
from pathlib import Path

from pydantic import Field

from hankeluotsi.model_quality import Manifest, Reply, assess, digest, read_json, write_new
from hankeluotsi.schemas import NonBlank, StrictModel


CRITERIA = ("development_need", "objectives", "activities", "results_indicators", "coherence_usability")
FLAGS = ("unsupported_assumptions", "invented_funding_requirements", "vague_indicators",
         "unrealistic_feasibility", "language_problems")


class Scores(StrictModel):
    development_need: int | None = Field(default=None, ge=1, le=5, strict=True)
    objectives: int | None = Field(default=None, ge=1, le=5, strict=True)
    activities: int | None = Field(default=None, ge=1, le=5, strict=True)
    results_indicators: int | None = Field(default=None, ge=1, le=5, strict=True)
    coherence_usability: int | None = Field(default=None, ge=1, le=5, strict=True)


class Flags(StrictModel):
    unsupported_assumptions: bool | None = Field(default=None, strict=True)
    invented_funding_requirements: bool | None = Field(default=None, strict=True)
    vague_indicators: bool | None = Field(default=None, strict=True)
    unrealistic_feasibility: bool | None = Field(default=None, strict=True)
    language_problems: bool | None = Field(default=None, strict=True)


class Rating(StrictModel):
    review_id: NonBlank
    scores: Scores = Field(default_factory=Scores)
    flags: Flags = Field(default_factory=Flags)
    evidence: str = ""
    comment: str = ""


class Ratings(StrictModel):
    rubric_version: str = "expert_quality_v1"
    rubric_sha256: str
    packet_sha256: str
    reviewer_id: NonBlank
    ratings: list[Rating]


def verify_report(report: dict) -> Manifest:
    if report["version"] != "quality_results_v1":
        raise ValueError("Unsupported results version")
    manifest = Manifest.model_validate(report["manifest"])
    if digest(manifest.model_dump(mode="json")) != report["manifest_sha256"]:
        raise ValueError("Manifest integrity check failed")
    requests = {r.request_sha256: r for r in manifest.requests}
    attempts = report["attempts"]
    keys = [a["request_sha256"] for a in attempts]
    if len(keys) != len(set(keys)) or set(keys) != set(requests):
        raise ValueError("Incomplete or duplicated run; retain all planned attempts and failures")
    for attempt in attempts:
        request = requests[attempt["request_sha256"]]
        if (attempt["case_id"], attempt["trial"], attempt["language"]) != (request.case_id, request.trial, request.language):
            raise ValueError("Attempt identity does not match its request")
        verified = assess(Reply.model_validate(attempt["reply"]))
        if any(attempt[field] != value for field, value in verified.items()):
            raise ValueError("Output validation facts were modified")
    return manifest


def prepare(reports: list[dict], output: Path, seed: int = 91) -> None:
    if not reports:
        raise ValueError("At least one completed report is required")
    manifest = verify_report(reports[0])
    seen_runs, seen_models = set(), set()
    entries = []
    for report in reports:
        verify_report(report)
        if report["manifest_sha256"] != reports[0]["manifest_sha256"]:
            raise ValueError("Compare only runs using exactly the same frozen manifest")
        model = (report["provider"], report["requested_model"])
        if report["run_id"] in seen_runs or model in seen_models:
            raise ValueError("Duplicate run/model would overweight one provider")
        seen_runs.add(report["run_id"])
        seen_models.add(model)
        entries.extend((report, attempt) for attempt in report["attempts"])
    random.Random(seed).shuffle(entries)
    cases = {c.case_id: c for c in manifest.cases}
    public, private, ratings = [], [], []
    for index, (report, attempt) in enumerate(entries, 1):
        review_id = f"R{index:04}"
        case = cases[attempt["case_id"]]
        public.append({"review_id": review_id, "case_id": case.case_id, "language": case.language,
            "fictional_idea": case.idea.model_dump(mode="json"), "review_notes": case.review_notes,
            "output": attempt["reply"]["text"]})
        private.append({"review_id": review_id, "case_id": case.case_id, "trial": attempt["trial"],
            "provider": report["provider"], "requested_model": report["requested_model"],
            "reported_model": attempt["reply"]["reported_model"],
            "first_attempt_success": attempt["first_attempt_success"],
            "structural_errors": any(f["severity"] == "error" for f in attempt["consistency_findings"]),
            "source_run_id": report["run_id"], "source_report_sha256": digest(report)})
        ratings.append(Rating(review_id=review_id).model_dump(mode="json"))
    output.mkdir(parents=True, exist_ok=False)
    packet = {"version": "blind_packet_v1", "rubric": manifest.rubric, "items": public}
    write_new(output / "review-packet.json", packet)
    write_new(output / "ratings-template.json", {"rubric_version": "expert_quality_v1",
        "rubric_sha256": manifest.rubric_sha256, "packet_sha256": digest(packet),
        "reviewer_id": "reviewer_01", "ratings": ratings})
    write_new(output / "PRIVATE-key.json", {"version": "blind_key_v1", "rubric_sha256": manifest.rubric_sha256,
        "packet_sha256": digest(packet), "shuffle_seed": seed, "items": private})


def analyze(key: dict, ratings: Ratings) -> dict:
    if key["version"] != "blind_key_v1" or ratings.rubric_version != "expert_quality_v1":
        raise ValueError("Review versions do not match")
    if ratings.packet_sha256 != key["packet_sha256"] or ratings.rubric_sha256 != key["rubric_sha256"]:
        raise ValueError("Ratings belong to a different blinded packet or rubric")
    mapping = {item["review_id"]: item for item in key["items"]}
    ids = [item.review_id for item in ratings.ratings]
    if len(ids) != len(set(ids)) or set(ids) != set(mapping):
        raise ValueError("Rating IDs must match the entire review template, including unassessed outputs")
    groups = {}
    for rating in ratings.ratings:
        item = mapping[rating.review_id]
        group = groups.setdefault(item["provider"] + ":" + item["requested_model"], [])
        scores = rating.scores.model_dump()
        flags = rating.flags.model_dump()
        complete = all(value is not None for value in scores.values())
        if (any(value is not None for value in scores.values()) or any(value is not None for value in flags.values())) and not rating.evidence.strip():
            raise ValueError("Assessed scores and flags require specific field/ID evidence")
        gate = None
        if complete and all(value is not None for value in flags.values()):
            gate = (min(scores.values()) >= 4 and not any(flags.values())
                    and item["first_attempt_success"] and not item["structural_errors"])
        group.append({**item, "scores": scores, "flags": flags, "complete": complete, "gate": gate})
    result = {"version": "human_quality_summary_v1", "reviewer_id": ratings.reviewer_id, "providers": {}}
    for model, items in groups.items():
        reviewed = [i for i in items if i["complete"]]
        case_means = []
        for case in sorted({i["case_id"] for i in reviewed}):
            case_items = [i for i in reviewed if i["case_id"] == case]
            case_means.append(statistics.mean(statistics.mean(i["scores"].values()) for i in case_items))
        result["providers"][model] = {"planned_outputs": len(items), "fully_scored_outputs": len(reviewed),
            "fully_scored_cases": len(case_means), "rating_coverage": len(reviewed) / len(items),
            "criterion_means": {c: statistics.mean(i["scores"][c] for i in reviewed) if reviewed else None for c in CRITERIA},
            "case_macro_mean": statistics.mean(case_means) if case_means else None,
            "case_mean_range": [min(case_means), max(case_means)] if case_means else None,
            "flags_present": {f: sum(i["flags"][f] is True for i in items) for f in FLAGS},
            "flags_unassessed": {f: sum(i["flags"][f] is None for i in items) for f in FLAGS},
            "candidate_usable_outputs": sum(i["gate"] is True for i in items),
            "usability_unassessed": sum(i["gate"] is None for i in items),
            "usable_fraction_of_all_planned": sum(i["gate"] is True for i in items) / len(items),
            "reported_model_ids": sorted({i["reported_model"] for i in items if i["reported_model"]}),
            "unknown_model_identity_outputs": sum(not i["reported_model"] for i in items)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline blinded evaluation; no model or database access.")
    sub = parser.add_subparsers(dest="command", required=True)
    blind = sub.add_parser("prepare")
    blind.add_argument("--reports", type=Path, nargs="+", required=True)
    blind.add_argument("--output", type=Path, required=True)
    blind.add_argument("--seed", type=int, default=91)
    score = sub.add_parser("analyze")
    score.add_argument("--key", type=Path, required=True)
    score.add_argument("--ratings", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare([read_json(path) for path in args.reports], args.output, args.seed)
            print("Prepared blinded packet; share packet and ratings only, keep PRIVATE-key.json from raters.")
        else:
            summary = analyze(read_json(args.key), Ratings.model_validate(read_json(args.ratings)))
            write_new(args.output, summary)
            print("Summarized supplied human ratings; unassessed values remain unknown.")
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, "Review input/output rejected; check versions, IDs, evidence and paths. No input payloads printed.\n")


if __name__ == "__main__":
    main()
