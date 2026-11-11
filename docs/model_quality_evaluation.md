# Model quality evaluation protocol — version 1

Prepared 11 November 2026. **Framework and evaluation preparation only: no new live Qwen/Mistral benchmark or human study has been performed.** No winner, quality score or API cost is claimed.

The application currently generates early `ConceptPaper` documents. This experiment evaluates that existing contract; it does not implement or evaluate a complete application draft, AI review or final funding application. A schema-valid response can still be misleading, impractical or professionally unusable.

## Frozen fictional scenarios

Source: [ideas_v1.json](../tests/fixtures/model_quality/ideas_v1.json). All people, organizations and localities in the case narratives are invented. Named countries/programmes provide planning context, not verified eligibility. All ten inputs pass the unchanged `ProjectIdea` schema. An incomplete case says information is unknown rather than filling required input fields with invented facts.

| ID | Language | Main topics | Challenge |
| --- | --- | --- | --- |
| Q01 | English | Creative industries, cultural entrepreneurship | Simple six-month enterprise-skills pilot |
| Q02 | Finnish | AI skills, SME digital transformation | Synthetic-data boundary; heterogeneous starting skills |
| Q03 | English | Tourism, regional development, sustainability | Complex conservation/accessibility/travel trade-offs; missing baseline |
| Q04 | Finnish | Cultural wellbeing | Participation outcomes without invented clinical benefits |
| Q05 | English | Cross-border cooperation, competence | Genuine joint value; unknown recognition and partner commitment |
| Q06 | Finnish | Circular economy, SME innovation | No invented material volumes, certification or carbon savings |
| Q07 | English | SME innovation, digital transformation | Ambiguous problem; platform is a proposed solution, not an established need |
| Q08 | Finnish | Creative skills, education | Incomplete target group, scope and resources |
| Q09 | English | AI, cross-border/regional development | Deliberately impossible proposal and automatic-funding assertion |
| Q10 | Finnish | Education, cultural entrepreneurship | Small explicit capacity; Å/ä/ö language handling |

Evaluator notes are withheld from the model and supplied to human raters. Both providers receive exactly the same case text, requested language, system/user messages and JSON schema. Five Finnish and five English cases provide bilingual coverage; they are **not translated pairs**, so language-specific averages are confounded with scenario difficulty.

## Five-criterion human rubric

The authoritative machine-readable rubric is [rubric_v1.json](../tests/fixtures/model_quality/rubric_v1.json). It contains **all five individual anchors for every criterion**, plus strong/weak examples. It is an expert-oriented draft for owner/domain-reviewer approval, not a claim that an expert panel has validated it.

| Criterion | 1 — unusable | 3 — useful starting point | 5 — excellent early concept |
| --- | --- | --- | --- |
| Development need | Misses/replaces the problem | Main need recognized, some generic reasoning | Precise need, causes, context and useful uncertainty handling |
| Objectives | Vague or impossible promises | Understandable change, incomplete measurement/time frame | Prioritized realistic change, explicit baseline/target reasoning |
| Activities | Irrelevant, unsafe or impossible | Mostly plausible, weak sequence/capacity detail | Proportionate sequenced pilot testing critical assumptions |
| Results and indicators | Missing/contradictory measures | Some useful measures, missing denominator/evidence/timing | Clear output/outcome distinction, linked definitions and feasible collection |
| Coherence and professional usability | Contradictory or fabricated rules/guarantees | Useful draft needing identifiable revisions | Clear, coherent decision-support concept with honest material unknowns |

For each criterion, **2** means major revision between anchors 1/3; **4** means a strong early concept between 3/5. Use the fuller criterion-specific anchors in the JSON, not this abbreviated table alone. Equal weights are the preregistered starting choice; changing weights after seeing a provider's outputs requires a new protocol/version and disclosure.

Examples: “wellbeing improves; count meetings” is a weak indicator; “successful practical demonstrations / assessed participants, collected at the final session” defines an observable proportion. Attendance can be a useful output measure but alone does not demonstrate competence. Missing baseline data should trigger a plan to establish it, not a fabricated baseline. A provisional, clearly labelled target is not automatically an unsupported assumption.

Human flags are independent of numeric scores:

- `unsupported_assumptions`: material baseline, partner commitment, resources or context invented as fact.
- `invented_funding_requirements`: unsupported rate/deadline/partner rule, eligibility verdict or funding guarantee. A fictional proposer's funding assertion is not evidence of an official rule.
- `vague_indicators`: unclear unit/denominator/method/timing, activity counts substituted for outcomes, or internally inconsistent measures.
- `unrealistic_feasibility`: impossible scope/timing accepted despite the stated capacity.
- `language_problems`: requested language not followed or substantial editing needed for clear professional meaning.

`true` means the problem was found; `false` means checked and absent; `null` means **not assessed**. Record field/ID evidence and a short explanation. Do not infer clinical effects, applicant eligibility or actual funding rules from a plausible tone.

## Procedure before looking at outputs

1. Owner/domain reviewer approves the cases, anchors, equal weights and proposed early-usability gate. Record any changes before the first measured run.
2. Calibrate raters with the rubric's authored strong/weak examples, not a selectively chosen provider output. Prefer two independent raters; the tool summarizes one pseudonymous reviewer file at a time. Compare disagreements before reconciliation and retain both originals. No inter-rater statistic is automatically calculated.
3. Freeze one manifest. Default is **10 cases × 3 first attempts = 30 outputs per provider**. For a smoke pilot use one trial and a different manifest; do not pool the pilot with the main comparison.
4. Record exact requested/reported model IDs, local artifact/runtime settings where verified, generation parameters and source hashes. Do not guess GGUF, context or hardware details. Thinking mode must be set/verified by the owner; the runner does not change LM Studio settings.
5. Use the same manifest for both providers. Preserve all failures, refusals, unknown finish reasons and truncated outputs. There are no repair retries, SDK retries or hidden warm-up requests.
6. Prepare the blinded packet. Give reviewers only `review-packet.json` and their copy of `ratings-template.json`; keep results, provider identities and `PRIVATE-key.json` private until scores are fixed. View generated output as text/JSON, never execute it.
7. Score independently, cite evidence, check all flags and save a new ratings file. Packet/rubric hashes prevent accidentally applying scores to another experiment's similarly numbered review IDs.
8. Unblind only after ratings are finalized. Report reliability, quality, coverage, flags, uncertainty and cost availability together. Keep failure examples and contradictory results in the final report.

