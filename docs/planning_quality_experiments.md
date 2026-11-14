# Expert planning prompt experiments — 11 November 2026

**Historical study notice,13 November:** This document and its source recipe/results retain the earlier compact-v1 control wording. Current production prompts have since changed under a separate owner-authorized task; see [readiness and current planning pilot](mistral_readiness.md). The historical recipes and outputs were not rewritten. New plans record their current outer wrapper version and source hashes and are not the old study. The old baseline is explicitly tested as distinct from current concept_v2 input; do not present it as today's production control or combine cohorts across revisions.

This is an exploratory local-model study, not a production prompt rollout, completed funding application or independent human expert validation. The production application, prompts, schemas, SQLite and approved workflows remain unchanged. The final results and AI-assisted content observations below concern fictional cases only.

## Questions and experimental design

Can stronger structured instructions improve the need → objective → activity → result → indicator chain? Does an explicit clarification gate avoid inventing essential answers? Can a fresh-context critique identify defects and improve a proposed revision without importing new facts or damaging another connection?

The study reuses the ten versioned ideas and five-criterion `expert_quality_v1` rubric from the existing quality framework. It uses the same local transport, raw-response model, safe error handling, JSON/Pydantic validation, deterministic concept checker and aggregation. A small shared `execute_request` helper also serves the original runner; its default concept behavior is covered by the existing regression tests. There is no second cloud client or replacement application pipeline.

| Approach | Experimental recipe | Scope and limitation |
| --- | --- | --- |
| Baseline | `production_wording_control_v1` | Exact compact production input wording, including one objective/activity/result/indicator and empty assumptions/questions. Uses the common experimental token budget, not the production 512-token limit. |
| A | `structured_planning_A_v1` | One structured generation with needs/evidence, participant change, feasible sequencing, operational indicators and explicit unknowns. |
| B | `clarification_gate_B_v1` → `clarified_concept_B_v1` only if allowed | Prioritized questions before planning. Essential unanswered gaps pause the job. No user answers are fabricated; a pause is not a generated concept or a request failure. |
| C | `needs_analysis_C_v1` → `analysed_concept_C_v1` → `fresh_context_critique_C_v1` → `proposed_revision_C_v1` | Separate analysis, initial candidate, critique and proposed revised candidate. Critique receives original idea/candidate/checks in a fresh context, not earlier reasoning. All calls use the same Qwen model, so this is not independent expert judgment. |

Recipes are stored separately in [planning_prompts_v1.json](../experiments/planning_prompts_v1.json). The existing `prompts.py`, compact application helper and base `concept_v1` stay unchanged. The baseline wording is guarded by an offline comparison with the actual application helper. Experimental auxiliary JSON contracts are benchmark-only and are not production draft/review schemas.

Default experimental settings: `qwen3.5-4b`, temperature 0.2, 1536 output tokens and a 120-second HTTP phase timeout per call; one trial per case/strategy. The timeout is not a strict total wall-clock limit. Request order is shuffled with the frozen seed 37. There are no repair retries, hidden warm-ups or automatic resumes. Both requested/reported model identifiers, actual request text/schema, prompt version, raw output, usage, measured latency and validation errors are retained.

Initial source ideas and per-call settings match across approaches. B/C naturally have additional calls and derived contexts, so their total compute/token/latency budgets are not equal to a one-shot method. Compare end-to-end cost and completion coverage as well as surviving output quality. Same token limits across different languages/models do not imply equal words, compute or determinism.

## Ten-case coverage and planning limitations

