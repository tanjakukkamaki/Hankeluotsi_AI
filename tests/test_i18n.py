import ast
import json
from pathlib import Path
from string import Formatter
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table
from streamlit.testing.v1 import AppTest

from hankeluotsi.i18n import TRANSLATIONS, localize, translate
from hankeluotsi.funding import retrieve_funding_opportunities
from hankeluotsi.funding_calls import FundingCall, LiveSearchResult, parse_call_date
from hankeluotsi.pdf_exporter import DISCLAIMER, generate_concept_pdf
from hankeluotsi.repository import ProjectRepository
from hankeluotsi.schemas import ConceptPaper


ROOT = Path(__file__).resolve().parents[1]


def concept(language):
    name = "concept_paper_fi.json" if language == "fi" else "concept_paper.json"
    return ConceptPaper.model_validate_json((ROOT / "tests/fixtures" / name).read_text(encoding="utf-8"))


def app_for(path, monkeypatch):
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()


def widget_key(app, base):
    return base + ("_fi" if app.selectbox(key="ui_language").value == "fi" else "")


def save(repository, language):
    project = repository.create_project(dict(title="High" if language == "en" else "Kuvitteellinen Ääni å",
        development_need="Fictional need" if language == "en" else "Kuvitteellinen yhteisö tarvitsee tukea.",
        target_groups=["Fictional volunteers"], expected_change="Fictional skills improve.",
        geography="Fictional Finland"), operation_id="idea-" + language)
    return repository.save_concept(project.project_id, concept(language), operation_id="concept-" + language)


def test_dictionary_placeholders_are_consistent_and_preserve_values():
    def fields(value):
        return {name for _, name, _, _ in Formatter().parse(value) if name}
    for english, finnish in TRANSLATIONS.items():
        assert finnish.strip()
        assert fields(english) == fields(finnish), english
    assert localize("Programme: High", "fi") == "Ohjelma: High"
    assert localize("Official identifier: O1", "fi") == "Virallinen tunniste: O1"
    assert localize("Unknown custom diagnostic", "fi") == "Unknown custom diagnostic"


def test_known_ui_literals_have_finnish_translations():
    for filename in ("app.py", "hankeluotsi/presentation.py"):
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("ui", "_ui") and node.args:
                value = node.args[0]
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
                    assert localize(value.value, "fi") != value.value, value.value


@pytest.mark.parametrize("language", ["en", "fi"])
def test_both_interfaces_render_without_changing_machine_keys(tmp_path, monkeypatch, language):
    app = app_for(tmp_path / "app.sqlite3", monkeypatch)
    app.selectbox(key="ui_language").select(language).run()
    assert not app.exception
    assert app.text_input(key="idea_title").label == translate("Project title", language)
    assert app.selectbox(key=widget_key(app, "open_project_id")).label == translate("Open a saved project", language)
    assert any(item.label == translate("Generate concept", language) for item in app.button)
    assert any(translate("Ideas with direction.", language) in item.value for item in app.markdown)
    app.run()
    assert app.selectbox(key="ui_language").value == language


def test_language_switch_keeps_both_saved_languages_exactly_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "saved.sqlite3"
    repository = ProjectRepository(path)
    english, finnish = save(repository, "en"), save(repository, "fi")
    before = repository.list_projects()
    with patch("hankeluotsi.llm_client.LLMClient.generate") as model, patch("hankeluotsi.live_funding.search_live_funding_calls") as search:
        app = app_for(path, monkeypatch)
        for project in (english, finnish):
            app.selectbox(key=widget_key(app, "open_project_id")).select(project.project_id).run()
            for language in ("fi", "en", "fi"):
                app.selectbox(key="ui_language").select(language).run()
                assert not app.exception
                assert app.selectbox(key=widget_key(app, "open_project_id")).value == project.project_id
                assert app.selectbox(key=widget_key(app, "open_project_id")).options[0] == translate("Select a saved project", language)
                assert any(translate("concept ready", language) in value for value in app.selectbox(key=widget_key(app, "open_project_id")).options)
                assert any(item.value == project.idea.title for item in app.text)
                assert any(item.value == project.concept.background_need for item in app.text)
                assert any(item.value == translate("Consistency Check", language) for item in app.subheader)
        model.assert_not_called()
        search.assert_not_called()
    assert repository.list_projects() == before


