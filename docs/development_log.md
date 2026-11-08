- **Offline tests:** Focused benchmark/client suite passed (18 tests after the malformed-JSON edge-case fix). Full suite: `python -m pytest -q` passed (74 tests, 1.53 s). The benchmark framework was not run live for all stages, and no 30-attempt benchmark was started.
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

## 2026-11-08 — PR2 local LM Studio client and prompt contract

- **Task:** Implement the local LM Studio adapter, configuration defaults, versioned prompts, and offline mocked tests for PR2 only.
- **Model and endpoint:** Local LM Studio server at `http://127.0.0.1:1234/v1`; configured default model `qwen3.5-4b` with stage mapping for `concept`, `draft`, and `review`.
- **Compatibility fix:** LM Studio 0.4.23 expects `response_format.type` to be `json_schema` for structured output. The earlier `json_object` format was rejected by the local server with the error `"response_format.type" must be 'json_schema' or 'text'`. The PR2 client now emits a JSON schema payload when a Pydantic model is provided, and the regression test locks this behavior.
- **Prompt contract:** Prompt templates are versioned (`concept_v1`, `draft_v1`, `review_v1`) and included in the generated metadata alongside the selected model and provider context.
- **Offline validation:** `.\.venv\Scripts\python.exe -m pytest -q` passed with 64 tests in 1.50s.
- **Real API probe:** Using fictional project data only, a direct local call to `qwen3.5-4b` returned an empty completion body even when the compatibility fix was applied. The text-mode local probe returned no model content and logged `elapsed=3.60s`; an earlier `json_schema` probe also returned an empty completion body after ~7.77s. The endpoint was reachable, but the model did not produce a usable payload in this environment.
- **Problems and limitations:** The model appears reachable but not reliably generating text for these bounded requests in this setup. The local adapter is implemented and tested offline, but real generation remains limited by the local model response quality and server behavior. No paid API was used, and no PR3 work was started.
- **Owner actual hours:** Not recorded by the agent; owner should enter actual time.
- **Next action:** Owner reviews PR2 implementation, live-probe results, and compatibility fix before approving the next stage.

### PR2 follow-up — reasoning budget, result metadata, and live validation

- **Original reasoning-token problem:** With LM Studio's `Enable Thinking` enabled, qwen3.5-4b used a 1,024-token completion budget for `reasoning_content`, returned empty `message.content`, and ended with `finish_reason=length`. Sending `enable_thinking=false` in the request did not override that server/model setting.
- **Successful local configuration:** The owner disabled `Enable Thinking` in LM Studio's inference settings for qwen3.5-4b. A fictional plain-text request with `max_tokens=512` then returned content, `finish_reason=stop`, zero reported reasoning tokens, and took 1.94 s. A small `json_schema` response took 1.71 s and passed Pydantic validation.
- **Client verification:** `LLMClient.generate("concept", ..., response_model=ProjectIdea)` succeeded through `http://127.0.0.1:1234/v1` using model `qwen3.5-4b`; it returned a validated `ProjectIdea`, prompt version `concept_v1`, `finish_reason=stop`, `truncated=False`, and a 9.55 s response time. The client result now carries model, prompt version, finish reason, truncation status, and response time; missing finish reasons are recorded as `unknown`, and truncated responses are retried at most once before a metadata-bearing error is raised.
- **Offline validation:** `tests/test_llm_client.py` passed (10 tests); the complete offline suite passed (66 tests, 1.70 s). All model inputs were fictional. No external API was used.
- **Remaining limitations:** This is a smoke test, not the PR3 benchmark of 10 independent first attempts for each stage. Draft/review reliability, output quality, exact GGUF artifact and quantization, context length, runtime version, and hardware offload settings remain unverified. The model's `Enable Thinking` setting must remain disabled for the observed behavior; the tested request flag alone did not disable reasoning.
- **Owner actual hours:** Not recorded by the agent; owner should enter their actual time.
- **Next action:** Owner reviews PR2 changes and evidence before approving any commit or starting PR3.

## 2026-11-08 — PR3 benchmark framework and preliminary concept run (before formal benchmark)