| Case | Topic / difficulty | Main quality questions |
| --- | --- | --- |
| Q01 EN | Creative enterprise, simple | Pricing/value competence versus offer-count outputs; twelve artists and six months are supplied; partner commitments are not. |
| Q02 FI | AI/digital SME skills | Synthetic-only boundary, heterogeneous competence, useful/safe trial versus perceived satisfaction; eight firms are supplied. |
| Q03 EN | Tourism/regional development, complex | Local-service benefit versus wetland pressure; baseline/accessibility/transport unknowns; no invented ecological threshold. |
| Q04 FI | Cultural wellbeing | Participation experience and access barriers versus unsupported clinical effects; qualitative evidence and consent need a defensible method. |
| Q05 EN | Cross-border education | Joint learning value, educators versus learners, language/commitment/recognition unknowns; no invented programme rules. |
| Q06 FI | Circular economy/SMEs | Material quantity versus safety and economic viability; missing material/cost baseline must not be invented. |
| Q07 EN | Ambiguous business platform | Problem diagnosis before solution design; disagreement is a reason for clarification, not evidence that future consensus is impossible. |
| Q08 FI | Incomplete creative competence | Target group, change, location, timing and resources unknown; null partner information is not confirmed absence. |
| Q09 EN | Deliberately unrealistic AI project | Challenge universal employment/automatic funding claims and infeasible two-week/five-country scope without presenting a provisional alternative as agreed. |
| Q10 FI | Accessible online events, simple | Ten volunteers, one instructor, three sessions/two months; event count and participation do not alone prove accessibility competence. |

All ten scenarios cover needs, objectives, target groups, activities, outputs/results, indicator methods, uncertainty, feasibility and bilingual terminology. Longer-term impact attribution requires evidence; a plausible activity cannot guarantee it. The current `ConceptPaper` has no formal work-package, partner-role, budget or risk register fields. Those are explicit scope gaps, not permission to invent keys or claim a full application. C's auxiliary analysis can discuss delivery/risk dependencies without implementing an expanded draft contract.

Missing information must remain distinct from a proposed assumption, a supplied fact and a user-confirmed answer. A model can violate that distinction even when its JSON passes validation. Numeric targets/methods can be proposed, but their provisional status and justification need checking; an invented baseline or official threshold is not a harmless wording choice.

## Reproduce the local experiment

Use the reviewed source and new output paths. Existing artifacts are never overwritten. The following commands make real local calls only after explicit opt-in; the plan command itself is offline.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.planning_experiments plan `
  --model qwen3.5-4b --trials 1 --max-tokens 1536 `
  --output benchmark-results/planning-quality-repeat/experiment-plan.json

.\.venv\Scripts\python.exe -m hankeluotsi.planning_experiments run-local `
  --execute-local --plan benchmark-results/planning-quality-repeat/experiment-plan.json `
  --output benchmark-results/planning-quality-repeat/qwen-run
