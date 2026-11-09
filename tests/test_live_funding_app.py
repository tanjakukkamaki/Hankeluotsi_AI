import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel
from streamlit.testing.v1 import AppTest

from hankeluotsi.funding_calls import FundingCall, LiveSearchResult, parse_call_date
from hankeluotsi.funding_matching import RELEVANCE_CATEGORIES
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FictionalStage(BaseModel):
    text: str


def save_idea(repository, operation="fictional-one"):
    return repository.create_project({
        "title": f"Fictional digital skills {operation}",
        "development_need": "Fictional participants need research and training.",
        "target_groups": ["Fictional volunteers"],
        "expected_change": "Participants practise digital skills.",
        "geography": "Fictional Finland",
    }, operation_id=operation)


def fictional_call(**changes):
    now = datetime.now(timezone.utc)
    fields = dict(
        source="Interreg Aurora", programme="Fictional programme for testing",
        identifier="FICTIONAL-1", title="Fictional digital skills call",
        objectives="Fictional research and training objectives.",
        geographic_area="Fictional area; verify conditions.",
        applicant_requirements="Fictional institutions; verify call terms.",
        opening=parse_call_date((now - timedelta(days=4)).isoformat()),
        deadline=parse_call_date((now + timedelta(days=8)).isoformat()),
        official_status="open",
        source_url="https://www.interregaurora.eu/projects/calls-for-applications-2/",
        evidence_url="https://www.interregaurora.eu/wp-content/uploads/Timetable-of-the-planned-calls-for-proposals-fictional.csv",
        retrieved_at=now,
        uncertainties=("Fictional source fixture; no eligibility assessment.",),
    )
    fields.update(changes)
    return FundingCall(**fields)


def test_live_search_is_explicit_local_and_preserves_saved_idea_across_reruns(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    call = fictional_call()
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(call,))) as search, patch("hankeluotsi.funding.retrieve_funding_opportunities") as guidance, patch("hankeluotsi.llm_client.LLMClient.generate") as generate:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        assert not any(button.label == "Search Live Funding Calls" for button in app.button)
        project = save_idea(repository)
        app.run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        search.assert_not_called()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        assert not app.exception
        search.assert_called_once_with()
        generate.assert_not_called()
        guidance.assert_not_called()
        for expected in ("Current status: open", "Official identifier: FICTIONAL-1", "Fictional digital skills call", "Shared vocabulary topics: digital, skills, research"):
            assert any(expected in item.value for item in app.text)
        assert any("Call record retrieved:" in item.value for item in app.caption)
        assert any(item.value == "#### General programme suggestions" for item in app.markdown)
        assert any(item.proto.url == call.evidence_url for item in app.get("link_button"))
        app.run()
        assert search.call_count == 1
        assert repository.load_project(project.project_id) == project


def test_unavailable_live_sources_keep_official_links_and_general_guidance_available(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(notices=("Fictional source unavailable; use its official link.",))):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
    assert not app.exception
    assert any("No live call records could be verified" in item.value for item in app.info)
    assert any("Fictional source unavailable" in item.value for item in app.warning)
    assert any(button.label == "Find Funding Opportunities" for button in app.button)
    assert not any(item.label == "Inspect a live call" for item in app.selectbox)
    assert repository.load_project(project.project_id) == project


def test_live_results_are_guarded_by_selected_project_and_saved_idea(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    first = save_idea(repository, "first")
    second = save_idea(repository, "second")
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(fictional_call(),))) as search:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(first.project_id).run()
        app.button(key=f"live-funding-search-{first.project_id}").click().run()
        assert any(item.label == "Inspect a live call" for item in app.selectbox)
        app.selectbox(key="open_project_id").select(second.project_id).run()
        assert not any(item.label == "Inspect a live call" for item in app.selectbox)
        app.selectbox(key="open_project_id").select(first.project_id).run()
        assert any(item.label == "Inspect a live call" for item in app.selectbox)
        repository.save_idea(first.project_id, first.idea.model_copy(update={"title": "Other fictional idea"}), operation_id="change-idea")
        app.run()
        assert not app.exception
        assert not any(item.label == "Inspect a live call" for item in app.selectbox)
        assert search.call_count == 1


def test_live_search_preserves_approved_concept_pdf_and_consistency_check(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    concept = ConceptPaper.model_validate(json.loads((APP_PATH.parent / "tests/fixtures/concept_paper.json").read_text(encoding="utf-8")))
    repository.save_concept(project.project_id, concept, operation_id="concept")
    repository.save_draft(project.project_id, FictionalStage(text="Fictional draft"), model_type=FictionalStage, operation_id="draft")
    repository.save_review(project.project_id, FictionalStage(text="Fictional review"), model_type=FictionalStage, deterministic_findings=[], operation_id="review")
    before = repository.approve_project(project.project_id, operation_id="approval")
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(fictional_call(),))):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
    assert not app.exception
    assert repository.load_project(project.project_id) == before
    assert any(item.label == "Download PDF" for item in app.get("download_button"))
    assert any(item.value == "Consistency Check" for item in app.subheader)