@pytest.mark.parametrize("language", ["en", "fi"])
def test_new_generation_requests_selected_language_and_validates_same_schema(tmp_path, monkeypatch, language):
    path = tmp_path / "generation.sqlite3"
    result = SimpleNamespace(data=concept(language), model="qwen3.5-4b", prompt_version="concept_v1", response_time_seconds=1.0)
    with patch("hankeluotsi.llm_client.LLMClient.generate", return_value=result) as model:
        app = app_for(path, monkeypatch)
        app.selectbox(key="ui_language").select(language).run()
        app.text_input(key="idea_title").set_value("Fictional test" if language == "en" else "Kuvitteellinen Ääni")
        app.text_area(key="idea_development_need").set_value("Fictional arts training")
        app.text_area(key="idea_target_groups").set_value("Fictional volunteers")
        app.text_area(key="idea_expected_change").set_value("Fictional skills improve")
        app.text_input(key="idea_geography").set_value("Fictional Finland")
        next(item for item in app.button if item.label == translate("Generate concept", language)).click().run()
        assert not app.exception
        model.assert_called_once()
        assert "text fields in " + ("Finnish" if language == "fi" else "English") in model.call_args.args[1]
        assert "Do not translate keys or IDs" in model.call_args.args[1]
        assert model.call_args.kwargs["response_model"] is ConceptPaper
        assert ProjectRepository(path).list_projects()[0].concept == result.data
        assert any(("Konsepti validoitu" if language == "fi" else "Concept validated") in item.value for item in app.success)
        app.selectbox(key="ui_language").select("en" if language == "fi" else "fi").run()
        assert model.call_count == 1


def test_finnish_generation_with_translated_json_keys_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "invalid.sqlite3"
    result = SimpleNamespace(data={"tausta": "Kuvitteellinen tarve"})
    with patch("hankeluotsi.llm_client.LLMClient.generate", return_value=result):
        app = app_for(path, monkeypatch)
        app.selectbox(key="ui_language").select("fi").run()
        app.text_input(key="idea_title").set_value("Kuvitteellinen hanke")
        app.text_area(key="idea_development_need").set_value("Kuvitteellinen tarve")
        app.text_area(key="idea_target_groups").set_value("Kuvitteelliset osallistujat")
        app.text_area(key="idea_expected_change").set_value("Kuvitteellinen muutos")
        app.text_input(key="idea_geography").set_value("Kuvitteellinen Suomi")
        next(item for item in app.button if item.label == "Luo hankekonsepti").click().run()
    assert not app.exception
    assert any("ei läpäissyt validointia" in item.value for item in app.error)
    assert ProjectRepository(path).list_projects()[0].concept is None


@pytest.mark.parametrize("language,content_language,long_document", [
    ("en", "en", False), ("fi", "en", False), ("en", "fi", False), ("fi", "fi", False), ("fi", "fi", True),
])
def test_pdf_localizes_only_labels_and_keeps_original_content(monkeypatch, language, content_language, long_document):
    content = concept(content_language)
    if long_document:
        content = content.model_copy(update={"open_questions": [f"Kuvitteellinen kysymys {index}: Miten yhteisöt jatkavat saavutettavaa toimintaa?" for index in range(80)]})
    before = content.model_dump_json()
    rendered, footers = [], []
    def record(document, flowable):
        if isinstance(flowable, Paragraph): rendered.append(flowable.getPlainText())
        elif isinstance(flowable, Table):
            for row in flowable._cellvalues:
                for cell in row:
                    for item in cell if isinstance(cell, (list, tuple)) else [cell]: record(document, item)
    original = Canvas.drawRightString
    def footer(canvas, x, y, text, *args, **kwargs):
        footers.append(text)
        return original(canvas, x, y, text, *args, **kwargs)
    monkeypatch.setattr(SimpleDocTemplate, "afterFlowable", record)
    monkeypatch.setattr(Canvas, "drawRightString", footer)
    pdf = generate_concept_pdf("Fictional Ääni å", content, language=language)
    assert pdf.startswith(b"%PDF-") and b"/ToUnicode" in pdf
    assert translate("Background", language) in rendered
    assert translate("Measurement method", language) in rendered
    assert translate(DISCLAIMER, language) in rendered
    assert content.background_need in rendered
    assert content.proposed_indicators[0].measurement_method in rendered
    assert footers == [translate("Page {number}", language, number=index) for index in range(1, len(footers) + 1)]
    if long_document:
        assert len(footers) >= 2
    assert content.model_dump_json() == before