```

Default coverage is all ten ideas × four strategies. `--case-ids Q01 Q02 Q08 Q09` can prepare a separately labelled smaller pilot. A plan contains source, recipe, data/rubric/schema hashes and all strategy jobs; changes require a separate new plan. Verify LM Studio/model settings manually; listing a model ID does not establish its GGUF artifact, quantization, context, runtime, thinking setting or hardware/offload. No such unverified values are claimed here.

Each completed job immediately writes a new `strategy-case-trial.json`, retaining every stage's raw text and intermediate validation, including failed/incomplete responses. `results.json` provides coverage/technical summaries and references the complete jobs. If interrupted, existing job files remain, but the run is incomplete and is not silently resumed/reclassified as first-attempt evidence.

## How to interpret the evidence

JSON/schema/ID findings are deterministic observations. Indicators' relevance, need justification, realism and professional wording require interpretation. The AI-assisted qualitative notes added on 12 November are recorded in this report, separately from the original responses. No numerical AI quality scores have been assigned. `human_quality` remains null; the five-criterion rubric is available for later owner assessment. Paused/failed strategies have no final candidate score; their missing coverage must remain visible. A high mean among surviving candidates cannot erase pauses or failures.

Neither a same-model critic nor this Codex assessment is independent human expert validation. The assessor also knows the strategies, so these qualitative judgments are unblinded and exploratory. One trial per case cannot establish robust superiority. Do not tune the recipes after seeing these outputs and then report the changed prompts as if they were the original frozen run.

## Future Mistral comparison

No Mistral connector or paid call is implemented. After separate approval, select an exact model and verified budget/privacy/transport policy. The existing provider protocol and shared request/assessment functions are reusable, but a cloud adapter/collector still needs review. Recreate the experiment with the same fictional cases, recipe versions, limits, timeout/retry policy and trial counts, changing only the declared model/provider. Use each provider's own intermediate outputs; do not feed Qwen's analysis to Mistral and call it an equivalent independent strategy run.

Capture every actual adaptive stage request/response, original latency, model ID, finish reason and token usage. Do not invent missing usage or cost. The existing verified-pricing helper can support compatible known billing later, but no pricing is supplied or estimated in this experiment. Record server-side differences and aggregate total calls/time as well as final candidate validity and quality.

The original `model_quality import-responses` command is for its frozen **single-stage** manifest. This adaptive experiment's journals are a different format and must not be passed off as that format or given fake model IDs to distinguish strategies. A later approved collector should return the same `Reply` contract and invoke the experimental recipe orchestrator; normalization/export and strategy-blinded human assessment need a reviewed bridge. Original provider-study artifacts and human ratings remain untouched.

## Draft & Review and human decisions

See [the architecture proposal](draft_review_architecture_proposal.md). Prioritize actual clarification answers, approved expanded draft contracts, evidence-linked semantic review, reviewable proposed changes, user acceptance/rejection, atomic invalidation/rechecking and approval-gated export. No production stage was implemented by these experiments.

Before any rollout, a human planning/domain expert should assess a blinded representative sample, verify any alleged official requirements, decide feasible scope and validate the measurement logic. The owner must approve prompt/configuration changes and resolve missing facts. Preserve the original and assess whether a revision introduces new errors. This supports the HAMK final method/evidence/reflection; it does not replace the full-workflow evaluation or human approval.


## Recorded results and completion audit ? 12 November 2026

**Status:** Saved run and retrospective documentation audit complete; human quality evaluation and repeat experiments remain pending. No winning prompt or production rollout is approved. This section supersedes any implication above that numerical quality scores or a finished comparison already existed.

### Evidence and reproducibility

All evidence is local and fictional: [frozen plan](../benchmark-results/planning-quality-2026-11-11/experiment-plan.json), [aggregate results](../benchmark-results/planning-quality-2026-11-11/qwen-run/results.json), and 40 individual strategy/case/trial journals in the same directory. Journals retain exact requests, response schemas, raw replies, intermediate candidates, model critiques, proposed revisions and recorded validation. The 42 original JSON artifacts and experimental recipes were preserved byte-for-byte during this completion task. No model generation was rerun.

An offline reconstruction using `load_plan`, `build_stage`, `assess` and `summarize_jobs` verified all frozen source hashes, the aggregate plan digest, all 68 request/message hashes and response schemas, raw-response JSON/Pydantic/consistency assessments, and aggregate summaries against the journals: **zero mismatches**. This establishes internal consistency with the saved evidence, not independent verification of server execution or semantic quality. The C Q04 failure remains in the denominator; B pauses remain separate from failures and completed plans.

The plan was created at 2026-11-11 21:05:54 UTC (23:05:54 Finland); results were saved at 21:18:36 UTC (23:18:36 Finland). These are artifact timestamps, not student working hours. A shared benchmark helper extraction is the sole pre-existing tracked code modification; the runner, its tests, recipes, results and two documents were untracked. All were inspected and retained. No production application/prompt/schema/repository change is part of this task.

### Verified identifiers and settings

| Item | Recorded evidence |
| --- | --- |
| Requested model | `qwen3.5-4b` in plan and all 68 stage records |
| Reported model | `qwen3.5-4b` in all 68 replies; provider `lm_studio` |
| Settings | One trial/case/strategy; temperature 0.2; max_tokens 1536 per call; HTTP phase timeout 120 s; order seed 37 |
| Base / recipe / rubric | `concept_v1` / `planning_prompts_v1` / `expert_quality_v1` |
| Baseline | `production_wording_control_v1`: 10 calls |
| A | `structured_planning_A_v1`: 10 calls |
| B | `clarification_gate_B_v1`: 10 calls; `clarified_concept_B_v1`: **0 calls**, not exercised live |
| C | `needs_analysis_C_v1`: 10; `analysed_concept_C_v1`: 10; `fresh_context_critique_C_v1`: 9; `proposed_revision_C_v1`: 9 |
| Output mode | Recorded JSON schema per stage; no repair retry |
| Finish reason | `stop` for 68/68 replies, including the schema-invalid Q04 reply; no recorded truncation |
| Exact model artifact / environment | GGUF filename/hash, quantization, loaded context, LM Studio/runtime version, GPU/CPU offload and hardware **not recorded/verified** for this run |
| Thinking / other server defaults | Not established by these journals; do not inherit settings from the 8 November benchmark |
| Endpoint | Runner defaults to loopback `http://127.0.0.1:1234/v1`; actual endpoint is not persisted per reply, so default configuration alone is not runtime proof |