- **Task:** Add a reproducible, local-only benchmark runner for concept, draft, and review; fictional stage fixtures; offline reporting tests; and benchmark documentation. No PR4 or later work was started.
- **Implementation:** `python -m hankeluotsi.benchmark` takes an explicit attempts-per-stage count and output path, requires a loopback endpoint, makes one request per scored attempt with retries disabled, and writes per-attempt JSON/Pydantic validity, prompt version, model ID, finish reason, truncation and incomplete-output flags, latency, success, and optional human quality score. Report-level data includes generation parameters and optional artifact, quantization, context, and runtime metadata. Draft/review currently use compact benchmark-only schemas pending their planned application schemas.
- **Fictional data:** Added one fixed fictional fixture for each of `concept`, `draft`, and `review`. No real project data or external services were used.
- **Offline tests:** Focused benchmark/client suite passed (19 tests). Full suite: `python -m pytest -q` passed (75 tests, 1.35 s). The benchmark framework was not run live for all stages, and no 30-attempt benchmark was started.
- **Preliminary local integration:** One first-attempt `ConceptPaper` generation using fixture `fictional_community_arts_concept_v1` passed through local LM Studio at `http://127.0.0.1:1234/v1`. Model `qwen3.5-4b`, prompt `concept_v1`, JSON valid, Pydantic valid, `finish_reason=stop`, not truncated, 7.03 s; generated one objective, activity, result, and indicator. LM Studio's Enable Thinking setting was disabled. This single sample does not establish benchmark reliability.
- **Problems and fixes:** Focused review found that malformed JSON could be accepted by the client when no response model was supplied. The success condition now requires valid JSON in all modes; a regression test covers the case. Benchmark attempts call the client with `max_attempts=1`, and failures retain parse/validation and response metadata.
- **Limitations at that stage:** No live draft/review attempts; the formal threshold of at least 8/10 successful first attempts per stage was untested. Exact GGUF file/hash, quantization, context length, runtime version, and GPU/offload settings remained unverified. No quality score was assigned to the preliminary output.
- **Owner actual hours:** Not recorded by the agent; owner should enter actual time.
- **Next action:** Owner reviews PR3 implementation and documentation before deciding whether to run the formal benchmark; no commit or push was made.

## 2026-11-08 — PR3 formal local reliability benchmark

- **Task:** Run the approved 10 first attempts per stage (30 total) against local LM Studio, sequentially, with `qwen3.5-4b` only. No PR4 or later work was started.
- **Preflight:** All stages were configured for `qwen3.5-4b`; the local `/v1/models` endpoint exposed that ID. The three benchmark fixtures were reviewed and contain fictional data. The focused offline benchmark/client tests passed (19 tests) before the live run.
- **Run:** `python -m hankeluotsi.benchmark --attempts-per-stage 10 --output benchmark-results/qwen3.5-4b-2026-11-08.json --enable-thinking-disabled`. The runner made exactly 30 sequential requests, one per attempt with no retry. Endpoint: `http://127.0.0.1:1234/v1`; temperature 0.2; max tokens 512; timeout 60 s; LM Studio Enable Thinking recorded disabled.
- **Results:** Concept `10/10` (100%, mean 6.07 s); draft `10/10` (100%, mean 2.86 s); review `10/10` (100%, mean 4.89 s). All 30 attempts produced valid JSON and passed their configured Pydantic schema; all had `finish_reason=stop`, were not truncated, and were not flagged incomplete. Prompt versions were `concept_v1`, `draft_v1`, and `review_v1` respectively. The 8/10 target was met for each configured schema.
- **Artifact:** Individual per-attempt records and stage summaries are saved in `benchmark-results/qwen3.5-4b-2026-11-08.json` and summarized in `docs/model_benchmark.md`.
- **Limitations:** Draft/review use provisional compact benchmark-only schemas, not the later application schemas. No human content-quality scores were performed; `quality_score` is null. GGUF artifact/hash, quantization, context length, LM Studio/runtime version, and hardware/offload settings remain unverified. Results apply only to the repeated fixed fixtures and do not establish content quality or general reliability.
- **Safety and version control:** Fictional data only; no external API, paid service, commit, or push used.
- **Next action:** Owner reviews the saved results, provisional schema limitations, and configuration gaps before deciding on follow-up.

## 2026-11-08 — PR4 SQLite repository and workflow state management