Blinding removes supplied provider/model/trial/latency metadata, not wording inside generated output. A model can identify itself or reveal a distinctive style. Do not silently rewrite its output; disclose such cases as imperfect blinding. Randomized order reduces presentation-order cues but cannot guarantee unbiased ratings.

## What is measured

The benchmark is independent of Streamlit and imports no repository/database code. It reuses the existing `ProjectIdea`, `ConceptPaper`, `build_prompt("concept", ...)` and deterministic concept checker. Production prompts and the existing `LLMClient` are unchanged. A separate bounded local transport is needed to preserve raw responses and token usage, which the production result object does not expose.

The **new benchmark-only** `quality_concept_v1` instructions are visible in `model_quality.py`; the existing base remains `concept_v1`. They request a concise but useful linked concept with explicit uncertainty. Default benchmark budget is 2048 output tokens/120 seconds, temperature 0.2. This differs from the prototype's compact 512-token request. Results therefore describe this frozen benchmark configuration, not an automatic improvement to the production application. Changing messages, schema, settings, dataset, rubric or benchmark source requires a new manifest and fresh paired runs.

| Measure | Meaning |
| --- | --- |
| JSON / Pydantic validity | Parsing and the existing schema, with no repair; extra/transformed keys are rejected by that schema |
| First-attempt success | JSON + Pydantic valid, no request error and exact normal `stop` finish; unknown/truncated/filtered finishes fail this metric |
| Deterministic findings | Existing structural errors/warnings retained independently; a schema pass does not hide broken links |
| Raw output | Preserved verbatim, including invalid/partial output, for diagnosis and human review |
| Latency | Local measured request wall time, including client/network overhead; imported latency only if supplied, otherwise unknown |
| Tokens | Reported prompt/completion/total counts where available; missing counts stay null, never inferred from characters |
| Human quality | Five 1–5 scores and evidence from a person; never automatically assigned by the runner |
| Candidate usability | Proposed owner-review gate: all criteria ≥4, all flags checked/false, structural first-attempt success and no structural errors |

The gate is **early-concept quality**, not funding eligibility, final application approval or a certification of professional readiness. An unknown flag prevents a positive gate. The owner must approve the gate as an evaluation decision.

Statistics include overall/per-case/per-language structural rates, error/truncation counts, observed latency mean/median/standard deviation, and known token/cost totals with observation counts. Human summaries report criterion means, rating coverage, number of rated cases, a mean giving each **rated case** equal weight, case-mean range and usability fraction over **all planned outputs**. Unknown scores are not zeros; unscored failures are not silently dropped from the planned-output denominator. Do not compare quality means without showing coverage. Do not declare a winner when a provider or its hard cases remain unassessed.

Repeated trials of ten fixed ideas are not independent samples of all EU projects. No significance test, population-confidence claim or automatic provider-routing decision is made. Model tokenizers and local/cloud conditions differ; equal token limits are comparable settings, not equal words or equal compute. Cold starts, server load and network conditions can influence latency.

## Cost, credentials and reproducibility boundaries

No pricing values are bundled. Cost is null unless the owner supplies model/provider-specific verified pricing, currency/source/date, complete token counts and a confirmed compatible billing basis. Only standard uncached text-token estimates are supported; unknown caching, discounts, taxes, special reasoning/tool tariffs or missing usage keep estimates unknown. Estimates cover only supported observations and are not invoices or total local computing cost.

The local endpoint is restricted to credential-free loopback `/v1`. Direct compatible HTTP uses the `httpx2` dependency already supplied by pinned OpenAI 3.6.0, avoiding SDK ambient credentials/custom headers. Redirects, proxy-environment use and automatic retries are disabled. No cloud key is read. Imported responses contain no credential fields. Exceptions are recorded as bounded error categories instead of raw messages that might contain headers. Raw imported model/provenance data is user-supplied evidence, not independently attested API execution.

Commands create only new JSON files/directories; existing destinations are rejected before generation. Per-attempt checkpoints survive interrupted runs, but there is no automatic resume. Treat an interrupted run as incomplete and disclose it; do not selectively drop failures or reclassify a rerun as its first attempt. File/source/prompt/schema hashes make changes visible, but do not replace preserving the reviewed source and environment. No changes to approved/saved projects are possible through this tool's persistence path.

## HAMK final submission

This provides a reproducible method, a frozen scenario set, transparent rubric, failure evidence and human-review workflow for explaining why a model's output is useful rather than merely well-formed. Include the reviewed source version, model settings, technical rates, complete human-rating coverage, examples, limitations, actual student hours and accepted/rejected AI suggestions in the final reflection.

The 8 November 10/10 results used fixed provisional contracts and did not establish content quality; do not combine those counts with this new experiment. The separate December requirement for full draft/review/approval/export workflows and five-scenario evaluation remains. Extend the protocol to approved final schemas later; this task does not start those stages or replace their acceptance criteria.

See [commands and future Mistral mapping](model_comparison_plan.md) and the [blank results template](model_quality_results_template.md).