The exact requested/reported API identifier is verified from saved records; it does not identify the exact model weights. No live server request was necessary for this retrospective audit, and a currently loaded model would not prove historical settings. Reported token usage is retained in replies; no API pricing or cost estimate was supplied. Local electricity/compute cost is unknown.

### Automated outcomes

| Strategy | Planned jobs | Final candidates | Pauses | Failed jobs | Calls | JSON/Pydantic-valid calls | Total call latency (s) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Baseline | 10 | 10 | 0 | 0 | 10 | 10/10; 10/10 | 64.65 |
| A | 10 | 10 | 0 | 0 | 10 | 10/10; 10/10 | 142.17 |
| B | 10 | 0 | 10 | 0 | 10 | 10/10; 10/10 (clarification objects) | 104.62 |
| C | 10 | 9 | 0 | 1 | 38 | 38/38; 37/38 | 445.54 |

All 29 final concepts passed JSON/Pydantic validation and had `stop`; this is **not** 29 high-quality plans. A Q09 has two unresolved result-reference errors despite schema validity. A Q02/Q04/Q09/Q10 and final C Q10 have advisory linkage warnings. Final baseline concepts have no deterministic findings, despite substantive weaknesses below. C Q04 failed at `C_generate`: indicator I3 has `result_ids=["O2"]`, rejected by the result-ID pattern. Its critique/revision were correctly not called. The reply was valid JSON and ended normally, so this is schema failure, not truncation.

**Denominator caution:** `final_concept_checks` in the original aggregate summarizes only candidate-ready jobs. Its C success rate of 9/9 is conditional on surviving all stages; end-to-end candidate completion is **9/10**. B has zero final-concept attempts. Absence of findings on auxiliary analysis/critique JSON does not mean semantic checks passed; the concept checker does not run on those auxiliary contracts.

### Case-by-case technical comparison

Cells show status, total measured seconds across all calls in that job, and final-concept findings. **V** = valid final JSON/Pydantic with `stop`; **P** = clarification pause, no concept; **F** = failed stage. W/E are warning/error finding counts, not quality ratings. C timings include analysis, generation, critique and revision where reached; failed C Q04 includes only its two executed calls. Latencies exclude human work and are not equal-compute comparisons.

