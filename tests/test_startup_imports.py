"""Cold-process imports are the deployment contract; browser refresh is not a cold start."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def child(code, tmp_path):
    environment = os.environ.copy()
    environment["HANKELUOTSI_DB_PATH"] = str(tmp_path / "fictional.sqlite3")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=environment,
        capture_output=True, text=True, timeout=25)


def test_fresh_process_imports_all_new_stage_dependencies_and_exception_identity(tmp_path):
    result = child('''
import importlib
for module in ("repository", "draft_schemas", "draft_checks", "review_evidence", "draft_workflow",
               "draft_exporter", "draft_ui", "mistral_client", "i18n", "presentation", "workflow_navigation"):
    importlib.import_module("hankeluotsi." + module)
from hankeluotsi import repository, draft_workflow
assert issubclass(repository.StaleProjectError, repository.RepositoryError)
assert draft_workflow.StaleProjectError is repository.StaleProjectError
assert callable(repository.ProjectRepository.load_snapshot)
assert callable(repository.ProjectRepository.operation_completed)
print("cold-imports-ok")
''', tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cold-imports-ok"
    assert not (tmp_path / "fictional.sqlite3").exists()  # importing must not open/create the database


def test_every_application_import_resolves_without_navigation_in_presentation(tmp_path):
    result = child('''
import ast
import importlib
from pathlib import Path
from hankeluotsi import presentation
from hankeluotsi.workflow_navigation import render_workflow_navigation
assert not hasattr(presentation, "render_workflow_navigation")
assert render_workflow_navigation.__module__ == "hankeluotsi.workflow_navigation"
tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("hankeluotsi."):
        module = importlib.import_module(node.module)
        for item in node.names:
            assert hasattr(module, item.name), (node.module, item.name)
            if item.name == "render_workflow_navigation":
                assert node.module == "hankeluotsi.workflow_navigation"
print("application-import-contract-ok")
''', tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "application-import-contract-ok"
    assert not (tmp_path / "fictional.sqlite3").exists()


def test_cached_old_repository_api_reproduces_error_but_fresh_process_recovers(tmp_path):
    # Deliberately emulate the old module already in sys.modules in an isolated child only.
    # Do not reload/patch production modules: exception identities elsewhere could diverge.
    stale = child('''
import sys
from hankeluotsi import repository
del repository.StaleProjectError
try:
    import hankeluotsi.draft_workflow
except ImportError as error:
    assert "StaleProjectError" in str(error)
    print("stale-cache-reproduced")
else:
    raise AssertionError("Unexpected placeholder or import fallback concealed the missing contract")
''', tmp_path)
    assert stale.returncode == 0, stale.stderr
    assert stale.stdout.strip() == "stale-cache-reproduced"
    fresh = child('''
from hankeluotsi import repository, draft_workflow
assert draft_workflow.StaleProjectError is repository.StaleProjectError
print("fresh-process-recovers")
''', tmp_path)
    assert fresh.returncode == 0, fresh.stderr
    assert fresh.stdout.strip() == "fresh-process-recovers"
