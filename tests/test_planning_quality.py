import json
from datetime import date
from pathlib import Path

import pytest

from hankeluotsi.draft_checks import check_draft_consistency
from hankeluotsi.draft_exporter import export_approved_markdown
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.draft_workflow import draft_input, review_input
from hankeluotsi.i18n import localize
from hankeluotsi.planning_quality import check_planning_advisories
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


DATA = Path(__file__).parent / "fixtures"
AS_OF = date(2026, 11, 13)


def cases():
    return json.loads((DATA / "planning_quality_cases_v1.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["case_id"])
def test_fixed_planning_fixtures_and_actual_versioned_source_packets(case):
    idea, concept, draft = (ProjectIdea.model_validate(case["idea"]), ConceptPaper.model_validate(case["concept"]),
        ApplicationDraft.model_validate(case["draft"]))
    assert check_draft_consistency(draft) == []  # a linked graph can still be a poor plan
    text = draft_input(idea, concept, case["language"], reference_date=AS_OF)
    assert "draft_workflow_v2" in text and AS_OF.isoformat() in text
    text, catalog = review_input(idea, draft, case["language"], reference_date=AS_OF)
    packet = json.loads(text.split("\nSOURCE_PACKET:\n", 1)[1])
    assert "review_workflow_v3" in text and "two-day workshop" in text
    assert packet["scope_comparison_evidence"]["claims"] and packet["scope_comparison_evidence"]["delivery"]
    assert packet["evidence_catalogue"] == catalog and packet["planning_reference_date"] == AS_OF.isoformat()
    codes = {item["code"] for item in packet["planning_observations"]}
    if case["case_id"] in ("P03", "P04"):
        assert {"PARTNER_NAME_HAS_LABEL", "DUPLICATE_PARTNER_NAME", "TIMELINE_DATES_IN_PAST"} <= codes
    else:
        assert not codes


@pytest.mark.parametrize("period,expected", [
    ("Proposed months 1–6", set()), ("2026", set()), ("2024–2027", set()),
    ("2027-05-01", set()), ("2024-05-01, extension through 2027", set()),
    ("2024-05-01 to 2024-05-02", {"TIMELINE_DATES_IN_PAST"}),
    ("Toukokuu 2024", {"TIMELINE_YEARS_IN_PAST"}),
    ("2024-99-99", {"TIMELINE_INVALID_DATE"}),
])
def test_timeline_advisory_is_explicit_and_does_not_infer_relative_or_future_dates(period, expected):
    model = ApplicationDraft.model_validate(cases()[0]["draft"])
    model.timeline[0].period = period
    before = model.model_dump_json()
    observations = check_planning_advisories(model, reference_date=AS_OF)
    assert {item.code for item in observations} == expected
    assert all(item.severity.value == "warning" and localize(item.message, "fi") != item.message for item in observations)
    assert model.model_dump_json() == before


def test_advisories_do_not_change_stored_structural_checks_or_break_old_approved_exports(tmp_path):
    case = cases()[0]
    model = ApplicationDraft.model_validate(case["draft"])
    model.timeline[0].period = "2024-05-01"
    repo = ProjectRepository(tmp_path / "fictional.sqlite3")
    project = repo.create_project(case["idea"], operation_id="idea")
    repo.save_concept(project.project_id, case["concept"], operation_id="concept")
    repo.save_draft(project.project_id, model, model_type=ApplicationDraft, operation_id="draft")
    review = ReviewReport.model_validate_json((DATA / "review_report.json").read_text())
    repo.save_review(project.project_id, review, model_type=ReviewReport, deterministic_findings=[], operation_id="review")
    before = repo.approve_project(project.project_id, operation_id="old-human-approval")
    original = export_approved_markdown(repo, project.project_id)
    assert check_planning_advisories(model, reference_date=AS_OF)
    assert export_approved_markdown(repo, project.project_id) == original
    assert repo.load_project(project.project_id) == before


def test_reference_date_is_explicit_and_not_an_implicit_time_dependent_approval_rule():
    model = ApplicationDraft.model_validate(cases()[0]["draft"])
    with pytest.raises(ValueError):
        check_planning_advisories(model, reference_date="today")