| Case | Baseline | A | B | C |
| --- | --- | --- | --- | --- |
| Q01 | [V, 5.84s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q01-trial-1.json) | [V, 13.54s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q01-trial-1.json) | [P, 8.02s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q01-trial-1.json) | [V, 46.19s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q01-trial-1.json) |
| Q02 | [V, 7.45s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q02-trial-1.json) | [V, 15.90s; 1W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q02-trial-1.json) | [P, 10.59s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q02-trial-1.json) | [V, 65.37s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q02-trial-1.json) |
| Q03 | [V, 5.36s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q03-trial-1.json) | [V, 11.17s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q03-trial-1.json) | [P, 10.35s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q03-trial-1.json) | [V, 42.49s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q03-trial-1.json) |
| Q04 | [V, 7.47s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q04-trial-1.json) | [V, 19.39s; 1W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q04-trial-1.json) | [P, 13.09s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q04-trial-1.json) | [F, 24.30s; C_generate schema](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q04-trial-1.json) |
| Q05 | [V, 5.76s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q05-trial-1.json) | [V, 12.14s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q05-trial-1.json) | [P, 8.84s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q05-trial-1.json) | [V, 36.49s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q05-trial-1.json) |
| Q06 | [V, 7.36s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q06-trial-1.json) | [V, 14.71s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q06-trial-1.json) | [P, 11.26s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q06-trial-1.json) | [V, 51.27s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q06-trial-1.json) |
| Q07 | [V, 6.02s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q07-trial-1.json) | [V, 16.91s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q07-trial-1.json) | [P, 9.84s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q07-trial-1.json) | [V, 37.27s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q07-trial-1.json) |
| Q08 | [V, 6.25s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q08-trial-1.json) | [V, 10.41s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q08-trial-1.json) | [P, 12.24s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q08-trial-1.json) | [V, 43.73s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q08-trial-1.json) |
| Q09 | [V, 6.09s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q09-trial-1.json) | [V, 12.75s; 1W/2E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q09-trial-1.json) | [P, 7.84s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q09-trial-1.json) | [V, 44.31s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q09-trial-1.json) |
| Q10 | [V, 7.04s; 0W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/baseline-Q10-trial-1.json) | [V, 15.27s; 1W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/A-Q10-trial-1.json) | [P, 12.56s; no concept](../benchmark-results/planning-quality-2026-11-11/qwen-run/B-Q10-trial-1.json) | [V, 54.13s; 1W/0E](../benchmark-results/planning-quality-2026-11-11/qwen-run/C-Q10-trial-1.json) |

### Case-by-case AI-assisted quality observations

**Assessment provenance:** The following are Codex's retrospective, unblinded textual judgments on the original ideas and saved outputs, made on 12 November. They are not deterministic verdicts, independent expert validation or pre-registered numerical scores. C's model-produced critiques are preserved as experimental outputs, not accepted facts. Human scores remain **unscored/null for every case and strategy**, including failures and pauses.

