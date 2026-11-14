# Qwen and Mistral comparison: exact operating procedure

**13 November follow-up:** For the current production-contract FI/EN pilot, see [Mistral readiness and planning-quality benchmark](mistral_readiness.md). Its separate offline plan freezes8 stage-isolated requests per provider, including seeded-defect reviews, with concept_v2/draft_workflow_v2/review_workflow_v3 and unchanged persisted schemas. Planning inputs are hand-authored controls, not model outputs. It provides strict import and private A/B packets with separate unscored human/AI forms; it has no online batch collector. No live run was made. The older concept-only collector and historical evidence below remain separate and must not be mixed with the new protocol. A minimal one-call owner-run Mistral smoke is prepared in the readiness guide; account/model/pricing approval is still required.

Prepared 11 November; updated 12 November 2026. An explicit Mistral collector is now implemented and tested offline; **no real cloud call or completed model comparison was performed**. Qwen/cloud execution is opt-in; preparation/import/review are offline. All benchmark data is fictional. Never use this as a route to send saved projects or private information to a provider. The implemented collector below supersedes the historical future-caller instructions retained later in this document.

## Implemented cloud collector — 12 November 2026

First configure the key and exact approved `MISTRAL_MODEL` as described in [Mistral setup](mistral_setup.md). Do not execute real requests until you approve the model, terms and budget. All commands below are owner-run instructions, not evidence of live comparison results.

Prepare one new common manifest using the existing offline `model_quality plan` command below. Run Qwen and Mistral from the same reviewed source version and **the same manifest file**; preserve its hash. For a separate pilot use one trial; the proposed study uses three trials × ten ideas. Do not mix the earlier adaptive A/B/C experiment or its different prompt recipes into this comparison.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality plan `
  --trials 3 --max-tokens 2048 --timeout-seconds 120 --order-seed 37 `
  --output benchmark-results/paired-study-01/plan

.\.venv\Scripts\python.exe -m hankeluotsi.model_quality run-local `
  --manifest benchmark-results/paired-study-01/plan/manifest.json `
  --model qwen3.5-4b --endpoint http://127.0.0.1:1234/v1 `
  --output benchmark-results/paired-study-01/qwen

# REAL CLOUD CALLS: execute only after owner approval of costs/privacy/model.
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_benchmark `
  --manifest benchmark-results/paired-study-01/plan/manifest.json `
  --output benchmark-results/paired-study-01/mistral `
  --execute-cloud --fictional-only --accept-costs

# Offline: give only the packet/template to the evaluator; retain PRIVATE-key.json separately.
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality_review prepare `
  --reports benchmark-results/paired-study-01/qwen/results.json benchmark-results/paired-study-01/mistral/results.json `
  --output benchmark-results/paired-study-01/blind
```

Both providers receive identical manifest messages, schema, temperature, token limit and request order with no automatic retries. Equal token limits do not establish equal compute or identical server behavior. Record the exact local model/runtime metadata using the optional `--metadata` file described below. Pin a supported Mistral model version if available; actual returned IDs are retained and unknowns remain unknown.

The cloud collector uses existing transport-independent `model_quality.run`, checkpointing and assessment. `results.json` remains compatible with the existing blinded-review validator and records provider/requested/reported model, prompt/base version, case/trial/language, JSON/schema/finish/truncation, timing, tokens and null human scores. Additive `error_type` distinguishes sanitized auth/rate-limit/connection/timeout/protocol/JSON/schema/incomplete failures; collector source hashes record adapter code. Generic per-attempt checkpoints are written immediately; detailed adapter categories are added in the completed report. An interrupted run retains checkpoints but is incomplete and cannot be silently resumed or used as a complete comparison.

Estimated costs remain **null**: no verified pricing or uncached billing basis is asserted. Use the existing reviewed pricing/import mechanism only when exact-model prices, currency/date/source, token counts and billing basis are independently established. Neither token totals nor a European provider establish costs, data residency or privacy guarantees.

Cloud connection failures do not fall back to local. The collector preserves every planned request/failure, with one bounded call per slot; a rate limit/auth failure may therefore be recorded for multiple independent slots. Stop/review account settings before initiating another run. Changed inputs, missing flags/configuration, unreviewed free text and existing output directories are rejected before requests. Only the fixed synthetic dataset is accepted, including for programmatic collection.

