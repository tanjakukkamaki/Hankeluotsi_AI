# Qwen vs Mistral: five-case concept-quality pilot

Date: 12 November 2026. **This is an incomplete comparison.** Mistral execution is blocked by missing configuration and unverifiable billing prerequisites. No paid model calls were made. No model winner or independent human expert assessment is claimed.

## Method and preflight

The task began with a clean working tree on `feature/mistral-integration`, HEAD `f44d9fd`. The branch was preserved. AGENTS, PLANS, comparison/evaluation instructions and existing benchmark code were inspected. Production application, prompts, schemas, saved SQLite data and prior benchmark results are not changed.

The process environment contains neither `MISTRAL_API_KEY` nor `MISTRAL_MODEL`; Windows User/Machine key-presence checks were also false. Only booleans were printed, never a credential. A key set in a different shell would not establish availability to this process. No exact Mistral model, available account balance or reliable model-specific price could be established. Therefore the paid-call gate failed before any Mistral request; no attempt was made to guess a model, price, balance or key location. Account/model identity, usage balance and current official pricing must be verified before resuming.

The local `/v1/models` inventory includes `qwen3.5-4b`; no other listed model was used. Five local first attempts were authorized and run as the independent Qwen arm. This does not complete the paired comparison. There are no automatic retries, repair attempts, warm-ups or substitute outputs from older studies.

## Frozen inputs and settings

Source: existing `fictional_ideas_v1` cases and `expert_quality_v1` rubric. Cases were selected before viewing outputs to cover a simple idea, synthetic AI skills, complex trade-offs, incomplete information and impossible claims. Three are English, two Finnish; they are not translated pairs and cannot isolate language effects.

| ID | Language | Input description |
| --- | --- | --- |
| Q01 | EN | Twelve fictional artists, six-month service-pricing/customer-development pilot |
| Q02 | FI | Eight fictional SMEs testing AI with synthetic data only; varied competence/privacy practices |
| Q03 | EN | Fictional rural off-season tourism routes with habitat/accessibility/transport trade-offs |
| Q08 | FI | Creative-skills idea with unknown target group, place, time and resources |
| Q09 | EN | Intentionally impossible mass AI training, two-week timeline and guaranteed employment/funding claims |

Exact original inputs, schemas, messages, hashes and request order are in [source-manifest.json](../benchmark-results/qwen-mistral-five-2026-11-12/source-manifest.json). The [selection protocol](../benchmark-results/qwen-mistral-five-2026-11-12/selection-protocol.json) freezes the five request hashes and one-attempt policy. The unchanged framework normally expects ten cases; this bounded run uses `create_manifest(Settings(trials=1))`, then `model_copy` filtering only `requests` by the five case IDs, followed by existing `run`, `LocalProvider`, `assess` and checkpointing. Its execution manifest retains the full frozen ten-case catalogue but executes exactly five request records. It is stored in the results report.

The stock `load_manifest`/Mistral collector intentionally rejects a subset. **Do not run the stock ten-case cloud command as a continuation of this five-case study.** A reviewed five-request execution path is required before cloud continuation. Reproduce the local selection from the saved source version and request hashes; any changed settings require a new separately labelled experiment. No framework source change was needed for this local arm.

| Setting | Qwen arm | Mistral arm |
| --- | --- | --- |
| Requested API model | `qwen3.5-4b` | Not configured; no identifier guessed |
| Prompt / base version | `quality_concept_v1` / `concept_v1` | Same frozen messages planned; not sent |
| Temperature | 0.2 | Planned 0.2; not executed |
| Maximum output tokens | 2048 per call | Planned 2048; not executed |
| HTTP phase timeout | 120 seconds | Planned 120 seconds; not executed |
| Trials / retries | One per case; zero retries | Zero requests / zero retries |
| Order seed | 37 (request ordering, not generation seed) | Same order planned |
| Response contract | Existing ConceptPaper JSON schema | Same schema planned |
| Tools / retrieval | None | None planned |

The [native local metadata capture](../benchmark-results/qwen-mistral-five-2026-11-12/local-model-metadata.json) reports GGUF format, Qwen3.5 4B, `Q4_K_M`, 3,383,082,464 model bytes and loaded context 8192. These are server-reported metadata, not an independently hashed GGUF file. Model maximum context 262144 is distinct from the loaded context. Flash attention and GPU KV-cache offload are reported enabled; actual layer offload, hardware and runtime versions remain unknown. Reasoning capability defaults to `on` in the catalogue, but the actual per-request thinking state is not established. No server settings were changed or historical settings inherited from prior runs.

