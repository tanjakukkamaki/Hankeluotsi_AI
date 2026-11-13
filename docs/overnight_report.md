# Overnight development handoff — 13 November 2026

Started on 12 November and completed after the owner's 13 November status message. Branch `feature/mistral-integration`, HEAD `f44d9fd`; previous uncommitted experiment and private evidence preserved. No commit, push, merge, reset, package installation or production database mutation.

## Delivered behavior

- Additive bounded `ApplicationDraft` / `ReviewReport` v1, with all 13 requested planning areas, stable O/A/R/I/WP links and application-trusted generation metadata. Original idea/concept contracts and prompts are unchanged.
- Saved concept → explicit draft generation → independent deterministic checks → evidence-linked AI suggestions → explicit human approval → escaped approved Markdown export. Immutable approved records and atomic downstream invalidation preserved.
- English/Finnish UI, document rendering, cloud/source/replacement/approval consents tied to exact snapshots, no request on reruns and actionable sanitized errors. The fourth navigation step now points to the implemented section. Existing design/logo, concept PDF and funding features remain.
- Local native reasoning-off stage adapter plus explicit Mistral selection using the existing provider interface. Neither automatic fallback nor model-driven approval/export exists. Missing cloud key/model disables generation.
- Safe Mistral error categories/status distinguish bad request/schema, model/resource access, auth, billing, size, rate limits, timeout and service failure. Official docs support the current endpoint/request shape; the original generic error does not identify its historical root cause. No real cloud call was made, and exact account/model/schema support is still unverified.

## Validation and observed limits

Final full offline suite: **623 passed, 0 failed, 2 skipped in 26.41 s**. The two skips are opt-in public-source checks. Earlier suites passed 616 and 621 cases while tests were being added; these are not substituted for the final run. Focused contract/checker tests, mocked provider failures, cross-process/thread locking, source races, rollback, legacy records, approval/export escaping and FI/EN AppTest are included.

Real local checks used only fictional fixtures/temp databases. Initial draft failures exposed schema copying; stronger instance instructions and a specific schema-echo regression were added. One Finnish Qwen draft then validated and persisted in **29.90 s**. It had one advisory WP/objective mismatch and unknown finish metadata. The real Qwen review's quotations failed exact-source validation, so it was rejected and the valid draft retained. There is no successful real AI-review/approval claim or human quality score. All captured raw model data is private/ignored.

The integrated workflow is proven with fake model outputs; live reliability and domain quality are separate gates. Real-key Mistral access/billing, final-schema 10-attempt stage reliability, independent five-scenario quality evaluation, screen-reader/device/browser and slow-call checks remain unfinished. No automatic correction editor, clarification-answer persistence or draft history was introduced. Regeneration replaces a mutable draft only after fresh acknowledgment.

## Defects identified and corrected

1. Separate project/content-token reads could accept stale generation or unseen approval. Added atomic `load_snapshot` and transactional expected-source comparison for saves/approval; race regressions verify no stale write.
2. Cloud consent could outlive its source. Bound consent and generation to the exact snapshot and recheck before provider access; stale source makes zero model calls.
3. Frontend-disabled actions alone were insufficient. Added Python-side readiness/approval/replacement conditions and snapshot-bound replacement confirmations after regeneration.
4. Finish/status, unsupported legacy payloads and forged partner provenance needed guards. Explicit abnormal finishes, unsupported existing nested contracts and unknown partners marked as supplied facts are rejected without replacing valid records. Native missing finish is retained as unknown.
5. Fractional stored schema versions could be coerced to 1. Repository now refuses unsupported stored types/versions.
6. Local Qwen echoed schema rather than producing data. Clarified the native instruction and added explicit schema-echo rejection; one subsequent real draft validated. Exact-quote review validation was preserved despite live review failure.

Independent agents reviewed security/privacy, persistence, evidence and UI behavior. Final read-only review found no new high-risk issue in the latest source. This is code review, not an independent human domain/accessibility audit.

One new UI test initially attempted to click a disabled AppTest button; it now explicitly asserts the documented disabled-widget rejection, retains the no-extra-call assertion and separately tests queued stale clicks. A stale-approval unit test was made deterministic by changing actual review text, avoiding identical-content/same-timestamp ambiguity. No production assertion or safety check was weakened.

## Files in this slice

New: `draft_schemas.py`, `draft_checks.py`, `draft_workflow.py`, `draft_exporter.py`, `draft_ui.py`; corresponding schema/checker/service/export/UI/CAS tests and fictional draft/review fixtures; this report, `draft_review.md` and `mistral_diagnosis.md`.

Updated: `repository.py`, `mistral_client.py`, `app.py`, `presentation.py`, `i18n.py`, Mistral tests, `README.md`, `PLANS.md`, development log and the historical architecture-proposal status. No table migration. Prior benchmark runner/results, privacy ignore rules, production SQLite, idea/concept schemas/prompts, funding/PDF implementation and logo/assets are preserved.

## Owner's next steps

1. Restart Streamlit to load changed modules and verify the new section using a separate fictional demonstration database. Inspect the whole draft and exact review quotations; do not use real project information.
2. Review these changes and the previous pending benchmark work before deciding on commits. Keep private runtime/model maps out of publication; no paid smoke runs automatically.
3. Address the observed local review citation reliability in a bounded evaluation without relaxing exact evidence checks. Run fresh final-contract draft/review benchmarks; old provisional benchmark schemas do not establish reliability for this slice.
4. For Mistral, use the same configured PowerShell, safe preflight, exact model availability and verified balance/pricing/privacy budget before authorizing one fictional call. The new error category/numeric status can guide a failure without exposing raw provider bodies.

See [Draft & Review operation](draft_review.md), [Mistral diagnosis](mistral_diagnosis.md) and the development log for commands, safeguards and evidence. Actual student hours and learning reflection remain for the owner to record; they were not invented from elapsed machine time.

## Later owner-authorized continuation — 13 November 2026

After this handoff the owner said to continue. A separate bounded follow-up addressed local review citation reliability using review_workflow_v2: the model selects existing source IDs and the application copies exact quotations, while the unchanged validator and persisted ReviewReport v1 remain mandatory. One new local review succeeded in18.94s, saved reviewed with four citations and zero reasoning tokens; the copied fictional draft stayed unchanged and no human approval/cloud call was made. Full suite632 passed,2 skipped (26.94s). See the follow-up in draft_review.md. The failed overnight v1 review above remains a real observation, not retroactively corrected. This later success still needs repeated/human quality evaluation and is not a model-quality winner.
