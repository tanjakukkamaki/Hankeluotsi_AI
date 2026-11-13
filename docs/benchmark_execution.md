# Benchmark execution diagnosis and safe smoke tests

12 November 2026. This task preserves the previous five-case experiment and all existing uncommitted work. Changes are confined to a new benchmark execution wrapper, offline tests, ignore rules and documentation. The production app, local application client, prompts, schemas, database and existing benchmark/blinded-review implementations remain unchanged.

## Evidence and diagnosis

The five previous requests used `qwen3.5-4b`, JSON-schema output, temperature 0.2 and `max_tokens=2048`. All returned empty captured content and `finish_reason=length`. The old transport discarded `reasoning_content` and detailed reasoning-token usage; the exact cause of those historical responses cannot be proven retrospectively.

Read-only local inventory/CLI inspection now confirms the loaded `qwen3.5-4b` instance, server-reported Q4_K_M and 8192-token loaded context, and the model-relative file `lmstudio-community/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf`. File hash/runtime/hardware are not independently verified. The catalogue lists reasoning default `on`; that is not the current UI checkbox value. Neither inventory nor CLI inspection exposed the actual Enable Thinking checkbox state. No GUI/global model setting was changed.

A new diagnostic request on the **same fictional Q01 case** with the same 2048 cap and `reasoning=off` on `/v1/chat/completions` still reported **1408 reasoning tokens**, 6558 reasoning characters, and only 1892 final-content characters before truncation. Thus this attempted switch did **not** turn reasoning off on this compatibility route. A subsequent `reasoning_effort=off` attempt failed immediately (request_failed, about 0.025 s); no completion/usage was returned and no valid answer resulted. That intermediate revision did not save the error envelope, so its precise rejection/network cause is not established. It is not treated as a supported control. Both attempts are preserved separately, not repaired, overwritten or counted as first-attempt successes.

These observations verify an operational failure mode: reasoning competes with the final answer for the completion budget, and unverified API switches cannot be assumed to disable it. They do not prove the historical five requests had the same exact reasoning counts. Structured response handling was not an empty-content parsing bug: the old transport read the final content field, but the current diagnostic shows substantial reasoning plus a truncated final answer. Reasoning must never be promoted to a validated final answer.

The diagnostic wrapper retains the established `/v1/chat/completions` schema request and Pydantic checks, removes the unverified control parameters and explicitly records `server_default` thinking. Its new-run default cap is **4096**. This is a diagnostic allowance, **not a verified generation or disable-thinking fix**. The final 4096-token test also failed: **3874 reasoning tokens**, 17301 reasoning characters, empty final content, `length`, 82.60 s. Increasing the budget alone did not solve the problem. It refuses an output cap consuming the whole known input context; true input/schema token overhead still requires measurement. A token-limit failure is explicit, retained, and exits nonzero without automatic retry.

The LM Studio native API documents `reasoning=off` for `/api/v1/chat`; that does not establish support on `/v1/chat/completions`. Switching endpoints would change schema delivery and comparison conditions, so the production route and prompt were preserved. If you disable Enable Thinking manually in LM Studio, record that change and run a separately labelled study; verify returned reasoning counters rather than relying only on the checkbox. Keep enough total budget if reasoning remains active.

## What the execution wrapper checks

`python -m hankeluotsi.benchmark_execution` reuses the existing fictional dataset, prompts, request hashes, run/checkpoint/assessment and review-compatible report format. It selects one to five distinct existing case IDs before execution, never SQLite or arbitrary project text. It records the full source manifest, selected request set, source hash, zero-retry policy, diagnostic fields and existing validation facts. No original experiment is overwritten. Selected reports pass the existing `verify_report`; they are separate experiments from the earlier ten-case manifests.

Local preflight checks a credential-free loopback endpoint and the exact **loaded** model. A listed but unloaded/unknown model, missing server, HTTP error or impossible output/context configuration blocks generation. Raw local request/response envelopes go only to a new private directory, including returned reasoning and usage. HTTP error envelopes are saved before failure classification when JSON is available. The original framework's generic request error remains compatible; the wrapper adds explicit token-limit, incomplete, JSON and schema diagnostics. Missing diagnostic fields mean unknown, not zero reasoning.