## Validation and quality-assessment separation

Automated checks record nonempty content, valid JSON, Pydantic validity, finish/truncation, references and linkage findings. A first-attempt success requires valid nontruncated schema output with `stop`; an ordinary HTTP response or token usage alone is not success. Completeness is structural only: valid required fields/lists plus the separate checker. Semantic completeness requires inspecting content against the original idea.

AI-assisted qualitative assessment, where assessable output exists, uses the existing five anchored 1–5 criteria: development need/reasoning; objectives; activities; results/indicators; coherence/professional usefulness. Scores must cite exact fields/IDs and flag invented facts, vague objectives, weak measures, unresolved references, feasibility and Finnish/English problems. These would be unblinded Codex judgments, not independent expert or human ratings. Empty/non-assessable outputs receive no invented semantic scores. Human scores remain null until the owner independently evaluates outputs.

## Cost gate and uncertainty

No Mistral call was made, so cloud generation attempts/successes/retries are all zero. There is no API invoice or usage statement to reconcile. Recorded spend attributable to this run is no paid calls; exact billed account cost is not independently verified. No numeric worst-case estimate is reliable without the exact model, input-token upper bound, supported context/schema overhead, verified input/output prices, currency and account balance. Output tokens alone do not bound input cost.

For the resumed five-case study, a conservative planning formula allowing one retry per failed request is `C_max = 10 * (B_input * P_input + 2048 * P_output) / 1,000,000`, provided B_input truly bounds all billed input including schema/system overhead, and the verified per-million prices cover the selected model and tariff. Five calls without retries have a 10,240 output-token cap; ten total requests with one retry each have a 20,480 output-token cap. These are token bounds, not money estimates. Do not interpret unknowns as zero prices, free credits or permission to spend. The current task's paid limit must also be enforced before any resumed calls.

Local API billing is not applicable; electricity/hardware costs are unknown. Reported model token usage is evidence of token accounting, not evidence of a professionally useful answer or verified cloud cost.

## Offline checks and remaining work

