"""Workflow placement and session state; real unsubmitted forms also need browser QA."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
import pytest
from streamlit.testing.v1 import AppTest

from hankeluotsi import workflow_navigation as navigation
from hankeluotsi.funding import retrieve_funding_opportunities
from hankeluotsi.i18n import localize
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper
from test_app import APP_PATH, concept_data, create_saved_concept, fill_fictional_idea


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=AssertionError("Navigation must not make network requests")))


def open_app(path, monkeypatch):
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def choose_stage(app, stage, index):
    # AppTest has no native tab-click API. Set the canonical control state and
    # inspect the panel index Streamlit sends; actual clicks are checked in Edge.
    app.session_state["workflow_stage"] = stage
    app.run()
    assert not app.exception
    assert app.get("tab_container")[0].proto.tab_container.default_tab_index == index


@pytest.mark.parametrize("language", ["en", "fi"])
def test_each_panel_contains_its_existing_functionality_once(tmp_path, monkeypatch, language):
    path = tmp_path / "navigation.sqlite3"
    repo, project = create_saved_concept(path)
    before = repo.list_projects()
    app = open_app(path, monkeypatch)
    app.selectbox(key="open_project_id").select(project.project_id).run()
    app.selectbox(key="ui_language").select(language).run()
    tr = lambda text: localize(text, language)
    assert [tab.label.split("\n")[0].rstrip() for tab in app.tabs] == [
        number + " " + tr(title) for _, number, title, _ in navigation.WORKFLOW_STAGES]
    idea, concept, explore, draft = app.tabs
    assert any(item.key == "idea_title" for item in idea.text_input)
    assert len(app.text_input(key="idea_title").value) == 0
    assert [item.label for item in concept.get("download_button")] == [tr("Download PDF")]
    assert any(item.value == tr("Concept paper") for item in concept.subheader)
    assert not concept.get("button")
    assert not any(item.value == tr("Consistency Check") for item in concept.subheader)
    assert any(item.value == tr("Consistency Check") for item in explore.subheader)
    assert any(item.label == tr("Find Funding Opportunities") for item in explore.button)
    funding_section = next(item for item in explore.expander if item.label == tr("Find Funding Opportunities (optional)"))
    assert funding_section.proto.expanded  # the dedicated stage exposes its research tools immediately
    assert any(item.key == "workflow-" + project.project_id + "-draft" for item in draft.button)
    assert not draft.get("download_button")  # approval is still required
    assert not any(item.key == "idea_title" for panel in (concept, explore, draft) for item in panel.text_input)
    assert len([item for item in app.subheader if item.value == tr("Consistency Check")]) == 1
    assert repo.list_projects() == before


@pytest.mark.parametrize("language", ["en", "fi"])
def test_navigation_reruns_and_language_switch_preserve_project_input_and_research(tmp_path, monkeypatch, language):
    path = tmp_path / "state.sqlite3"
    repo, project = create_saved_concept(path)
    before = repo.list_projects()
    app = open_app(path, monkeypatch)
    app.selectbox(key="open_project_id").select(project.project_id).run()
    fill_fictional_idea(app)
    app.text_area(key="idea_partners").set_value("Fictional partner")
    app.text_input(key="idea_funding_context").set_value("Fictional funding context")
    app.run()
    expected = {key: app.session_state[key] for key in (
        "idea_title", "idea_development_need", "idea_target_groups", "idea_expected_change",
        "idea_geography", "idea_partners", "idea_funding_context")}
    records = retrieve_funding_opportunities()
    with patch("hankeluotsi.funding.retrieve_funding_opportunities", return_value=records) as research:
        app.button(key="FormSubmitter:funding-search-" + project.project_id + "-Find Funding Opportunities").click().run()
        cached = app.session_state["funding_research_result"]
        for stage, index in (("concept", 1), ("explore", 2), ("draft", 3), ("idea", 0), ("draft", 3)):
            choose_stage(app, stage, index)
            app.run()
            app.selectbox(key="ui_language").select(language).run()
            assert app.get("tab_container")[0].proto.tab_container.default_tab_index == index
            assert app.session_state["workflow_stage"] == stage
            selector = "open_project_id" + ("_fi" if language == "fi" else "")
            assert app.selectbox(key=selector).value == project.project_id
            assert {key: app.session_state[key] for key in expected} == expected
            assert app.session_state["funding_research_result"] == cached
        research.assert_called_once_with(retrieve_live=False)
    assert repo.list_projects() == before


def test_prerequisite_guidance_returns_to_idea_without_changing_data(tmp_path, monkeypatch):
    path = tmp_path / "prerequisites.sqlite3"
    app = open_app(path, monkeypatch)
    for stage, index, key in (("concept", 1, "concept-open-idea"),
                              ("explore", 2, "explore-open-idea"), ("draft", 3, "draft-open-idea")):
        choose_stage(app, stage, index)
        assert app.tabs[index].info
        app.button(key=key).click().run()
        assert app.session_state["workflow_stage"] == "idea"
        assert app.get("tab_container")[0].proto.tab_container.default_tab_index == 0
    assert ProjectRepository(path).list_projects() == []


def test_successful_generation_opens_concept_and_next_rerun_keeps_that_stage(tmp_path, monkeypatch):
    app = open_app(tmp_path / "generation.sqlite3", monkeypatch)
    result = SimpleNamespace(data=ConceptPaper.model_validate(concept_data()), model="fictional-local",
        prompt_version="concept_v1", response_time_seconds=1.0)
    with patch("hankeluotsi.llm_client.LLMClient.generate", return_value=result) as model:
        fill_fictional_idea(app)
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()
        selected = app.selectbox(key="open_project_id").value
        assert selected is not None
        assert app.session_state["workflow_stage"] == "concept"
        assert app.get("tab_container")[0].proto.tab_container.default_tab_index == 1
        choose_stage(app, "idea", 0)
        assert app.text_input(key="idea_title").value == "Fictional volunteer digital skills"
        choose_stage(app, "concept", 1)
        app.run()
        assert app.session_state["workflow_stage"] == "concept"
        assert app.selectbox(key="open_project_id").value == selected
        model.assert_called_once()


@pytest.mark.parametrize("language", ["fi", "en"])
@pytest.mark.parametrize("index", range(4))
def test_native_tab_callback_uses_fixed_step_number_not_translated_label(monkeypatch, language, index):
    stage, number, title, subtitle = navigation.WORKFLOW_STAGES[index]
    state = {"workflow_navigation": number + " " + localize(title, language) + "  \n" + localize(subtitle, language)}
    monkeypatch.setattr(navigation.st, "session_state", state)
    navigation._remember_workflow_stage()
    assert state["workflow_stage"] == stage