Mistral preflight reads `MISTRAL_API_KEY` and validated `MISTRAL_MODEL` from **its launching process environment**. Its default configuration check makes no HTTP request and prints no key or model identifier. `--verify-model` additionally makes one read-only authenticated request to the fixed official model-list endpoint; it sends no project data and does not generate tokens. Authentication errors, unavailable models and network failures are sanitized. A key/model presence check does not verify balance, pricing or permission to spend.

## Commands in your existing PowerShell

Use the PowerShell window where `$env:MISTRAL_API_KEY` is already configured. Launch Python directly from that same window; do not launch through a new unrelated terminal expecting it to inherit another shell's variables. No key needs to be pasted into this conversation, a command argument or a source file. If only `setx` was used, it does not populate an already-open shell; configure the current process securely using [the setup instructions](mistral_setup.md).

From the project root, the following is the exact **no-generation** configuration check:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark_execution preflight --provider mistral
```

If the model variable is missing, set the exact owner-approved identifier (not a key):

```powershell
$env:MISTRAL_MODEL = Read-Host 'Exact approved Mistral model identifier'
```

Optional read-only availability check, with no generation or project text:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark_execution preflight --provider mistral --verify-model
```

An actual subprocess test confirmed inheritance using a **fictional** key/model: configuration was received, the process exited successfully, and stdout/stderr contained no key. This does not prove access to your separate live PowerShell session; only running the command there can establish that. Do not print `$env:MISTRAL_API_KEY`, environment dumps or verbose HTTP traces.

## One Qwen smoke test

The execution task attempted the single Q01 fixture in three separate diagnostic runs (two token-producing responses and one immediate failure), not three different ideas or hidden automatic retries. No valid concept was obtained. **Before a separately approved repeat, turn off Enable Thinking for the loaded Qwen model in LM Studio's Developer/model inference settings.** The actual UI state could not be read or changed through this benchmark. Keep the JSON-schema route and verify actual reasoning counters afterwards; no benchmark batch is recommended until the single smoke succeeds. Change the output suffix every time. The following makes **one** local request, no retries:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark_execution run `
  --provider local --model qwen3.5-4b --case-ids Q01 --max-tokens 4096 `
  --output .benchmark-private/qwen-smoke-owner-01
```

Inspect `results.json` and the private `diagnostics/` envelope. Require valid JSON/Pydantic, normal `stop`, no truncation and plausible content. Inspect reasoning counts and remaining deterministic findings separately. Exit code 1 means a recorded generation/validation failure; 2 means rejected execution/preflight. A success is not a human quality score. Original failed attempts remain unchanged.

## One Mistral smoke test — pending owner approval

**No paid Mistral calls were made during this task. Do not execute this command yet.** First verify the exact available model, account balance, current official input/output pricing, schema support and a conservative input-plus-output cost bound. The model-list API does not expose a reliable account balance here. The execution flags below are an explicit owner assertion of completed privacy/billing review, not automatic billing verification. Do not use them while those facts remain unknown.

After owner approval, from the same configured PowerShell:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark_execution run `
  --provider mistral --case-ids Q01 --max-tokens 4096 `
  --output .benchmark-private/mistral-smoke-owner-01 `
  --execute-cloud --fictional-only --accept-costs
```

This verifies model availability, selects **one** existing fictional request, then makes one generation request with zero retries. It does not run the old ten-case collector. Optional five-case continuation replaces `--case-ids Q01` with `--case-ids Q01 Q02 Q03 Q08 Q09` and uses another fresh output directory, **only after separate approval of that paired experiment**. Use the same source version/settings and record actual reasoning differences. Do not combine new 4096-token results with the old 2048-token study as if equivalent.

## Git privacy and preserved evidence

All new execution/runtime/raw evidence must be below `.benchmark-private/`, which is ignored. Existing `PRIVATE-*.json` mappings anywhere in the workspace and benchmark `local-model-metadata.json`/`raw-response*.json` are also ignored. Old evidence remains on disk; ignoring is not deletion. At inspection, no matching private map/runtime metadata was already tracked. Ignore rules do not remove a file previously committed or explicitly force-added; inspect publication diffs before approval. Never use `git add -f` for these files.

Existing blinded-review code is unchanged. Generate private packets/mappings below `.benchmark-private/`; share only reviewed anonymized outputs and empty rating forms with a human evaluator. Raw runtime files, provider maps, keys and unblinded reports do not belong in the public GitHub repository. Public documentation uses aggregate diagnostic facts and never raw reasoning, local absolute model paths or credentials.

## Sources and limits

