# AGENTS.md — HankeLuotsi AI

**Project:** HankeLuotsi AI — EU project planning assistant  
**Owner:** Tanja Kukkamäki (individual HAMK AI Expert project)  
**Course effort:** 135 hours / 5 ECTS  
**Planning submission:** Sunday 8 November 2026, 12:00 (Finland time); **prototype:** 22 November 2026; **final:** 13 December 2026  
**Document version:** 1.1 — 7 November 2026 (planning deadline corrected)

> This file instructs AI coding agents (primarily Codex). It is **not** a system prompt for the application's end users. The owner remains accountable for design, tests, code review and approval.

## 1. Mission, scope and non-goals

Build a **single-user, local-first Streamlit application** that supports early EU project planning using the following *one* workflow:

`Project idea → Concept paper → Application draft → Deterministic consistency checks → AI review → Human approval → Markdown export`

The application must always show a clear disclaimer:

> AI-generated draft. Not a funding eligibility assessment. Verify requirements against the relevant funding programme.

**In scope**
- Structured idea input, concept generation, application drafting and qualitative review.
- Pydantic v2 validation of all structured model outputs.
- Deterministic Python checks for completeness and cross-references.
- SQLite persistence with explicit workflow states and human approval.
- Markdown export of an approved application draft.
- Local inference through LM Studio, with an optional *per-stage* cloud API fallback using fictional data only.
- Automated unit, integration and Streamlit UI tests; reproducible setup and a short recorded demo.

**Owner-approved addition — 8 November 2026:** Optional Funding Opportunities Research for saved fictional ideas. The first slice uses reviewed official programme guidance for EURA 2021 (EAKR, ESR+, JTF), Interreg Aurora, the EU Funding & Tenders Portal and Business Finland, with optional bounded retrieval of public page descriptions. Comparison runs locally; project data is never sent to funding sources. Programme profiles must be distinguished from verified calls, with unknown call dates/status and visible source/review/retrieval dates. This authorizes read-only public-source research, not submissions, eligibility decisions, paid services or PR7. See the bounded task in `PLANS.md`.

**Out of scope — do not add without owner approval**
- Funding eligibility judgments, official programme-specific forms or compliance certifications.
- Budget calculations, grant applications submitted to authorities or funding-platform integrations.
- Logins, accounts, multi-user hosting, complex autonomous multi-agent orchestration.
- PDF/DOCX generation, document history/branching, vector databases, LangChain, LangGraph or Django.
- Processing actual confidential employer, partner or personal data.

**Prototype milestone (22 November):** A working Streamlit vertical slice with idea input, local-or-fallback concept generation, strict validation, SQLite save/load and visible error handling. If a draft/review screen is not yet built, that is **not a prototype blocker**; their *benchmark harnesses* must nevertheless be exercised by 16 November. The full workflow is due for the final delivery.

## 2. Technical decisions

| Concern | Chosen approach |
|---|---|
| Language | Python 3.11+ |
| UI | Streamlit, single-page or simple staged interface |
| Schemas | Pydantic v2; model JSON schema where supported |
| Persistence | Standard-library `sqlite3`; one local database; explicit transactions |
| Local model | LM Studio OpenAI-compatible server (default `http://localhost:1234/v1`) |
| Initial benchmark | Candidate Qwen3.5-4B GGUF Q4_K_M, initial 8192-token context **subject to verification**; compare at least one practical alternative |
| Cloud fallback | OpenAI-compatible provider adapter, separately configured; **no API key in source control** |
| Agent | Codex for bounded coding, tests, debugging and documentation |
| Testing | pytest for logic and persistence; Streamlit AppTest for UI with mocked model |
| Version control | Git/GitHub; small reviewable commits |

The model's actual file, quantization, context length, parameters, runtime version and GPU/CPU offload settings must be recorded in `docs/model_benchmark.md` **after verification on the owner's laptop**. Do not claim any exact GGUF filename or benchmark result before testing.

## 3. Repository layout (target; create incrementally)