The packet contains original outputs, which may self-identify; blinding is imperfect. The human evaluator fills a **copy** of ratings-template.json, records evidence using `expert_quality_v1` and returns it for the existing offline `analyze` command. Never distribute PRIVATE-key.json before ratings are complete. Mocked comparison tests validate packet compatibility and blank scores; they are not quality evidence. No real-key request, live model availability/schema support, pricing or quality advantage was verified during implementation.

## Prepare one experiment offline

Use PowerShell in the repository root with the existing requirements installed. Commands below create new directories; change a suffix when repeating. Preserve the generated manifest and exact source version for both providers. A changed source/schema/rubric is rejected rather than silently changing the experiment.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality plan `
  --trials 3 --max-tokens 2048 --timeout-seconds 120 --order-seed 37 `
  --output benchmark-results/quality-study-01/plan
```

This makes **no model request**. It writes `manifest.json` (30 exact case/trial/message records, schema, parameters, versions and hashes) and `responses-template.json` (explicit `not_run` placeholders, not results). One trial can be used for a separate pilot. The order seed controls request order, not model generation randomness.

For an optional metadata file, save the following as `benchmark-results/quality-study-01/qwen-metadata.json`, replacing only verified values. Null is an honest unknown, not a claim that configuration was measured.

```json
{
  "artifact": null,
  "artifact_sha256": null,
  "quantization": null,
  "context_tokens": null,
  "lm_studio_version": null,
  "runtime_version": null,
  "hardware": null,
  "offload": null,
  "thinking_disabled": null
}
```

Record `git log -1 --oneline`, package/runtime versions and any uncommitted benchmark-source state alongside the study. The manifest includes benchmark/production-prompt/schema/checker file hashes, and results include actual Python/platform/package versions. Do not guess an exact artifact or treat a server model alias as a verified GGUF identity.

## Run Qwen later, explicitly

Start LM Studio locally, verify sufficient context and the selected model's **Enable Thinking** setting. Setting `thinking_disabled` in metadata records a checked fact; it does not control the server. The existing app/model configuration is not edited by these commands. Use the exact local model identifier shown by your server; `qwen3.5-4b` is the current prototype's configured identifier, not a verified artifact filename.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality run-local `
  --execute-local --model qwen3.5-4b --endpoint http://127.0.0.1:1234/v1 `
  --manifest benchmark-results/quality-study-01/plan/manifest.json `
  --metadata benchmark-results/quality-study-01/qwen-metadata.json `
  --output benchmark-results/quality-study-01/qwen
```

This is **30 real local requests**, one per planned attempt; allow time for completion. Defaults set a 120-second HTTP phase timeout and 2048 output tokens; the timeout is not a strict total wall-clock deadline. Unavailable service, malformed output or timeout becomes a failed observation and later cases continue. No repair/transport retries or hidden warm-up calls occur. `attempts/attempt-NNN.json` records completed attempts; `results.json` adds summaries. Every destination must be new; even an empty directory from a failed setup is not reused automatically. No application database is read or written.

## Future Mistral: approval and official API work still required

**Historical manual-import alternative (11 November design):** This section remains useful for separately collected responses. The implemented `mistral_benchmark` collector above now provides executable, opt-in collection without a Mistral SDK. Manual collection must still use the [official Chat Completion API](https://docs.mistral.ai/api) and [custom structured outputs](https://docs.mistral.ai/inference/conversations/structured-output/custom), with separate owner approval of model, budget and privacy. No real collection was performed during this implementation.

For **each request, in manifest order**, the future caller must:

1. Select and record an exact model/version identifier, not assume that a mutable `latest` alias is reproducible. Record the actual response model too; unknown identity remains a limitation.
2. Send `requests[i].messages` unchanged, the manifest's `response_format` JSON schema and the same `temperature`/`max_tokens`. Apply the same timeout and one-request/no-retry policy. Do not add provider-specific content instructions or enable tools/retrieval. Record unavoidable server-side behavior differences rather than claiming identical underlying implementations.
3. Measure full request wall time. Copy the unmodified returned text, actual model, finish reason and supplied usage counts. For failures, record the bounded category and null unknown fields; retain the request's slot instead of dropping it.
4. Keep credentials only in the approved caller's environment/secret mechanism. Do not copy auth headers, environment dumps or arbitrary exception strings into artifacts. This repository's importer does not need or read a Mistral key.
5. Fill a **copy** of `responses-template.json`, keeping its `manifest_sha256` and every `request_sha256`. Set `provider` to `mistral` and `requested_model` to the exact model used. Replace every `not_run` with an actual response or actual failure. The importer rejects placeholders, missing slots, duplicates, changed manifest and extra credential fields.

Normalized reply fields (all are already present in the generated template):

| Field | Future caller supplies |
| --- | --- |
| `text` | Exact assistant output string, including invalid JSON; null if no output |
| `reported_model` | Returned model identifier or null when unavailable |
| `finish_reason` | Returned reason, such as `stop`/`length`; null if absent |
| `usage` | `{ "prompt_tokens": integer-or-null, "completion_tokens": integer-or-null, "total_tokens": integer-or-null }`, or null |
| `billing_basis` | `standard_uncached` only if independently confirmed applicable; otherwise null |
| `latency_seconds` | Measured nonnegative finite seconds; null if not captured, never import-processing time |
| `error` | null for a completed request; `timeout`, `request_failed` or `invalid_response` for actual failure |

Example mappings are specifications for later approved collection, not evidence of an API call today. Imported metadata is self-reported; linkage checks cannot prove that an external caller actually used the manifest or verify that a provider really served a declared model.

Once the owner has collected real responses into `benchmark-results/quality-study-01/mistral-responses.json`, normalization/validation is entirely offline:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality import-responses `
  --manifest benchmark-results/quality-study-01/plan/manifest.json `
  --responses benchmark-results/quality-study-01/mistral-responses.json `
  --output benchmark-results/quality-study-01/mistral
