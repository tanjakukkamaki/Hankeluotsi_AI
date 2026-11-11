# Model quality results — blank reporting template

**Status: NOT RUN / NOT HUMAN-SCORED.** Replace placeholders only with observed evidence. This template is not a benchmark result. Generated `responses-template.json` and `ratings-template.json` provide the matching machine-readable input forms; `results.json` and the human summary are produced only by their explicit commands.

## Study identity

| Item | Recorded evidence |
| --- | --- |
| Study/experiment ID and manifest SHA-256 | Pending |
| Reviewed source commit, uncommitted state and code hashes | Pending |
| Dataset/rubric/base prompt/benchmark prompt/schema versions and hashes | Pending |
| Run dates, requested languages, cases/trials and request-order seed | Pending |
| Temperature, token/timeout limits, retry policy | Pending |
| Qwen requested/reported IDs; verified GGUF/hash/quantization/context | Pending; unknown values stay unknown |
| Local server/runtime/version/hardware/offload/thinking setting | Pending |
| Future Mistral requested/reported IDs and collection method | Not connected / not run |
| Pricing source/date/currency and billing basis | Not supplied; cost unknown |
| Reviewer pseudonyms, calibration and blinding limitations | Not scored |
| Owner approval of rubric and proposed usability gate before outputs | Pending |

## Technical reliability and performance

| Measure | Local Qwen | Future Mistral |
| --- | --- | --- |
| Planned/completed attempts | Not run | Not run |
| Valid JSON / all planned attempts | Unknown | Unknown |
| Pydantic valid / all planned attempts | Unknown | Unknown |
| First-attempt valid nontruncated normal-stop / all attempts | Unknown | Unknown |
| Request failures, timeouts, unknown finishes, truncations | Unknown | Unknown |
| Outputs with deterministic errors / warnings | Unknown | Unknown |
| Mean/median/standard-deviation latency; observed n | Unknown | Unknown |
| Known input/output/total tokens and coverage | Unknown | Unknown |
| Known-subset API estimate, currency and missing-cost count | Unknown | Unknown |
| Exact response model identity missing/changed | Unknown | Unknown |

Report per-case and per-language summaries alongside overall figures. Ten ideas with repeated trials do not represent all EU projects; do not treat trials as independent evidence for a population-level claim. Distinguish measured local request latency from imported measurements and unknown values.

## Human content quality

| Criterion / coverage | Qwen | Mistral |
| --- | --- | --- |
| Fully scored outputs / all planned outputs; rated cases / 10 | Not scored | Not scored |
| Need understanding, 1–5 | Not scored | Not scored |
| Objective clarity/measurability, 1–5 | Not scored | Not scored |
| Activity relevance/feasibility, 1–5 | Not scored | Not scored |
| Results/indicator quality, 1–5 | Not scored | Not scored |
| Coherence/professional early usability, 1–5 | Not scored | Not scored |
| Case-weighted mean and case-mean range | Not scored | Not scored |
| Flag counts and unassessed counts, each of five flags | Not assessed | Not assessed |
| Candidate usable / all planned; gate unassessed count | Not assessed | Not assessed |

For each criterion/flag, include specific output field/ID evidence and representative strong/weak excerpts, including difficult scenarios and failures. Identify baseline/target fabrication, unsupported official funding claims, denominators/method mismatches and unrealistic scope. A score is not a funding eligibility verdict. Do not declare a winner from a high conditional mean with poor failure/rating coverage.

## Interpretation and HAMK reflection

- Which needs/scenarios did each model handle well or poorly? Separate language, complexity and feasibility observations from causal claims.
- How did numeric reliability differ from human usefulness? What substantive revisions were needed?
- Were raters independent/blinded, and where was blinding imperfect? Record disagreement before reconciliation.
- Did any configuration or rubric change after outputs were inspected? Disclose it; a changed experiment needs separate results.
- Which exact limitations remain, and what does the owner recommend for later model/provider use? No automatic routing or cloud rollout follows this report.
- What did the student learn, what work was delegated to Codex, and what were actual independently recorded hours?
- How does this early-concept evidence support, but not replace, the December full-workflow evaluation?

**Decision:** Pending actual runs, independent content scoring and owner review.
