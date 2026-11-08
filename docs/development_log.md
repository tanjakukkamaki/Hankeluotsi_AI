# Development log

## 2026-11-07 — PR0 repository shell

- **Task:** Initial repository hygiene, setup documentation, and Streamlit shell.
- **Initial decisions:** Python 3.11+; Streamlit UI; Pydantic v2 structured outputs; SQLite persistence; LM Studio on localhost as the initial local inference option; fictional data only.
- **Scope boundary:** This shell does not generate or persist project content. No PR1 schema work or later workflow stages are included.
- **Tools:** GitHub Copilot; local Python environment. No live model or cloud service used.
- **Validation:** Pending focused smoke test and repository checks.
- **Validation:** `python -m unittest discover -s tests -v` passed (1 test); `python -m py_compile app.py tests/test_app_shell.py` passed; `git check-ignore` confirmed `.env`, `.env.local`, `test.db`, and `test.sqlite3` are ignored while `.env.example` is not.
- **Test limitation:** `pytest` is not installed in the current environment, so `python -m pytest -q` was not run. No packages were installed during this task.
- **Owner actual hours:** Not recorded by the agent; owner should enter their actual time.
- **Next action:** Owner reviews the PR0 files and test results before approving any commit.

## 2026-11-08 — PR1 minimal schemas

- **Task:** Add versioned project-idea and concept-paper schemas, fictional fixtures, and offline validation tests.
- **Schema decisions:** Top-level inputs accept schema version `1`; required strings are stripped and must remain nonblank; required collections must be nonempty; extra fields are rejected. Objectives, activities, results, and indicators use `O<n>`, `A<n>`, `R<n>`, and `I<n>` IDs with explicit typed reference lists.
- **Reference boundary:** PR1 validates reference field shapes and ID formats. Duplicate-ID, unresolved-reference, and semantic consistency findings remain for the PR6 deterministic checker.
- **Fixtures:** Synthetic community-arts digital-skills idea and concept only; no real organizations or programme rules.
- **Tools:** GitHub Copilot; local `.venv` Python environment. No live model or external service used.
- **Validation:** Pending `.venv` test run.
- **Validation:** `.\.venv\Scripts\python.exe -m pytest -q` passed (56 tests, offline); the suite includes the existing PR0 AppTest shell smoke test.
- **Limitations:** No `ApplicationDraft`, generation, persistence, consistency checker, or UI changes are included.
- **Owner actual hours:** Not recorded by the agent; owner should enter actual time.
- **Next action:** Owner reviews PR1 schemas, fixtures, and test results before approval.