Full offline pytest command with live funding disabled, a temporary default database and bytecode writes disabled: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` → **480 passed, 2 skipped in 22.12 s**. The two skips are opt-in public-source checks. These tests validate software, not Qwen/Mistral content quality. Final whitespace/preservation checks are recorded in the development log.

Before completing a comparison: make the key and exact model available to the execution process; independently verify account balance and current official model pricing; bound both input/output costs; review a strictly five-request cloud continuation; and preserve all failures/retries. Match the frozen inputs and settings, then prepare paired blinded outputs and separate mapping, followed by independent owner rubric ratings. If local reasoning settings are changed after this run, rerun both arms as a new labelled experiment rather than mixing results. Five cases and one trial cannot establish population-level superiority, causal language effects, funding eligibility or final-application readiness.


## Recorded outcomes

All five local requests returned an ordinary response with an empty assistant-content string, `finish_reason=length`, and exactly 2048 reported completion tokens. These are five failed first attempts, not five usable concepts. No automatic or manual retry was made. Original captured reply fields and per-attempt checkpoints are preserved in [the Qwen report](../benchmark-results/qwen-mistral-five-2026-11-12/qwen/results.json). The unchanged transport captures assistant content and selected metadata, not the full HTTP envelope or any separate reasoning field; this limits root-cause diagnosis.

| Case | Reported model | Seconds | Prompt/completion tokens | JSON / Pydantic | Finish / completeness | Mistral |
| --- | --- | ---: | --- | --- | --- | --- |
| Q01 | `qwen3.5-4b` | 42.59 | 361 / 2048 | fail / fail | length; no concept | Not run |
| Q02 | `qwen3.5-4b` | 42.35 | 436 / 2048 | fail / fail | length; no concept | Not run |
| Q03 | `qwen3.5-4b` | 41.73 | 387 / 2048 | fail / fail | length; no concept | Not run |
| Q08 | `qwen3.5-4b` | 41.02 | 388 / 2048 | fail / fail | length; no concept | Not run |
| Q09 | `qwen3.5-4b` | 46.24 | 367 / 2048 | fail / fail | length; no concept | Not run |

Local first-attempt success: **0/5 (0%)**; JSON 0/5, schema 0/5, truncation 5/5. No parsed concept exists on which to assess reference integrity: `structural_error_outputs=0` does **not** mean clean references. Transport error count is zero, distinct from generation failure. Mistral success rate is **undefined (0 attempts)**, not 0% and not 100%.

Local mean response time: **42.79 s**; median **42.35 s**; range **41.02–46.24 s**; total measured call time **213.93 s**. Total reported prompt/completion tokens: **1939 / 10240** (12179 total). These times describe truncated failures; there is no successful-concept latency or cross-provider latency comparison. API costs remain unknown/not applicable as described above.

### AI-assisted quality observations

All five criteria are **not assessable** for all five Qwen outputs and all five unrun Mistral slots. The [AI-assessment artifact](../benchmark-results/qwen-mistral-five-2026-11-12/ai-quality-assessment.json) preserves null scores, reasons and assessment provenance. There is no textual evidence to score development reasoning, objective clarity, feasible activities, indicator quality, coherence or professional Finnish/English. No unsupported-fact or language flag is declared absent merely because no content was returned. No semantic quality average or model ranking is computed. Human expert scores remain unscored.

Empty content with full completion usage is consistent with budget being consumed before a final answer, potentially by reasoning, but the saved response fields do not establish the cause. Verify the actual thinking/runtime configuration before a new run. Do not conclude that Qwen concepts are intrinsically worse than an unavailable Mistral model. Earlier successful Qwen outputs used other settings/prompts and cannot replace these observations.

### Anonymized review material

[Review folder](../benchmark-results/qwen-mistral-five-2026-11-12/blind/) contains Q01/Q02/Q03/Q08/Q09 folders with **A.json** and **B.json**, randomly assigned model labels with provider metadata omitted. One arm preserves the original empty captured strings; the other is explicitly `not_run` with null output, not an invented Mistral answer. **PRIVATE-model-map.json** is separate and must be withheld from the evaluator, along with this report and unblinded source artifacts until ratings are complete. A human-ratings template contains ten slots with five null scores each.

This preserves the requested A/B structure but is **not a completed two-model blinded quality review**: there are no assessable concepts from either arm. Status patterns/report knowledge can reveal identities; absence cannot be anonymized into real evidence. No independent preference result can be inferred. The public packets contain no provider names/model identifiers in metadata or captured output.

### Audit and recommendation

Offline reconstruction verified the source-plan digest, selected execution-manifest digest, exact five original request records and all validation observations using existing `verify_report`: **zero mismatches**, recorded in [audit.json](../benchmark-results/qwen-mistral-five-2026-11-12/audit.json). Only five local generation calls and zero cloud calls were executed. Preserve this evidence as an unsuccessful local generation pilot plus a blocked cloud preflight.

Priorities: (1) verify actual local reasoning/output-budget behavior and create a separately labelled five-case repeat only after owner review; (2) establish exact Mistral model, available balance, current pricing and reliable worst-case budget before any paid call; (3) run an actually paired bounded experiment, then independently rate complete A/B concepts with the existing rubric. No production change or winning model is recommended from this evidence.

Final preservation checks passed: `git diff --check`, separate new-text scan and SHA-256 comparison against the initial snapshot. Only PLANS.md and development_log.md changed among pre-existing files; this report and the evidence/review folder are new. Production sources, SQLite and prior results are unchanged. Branch/HEAD remain feature/mistral-integration / f44d9fd; no staged changes, commit, push or merge.


## Appended execution-diagnosis follow-up - 12 November 2026

The original five-case results above remain unchanged. A later, separately authorized diagnostic task tested only Q01 in three explicit attempts, retaining each under ignored .benchmark-private. The 2048-token reasoning=off request still used 1408 reasoning tokens and truncated; a reasoning_effort=off attempt failed immediately without a retained exact error envelope; a standard-field 4096-token test consumed 3874 reasoning tokens and returned empty final content/length. This directly establishes a reasoning-budget failure mode but does not retrospectively prove old per-call thinking settings or a successful fix. No new valid concept, paid call, human score or model winner was obtained.

See [execution diagnosis and commands](benchmark_execution.md). The new wrapper adds safe same-shell configuration checks, model availability checks, token-limit failure reporting and private diagnostics while reusing existing benchmark/review contracts. Private mapping/runtime files are now ignored, not deleted; the old evidence remains intact on disk. Final offline suite: 501 passed, 2 skipped (22.72 s). Next owner action is to disable Enable Thinking in LM Studio and authorize a fresh single smoke with actual counters checked before another benchmark. Mistral smoke remains pending exact model/balance/pricing/cost verification and approval.