```text
hankeluotsi-ai/
├── app.py
├── README.md
├── AGENTS.md
├── PLANS.md
├── requirements.txt
├── .env.example
├── .gitignore
├── hankeluotsi/
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── prompts.py
│   ├── llm_client.py
│   ├── pipeline.py
│   ├── consistency.py
│   ├── repository.py
│   └── exporter.py
├── tests/
│   ├── test_schemas.py
│   ├── test_llm_client.py
│   ├── test_consistency.py
│   ├── test_pipeline.py
│   ├── test_repository.py
│   └── test_app.py
└── docs/
    ├── development_log.md
    ├── model_benchmark.md
    └── evaluation.md
```

Prefer the **simplest** implementation that satisfies a stated acceptance criterion. Do not create placeholder packages or extra frameworks simply to match the tree.

## 4. Data contracts and state rules

Define the following **small, versioned** Pydantic structures, with exact field choices agreed in `PLANS.md` before implementation:

- `ProjectIdea`: title, development need, target groups, expected change, geography, optional partners and optional funding context.
- `ConceptPaper`: background/need, objectives, target groups, preliminary activities, expected results, proposed indicators, assumptions and open questions.
- `ApplicationDraft`: background, objectives, target groups, work packages, activities, results, indicators, partner roles, impact, sustainability, risks and open questions.
- `ReviewReport`: strengths, structured findings, missing information, overall assessment and explicit uncertainties.

Give related objectives, activities, results, indicators and work packages stable IDs (`O1`, `A1`, `R1`, `I1`, `WP1`). Include the cross-reference IDs explicitly in the schema. Keep illustrative outputs short enough to fit a small local model's context and output limits.

**State transitions**
1. `created`: input captured and saved.
2. `concept_ready`: validated concept committed.
3. `draft_ready`: validated draft committed.
4. `reviewed`: deterministic findings and validated AI review saved.
5. `approved`: user explicitly approved the current reviewed draft; export allowed.

**Invariants**
- The database, not `st.session_state`, is the source of truth for durable records.
- Never let the LLM write directly to SQLite, approve a draft or export an unapproved record.
- Regeneration of an upstream stage must invalidate its dependent outputs and move status backwards **atomically**. Avoid stale reviews and exports.
- An approved record is immutable. To change it, create a new project record; no version-history feature is required.
- Repeated clicks, Streamlit reruns and retry attempts must not duplicate records or silently repeat an expensive generation. Use explicit form submissions, stable operation guards and transactions.
- Failed validation or timeouts preserve the last valid persisted state and display a recoverable error.
- A schema version is included in persisted records; refuse unsupported versions with a clear message instead of silently coercing them.

## 5. AI model call contract and evaluation gate

- Implement a single provider-independent `LLMClient` interface; stage-to-provider mapping belongs in configuration, not UI code.
- Stage names: `concept`, `draft`, `review`.
- Use versioned prompt templates, e.g. `concept_v1`, `draft_v1`, `review_v1`; record the version and provider/model used for each benchmark and generation.
- Ask for bounded JSON using a JSON schema/structured output mode when supported; validate with the corresponding Pydantic model.
- **First-attempt success** means: nonempty response, valid JSON, Pydantic validation succeeds with **no repair**, and `finish_reason` does not indicate truncation. If `finish_reason` is absent, log it as unknown and independently flag incomplete output.
- A single validation-feedback retry may be offered after failure. It **does not count** toward the first-attempt benchmark success rate.
- Configure request timeouts and bounded token limits. Never recurse or retry indefinitely. Keep UI status and error messages understandable.

**Benchmark by 16 November:** At least 10 independent first attempts **per stage** (`concept`, `draft`, `review`) with preliminary representative prompts and fictional fixtures. Record success rate, latency, truncation, JSON validity, Pydantic validation, basic quality score, exact model/configuration and prompt version. The engineering threshold is **at least 8/10 valid nontruncated first attempts for each stage**. Approximate targets: concept 90 s; draft 180 s; these are performance targets, not formal pass criteria.

If a stage fails reliability or is impractically slow, assign **only that stage** to an external compatible API. Cloud processing is optional, separately billed and must never receive non-fictional project information. The full application remains functional even if the local server is offline, with a clear actionable error if no configured provider is available.

## 6. Deterministic checks: never delegate these to an LLM

