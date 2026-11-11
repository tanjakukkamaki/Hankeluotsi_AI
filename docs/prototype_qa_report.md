# Prototype quality assurance — 11 November 2026

## Readiness assessment

**The implemented vertical slice is technically ready for owner review and a fictional-data prototype demonstration on 22 November. Submission readiness remains conditional on the owner's review, recorded demonstration, model configuration evidence and current teacher requirements.** No startup, persistence or PDF regression was reproduced. The December workflow is incomplete and must not be presented as finished.

This assessment follows the prototype acceptance criteria in [PLANS.md](../PLANS.md): idea input, local generation, strict concept validation, SQLite save/reopen and recoverable errors. Draft generation, AI review, human approval in the UI and approved Markdown export are final-delivery work. Funding research is an optional research aid, not an eligibility assessment.

## Follow-up: three Medium findings corrected — 11 November

**All three reported Medium findings have focused fixes and passing regression checks, pending owner review.** The original QA evidence below remains a historical baseline. Submission conditions concerning model configuration evidence, independent quality review, demonstration and teacher requirements remain open.

| Finding | Correction and verification |
| --- | --- |
| Misleading prize relevance | Extended the existing non-art phrase handling to cover `culture within research` and `culture in research`. This removes organizational/scientific wording from arts evidence without changing source facts, applicant rules, status or access to the result. Replaying the originally captured Rising Innovators record against the original idea/concept now gives **Low, 0/100**, previously Medium, 29/100. No fresh funding request was needed. |
| Generate-button contrast | Primary styling now includes Streamlit's actual `primaryFormSubmit` kind and its hover state. Actual browser foreground/background measurements in **both languages**, at all four widths, gave **5.95:1** normally (white on `#206E71`) and **7.47:1** on hover (white on `#185E61`). |
| Page-language metadata | A minimal local script sets the live document's `<html lang>` to the selected `fi` or `en` on rendering/reruns. It uses the installed Streamlit 1.64 `st.html(..., unsafe_allow_javascript=True)` interface, confirmed in the installed source and [official API documentation](https://docs.streamlit.io/develop/api-reference/text/st.html). Only two fixed locale literals can enter the script; no project/model/source text is interpolated or sent anywhere. Real browser checks confirmed default English and correct FI/EN metadata after repeated switches. |

Changed implementation files: `hankeluotsi/funding_matching.py`, `hankeluotsi/presentation.py`, `assets/styles.css`. Added eight collected regression cases in `tests/test_funding_matching.py` and `tests/test_presentation.py`: phrase variants, ranking and retained access, missing applicant information, unchanged call facts, a positive arts-prize counterexample, both button languages/states, page-language reruns and isolation from hostile project text. These tests initially reproduced all three defects; focused verification then passed **40 tests**.

Complete offline command, with a temporary default database and live-source opt-in unset: `.\.venv\Scripts\python.exe -m pytest -q` → **367 passed, 0 failed, 2 skipped in 18.33 s**. Skips remain the two optional public-source integration cases. Existing Qwen validation/integration mocks, persistence, PDF, consistency and funding suites passed; no new real-model request or public funding query was made for these display/matching corrections.

Actual current-source Streamlit/Edge checks used a separate fictional database at `http://127.0.0.1:8517`: both interfaces at **1440×1000, 820×1180, 390×844 and 320×800**, normal/hover contrast, root language, selector visibility, unchanged saved content, six programme guides and a PDF download passed with no exceptions or document overflow. Desktop/mobile screenshots were visually inspected. Temporary evidence is under `%TEMP%\hankeluotsi-medium-fixes-5r0mxoff`; the dedicated browser was closed after checks and the isolated preview retained for review. The normal 8501 instance was not restarted; restart it before assessing updated imported modules there.

The pre-existing QA documents were preserved. The demo checklist was left byte-identical; the development log was appended. No project schemas, prompts, repository, Qwen configuration/client, PDF code, source adapters, verified funding facts, logo or normal database content changed. No packages, providers, features or Git history actions were added. Final whitespace and preservation checks passed.