| Case | Baseline observation | A observation | B observation | C observation / remaining concern |
| --- | --- | --- | --- | --- |
| Q01 EN | I1 at least addresses explaining cost/value, but uses interviews rather than demonstrated performance. | Adds cost modelling; R3 introduces ?at least 5? without making the target clearly provisional. | Blocks partly on funding eligibility even though recipe says no selected call alone should not block an early concept. | Adds denominator/timing, but I1 counts submitted proposals while its description claims offers tested; R3 confidence is not demonstrated competence. |
| Q02 FI | Synthetic-data boundary retained; trial count does not establish usefulness or safety. | I2 uses a self-rated 1?5 ability measure; A1 has no linked result. Finnish phrasing remains awkward. | Re-asks beneficiaries already supplied and labels the synthetic-only boundary an unsupported assertion. | I2 treats management's safety opinion (mean >=4.0) as safety evidence; adds partner-role confirmation and four indicators despite the three-indicator instruction. |
| Q03 EN | I1 introduces ?one step per hour? as an unsupported ecological threshold. | Risk-zone counts and co-design participation do not measure local-service benefit or habitat preservation; volunteer expertise is assumed. | Pauses for clarification rather than inventing answers; whether all questions are essential needs owner judgment. | Acknowledges missing baseline, but assumes expert consensus can define low-impact without one; I1 relies on unspecified provisional thresholds. |
| Q04 FI | Six workshops / attendance counts replace participant access/change; objective wording is unclear. | O1 better expresses participation possibility, but positive-response counting lacks a clear denominator and R1 has no indicator. | Pause is recorded; no live evidence of a concept after real clarification answers. | No final concept: C_generate I3 points to O2 as a result. Raw output also presents unresolved planning matters as confirmed statements; cannot assess a completed revision. |
| Q05 EN | Survey-based ?techniques taught and assessed? gives weak evidence of practical joint learning. | Joint design is clearer, but pages finalized are outputs and I2's 60% target lacks an explicit provisional rationale. | Pause protects unknown commitments; no completed plan demonstrates utility of the extra step. | I2 converts a five-point pre/post survey to percentage improvement without specifying the conversion; partner commitment by month 3 remains an assumption. |
| Q06 FI | Kilograms alone do not establish safe or economically viable reuse. | Recognizes sorting and economics but assumes material safety, which is the matter to test. | Pause preserves missing information; real answers and continuation remain untested live. | I1 describes a ratio but labels unit kpl; I2 combines safety and economics as kpl/EUR, which cannot by itself demonstrate both. |
| Q07 EN | Diagnostic workshop appropriately precedes platform construction; consensus recognition is still a limited outcome. | Adds diagnosis but also commits to a digital prototype before the problem is established; 80% agreement is a proposed threshold without clear authority. | Pausing is plausible for this intentionally ambiguous case; usefulness of the exact questions still needs review. | Critic treats current disagreement as a defect in a future consensus objective. Final assumptions still say a problem can be isolated without further data, despite critique recommending removal. |
| Q08 FI | Forced compact concept has no assumptions/questions by design, so material unknowns are not surfaced in those fields. | Background claims need has been demonstrated (?on osoitettu?); assumptions invent basic knowledge and open_questions is empty despite incomplete input. | Pausing is plausible because target group/change/place/resources are intentionally incomplete. | Shifts to defining scope/resources, but indicator I2 only confirms a schedule while R2 also promises a budget. This is preparatory planning, not a validated intervention. |
| Q09 EN | Endorses universal training and guaranteed immediate employment despite impossible scope/resources. | Replaces scope with partnerships/funding submission and unresolved R2/R3 references; still assumes volunteer delivery in two weeks. This is text only, not an actual submission. | Correctly challenges automatic EU approval, guaranteed jobs and two-week mass delivery; no fabricated answers. | Challenges original claims, but I3 measures timeline ?reduction? from two weeks when realistic delivery would likely require more time. Critique proposes ages 25?60/two regions without supplied authority; these suggestions require rejection or owner decision. |
| Q10 FI | Changes the supplied three practice sessions to two and counts events rather than accessible delivery competence. | Measures self-reported participation, re-asks participant numbers and leaves A1 unlinked to a result. | Known facts say three sessions but question invents eight (?kahdeksan?); asks funding despite null not establishing an essential blocker. | Preserves three sessions, but critique introduces ?k?ytt?j?tunnustus? as an accessibility criterion and revision copies it. Final A1 has no linked result; event counts still do not prove accessibility. |

C demonstrates why critique is not an automatic quality guarantee: Q07 retains a challenged assumption, Q09 retains a reversed timeline metric, and Q10 copies a dubious technical term from critique. These are evidence-backed concerns, not a measured average revision effect. All nine initial/final C pairs remain available for owner comparison; no quantitative improvement rate is claimed.

### Limitations and exact remaining work

This is one local model, ten cases (five FI/five EN), one trial each. No statistical superiority, language-level reliability or professional funding readiness can be inferred. Baseline forces shorter content and empty unknowns; its 1536-token experimental allowance differs from the app's 512-token allowance. B/C consume different numbers of calls and contexts. The current ConceptPaper has no final draft/work-package contract. This experiment does not replace the separate 8 November structural benchmark or full-workflow evaluation.

Before selecting or deploying a recipe:

1. Owner/domain expert applies the existing five-criterion rubric to anonymized representative outputs, records evidence and separate human scores, and compares all nine C initial/revised pairs for new errors. The existing single-stage blinding/import tools are not an approved adaptive-study bridge; do not silently mix formats.
2. Collect actual owner answers for B and run a separately frozen continuation study. Include simple sufficiently specified ideas (Q01/Q10), genuinely incomplete ideas (Q08), and impossible scope (Q09); measure unnecessary pauses and repeated questions. No fabricated answers or retrospective alteration of this run.
3. Repeat frozen strategies on the same cases with at least three independent trials, retaining failures and all call latencies. Any changed prompt needs a new version/plan and separate results. Test source-fact preservation, indicator validity, cross-references, and whether C worsens a previously correct candidate.
4. Record exact GGUF hash/file, quantization, context, runtime, thinking and hardware/offload settings at the time of the next run. Current API identifier evidence alone is insufficient for exact reproduction.

No additional model calls, prompt revisions, Mistral integration or Draft & Review implementation were performed during this completion. Their implementation requires a separate bounded task. Human scores remain blank; there is **no declared winning prompt**.

### Suomenkielinen yhteenveto ja kolme t?rkeint? parannusta

Kokeessa k?siteltiin 40 tapausta nelj?ll? menetelm?ll? ja tehtiin 68 Qwen-kutsua. Baseline ja A tuottivat kumpikin 10 konseptia, B pys?htyi aina lis?kysymyksiin ja C tuotti 9 konseptia. Rakenteellinen kelvollisuus ei takaa hyv?? hankesuunnitelmaa: tuloksissa oli keksittyj? l?ht?tietoja, heikkoja mittareita ja virheellisi? viittauksia. Ihmisarvioita ei ole pisteytetty eik? voittajaa voida nimet?.

1. **S?ilyt? annetut faktat ja rajaa lis?kysymykset olennaisiin.** Erota puuttuva tieto, ehdotus ja vahvistettu tieto. ?l? keksi resursseja tai pys?yt? varhaista ideointia pelk?n rahoitusohjelman puuttumisen vuoksi (Q01/Q08/Q10).
2. **Mittaa tavoiteltua muutosta oikealla menetelm?ll?.** M??rit? yksikk?, laskentas??nt?, hyv?ksymiskriteeri, ajankohta ja tiedonkeruu. Mielipide ei todista turvallisuutta eik? tapahtumam??r? saavutettavuutta; turvallisuus ja taloudellisuus tarvitsevat eri mittarit (Q02/Q06/Q09/Q10).
3. **Tarkista korjaukset uudelleen ja s?ilyt? ihmisen p??t?svalta.** Korjausehdotuksen pit?? perustua alkuper?iseen tietoon, ratkaista havaittu ongelma ja l?p?ist? viite- sek? merkitystarkistus. Saman mallin kritiikki voi lis?t? virheit? (Q07/Q09/Q10). N?it? parannuksia ei viel? otettu tuotantoon.


### Offline verification ? 12 November 2026

Full suite: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` ? **439 passed, 2 skipped in 17.52 s**. Environment: `HANKELUOTSI_LIVE_FUNDING=0`, `HANKELUOTSI_DB_PATH` set to a unique temporary SQLite path, `PYTHONDONTWRITEBYTECODE=1`. The two skipped cases are explicit opt-in public-source checks. Tests use fictional data and mocked generation; no live Qwen/cloud/public-source request was made. The increase from the earlier 421 passes is 18 existing experimental test cases; no new implementation or tests were needed for documentation completion.

`git diff --check` is run after the documentation updates; final outcome is recorded in the development log. Untracked new text files are also checked separately because ordinary Git diff does not cover them. Model/runtime identification is limited to saved evidence as described above. Owner review remains required before any commit or next implementation task.

Final checks passed: `git diff --check` (exit 0), separate untracked-text whitespace/conflict-marker scan, and SHA-256 preservation comparison. Only this report, PLANS.md and development_log.md changed during completion. Original experimental evidence, code/prompts/schemas and root SQLite files remained byte-identical; branch/HEAD/index were preserved.