[LM Studio chat-completion interface](https://lmstudio.ai/docs/developer/openai-compat/chat-completions) and [native reasoning control](https://lmstudio.ai/docs/developer/rest/chat) were checked. The project's [Qwen model-card source](https://huggingface.co/Qwen/Qwen3.5-4B) describes a template thinking switch; that does not prove the installed LM Studio route honors it. [LM Studio issue 1773](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1773) reports related structured-output/reasoning interactions, and [issue 1990](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1990) distinguishes native-route workarounds. Issue reports are diagnostic leads, not proof of this machine's historic configuration. Local recorded response counters are the direct evidence used here.

## Final verification

Full final offline suite: **501 passed, 2 skipped in 22.72 s**, using live-source opt-in disabled, temporary default SQLite and bytecode writes disabled. The two skipped cases are opt-in public-source checks. `git diff --check`, a separate new-text scan and prior source/data/evidence hash comparisons passed. All three diagnostic reports pass the unchanged review validator using UTF-8 reads. Real-child-process environment inheritance and Git exclusion of private data are tested. No new valid Qwen concept or paid Mistral result is claimed. This is a verified diagnostic/preflight/privacy improvement with a remaining live-generation blocker; owner approval is required before more smoke tests or publication.

## Follow-up: explicit native thinking-off verified — 12 November 2026

This follow-up supersedes the unresolved live-generation status above for **one native-mode smoke test only**. Earlier results and their settings remain unchanged. The owner reported switching Enable Thinking OFF. A fresh compatibility-route Q01 request still returned 3589 reasoning tokens, `length`, invalid JSON/Pydantic and 83.57 s. Thus the UI selection alone did not establish effective thinking-off on that API route; the actual checkbox state is not independently observable here.

Added opt-in **`--local-api native`** to the benchmark execution wrapper only. It uses documented `POST /api/v1/chat` with `reasoning=off`, `store=false`, empty integrations, temperature 0.2 and `max_output_tokens=4096`. It does not change the app, global model settings or the default compatibility route, and there is no automatic fallback. It preserves the base fictional prompt but adds the exact JSON schema to the native system prompt under version **`native_schema_prompt_v1`**. This endpoint does not document server-side JSON-schema enforcement: structured validation is performed locally with the unchanged strict `ConceptPaper` model and deterministic checker. The private diagnostic envelope records the actual transmitted prompt/schema, distinct from the source fixture request in the manifest.

The single corrected Q01 repeat reported model `qwen3.5-4b`, 8192 loaded context, Q4_K_M, **0 reasoning tokens / 0 reasoning characters**, **20.69 s**, 1286 input / 950 output tokens (2236 total), valid JSON and valid Pydantic `ConceptPaper`, and **no deterministic findings**. Output was below its 4096 cap. Effective reasoning-off is verified for this request; this is not proof of every future request or the global UI state. No paid/cloud request was made. The first compatibility request and native repeat are separate, preserved attempts on one fictional case, not hidden retries.

**Finish-reason limitation:** The native response did not report `finish_reason`. It remains null; the existing benchmark therefore conservatively flags incomplete/unknown finish and does not count a strict first-attempt success. A valid concept and zero reasoning do not justify fabricating `stop`. CLI exit code 1 can consequently mean unknown finish even when both JSON/Pydantic pass; inspect those fields separately. This native smoke cannot establish the original reliability gate or superiority versus Mistral. Any paired study needs a newly frozen protocol with comparable effective schema/prompt delivery to both providers; do not mix this mode with old server-enforced-schema runs as if identical.

For an owner-approved repeat in a fresh private directory:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark_execution run `
  --provider local --local-api native --model qwen3.5-4b `
  --case-ids Q01 --max-tokens 4096 `
  --output .benchmark-private/qwen-native-owner-01
```

Evidence is ignored under `.benchmark-private/qwen-thinking-off-20261112T193403Z` (compatibility attempt) and `.benchmark-private/qwen-native-off-20261112T193708Z` (native repeat). Both reports pass the existing UTF-8 review validator; no old result was overwritten. New native regressions verify correct endpoint/control, no server conversation storage/integrations, schema delivery, strict validation, reasoning separation, unknown finish preservation and prohibition of native cloud mode. Focused framework regressions: **95 passed in 2.82 s**. Full final offline suite: **503 passed, 2 skipped in 23.39 s**; skips are opt-in public-source checks.