Remaining limits: deterministic matching is still a small vocabulary and can make other semantic errors; a low score is not an eligibility decision. This fix marks the interface's default language, not the automatically detected language of every saved/source passage. Streamlit's initial static shell remains English until the client renders the selected UI language. A full screen-reader/physical-device/mixed-language accessibility audit remains outstanding, and these targeted fixes do not establish full WCAG conformance. The explicit JavaScript API and internal button-kind selector should be rechecked after a Streamlit upgrade.

## Initial QA scope and preservation

- Reviewed `AGENTS.md`, `PLANS.md`, README, development history, model/source/language/UI documentation and current implementation/tests.
- Initial branch: `feature/live-funding-search`; HEAD: `f50211bfee3a22414ab2c669452694dfd1329ab5` (`Add bilingual support and finalize prototype features`). Working tree and index were clean.
- No branches, commits, staging, model settings, dependencies or application code were changed. Only this report, the demo checklist and the development log were written.
- Captured SHA-256 hashes of all 71 initially tracked files, HEAD/index state and a read-only logical dump hash of the normal workspace database. Before documentation changes, every tracked file and the database matched. Final checks permit only the requested documentation changes.
- All new projects, failed requests, downloads and browser evidence used temporary fictional-data databases. The normal `localhost:8501` application, existing data and local model service were left running unchanged.

## Environment and method

| Item | Verified environment |
| --- | --- |
| OS / interpreter | Windows 11, Python 3.12.0 |
| Browser | Dedicated headless Microsoft Edge 156.0.4314.58, real browser/Streamlit WebSocket session |
| Existing dependencies | Streamlit 1.64.0; Pydantic 2.13.5; OpenAI client 3.6.0; pytest 8.4.2; ReportLab 4.4.4 |
| Model endpoint | Loopback LM Studio; `qwen3.5-4b` used for both new generations |
| Application under browser test | Absolute current workspace `app.py`, workspace cwd, explicit temporary `HANKELUOTSI_DB_PATH` |
| Primary preview | `http://127.0.0.1:8514`, fictional database only |
| Failure preview | Separate port 8515, temporary database, unreachable process-local model/proxy endpoints |

The offline suite ran from a fresh **tracked-file archive of HEAD**, without `.env`, ignored databases or untracked helpers. It used the existing environment's interpreter/dependencies, with live funding integration disabled and an isolated database path. This checks tracked-source completeness; it is not a fresh Windows installation or a network package-install test.

Local temporary evidence is under `%TEMP%\hankeluotsi-prototype-qa-wprsvfn7`: test output, structured browser results, fictional PDFs/PNG renders, captured public funding payloads and preservation checks. It is not committed, is not portable submission evidence and may be removed by normal temporary-file cleanup. The results below are recorded here so the report does not depend on those files surviving.

## Initial QA test results

