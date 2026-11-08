import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from hankeluotsi.repository import ProjectRepository, ProjectState
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def concept_data():
    fixture_path = Path(__file__).parent / "fixtures" / "concept_paper.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def fill_fictional_idea(app):
    app.text_input(key="idea_title").set_value("Fictional volunteer digital skills")
    app.text_area(key="idea_development_need").set_value(
        "Fictional arts volunteers need practice choosing accessible digital tools."
    )
    app.text_area(key="idea_target_groups").set_value("Arts staff and volunteers")
    app.text_area(key="idea_expected_change").set_value(
        "Participants use one suitable digital practice."
    )
    app.text_input(key="idea_geography").set_value("Fictional western Finland")


def legacy_content_operation_id(operation: str, idea: ProjectIdea) -> str:
    payload = idea.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"pr5:{operation}:{digest}"


def test_app_renders_disclaimer_form_and_saved_projects_selector(tmp_path, monkeypatch):
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(tmp_path / "app.sqlite3"))

    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

    assert not app.exception
    assert [element.value for element in app.title] == ["HankeLuotsi AI"]
    assert any("From project idea to structured concept" in item.value for item in app.markdown)
    assert any("Not a funding eligibility assessment" in item.value for item in app.warning)
    assert any(item.label == "Project title" for item in app.text_input)
    assert any(item.label == "Open a saved project" for item in app.selectbox)


def test_app_validates_and_saves_concept_then_rerun_does_not_regenerate(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    result = SimpleNamespace(
        data=ConceptPaper.model_validate(concept_data()),
        model="qwen3.5-4b",
        prompt_version="concept_v1",
        response_time_seconds=1.25,
    )
    mock_generate = Mock(return_value=result)

    with patch("hankeluotsi.llm_client.LLMClient.generate", mock_generate):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        fill_fictional_idea(app)
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()

        assert not app.exception
        assert any("Concept validated and saved" in item.value for item in app.success)
        assert mock_generate.call_count == 1
        assert any("#### Background" in item.value for item in app.markdown)
        mock_generate.assert_called_once()
        assert mock_generate.call_args.args[0] == "concept"
        assert "exactly one objective (O1)" in mock_generate.call_args.args[1]
        assert "Fictional volunteer digital skills" in mock_generate.call_args.args[1]
        assert mock_generate.call_args.kwargs["response_model"] is ConceptPaper
        assert mock_generate.call_args.kwargs["max_attempts"] == 1

        app.run()
        assert mock_generate.call_count == 1

    repository = ProjectRepository(database_path)
    projects = repository.list_projects()
    assert len(projects) == 1
    assert projects[0].state == ProjectState.CONCEPT_READY
    assert projects[0].concept == result.data


def test_app_reopens_saved_concept_from_sqlite(tmp_path, monkeypatch):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    repository = ProjectRepository(database_path)
    idea = {
        "title": "Fictional saved concept",
        "development_need": "Fictional need",
        "target_groups": ["Fictional volunteers"],
        "expected_change": "Fictional change",
        "geography": "Fictional region",
    }
    project = repository.create_project(idea, operation_id="saved-idea")
    repository.save_concept(
        project.project_id,
        ConceptPaper.model_validate(concept_data()),
        operation_id="saved-concept",
    )

    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    app.selectbox(key="open_project_id").select(project.project_id).run()

    assert not app.exception
    assert any("Validated concept paper" in item.value for item in app.subheader)
    assert any("concept_ready" in item.value for item in app.caption)
    displayed_markdown = [item.value for item in app.markdown]
    displayed_text = [item.value for item in app.text]
    for heading in (
        "#### Background",
        "#### Objectives",
        "#### Target groups",
        "#### Activities",
        "#### Expected results",
        "#### Indicators",
        "#### Assumptions",
        "#### Open questions",
    ):
        assert heading in displayed_markdown

    expected_content = concept_data()
    assert expected_content["background_need"] in displayed_text
    assert expected_content["objectives"][0]["description"] in displayed_text
    assert expected_content["target_groups"][0] in displayed_text
    assert expected_content["preliminary_activities"][0]["description"] in displayed_text
    assert expected_content["expected_results"][0]["description"] in displayed_text
    assert expected_content["proposed_indicators"][0]["description"] in displayed_text
    assert expected_content["proposed_indicators"][0]["measurement_method"] in displayed_text
    assert expected_content["assumptions"][0] in displayed_text
    assert expected_content["open_questions"][0] in displayed_text
    assert any('concept-id">O1</span>' in value for value in displayed_markdown)
    assert any('concept-relationship">Linked objectives: O1</span>' in value for value in displayed_markdown)
    assert any('concept-relationship">Linked activities: A1, A2</span>' in value for value in displayed_markdown)
    assert any('concept-relationship">Linked results: R1</span>' in value for value in displayed_markdown)
    assert any(item.label == "Raw ConceptPaper JSON" for item in app.expander)
    assert any(item.label == "Raw project idea JSON" for item in app.expander)


def test_app_shows_validation_error_without_calling_model(tmp_path, monkeypatch):
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(tmp_path / "app.sqlite3"))
    mock_generate = Mock()

    with patch("hankeluotsi.llm_client.LLMClient.generate", mock_generate):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()

    assert not app.exception
    assert any("Please correct the project idea" in item.value for item in app.error)
    assert mock_generate.call_count == 0
    assert ProjectRepository(tmp_path / "app.sqlite3").list_projects() == []


