import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import hankeluotsi
import hankeluotsi.presentation as presentation
import hankeluotsi.repository as repository_module
from hankeluotsi.presentation import ASSET_DIRECTORY, PROJECT_ROOT
from hankeluotsi.repository import ProjectRepository


def test_workspace_path_is_stable_from_another_launch_directory(tmp_path, monkeypatch):
    requested_paths = []

    def isolated_repository(database_path):
        requested_paths.append(Path(database_path))
        return ProjectRepository(tmp_path / "isolated.sqlite3")

    monkeypatch.setattr(repository_module, "ProjectRepository", isolated_repository)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HANKELUOTSI_DB_PATH", raising=False)
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    assert not app.exception
    assert requested_paths == [PROJECT_ROOT / "hankeluotsi.sqlite3"]
    selected = tmp_path / "selected.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(selected))
    app.run()
    assert not app.exception
    assert requested_paths[-1] == selected


def test_app_starts_and_reopens_saved_idea_with_older_presentation_module_cached(tmp_path, monkeypatch):
    """A Streamlit rerun may retain the module loaded before the path helper existed."""
    cached_presentation = types.ModuleType("hankeluotsi.presentation")
    cached_presentation.__file__ = presentation.__file__
    for name in (
        "ASSET_DIRECTORY", "PROJECT_ROOT", "anchor", "apply_styles",
        "render_brand", "render_intro", "status_badge",
    ):
        setattr(cached_presentation, name, getattr(presentation, name))
    monkeypatch.setitem(sys.modules, "hankeluotsi.presentation", cached_presentation)
    monkeypatch.setattr(hankeluotsi, "presentation", cached_presentation)
    path = tmp_path / "startup.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    project = repository.create_project(
        dict(title="Fictional startup recovery", development_need="Fictional need",
             target_groups=["Fictional volunteers"], expected_change="Fictional change",
             geography="Fictional Finland"),
        operation_id="startup-recovery",
    )
    before = repository.list_projects()
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    assert not app.exception
    assert [item.value for item in app.title] == ["HankeLuotsi AI"]
    app.selectbox(key="open_project_id").select(project.project_id).run()
    assert not app.exception
    assert app.selectbox(key="open_project_id").value == project.project_id
    assert any(project.idea.title in item.value for item in app.text)
    assert repository.list_projects() == before


@pytest.mark.parametrize("name", ["hankeluotsi-mark.svg", "hankeluotsi-logo.svg"])
def test_original_local_logo_is_accessible_and_has_no_external_or_active_content(name):
    root = ET.fromstring((ASSET_DIRECTORY / name).read_text(encoding="utf-8"))
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    assert root.attrib["role"] == "img"
    assert root.find("svg:title", namespace).text
    assert root.find("svg:desc", namespace).text
    ids = {element.attrib["id"] for element in root if "id" in element.attrib}
    assert set(root.attrib["aria-labelledby"].split()).issubset(ids)
    for element in root.iter():
        assert element.tag.split("}")[-1] not in {"script", "foreignObject", "image", "animate"}
        for attribute, value in element.attrib.items():
            assert not attribute.lower().startswith("on")
            assert not value.lower().startswith(("http:", "https:", "javascript:"))


def test_duplicate_saved_project_titles_remain_independently_selectable(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    repository = ProjectRepository(path)
    idea = dict(title="Fictional identical title", development_need="Fictional need",
                target_groups=["Fictional volunteers"], expected_change="Fictional change", geography="Fictional Finland")
    first = repository.create_project(idea, operation_id="first")
    second = repository.create_project(idea, operation_id="second")
    before = repository.list_projects()
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    selector = app.selectbox(key="open_project_id")
    assert len(selector.options) == len(set(selector.options))
    for project in (first, second):
        app.selectbox(key="open_project_id").select(project.project_id).run()
        assert not app.exception
        assert app.selectbox(key="open_project_id").value == project.project_id
    assert repository.list_projects() == before


def test_ui_assets_load_when_app_is_started_outside_project_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(tmp_path / "isolated.sqlite3"))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    assert not app.exception
    assert [item.value for item in app.title] == ["HankeLuotsi AI"]
    assert any("data:image/svg+xml;base64," in item.value and "alt=" in item.value for item in app.markdown)


def test_workflow_navigation_points_to_available_content(tmp_path, monkeypatch):
    path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("HANKELUOTSI_DB_PATH", str(path))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=10).run()
    navigation = next(item.value for item in app.markdown if 'aria-label="Planning workflow"' in item.value)
    assert navigation.count('href="#project-workspace"') == 3
    repository = ProjectRepository(path)
    project = repository.create_project(dict(title="Fictional navigation", development_need="Fictional need",
        target_groups=["Fictional volunteers"], expected_change="Fictional change", geography="Fictional Finland"), operation_id="navigation")
    app.run()
    app.selectbox(key="open_project_id").select(project.project_id).run()
    navigation = next(item.value for item in app.markdown if 'aria-label="Planning workflow"' in item.value)
    assert 'href="#concept-paper"' in navigation
    assert 'href="#funding-opportunities"' in navigation