- **Task:** Implement SQLite persistence and repository-level state transitions for PR4 only. No PR5 or later work was started.
- **Implementation:** Added `ProjectRepository` with explicit transactions, schema-version checks, validated project-idea/concept storage, generic Pydantic-validated draft/review storage, deterministic findings storage, loading and listing. The state path is `created` → `concept_ready` → `draft_ready` → `reviewed` → `approved`; invalid transitions raise explicit errors.
- **Safety and consistency:** Every write requires a stable `operation_id`. Replayed IDs with identical operation type/payload are idempotent; reuse with different content raises a conflict. Idea, concept, or draft regeneration clears dependent stages and moves status back atomically. Invalid Pydantic values are rejected before writes. An approved project is immutable, approval requires a reviewed draft, and `load_for_export` blocks unapproved records.
- **Tests:** `tests/test_repository.py` uses only `tmp_path` SQLite databases and fictional fixtures. Focused repository tests passed (16 tests). Full offline suite: `python -m pytest -q` passed (91 tests, 1.72 s). The rollback test injects a temporary SQLite trigger failure and confirms neither the project update nor operation record persisted. Diagnostics and `git diff --check` passed.
- **Limitations:** The repository is not wired into the Streamlit app or generation pipeline; that integration belongs to a later approved task. Draft/review application schemas are not yet defined, so callers must supply their Pydantic model type. Unsupported database record versions are refused; no migration framework is included. Every mutation requires the caller to provide a stable idempotency key.
- **Safety and version control:** No external APIs, paid services, production database, commits, or pushes were used. `AGENTS.md` and `PLANS.md` were not modified.
- **Owner actual hours:** Not recorded by the agent; owner should enter their actual time.
- **Next action:** Owner reviews PR4 repository behavior, tests, and limitations before approving any commit or starting PR5.

## 2026-11-08 — PR5 Streamlit prototype vertical slice

- **Task:** Implement the fictional project-idea-to-validated-concept flow with SQLite save/reload, mocked AppTest coverage, and launch instructions. No PR6 or later work was started.
- **Implementation:** The Streamlit form validates `ProjectIdea`, sends a size-bounded concept request to the existing `LLMClient` with `ConceptPaper` as its response model and one attempt only, then validates and saves the concept through `ProjectRepository`. Saved projects can be reopened from the selector. Per-submission operation IDs, form-submit handling, and a saved-concept check prevent reruns from triggering duplicate generation. Model failures leave the valid idea in `created` state and display an actionable error. The default DB is `hankeluotsi.sqlite3`; `HANKELUOTSI_DB_PATH` can override it.
- **Offline validation:** `tests/test_app.py` AppTest/repository integration cases passed (5 tests). The full offline suite passed: `python -m pytest -q` (96 tests, 2.32 s). The mocked AppTest verified one generation call across reruns, validation-before-generation, timeout preservation, concept persistence, and reopening.
- **Live local workflow:** LM Studio exposed `qwen3.5-4b` at `http://127.0.0.1:1234/v1`. The first two `ConceptPaper` requests using only idea JSON were rejected as truncated (`finish_reason=length`, 512-token cap); neither wrote a concept. The app prompt was then bounded to one objective, activity, result, and indicator. One real AppTest form submission subsequently passed in 6.03 s: JSON/Pydantic-valid `ConceptPaper`, `finish_reason=stop`, saved as `concept_ready`, then reloaded from a temporary SQLite database with one linked objective/activity/result/indicator. No retry was used by the app.
- **Documentation:** README now describes LM Studio setup, the prototype launch command, fictional-data-only manual flow, offline tests, and the local database path.
- **Limitations:** The successful real run is a single sample; the two truncations show that the model can still fail within the same token cap. Keep LM Studio `Enable Thinking` disabled. Generated content received schema validation but no independent quality assessment. Draft/review, later workflow stages, and production-database behavior remain out of PR5 scope.
- **Safety and version control:** All model/test inputs were fictional. No external API or paid service was used. Tests used temporary SQLite databases. No dependency, `AGENTS.md`, or `PLANS.md` changes; no commit or push.
- **Owner actual hours:** Not recorded by the agent; owner should enter their actual time.
- **Next action:** Owner reviews the PR5 prototype and live output before approving any commit or starting PR6.

### PR5 follow-up — operation-ID collision fix

- **Root cause:** The UI derived `create_project` and `save_concept` operation IDs from a hash of the idea content. Repository operation IDs are globally unique and intentionally reject reuse for a different project, operation type, or payload. A later explicit submission of the same idea therefore reused an old key; when it reached a different project or generated concept payload, the repository correctly raised `IdempotencyConflict` with “operation_id was already used for a different operation.”
- **Fix:** The UI now generates a UUID for each explicit form submission and uses that token for both operation IDs. Streamlit reruns do not re-enter the submission branch, so they reuse no new key and trigger no duplicate model request. The repository’s payload checks and idempotency/approval protections are unchanged.
- **Regression tests:** AppTest seeds the database with the exact legacy content-derived concept key on another project, then verifies a new submission succeeds. Another test changes the idea and confirms a distinct project and generation; the existing rerun test still asserts one generation call.
- **Validation:** Focused AppTest suite passed (7 tests). Full offline suite passed: `python -m pytest -q` (98 tests, 2.61 s). No external API or live model call was used for this fix.
- **Next action:** Owner repeats the manual browser test with a fresh fictional submission and reviews the PR5 follow-up before any commit.

