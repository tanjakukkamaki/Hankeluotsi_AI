import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from streamlit.testing.v1 import AppTest

from hankeluotsi.funding import programme_guidance, retrieve_funding_opportunities
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FictionalStage(BaseModel):
    text: str


def save_project(repository, operation="fictional-idea"):
    return repository.create_project(
        {
            "title": f"Fictional digital skills {operation}",
            "development_need": "Fictional groups need digital training.",
            "target_groups": ["Fictional cultural volunteers"],
            "expected_change": "Participants practise digital skills.",
            "geography": "Fictional western Finland",
        },
        operation_id=operation,
    )


def search_button(app):
    return next(button for button in app.button if button.label == "Find Funding Opportunities")


def comparison_tables(app):
    return [item.value for item in app.markdown if item.value.startswith("| Programme | Shared topics | Call status |")]


def test_funding_search_requires_saved_project_and_explicit_submission(tmp_path, monkeypatch):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    with patch("hankeluotsi.funding.retrieve_funding_opportunities", return_value=programme_guidance()) as retrieve:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        assert not any(button.label == "Find Funding Opportunities" for button in app.button)
        repository = ProjectRepository(database_path)
        project = save_project(repository)
        app.run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        assert not app.exception
        retrieve.assert_not_called()
        search_button(app).click().run()
        retrieve.assert_called_once_with(retrieve_live=False)
        assert not app.exception
        assert any("Programme guidance only" in item.value for item in app.warning)
        assert comparison_tables(app)[0].count("| unknown |") == 6
        assert "skills" in comparison_tables(app)[0]
        assert any("General guidance verified: 2026-11-08" in item.value for item in app.caption)
        assert any("Application dates: Unknown" in item.value for item in app.text)
        app.run()
        assert retrieve.call_count == 1
        assert repository.load_project(project.project_id) == project


@pytest.mark.parametrize("approved", [False, True], ids=["concept-ready", "approved"])
def test_funding_search_survives_offline_sources_without_llm_or_saved_concept_mutation(tmp_path, monkeypatch, approved):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    repository = ProjectRepository(database_path)
    project = save_project(repository)
    fixture = Path(__file__).parent / "fixtures" / "concept_paper.json"
    before = repository.save_concept(
        project.project_id,
        ConceptPaper.model_validate(json.loads(fixture.read_text(encoding="utf-8"))),
        operation_id="fictional-concept",
    )
    if approved:
        repository.save_draft(
            project.project_id, FictionalStage(text="Fictional draft"),
            model_type=FictionalStage, operation_id="fictional-draft",
        )
        repository.save_review(
            project.project_id, FictionalStage(text="Fictional review"),
            model_type=FictionalStage, deterministic_findings=[], operation_id="fictional-review",
        )
        before = repository.approve_project(project.project_id, operation_id="fictional-approval")
    with patch("hankeluotsi.funding._fetch_public_page", side_effect=TimeoutError("offline")) as fetch, patch("hankeluotsi.llm_client.LLMClient.generate") as generate:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.checkbox(key=f"funding-live-{project.project_id}").check()
        search_button(app).click().run()
        assert not app.exception
        assert fetch.call_count == 4
        generate.assert_not_called()
        assert any("Live programme page description unavailable" in item.value for item in app.caption)
        assert any(item.label == "Download PDF" for item in app.get("download_button"))
        assert any("Consistency Check" in item.value for item in app.subheader)
        assert repository.load_project(project.project_id) == before
        app.run()
        assert fetch.call_count == 4


def test_switching_saved_ideas_hides_previous_research_and_changed_idea_invalidates_results(tmp_path, monkeypatch):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    repository = ProjectRepository(database_path)
    first = save_project(repository, "first")
    second = save_project(repository, "second")
    with patch("hankeluotsi.funding.retrieve_funding_opportunities", return_value=programme_guidance()) as retrieve:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(first.project_id).run()
        search_button(app).click().run()
        assert len(comparison_tables(app)) == 1
        app.selectbox(key="open_project_id").select(second.project_id).run()
        assert not app.exception
        assert len(comparison_tables(app)) == 0
        assert retrieve.call_count == 1
        app.selectbox(key="open_project_id").select(first.project_id).run()
        assert len(comparison_tables(app)) == 1
        repository.save_idea(
            first.project_id,
            first.idea.model_copy(update={"title": "Other fictional idea"}),
            operation_id="change-idea",
        )
        app.run()
        assert not app.exception
        assert len(comparison_tables(app)) == 0
        assert retrieve.call_count == 1


def test_live_metadata_is_plain_text_with_its_own_source_and_retrieval_date(tmp_path, monkeypatch):
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(tmp_path / "app.sqlite3"))
    repository = ProjectRepository(tmp_path / "app.sqlite3")
    project = save_project(repository)
    hostile_text = '<img src="https://untrusted.invalid/tracker" onerror="alert(1)">'
    records = retrieve_funding_opportunities(
        retrieve_live=True,
        fetch_page=lambda url: f"<title>Official programme</title><meta name='description' content='{hostile_text}'>",
    )
    with patch("hankeluotsi.funding.retrieve_funding_opportunities", return_value=records):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="open_project_id").select(project.project_id).run()
        search_button(app).click().run()
    assert not app.exception
    assert any(hostile_text in item.value for item in app.text)
    assert not any(hostile_text in item.value for item in app.markdown)
    assert any("Page description retrieved:" in item.value for item in app.caption)
    assert repository.load_project(project.project_id) == project
