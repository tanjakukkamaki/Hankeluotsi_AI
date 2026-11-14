# Draft & Review startup recovery — 13 November 2026

The reported `ImportError: cannot import name 'StaleProjectError'` occurred with the overnight workflow files and an already-running Streamlit Python process. The current UI module is `hankeluotsi/draft_ui.py`, which imports `draft_workflow.py`.

## Cause and smallest correction

The exception is already defined in `repository.py`. Its semantics are implemented by the repository, not by methods on the exception: `load_snapshot` reads content and fingerprint from the same row; `_mutate` and `approve_project` compare `expected_source` inside their SQLite transaction and raise `StaleProjectError` before a stale write or approval. Approval locking, rollback and operation-id replay protection remain in place.

The startup failure was a stale imported repository module in the old server process. A fresh interpreter imports the complete current dependency chain successfully, with the same exception class in repository and workflow. An isolated regression reproduces the reported missing-name failure when the cached repository exposes the old API; a separate fresh process recovers. The old process memory was not dumped: this diagnosis rests on the source/import evidence, controlled reproduction and successful cold-server/browser verification.

The operational fix is a **full Streamlit process restart** after these module changes. Browser refresh and an app rerun do not reliably replace imported Python modules. No placeholder class, exception alias, import fallback or `importlib.reload` workaround was added. No production source code, schema or saved project needed changing for this repair.

From the project folder, stop the existing server with **Ctrl+C in its original PowerShell terminal**, then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
```

Open <http://localhost:8501>. Use the same configured PowerShell if provider environment variables are needed; another terminal or a background process does not automatically inherit variables set in that existing terminal. Do not paste credentials into commands, screenshots or bug reports. A port-in-use message means the previous server is still running; stop that server rather than starting another copy.

For a separate fictional demonstration database, set a new temporary path in the demonstration terminal **before** starting Streamlit:

```powershell
$env:HANKELUOTSI_DB_PATH = Join-Path $env:TEMP ("hankeluotsi-demo-" + [guid]::NewGuid().ToString("N") + ".sqlite3")
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502
```

That instance opens at <http://localhost:8502>; do not reuse an existing project database for a demonstration.

## Navigation import error: check the actual hostname route

The later `cannot import name 'render_workflow_navigation' from 'hankeluotsi.presentation'` had two integration/runtime causes. The helper had been added to presentation while an older server retained its previous interface; a second newer server had been started on IPv4 only. The older project process still listened on the IPv6 wildcard, so the browser's `localhost` connection reached a different process than the prior `127.0.0.1` smoke test. A healthy IPv4 page did not prove that the hostname worked.

The full navigation implementation now lives in `hankeluotsi/workflow_navigation.py`, and app.py imports it directly there. Presentation retains branding/display helpers. No alias, placeholder, import fallback or runtime reload was added. The actual app imports are checked in a fresh interpreter, and the cached-presentation UI regression explicitly lacks the navigation helper.

Both existing project servers were verified against the project virtual environment and Streamlit command, stopped, and replaced by one cold server bound to `127.0.0.1:8501`. Only project servers were stopped; no database records or credentials were changed. To inspect listeners without stopping anything:

```powershell
netstat -ano | Select-String ':8501\s' | Select-String 'LISTENING'
```

Use one project server on this port. Stop old project instances in their original terminals before starting a new one; do not terminate unrelated Python processes. Binding `localhost` in this installed runtime did not expose a direct IPv6 listener in the isolated test. The verified setup therefore uses explicit IPv4 loopback. Edge successfully opens the normal hostname by falling back to it; direct `[::1]:8501` is intentionally not served. No wildcard binding, browser sandbox change or CORS/security relaxation was used.

| Address | Before repair, real browser | After repair, real browser |
| --- | --- | --- |
| `http://localhost:8501` | Missing navigation import | Title/footer rendered, zero exceptions |
| `http://127.0.0.1:8501` | Rendered in a different newer process | Title/footer rendered, zero exceptions |
| `http://[::1]:8501` | Missing navigation import in old process | No listener; old process removed |

The earlier port-8501 smoke evidence in this guide and the development log covered IPv4 only. It must not be read as a successful check of the hostname/IPv6 route. This follow-up explicitly checked the browser URL `localhost` before and after repair. Full follow-up results and session limits are in [workflow navigation](workflow_navigation.md).

## Verification and limits

- Fresh-process regression imports all new workflow dependencies, verifies exception identity and confirms imports alone do not create a database. A separate child emulates the old cached API and verifies cold-process recovery.
- Focused startup/repository/workflow/UI tests: **42 passed in 10.19 s**. Existing tests exercise stale-save rejection, atomic source snapshots, replay/concurrency protection, approval locking and rollback.
- Full offline suite: **634 passed, 2 skipped in 29.60 s**, using `python -m pytest -q -p no:cacheprovider` from the project virtual environment, `HANKELUOTSI_LIVE_FUNDING=0`, a temporary default database and disabled bytecode writes. Skips are explicit opt-in public-source checks. `git diff --check` passed.
- Finnish and English AppTest flows use synthetic fixtures, mocked providers and temporary SQLite databases: saved concept → validated draft → validated evidence-linked review → explicit human approval → approved Markdown download. Reruns do not repeat generation; approved records remain locked. AppTest is synchronous, not an in-flight click simulation.
- A separate headless Edge profile rendered both a cold Streamlit instance with a temporary database and the recovered existing server at port 8501: application title/footer present, **zero Streamlit exceptions**. No project actions were clicked and no model or cloud requests were made. The restricted runner initially prevented Edge subprocess startup; the same isolated check succeeded outside that restriction without disabling browser sandboxing. Test-server and test-browser processes were then closed; the owner's port-8501 server remained running.

This startup repair does not establish model quality or repeated real-model reliability. The earlier single successful local draft/review observations remain documented in [Draft & Review](draft_review.md); no new live Qwen generation was needed here. Live Mistral testing, repeated final-contract evaluations, independent professional assessment, slow-call UX and accessibility review remain incomplete. Private browser/runtime evidence stays in ignored local storage. No paid calls, saved-project edits, commits or pushes were performed.