| Check | Result / practical limit |
| --- | --- |
| Complete offline `python -m pytest -q` | **359 passed, 2 skipped, 20.39 s**. The two public-source integration cases are deliberately opt-in. |
| Existing environment `python -m pip check` | Passed: no broken requirements; all five direct package pins match. No packages installed. |
| Actual browser startup | Current absolute source path served successfully; inspected sessions had no Streamlit exception blocks. |
| Required-field validation | English and Finnish errors appeared; blank submissions created no records. |
| Real Finnish concept generation | Validated and saved; `qwen3.5-4b`, `concept_v1`, **14.76 s** displayed response latency. |
| Real English concept generation | Validated and saved; same model/prompt, **6.50 s** displayed response latency. |
| Language switching | Repeated FI/EN switches preserved selected projects, original English/Finnish content and IDs; no extra records were generated. |
| Save/reopen after server restart | Both new concepts reopened. All seven primary QA records compared equal to their complete pre-restart snapshots. |
| Approved fixture preservation | Initial approved fictional record, approval timestamp and other seeded records stayed equal in both QA databases. This does not test a production approval UI. |
| Concept consistency | Clean records showed no structural findings. Broken-reference fixture displayed one error (`UNRESOLVED_OBJECTIVE_REFERENCE`, A1 → O99) and one warning (`OBJECTIVE_WITHOUT_ACTIVITY`, O1). |
| Saved idea without a concept | Reopened with an explanatory message rather than an exception. |
| Model unavailable | Finnish recoverable timeout message; idea retained in `created`, no invalid concept saved; existing records unchanged. Switching languages did not retry generation. |
| General funding research | Six programme guides rendered; clearly unknown call dates/status and visible guidance/source information. |
| Live funding / ranking / filters | Actual browser retrieved 36 records; all categories remained available; Low filter showed 20, Horizon/open/Low combination 17; empty selection showed recovery guidance. |
| Funding reruns | Filters and FI/EN switching retained the original explicit-search timestamp. Offline transport/AppTest tests additionally verify no automatic requests and no project text in source requests. |
| Funding unavailable | Separate failure preview displayed source notices, no verified live calls, official links and six fallback guides. Failed programme-description fetches showed unavailable labels rather than successful retrieval dates. |
| PDF downloads | Real browser downloads: short EN/EN labels **1 A4 page**; EN/FI labels **1**; FI/FI labels **1**; long FI **2**. Also downloaded the genuinely generated Finnish concept after restart. |
| PDF visual inspection | Windows PDF renderer used to inspect EN page 1, FI page 1 and both long-FI pages. Readable headings/content, disclaimer, Page/Sivu footers and `ä ö å Ä Ö Å`; both indicator/method groups remained together. Long questions flowed naturally onto page 2. |
| PDF regression coverage | Offline tests cover compact layout, indicator grouping across page boundaries, oversized content, preserved IDs/text, translated labels and Finnish multi-page numbering. |
| Responsive browser | Both languages at **1440×1000, 820×1180, 390×844, 320×800**: header selector visible, document width matched viewport, no exceptions. Finnish programme-research view also checked at 320 px. |
| Accessibility sample | Form/select controls had accessible labels; logo had localized alt text; a keyboard Tab moved focus with a visible outline; reduced-motion preference produced `scroll-behavior: auto`. Two issues below remain. |
| Git whitespace/security checks | `git diff --check` passed; new documents also checked separately. See security scope below. |

The live model checks are **two smoke attempts**, not a bilingual reliability benchmark. Pydantic validates structure, not Finnish fluency, usefulness or indicator quality. For example, the English output described a percentage but its measurement method only said to track completed tasks; human review must clarify the denominator. The Finnish output also benefits from language review. No generated content was edited.

Two QA-driver assertions needed correction: a repeat PDF download overwrote the browser's existing same-name download, and a partial message lookup did not translate like the complete displayed error. The downloaded files and full Finnish error were inspected directly, and the remaining checks completed without application workarounds or repeated model generations. These were harness assumptions, not application failures.

## Official live-source evidence

The browser search and a separate bounded adapter capture both returned **16 Aurora + 20 EU Portal records** on 11 November, around 19:21–19:22 UTC. Titles, identifiers, source URLs and available original date values were checked against the exact official CSV/API payloads for all **36** captured records. Adapter tests validate source status/filter contracts; current statuses are assessed separately from source labels.