def test_app_shows_model_failure_and_preserves_created_idea(tmp_path, monkeypatch):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))

    with patch(
        "hankeluotsi.llm_client.LLMClient.generate",
        side_effect=TimeoutError("local model request timed out"),
    ) as mock_generate:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        fill_fictional_idea(app)
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()

    assert not app.exception
    assert mock_generate.call_count == 1
    assert any("Concept generation or saving failed" in item.value for item in app.error)
    projects = ProjectRepository(database_path).list_projects()
    assert len(projects) == 1
    assert projects[0].state == ProjectState.CREATED
    assert projects[0].concept is None


def test_new_submission_does_not_reuse_legacy_content_key_for_concept(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    submitted_idea = ProjectIdea.model_validate(
        {
            "title": "Fictional volunteer digital skills",
            "development_need": "Fictional arts volunteers need practice choosing accessible digital tools.",
            "target_groups": ["Arts staff and volunteers"],
            "expected_change": "Participants use one suitable digital practice.",
            "geography": "Fictional western Finland",
            "partners": None,
            "funding_context": None,
        }
    )
    repository = ProjectRepository(database_path)
    prior_submission = repository.create_project(
        submitted_idea,
        operation_id=legacy_content_operation_id("create", submitted_idea),
    )
    other_idea = submitted_idea.model_copy(update={"title": "Other fictional project"})
    prior_concept_project = repository.create_project(other_idea, operation_id="prior-other-project")
    repository.save_concept(
        prior_concept_project.project_id,
        ConceptPaper.model_validate(concept_data()),
        operation_id=legacy_content_operation_id("concept", submitted_idea),
    )
    mock_generate = Mock(
        return_value=SimpleNamespace(
            data=ConceptPaper.model_validate(concept_data()),
            model="qwen3.5-4b",
            prompt_version="concept_v1",
            response_time_seconds=1.0,
        )
    )

    with patch("hankeluotsi.llm_client.LLMClient.generate", mock_generate):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        fill_fictional_idea(app)
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()

    assert not app.exception
    assert not any("operation_id was already used" in item.value for item in app.error)
    assert any("Concept validated and saved" in item.value for item in app.success)
    assert mock_generate.call_count == 1
    projects = repository.list_projects()
    assert len(projects) == 3
    assert repository.load_project(prior_submission.project_id).state == ProjectState.CREATED
    assert sum(project.state == ProjectState.CONCEPT_READY for project in projects) == 2


def test_modified_form_submission_gets_new_project_and_generation(tmp_path, monkeypatch):
    database_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(database_path))
    result = SimpleNamespace(
        data=ConceptPaper.model_validate(concept_data()),
        model="qwen3.5-4b",
        prompt_version="concept_v1",
        response_time_seconds=1.0,
    )
    mock_generate = Mock(return_value=result)

    with patch("hankeluotsi.llm_client.LLMClient.generate", mock_generate):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        fill_fictional_idea(app)
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()
        app.text_input(key="idea_title").set_value("Another fictional digital skills project")
        app.button(key="FormSubmitter:project_idea_form-Generate concept").click().run()

    assert not app.exception
    assert mock_generate.call_count == 2
    projects = ProjectRepository(database_path).list_projects()
    assert len(projects) == 2
    assert len({project.project_id for project in projects}) == 2
    assert all(project.state == ProjectState.CONCEPT_READY for project in projects)