### PR5 follow-up — readable ConceptPaper presentation

- **Implementation:** Replaced JSON-first concept display with labeled sections for background, objectives, target groups, activities, expected results, indicators, assumptions, and open questions. Original field text and IDs render as plain text; objective/activity/result/indicator relationships display their stored reference IDs. Project-idea values are also readable. Raw project and concept JSON remain available in collapsed expanders for debugging.
- **Rendering consistency:** Generated and reopened concepts both pass through the same saved-project renderer; schemas, stored data, prompts, and database behavior were not changed.
- **Tests:** AppTest verifies each section, exact fixture text, IDs and relationship labels, and raw JSON expanders. Focused UI tests passed (7 tests); full offline suite passed: `python -m pytest -q` (98 tests, 2.83 s).
- **Limitations:** No change to model output or assessment; this is presentation-only. No live model call was needed.
- **Next action:** Owner reviews the human-readable concept view before approving any commit or further PR5 changes.

### PR5 follow-up — visual polish

- **Presentation:** Applied the requested light palette (`#163A5F`, `#2A9D8F`, `#F7FAFC`, `#FFFFFF`, `#D9E2EC`, `#EAF4FF`, `#FFF4CC`, `#1F2937`), clearer title/subtitle hierarchy, bordered concept-section cards, subtle reference-ID labels, styled controls, and narrower-screen spacing. Original generated content remains rendered as text; IDs and links are unchanged; raw JSON stays in collapsed expanders.
- **Tests:** AppTest continues to cover the rendered sections, source wording, IDs, links, subtitle, and debug expanders. Full offline suite passed: `python -m pytest -q` (98 tests, 2.62 s).
- **Visual check:** Browser computed styles matched the requested background, heading, info, warning, form, and border colors. At 390 px the form remained vertically readable with no horizontal overflow.
- **Scope:** Presentation only; no schema, repository, prompt, LLM, or dependency changes. No commit or push.

## 2026-11-08 — Optional ConceptPaper PDF export

- **Task:** Add the approved optional PDF export on the isolated `feature/pdf-export` branch; no funding research or later workflow stages were added.
- **Implementation:** Added `generate_concept_pdf`, which creates an A4 document in `BytesIO` from a saved `ConceptPaper` without writing to the database or filesystem. It includes the project title, all concept sections, relationship IDs, the required AI-draft disclaimer, and page numbers. ReportLab's bundled Vera regular/bold TTF fonts are embedded for Finnish/English character support. The saved-concept UI now offers a sanitized `.pdf` filename through a `Download PDF` button.
- **Dependency:** Added the single permitted new dependency, `reportlab==4.4.4`; no other direct dependency changes.
- **Tests:** PDF tests cover PDF/A4 output, embedded font and Unicode glyph coverage, multi-page content, safe filenames, and preservation of the input model. AppTest checks the download control. Focused exporter/UI tests passed (10 tests); full offline suite passed: `python -m pytest -q` (101 tests, 2.82 s).
- **Limitations:** No dedicated PDF text-extraction dependency was added; the output is validated structurally and by embedded font coverage. Download is available only for a project with a saved concept. No live model or external API was used for export tests.
- **Owner actual hours:** Not recorded by the agent; owner should enter their actual time.
- **Next action:** Owner reviews the optional PDF layout and Unicode rendering before approving any commit; no commit, push, or merge was made.

## 2026-11-08 — PR5 planning workspace visual redesign

- **Presentation:** Reorganized the page into a compact compass-branded header, preserved disclaimer note, three-step workflow strip, two-column idea/saved-project workspace, and full-width concept report. Draft/review is explicitly marked “Planned · not available yet.” Saved concepts retain their sections, IDs, relationship labels, collapsed JSON, and PDF download action.
- **Responsive checks:** Browser inspection confirmed the workflow and workspace render at desktop width and the form remains within 390 px without horizontal overflow.
- **Regression tests:** Existing AppTests cover generation, saved-project reopening, download availability, and submission behavior. Updated the older shell smoke test to look for the disclaimer note rather than a warning component. Full offline suite passed: `python -m pytest -q` (101 tests, 3.03 s).
- **Scope:** Presentation and the corresponding disclaimer test assertion only. PDF export changes on `feature/pdf-export` were preserved; no schema, prompt, LLM, repository, or dependency changes. No commit, push, or merge.

