"""Cloud UI consent, rerun and persistence checks with no external API access."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
import pytest
from streamlit.testing.v1 import AppTest

from hankeluotsi.i18n import localize
from hankeluotsi.mistral_client import CloudError
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper
from test_app import APP_PATH, concept_data, create_saved_concept, fill_fictional_idea


@pytest.fixture(autouse=True)
def no_live_cloud(monkeypatch):
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=AssertionError("No live cloud calls")))
    monkeypatch.setenv("MISTRAL_API_KEY", "fictional-ui-key")
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-cloud-model")


def submit(app):
    return next(b for b in app.button if "FormSubmitter:project_idea_form-" in str(b.key))


def test_missing_key_disables_generation_and_does_not_create_project(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    monkeypatch.delenv("MISTRAL_API_KEY")
    with patch("hankeluotsi.mistral_client.MistralClient.generate") as cloud:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        assert app.selectbox(key="generation_provider").value == "local"
        app.selectbox(key="generation_provider").select("mistral").run()
        assert not app.exception and submit(app).disabled
        assert app.checkbox(key="cloud_consent").disabled
        assert any("MISTRAL_API_KEY" in x.value for x in app.info)
        app.run()
        cloud.assert_not_called()
    assert ProjectRepository(path).list_projects() == []


@pytest.mark.parametrize("language", ["fi", "en"])
def test_explicit_consent_generation_language_reruns_and_saved_project_preservation(tmp_path, monkeypatch, language):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository, saved = create_saved_concept(path)
    original = repository.load_project(saved.project_id)
    result = SimpleNamespace(data=ConceptPaper.model_validate(concept_data()), model="fictional-cloud-model",
        prompt_version="concept_v1", response_time_seconds=0.5)
    with patch("hankeluotsi.mistral_client.MistralClient.generate", return_value=result) as cloud, \
            patch("hankeluotsi.llm_client.LLMClient.generate") as local:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="ui_language").select(language).run()
        app.selectbox(key="generation_provider").select("mistral").run()
        assert submit(app).disabled
        assert any(localize("Mistral sends this new idea to an external cloud service and may incur charges. Use fictional data only. Saved projects are not sent.", language) in x.value for x in app.warning)
        app.checkbox(key="cloud_consent").check().run()
        assert not submit(app).disabled
        cloud.assert_not_called()
        fill_fictional_idea(app)
        submit(app).click().run()
        assert not app.exception
        cloud.assert_called_once()
        assert ("Finnish" if language == "fi" else "English") in cloud.call_args.args[1]
        assert cloud.call_args.kwargs["max_attempts"] == 1
        app.run()
        app.selectbox(key="ui_language").select("en" if language == "fi" else "fi").run()
        assert app.selectbox(key="generation_provider").value == "mistral"
        cloud.assert_called_once()
        local.assert_not_called()
    assert repository.load_project(saved.project_id) == original
    assert len(repository.list_projects()) == 2


def test_switching_provider_revokes_consent_and_preserves_records(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository, saved = create_saved_concept(path)
    original = repository.load_project(saved.project_id)
    with patch("hankeluotsi.mistral_client.MistralClient.generate") as cloud:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="generation_provider").select("mistral").run()
        app.checkbox(key="cloud_consent").check().run()
        app.selectbox(key="generation_provider").select("local").run()
        app.selectbox(key="generation_provider").select("mistral").run()
        assert not app.exception and not app.checkbox(key="cloud_consent").value
        assert submit(app).disabled
        cloud.assert_not_called()
    assert repository.load_project(saved.project_id) == original


def test_cloud_failure_preserves_previous_concept_and_never_falls_back(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository, saved = create_saved_concept(path)
    original = repository.load_project(saved.project_id)
    with patch("hankeluotsi.mistral_client.MistralClient.generate", side_effect=CloudError("authentication")) as cloud, \
            patch("hankeluotsi.llm_client.LLMClient.generate") as local:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.selectbox(key="generation_provider").select("mistral").run()
        app.checkbox(key="cloud_consent").check().run()
        fill_fictional_idea(app)
        submit(app).click().run()
        assert not app.exception and any("authentication failed" in x.value for x in app.error)
        app.run()
        cloud.assert_called_once()
        local.assert_not_called()
    assert repository.load_project(saved.project_id) == original
    assert sum(p.concept is not None for p in repository.list_projects()) == 1