Implement pure Python checks with stable finding codes. At minimum:
- Missing required fields or empty required lists.
- Duplicate IDs, malformed IDs and unresolved cross-references.
- Objective without an associated activity.
- Result without a linked activity and/or indicator.
- Indicator without an associated result or without a measurable definition.
- Missing partner roles or cross-border value **only as advisory findings** where relevant; do not invent programme requirements.

An AI review supplements these checks but must not overwrite or conceal deterministic findings. Mark AI observations as suggestions, not certified funding rules.

## 7. Agentic working agreement

For **every bounded coding task**, Codex must:

1. **Read** this file, the relevant `PLANS.md` task and existing code/tests.
2. **Propose** a short implementation plan, list files to change and state acceptance criteria before changing code.
3. **Implement** only the agreed task. Do not silently expand scope, change technology stack or add dependencies.
4. **Test** the changed functionality using offline tests first; capture commands and outcomes.
5. **Inspect and correct** failures, with a maximum bounded debugging cycle; escalate unresolved issues rather than concealing them.
6. **Summarize** changes, tests, limitations and any decision required from the owner.
7. **Wait for owner approval** before committing changes or proceeding to the next task.

A task is done only after the owner can explain what changed, what was tested and why the result is acceptable. Code and generated text are reviewed as untrusted drafts.

**Owner (student) responsibilities**: select scope, write/test acceptance criteria, run/inspect demos, review code and data model, decide fallback, approve commits, evaluate five scenarios, record actual hours and explain the architecture in the final report.

**Other AI tools**: ChatGPT helps clarify design and debug; Claude, Grok and Perplexity may give independent review. Their suggestions are evaluated, not accepted automatically. Log accepted/rejected significant suggestions.

## 8. Testing instructions

- **Unit/integration tests (pytest, offline, deterministic):** schemas, reference integrity, SQLite state transitions, failure rollback, approval immutability, idempotent submissions, timeouts, provider adapters using mocked responses.
- **Streamlit AppTest:** mock the model client; test available buttons, input validation, state-related rendering and human approval. Set `AppTest.from_file(..., default_timeout=10)` (adjust if needed). AppTest is synchronous: **do not claim it simulates a click while a request is still running**. Test that concurrency/idempotency protection at service/repository level with pytest; manually test slow-call UX.
- **Live integration:** check LM Studio/local API separately, then fallback provider if configured. Never make live API calls from normal CI or default pytest runs.
- **Evaluation:** prepare five fictional scenarios and a 1–5 scoring rubric **before** examining outputs; measure completeness, coherence, indicator quality and AI-review usefulness. Target ≥4/5 full workflows completed.
- Save reproducibility information, not credentials. Include model/version/prompt version/latency and non-sensitive examples in logs.

## 9. Safety, privacy, and security rules

- Work exclusively with **fictional synthetic project data**, not real grant applications, partner information or employer documents. This reduces confidentiality and personal-data risk; it is not a substitute for normal security review.
- No secrets, `.env`, SQLite files, personal records or private documents in GitHub. Ensure `.gitignore` includes `.env`, `*.db`, `*.sqlite*`, caches, and any local samples containing sensitive data.
- Do not execute destructive commands, delete existing files, push to remotes, install unexpected packages, contact external services or change security settings without the owner's explicit approval.
- Keep the LM Studio server on localhost by default, with no public/network exposure.
- Treat model responses as untrusted data; never execute arbitrary content they generate. Use parameterized SQL and escape user text in exports.
- Show uncertainty and the funding eligibility disclaimer; require human review and approval before export.

## 10. Documentation and references

Update `docs/development_log.md` after each substantial work session with date, hours, task, tools/agents used, prompts or prompt versions, tests, problems, fixes, what the owner learned and next action. Log **actual** hours independently from the planned 135.

Use `PLANS.md` as the controlling implementation and milestone tracker. When course text and this file conflict, **follow the current teacher instructions** and propose a documented update.

Official technical references (for implementation checks):
- LM Studio server: https://lmstudio.ai/docs/developer/core/server
- Streamlit AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest
- Pydantic validation: https://docs.pydantic.dev/latest/concepts/models/
