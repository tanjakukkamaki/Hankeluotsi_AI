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