### PDF export QA follow-up

- **Layout issue and fix:** Visual review of the normal fixture showed a mostly empty second page containing only assumptions/open questions. Reduced typography and vertical spacing modestly while retaining 9 pt body text, A4 margins, and flow-based pagination. Normal fixture now fits one A4 page; a long-content regression still spans multiple pages.
- **Content and Unicode:** Confirmed the fixture's O1/O2, A1-A3, R1-R2, I1-I2 relationships are emitted by the PDF story and checked the rendered browser preview. A codepoint-built Finnish sample rendered `Ääni` and `ä, ö, å, Ä, Ö, Å` correctly with embedded Vera fonts and ToUnicode maps. The generated ConceptPaper remained unchanged.
- **Validation:** PDF-focused tests passed (3 tests); full offline suite passed: `python -m pytest -q` (101 tests, 3.18 s). No PDF rendering or extraction dependency was added.
- **Limitations:** No dedicated text-extraction package is installed, so QA used source-level section/reference coverage, font/ToUnicode checks, page-box/page-count checks, and browser rendering rather than automated PDF text extraction. No external API or paid service was used.

## 2026-11-08 — PR6 first slice: deterministic concept consistency checker

- **Task:** Add the limited pure-Python O→A→R→I concept consistency checker only. No draft-generation, UI, persistence, or later PR6/PR7 work was started.
- **Implementation:** Added `check_concept_consistency(ConceptPaper)` and structured `ConsistencyFinding` records with stable code, severity, explanation, element ID, and related IDs. It detects duplicate objective/activity/result/indicator IDs and duplicate links; unresolved O/A/R references and empty relationship lists are errors. Objectives without activities, activities without results, and results without indicators are warnings. Valid links follow existing typed schema fields only; no programme-specific assumptions or eligibility judgments are encoded.
- **Tests:** Ten focused tests cover the valid fictional fixture, duplicate IDs for all element classes, all unresolved reference edges, duplicate links, missing links, disconnected elements, deterministic results, severity, and serialization. Full offline suite passed: `python -m pytest -q` (111 tests, 3.38 s).
- **Limitations / next work:** The checker is not yet called from Streamlit or a pipeline, and it does not generate or save drafts. That integration remains for a separately approved continuation. The checker only receives an existing `ConceptPaper`; Pydantic remains responsible for field shapes and ID formats.
- **Branch and safety:** Created `feature/pr6-consistency-checker` from the clean `feature/pdf-export` branch. Fictional fixtures only; no external APIs, paid services, schema/repository/prompt edits, commit, push, or merge.

### PR6 Part 2 — Streamlit consistency-check integration

- **Implementation:** The shared saved-concept renderer now runs `check_concept_consistency` for both newly generated and reopened ConceptPapers. A navy/teal-consistent `Consistency Check` section shows error and warning counts, overall structural status, each stable finding code and explanation, and affected/related IDs. Error and warning styles are distinct; a clean concept receives an explicit success message.
- **Scope and safety:** This is deterministic structure/reference validation only. The UI explicitly says it does not assess content quality or funding eligibility. Rendering does not call an LLM or repository write method and preserves saved concept data, project state, and approval timestamp.
- **Tests:** AppTests cover valid, unresolved-reference, duplicate-ID, disconnected-element, saved-project, generated-concept, rerun, and approved-record cases. Full offline suite passed: `python -m pytest -q` (115 tests, 3.95 s).
- **Remaining PR6 work:** Draft generation and integration of consistency findings into the broader draft/review workflow remain unimplemented; no PR7 work was started.
- **Live browser follow-up:** The shared `127.0.0.1:8501` preview was configured with an isolated temporary database that initially contained zero projects, so no ConceptPaper (and therefore no consistency results) could be rendered. Added an empty-state cue and moved the check directly below the concept heading. Seeded only that temporary preview database with a fictional saved concept, then confirmed the saved-project view displayed 0 errors/0 warnings; a separate local Qwen3.5-4B submission completed in 6.69 s and displayed the check immediately after generation. No normal project database was modified.