def test_stale_snapshot_becomes_unknown_without_hidden_refresh_and_source_text_is_plain(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    hostile = '<script>fetch("https://untrusted.invalid")</script>'
    call = fictional_call(title=hostile, objectives=hostile, retrieved_at=datetime.now(timezone.utc) - timedelta(hours=7))
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(call,))) as search:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        app.run()
    assert not app.exception
    assert search.call_count == 1
    assert any("Current status: unknown" in item.value for item in app.text)
    assert any("Snapshot is stale" in item.value for item in app.text)
    assert any(item.value == hostile for item in app.text)
    assert not any(hostile in item.value for item in app.markdown)


def test_ranking_and_all_filters_are_local_and_preserve_low_and_unmatched_records(tmp_path, monkeypatch):
    path = tmp_path / "ranked.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    good = fictional_call(identifier="FICTIONAL-Z-SKILLS", programme="Fictional skills programme")
    bad = fictional_call(identifier="FICTIONAL-A-SOLAR", programme="Fictional research programme",
        title="Fictional Solar Radiation Modification research",
        objectives="Atmospheric climate research using solar radiation modelling.")
    unknown = fictional_call(identifier="FICTIONAL-UNKNOWN", title="Fictional Call 7", objectives=None,
        opening=parse_call_date("2030-01-01"), deadline=parse_call_date("2020-01-01"))
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(bad, unknown, good))) as search, patch("hankeluotsi.llm_client.LLMClient.generate") as generate:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        selector = f"ranked-live-call-selection-{project.project_id}"
        assert app.selectbox(key=selector).value.endswith(good.identifier)
        assert len(app.selectbox(key=selector).options) == 3
        app.multiselect(key=f"live-relevance-{project.project_id}").set_value(["Low"]).run()
        assert app.selectbox(key=selector).value.endswith(bad.identifier)
        app.multiselect(key=f"live-relevance-{project.project_id}").set_value(list(RELEVANCE_CATEGORIES)).run()
        app.multiselect(key=f"live-programme-{project.project_id}").set_value([bad.programme]).run()
        assert len(app.selectbox(key=selector).options) == 1
        app.multiselect(key=f"live-status-{project.project_id}").set_value(["closed"]).run()
        assert not any(item.label == "Inspect a live call" for item in app.selectbox)
        assert any("No calls match these filters" in item.value for item in app.info)
        assert any(button.label == "Find Funding Opportunities" for button in app.button)
        app.multiselect(key=f"live-programme-{project.project_id}").set_value([good.programme, bad.programme, unknown.programme]).run()
        app.multiselect(key=f"live-status-{project.project_id}").set_value(["unknown"]).run()
        assert app.selectbox(key=selector).value.endswith(unknown.identifier)
        assert any("Current status: unknown" in item.value for item in app.text)
        assert any("Local relevance score: not assigned" in item.value for item in app.text)
        app.multiselect(key=f"live-relevance-{project.project_id}").set_value([]).run()
        assert not app.exception
        search.assert_called_once_with()
        generate.assert_not_called()
        assert repository.load_project(project.project_id) == project


def test_unconfirmed_source_is_not_presented_as_verified_or_open(tmp_path, monkeypatch):
    path = tmp_path / "unconfirmed.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    unconfirmed = fictional_call(evidence_url="https://www.interregaurora.eu/unconfirmed.csv")
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(unconfirmed,))):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
    assert not app.exception
    assert any("This record is not verified" in item.value for item in app.caption)
    assert any("Current status: unknown" in item.value for item in app.text)
    assert any("Insufficient Information relevance" in item.value for item in app.markdown)
    assert any("Local relevance score: not assigned" in item.value for item in app.text)


def test_explicit_refresh_with_changed_programmes_restores_valid_selection(tmp_path, monkeypatch):
    path = tmp_path / "refresh.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = save_idea(repository)
    first = fictional_call(programme="Fictional previous programme")
    second = fictional_call(identifier="FICTIONAL-NEW", programme="Fictional replacement programme")
    with patch("hankeluotsi.live_funding.search_live_funding_calls", side_effect=[LiveSearchResult(calls=(first,)), LiveSearchResult(calls=(second,))]) as search:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        assert not app.exception
        assert app.selectbox(key=f"ranked-live-call-selection-{project.project_id}").value.endswith(second.identifier)
        assert app.multiselect(key=f"live-programme-{project.project_id}").value == [second.programme]
        assert search.call_count == 2