| Source | Observed capability / limitation |
| --- | --- |
| [Interreg Aurora official calls](https://www.interregaurora.eu/projects/calls-for-applications-2/) | Official page and its linked timetable CSV worked: **16** published records, all currently assessed closed in this snapshot. Historical/indicative timetable data does not imply an open application window. |
| [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals) | Documented public search adapter worked: **20** Horizon Europe topics in a two-page window. Results can include prizes as well as project funding; a programme/topic match is not applicant suitability. |
| [EURA 2021](https://eura2021.fi/hakuilmoitukset/) | No live call adapter in this version; EAKR, ESR+ and JTF remain reviewed general guidance with official links. No new live interface was implemented or claimed. |
| [Business Finland](https://www.businessfinland.fi/en/services/funding/) | General guidance/official links only; call-level parsing and pagination are not integrated. Business Finland instruments are not necessarily EU-funded. |

Combined date/status assessment: **18 open, 17 closed, 1 unknown, 0 upcoming**, with deadlines available on **35/36** records. The zero upcoming count describes this retrieval window; upcoming behavior is covered by offline tests. One multi-stage Horizon topic had no unambiguous single deadline and correctly remained unknown. Date-only values retain unverified exact time/timezone; snapshots older than six hours become unknown until an explicit refresh.

Example captured official record: [Rising Innovators category — HORIZON-EIC-2026-PRIZE-WIP-RisingInnovators](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-EIC-2026-PRIZE-WIP-RisingInnovators), opening `2026-09-02`, deadline `2026-12-01`, date-only values, retrieved `2026-11-11T19:22:23.807698+00:00`. This is a historical QA observation, not a promise that the call remains open when this report is read.

Individual official topic pages were not all opened interactively. Their identifiers/canonical URLs were verified against retrieved official metadata, and Aurora provenance against its linked CSV. Reruns do not recheck every URL's availability. Portal API evidence is a POST interface; opening its evidence URL as an ordinary browser GET may not reproduce the request. Use the official topic link for human verification. No project descriptions are accepted by the fixed-request source adapters; comparison runs locally.

## Findings and recommended fixes

No blocking functional regression was reproduced in the initial QA. The following rows preserve that investigation; the three Medium findings are corrected by the follow-up above, pending owner review. Model-evidence and reproducibility follow-ups remain open.

| Priority | Finding and evidence | Recommended bounded action |
| --- | --- | --- |
| Before submission / model gate | The existing 8 November benchmark records 10/10 structural first attempts per stage, but uses fixed fixtures, provisional draft/review schemas and null human quality scores. Exact GGUF artifact, quantization, context, LM Studio/runtime version and hardware/offload remain unverified; an alternative-model comparison is not documented. | Owner verify/record actual settings and compare a practical alternative by the planned 16 November gate. Review content quality independently. Rebenchmark final draft/review contracts later; do not treat today's two attempts as that benchmark. |
| Medium — matching quality; corrected | A women-innovators prize was ranked **Medium, 29/100** for the community-arts fixture. Its source excerpt says “a culture within research and innovation organisations”; the vocabulary treated this as cultural/creative evidence. The selected first prize varied between the two source snapshots. | Phrase-context correction and regressions now pass; captured record becomes Low/0 while remaining accessible with unchanged facts. Matching still requires human interpretation. |
| Medium — accessibility; corrected | Actual Generate button is `kind="primaryFormSubmit"`, originally white text on `#278F91`, 13.44 px/600 weight: **3.87:1** contrast. Dark-teal CSS missed the form variant. | Both language buttons now measure 5.95:1 normally and 7.47:1 on hover. [WCAG text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) requires 4.5:1 for normal-size text. |
| Medium — accessibility; corrected | `document.documentElement.lang` originally remained `en` when the UI was Finnish. | Live root language now follows `fi`/`en`, verified through switches/reruns. Mixed-language passages and full assistive-technology testing remain outside this focused fix; see [W3C page-language guidance](https://www.w3.org/WAI/WCAG22/Understanding/language-of-page.html). |
| Documentation / reproducibility | README still calls the expanded app a PR5 prototype and refers to “tomorrow's” UI review. `.env.example` includes old PR0/cloud placeholders; no `.env` loader exists. Direct dependencies are pinned, transitives are not locked. | Refresh wording/config examples in a separate reviewed documentation change. Use explicit PowerShell environment variables and activation-free commands in the checklist. Verify a clean installation before claiming fresh-machine reproducibility. |

The earlier Solar Radiation Modification example is covered by fictional offline ranking tests, which passed; that exact topic was not in today's bounded live window. The specific prize false positive is now corrected, but passing regressions do not eliminate other semantic ranking errors.

## Draft & Review: actual state and final-delivery plan

The workflow card is visibly **planned**, with `aria-disabled="true"` and no navigation/action. There is no production Draft & Review screen.

- Production schemas define `ProjectIdea` and `ConceptPaper` with linked objective/activity/result/indicator structures. They do **not** define final `ApplicationDraft` or `ReviewReport` contracts.
- `benchmark.py` has compact **benchmark-only** draft/review Pydantic contracts and fixtures; `prompts.py` has versioned stage names. These are groundwork, not a finished application pipeline.
- Repository methods for saving draft/review, approval locking, idempotency, invalidation and approved-export access already exist and pass offline tests. The approved fixture used in QA exercises preservation of this groundwork, not real draft generation or human approval in the browser.
- There is no `pipeline.py` or Markdown `exporter.py`. `load_for_export` returns an approval-gated record; it does not serialize a Markdown document. Current PDF export is a concept-draft feature and is not evidence of approved final-application export.
- Current deterministic UI checks inspect concepts. Final work-package/partner-role/draft checks remain to be agreed. Runtime output is bounded to 512 tokens; final stage budgets and reliability need separate testing.

Proposed order, **for owner approval, not implementation in this task**:

| Target | Priority / acceptance gate |
| --- | --- |
| By 16 November | Complete owner-verified model/configuration evidence and alternative comparison. Review existing preliminary benchmark scope and current concept language behavior. |
| Before 22 November prototype | Review this QA/diff, record a short fictional-data demonstration and actual student hours, verify submission instructions/time, retain a saved-concept fallback. Do not promise a finished draft/review workflow. |
| 23–26 November | Agree bounded versioned final `ApplicationDraft`/`ReviewReport` contracts, work packages and stable links in PLANS before coding. Decide compatibility for existing records explicitly; no silent migration/coercion. |
| 24–30 November, after contract approval | Draft service/pipeline and UI: strict validation, deterministic link checks, explicit generation, operation guards, atomic invalidation and failure preservation. Demonstrate `concept_ready` → `draft_ready` and regression tests. |
| 1–4 December | AI review supplements visible deterministic findings; explicit human approval locks the record; only approved content gets escaped Markdown export. Benchmark final contracts with at least 10 independent first attempts/stage and the 8/10 engineering gate. Feature freeze 4 December. |
| 5–10 December | Use the five fictional scenarios and 1–5 rubric in PLANS, reviewed before outputs. Owner independently scores completeness/coherence/indicators/review usefulness; target at least 4/5 complete workflows. Record failures, latency, settings and limitations in the still-missing `docs/evaluation.md`. |
| 11–13 December | Fresh setup check, final demo/report, reproducibility details, AI-use disclosure, actual effort and self-reflection; submit by the teacher-confirmed deadline. |

No PR7 or other final-stage implementation was started. Dates above are a proposed prioritization aligned with PLANS, not claims of completed work.

## Repository reproducibility and security

README lists the correct basic Python/venv/requirements/Streamlit commands and local Qwen thinking-off setup. All required source, SVG/CSS/theme, fixtures and font assets needed by the offline suite were present in the tracked export. `pip check` passed in the existing environment. Python 3.11 compatibility, a new dependency download/install, other operating systems and an independent fresh machine were **not** tested. The checklist supplies an activation-free PowerShell alternative without changing execution policy.

The normal database is anchored to the workspace, not arbitrary cwd. Launching the absolute current `app.py` from its root also loads the intended theme. `.env` is not loaded automatically; set supported process environment variables explicitly. This build uses local inference; sample cloud variables do not mean an implemented cloud fallback. Verify the submission branch/commit rather than assuming GitHub's default branch contains this version.

Security/path inspection found:

- No tracked `.env`, SQLite/database, cache or virtual-environment files among the 71 initial tracked files.
- No historical `.env` or SQLite/database paths in the 23 reachable commits examined.
- No matches for the bounded OpenAI/AWS/private-key token patterns scanned across those commits. Only filenames/counts were reported, not secret values.
- Ignore checks covered `.env`, `*.sqlite3`, `*.db`, `.pytest_cache` and `.venv`. The public Portal `SEDIA` identifier is a documented public interface identifier, not a private API secret.
- Temporary QA databases, helper scripts and captured responses stayed outside the repository. This task adds no credentials or real project data.

This is a targeted tracked-file/history review, not a guarantee that every possible credential format or semantic confidential detail has been detected. Owner identity/course attribution in project instructions is intentional; project test examples were fictional.

## Boundaries and owner next action

No full screen-reader, physical-device, exhaustive keyboard, browser-zoom or PDF accessibility/tagging audit was performed. Mobile live-filter controls were not separately exercised with a live snapshot; responsive header/form/project and programme-guidance views were checked, and live filtering was exercised on desktop. Clicks during in-flight requests were not simulated; repository/client tests cover operation/failure guards. A saved language selection is session state, not a durable account preference.

Funding catalogue coverage, source availability and heuristic relevance are limited; requirements and exact deadlines need human checking. Historical PDFs/screenshots and older benchmark results are not evidence that external information remains current. Full final-stage functionality, representative human quality evaluation and submission approval remain the owner's responsibility.

Review the [demo checklist](prototype_demo_checklist.md), the three documentation changes and the findings above. No commit, push, merge or branch switch was performed; approval is pending.
