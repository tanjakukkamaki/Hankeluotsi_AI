# Local Model Benchmark

## Purpose and scope

This benchmark measures first-attempt structured-output reliability for the `concept`, `draft`, and `review` stages using fictional fixtures and the local LM Studio endpoint only. It does not assess funding eligibility. Draft and review use compact benchmark-only Pydantic schemas because their application schemas are scheduled for later project tasks; these preliminary contracts should be reviewed against the final schemas before the formal benchmark.

The runner is intentionally explicit about attempt count and output path. Each attempt makes exactly one model request, so retries cannot inflate first-attempt success. No benchmark was run automatically as part of pytest.

## Run the benchmark

With LM Studio serving the selected local model at `http://127.0.0.1:1234/v1` and **Enable Thinking disabled** for the tested Qwen model, run the formal 10-attempt-per-stage benchmark only after confirming the model/runtime settings:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.benchmark `
  --attempts-per-stage 10 `
  --output benchmark-results/qwen3.5-4b-2026-11-08.json
```

Only add `--model-artifact`, `--quantization`, `--context-length`, and `--runtime-version` after verifying their values; do not guess. The output is JSON and includes individual attempts plus per-stage attempt counts, first-attempt success rates, and mean latency. It is not created until the command is run.

## Recorded attempt fields

Each attempt records its UTC timestamp, stage, attempt number, fictional fixture ID, model identifier, prompt version, JSON validity, Pydantic validity, `finish_reason`, truncation and incomplete-output flags, response time, first-attempt success, optional reviewer quality score, and an error summary when applicable. Generation parameters, endpoint, and supplied model/runtime metadata are recorded at report level. `quality_score` remains null until a human reviews the generated content; the runner does not invent a quality score.

A first-attempt success requires valid JSON, successful Pydantic validation, a normal `stop` finish reason, no incomplete-output flag, and no retry. A missing finish reason is recorded as `unknown` and independently flagged as incomplete. `finish_reason=length` is recorded as truncated and incomplete.

## Preliminary result: 2026-11-08

One real concept-stage request was run using only the fictional `fictional_community_arts_concept_v1` fixture. It was a preliminary smoke test, not the formal benchmark and not a 10-attempt reliability estimate.

| Stage | Model | Prompt | Attempts | JSON | Pydantic | Finish | Truncated | Response time | Outcome |
|---|---|---|---:|---|---|---|---|---:|---|
| concept | `qwen3.5-4b` | `concept_v1` | 1 | valid | valid `ConceptPaper` | `stop` | no | 7.03 s | PASS |

The output contained one objective, activity, expected result, and indicator. No independent quality score was assigned. The local model completed this request with LM Studio's **Enable Thinking** disabled, consistent with the earlier observation that reasoning could consume the completion budget and leave `message.content` empty when thinking was enabled.

## Configuration and limitations

| Setting | Recorded value |
|---|---|
| Endpoint | `http://127.0.0.1:1234/v1` |
| Model identifier | `qwen3.5-4b` |
| LM Studio Enable Thinking | Disabled for the successful test |
| Output token limit | 512 |
| Temperature | 0.2 |
| Prompt version | `concept_v1` |
| GGUF filename / hash | Not verified |
| Quantization | Not verified |
| Context length | Not verified |
| LM Studio/runtime version | Not recorded for this run |
| Hardware / GPU offload | Not verified |
| Draft and review stages | Not run against a live model |
| Formal benchmark gate | Not run; requires 10 independent attempts per stage and at least 8/10 first-attempt successes for each stage |

The preliminary 1/1 concept success is not evidence that the planned 8/10 threshold has been met. Draft/review quality and reliability, exact model artifact, runtime configuration, and hardware behavior still need owner verification. No cloud API was used.
