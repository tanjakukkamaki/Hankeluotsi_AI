# Qwen and future Mistral comparison: exact operating procedure

Prepared 11 November 2026. **No live Mistral connector, cloud key handling, paid call or completed model comparison is included.** Qwen execution is opt-in; preparation/import/review are offline. All benchmark data is fictional. Do not use this command as a route to send saved projects or private information to a provider.

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

There is deliberately **no `run-mistral` command**. After separate owner approval of model, budget, privacy and transport work, the owner or a separately reviewed connector can make the corresponding requests through the [official Chat Completion API](https://docs.mistral.ai/api/endpoint/chat), documented as `POST https://api.mistral.ai/v1/chat/completions`. Mistral documents [custom structured outputs](https://docs.mistral.ai/inference/conversations/structured-output/custom). No Mistral SDK or executable cloud request is installed/implemented here. Consult current official documentation again before that later work.

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