def test_system_messages_translate_without_changing_codes_or_ids():
    result = localize("Activity A1 refers to objective O9, which is not defined in this concept.", "fi", system_values=True)
    assert "A1" in result and "O9" in result and "ei ole määritelty" in result
    assert "Toimenpide" in result
    failure = "EU Portal page 1 unavailable (network, TLS, HTTP or protocol error); earlier verified results, if any, are retained. Use the official Portal link to check other calls."
    assert "protokollavirhe" in localize(failure, "fi", system_values=True)
    topics = "Thematic overlap in title/objectives: culture & creative work, skills & learning."
    assert "kulttuuri ja luovat alat, osaaminen ja oppiminen" in localize(topics, "fi", system_values=True)


def test_finnish_empty_form_gives_localized_field_errors_without_generation(tmp_path, monkeypatch):
    with patch("hankeluotsi.llm_client.LLMClient.generate") as model:
        app = app_for(tmp_path / "empty.sqlite3", monkeypatch)
        app.selectbox(key="ui_language").select("fi").run()
        next(item for item in app.button if item.label == "Luo hankekonsepti").click().run()
        assert any("Hankkeen nimi: Tarkista kentän arvo." in item.value for item in app.error)
        model.assert_not_called()


def test_switching_cached_funding_localizes_labels_without_fetching_or_changing_facts(tmp_path, monkeypatch):
    path = tmp_path / "funding.sqlite3"
    repository = ProjectRepository(path)
    project = save(repository, "en")
    now = datetime.now(timezone.utc)
    call = FundingCall(source="Interreg Aurora", programme="Official programme name", identifier="FICTIONAL-1",
        title="Official English arts and skills title", objectives="Fictional cultural learning and skills for local community participants.",
        opening=parse_call_date((now - timedelta(days=3)).isoformat()),
        deadline=parse_call_date((now + timedelta(days=8)).isoformat()), official_status="open",
        retrieved_at=now, source_url="https://www.interregaurora.eu/projects/calls-for-applications-2/",
        evidence_url="https://www.interregaurora.eu/wp-content/uploads/Timetable-of-the-planned-calls-for-proposals-fictional.csv")
    original_call = call.model_dump_json()
    with patch("hankeluotsi.live_funding.search_live_funding_calls", return_value=LiveSearchResult(calls=(call,))) as search, patch("hankeluotsi.funding.retrieve_funding_opportunities", wraps=retrieve_funding_opportunities) as guides:
        app = app_for(path, monkeypatch)
        app.selectbox(key="open_project_id").select(project.project_id).run()
        app.button(key=f"live-funding-search-{project.project_id}").click().run()
        next(item for item in app.button if item.label == "Find Funding Opportunities").click().run()
        app.multiselect(key=f"live-status-{project.project_id}").set_value(["open"]).run()
        selected = app.selectbox(key=f"ranked-live-call-selection-{project.project_id}").value
        for language in ("fi", "en", "fi"):
            app.selectbox(key="ui_language").select(language).run()
            assert not app.exception
            assert app.multiselect(key=widget_key(app, f"live-status-{project.project_id}")).value == ["open"]
            assert app.selectbox(key=widget_key(app, f"ranked-live-call-selection-{project.project_id}")).value == selected
            assert any(item.value == call.title for item in app.text)
            assert any(item.value == call.objectives for item in app.text)
            assert any(translate("Official identifier: {id}", language, id=call.identifier) == item.value for item in app.text)
        search.assert_called_once_with()
        guides.assert_called_once_with(retrieve_live=False)
    assert call.model_dump_json() == original_call
    assert repository.load_project(project.project_id) == project


def test_language_switch_preserves_approved_record_and_approval_timestamp(tmp_path, monkeypatch):
    class FictionalStage(BaseModel):
        text: str
    path = tmp_path / "approved.sqlite3"
    repository = ProjectRepository(path)
    project = save(repository, "fi")
    repository.save_draft(project.project_id, FictionalStage(text="Fictional draft"), model_type=FictionalStage, operation_id="draft")
    repository.save_review(project.project_id, FictionalStage(text="Fictional review"), model_type=FictionalStage, deterministic_findings=[], operation_id="review")
    before = repository.approve_project(project.project_id, operation_id="approve")
    app = app_for(path, monkeypatch)
    app.selectbox(key="open_project_id").select(project.project_id).run()
    for language in ("fi", "en", "fi"):
        app.selectbox(key="ui_language").select(language).run()
        assert not app.exception
        assert repository.load_project(project.project_id) == before