```

The importer uses the same schema, deterministic checks and aggregation as Qwen; missing timing/usage/cost remains null. A schema-valid raw response with an unknown/truncated finish is not a first-attempt success.

## Optional pricing, only with reliable supplied data

No rates are included or assumed. To enable supported estimates, supply a JSON file with exactly these fields: `provider`, `model`, `currency`, `input_per_million`, `output_per_million`, `source_url`, `verified_on` (`YYYY-MM-DD`), `billing_basis` (`standard_uncached`). Use verified nonnegative decimal rates per million tokens and a current authoritative source for the **exact reported model**. Never put a key in this file.

Add `--pricing path/to/verified-pricing.json` to the import command only after checking billing compatibility. Cost is left unknown unless provider/model match, both token counts are present and reply/pricing explicitly agree on the supported billing basis. Cached/special tariffs, discounts and taxes are not computed. Known-subset totals are not the cost of unknown failed/missing observations, and local electricity/hardware cost is not estimated. Recheck pricing before any later paid experiment and agree a budget separately.

## Prepare and score blinded packets offline

After both reports exist:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality_review prepare `
  --reports benchmark-results/quality-study-01/qwen/results.json benchmark-results/quality-study-01/mistral/results.json `
  --seed 91 --output benchmark-results/quality-study-01/blind
```

One report also works for a local-only pilot, but is not a provider comparison. Duplicate runs/models or different manifests are rejected. The packet retains invalid outputs and failures. Share **only** `review-packet.json` and a copy of `ratings-template.json`; do not share `PRIVATE-key.json` or source reports with raters until ratings are finalized.

Review JSON as text. Each rater saves a new `ratings-reviewer-01.json` with a pseudonymous ID, five scores, five checked flags and specific field/ID evidence. Preserve the packet/rubric hashes and review IDs. Blank/null values are unassessed, not poor scores or absent problems. Keep independent raters' files separate; the current tool analyzes one at a time.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.model_quality_review analyze `
  --key benchmark-results/quality-study-01/blind/PRIVATE-key.json `
  --ratings benchmark-results/quality-study-01/blind/ratings-reviewer-01.json `
  --output benchmark-results/quality-study-01/quality-summary-reviewer-01.json
```

Do not edit scores after unblinding without keeping the original and explaining the change. Use the [results template](model_quality_results_template.md) to report all technical and human denominators, failures and limits. No command changes the application's provider routing or approves a saved project.

## Verify the framework offline

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_model_quality.py tests/test_model_quality_review.py
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Normal pytest uses fictional mocked transports; optional live funding checks remain opt-in. Do not set live funding opt-in for an offline test run. The separate local transport follows the [LM Studio chat-completion interface](https://lmstudio.ai/docs/developer/openai-compat/chat-completions) using the existing HTTP dependency, so raw text/usage can be retained without altering the production client or reading cloud SDK credentials.
