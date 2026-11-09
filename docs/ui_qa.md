# UI polish and end-to-end QA — night of 8–9 November 2026

The existing redesign was continued on `feature/live-funding-search`. Owner-created WIP commits `899bee4` and `cd391ca` were preserved. No Git commit, push, merge, branch change or history rewrite was performed by this QA continuation.

## Current interface

The original navy/teal compass and native wordmark remain in the header. White cards, a four-step workflow, compact forms, saved-project controls and a single concept document use the existing palette. Source details and long funding excerpts are expandable; essential status, deadline uncertainty, retrieval date and the official call link remain visible. General programme suggestions stay separate from actual live calls.

The first three workflow links point to the project workspace until a project is selected, then to the corresponding concept/funding sections. Draft/review is explicitly planned. A unique project-ID suffix distinguishes records with identical titles. The default SQLite path and asset paths remain stable when launched from a different directory; explicit database overrides are kept.

The original local vectors are [compass mark](../assets/hankeluotsi-mark.svg) and [wordmark](../assets/hankeluotsi-logo.svg). They were inspected at 16, 24, 48 and 96 px, with the wordmark at normal/double size. SVG titles/descriptions, the interface image alt text and native heading/label semantics are retained. The files contain no scripts, embedded foreign content or external image references. No external image service or logo download was used.

## Verification completed

| Area | Actual result |
|---|---|
| Correct app/source | An isolated localhost server launched the repository's absolute `app.py` from `C:\Users\tanja\OneDrive\Työpöytä\Uusi kansio\assignment_9\Hankeluotsi_AI`. The preview used temporary fictional SQLite data. Existing user app servers were left alone. |
| Input and local generation | A browser-submitted fictional idea generated a valid concept through local LM Studio `qwen3.5-4b`, prompt `concept_v1`, in **6.68 s**. It was saved and displayed with intact IDs/content. This is one smoke check, not a reliability benchmark. |
| Saved concepts | Browser selection reopened saved ideas/concepts. Offline regression tests also verify independently selectable duplicate titles and source assets when launching outside the repo. |
| Consistency | A clean fixture showed 0 errors/0 warnings. A separate fictional fixture showed 1 unresolved-reference error and 1 disconnected-objective warning with the correct finding codes. |
| PDF | The browser downloaded actual PDFs. Windows' built-in PDF renderer displayed one-page A4 output with all sections, links/IDs, disclaimer and page number. A second downloaded fixture visibly rendered `ä, ö, å, Ä, Ö, Å` and a Finnish title correctly. PDF generator code was unchanged. |
| Programme research | All six reviewed programme cards rendered. Offline guides remained usable during a deliberate connection failure. An explicit online-description attempt through the unavailable test connection showed six unavailable-description labels and retained the guides. |
| Live calls | An explicit browser action returned **36 source records** in that observation: Aurora and the bounded Horizon Europe window. The call page/evidence URLs, date precision, current/source status, uncertainty and retrieval time rendered. Counts/catalogue contents can change. |
| Reruns | Selecting a genuinely different retrieved call kept the same explicit-search timestamp. Offline spies also verify no repeated retrieval on reruns. No click-during-request concurrency claim is made. |
| Source failure | A second temporary server used an unavailable localhost proxy in its own environment. Live search produced source notices, official links and no fabricated calls; offline guidance continued to work. No system proxy/security settings were changed. |
| Approved records | The approved fictional record, including its approval timestamp, compared equal before/after browser inspection and guidance actions in both healthy and failure previews. |
| Normal project data | The real workspace database's read-only logical hash matched the snapshot taken before QA. Protected schema/prompt/repository/model/consistency/funding files also matched. The app's concept prompt and operation-ID helper were unchanged. |
| Responsive browser | Real headless Edge checks at **1440×1000**, **820×1180**, **390×844** and **320×800** found zero horizontal overflow, zero leaked closed-expander bodies and zero Streamlit exceptions in the inspected concept/funding views. |

Primary button text was checked against its rendered dark-teal background. Captions no longer inherit the faint default opacity, keyboard focus remains visible, and reduced-motion preferences are respected. This is a focused accessibility check, not a formal full accessibility audit.

## Bugs and stability corrections

- Closed expander bodies leaked into the page with the installed Streamlit/browser combination. Explicit closed-details visibility now prevents that clutter and keeps hidden controls out of the visible layout.
- Identical project titles/state labels were ambiguous in selection. Short ID suffixes preserve distinct options; an end-to-end regression selects both records without mutations.
- A cwd-relative default database could select a different file when launching elsewhere. The project-root default is now centralized and tested; configured paths are respected.
- Workflow links without a selected project led to empty sections. They now direct users to the available workspace first.
- During refactoring, UI tests exposed a duplicate presentation-container key; it was corrected before final verification.
- A long-running preview retained an older imported presentation module. A fresh process loaded the correct code. Restart instructions are included below; runtime import-reload machinery was not added.

## Automated result

Complete final offline suite: **307 passed, 2 skipped in 8.87 s**. The two public-source checks remain opt-in. Normal tests use mocked model/funding responses and an isolated default database for the shell smoke test. `git diff --check` passed; new text files were checked separately as well.

The new `tests/test_presentation.py` checks accessible/local SVG content, stable workspace paths, duplicate saved-title selection, source assets under a different cwd and usable workflow destinations. Existing generation, SQLite, PDF, consistency, programme research and live-source tests remain in place.

## Visual evidence

All screenshots contain fictional project data or public funding information:

- [Desktop header and workspace](qa/desktop-workspace.png)
- [Desktop concept](qa/desktop-concept.png)
- [Tablet concept](qa/tablet-concept.png)
- [Mobile concept](qa/mobile-concept.png)
- [Desktop funding card](qa/desktop-funding.png)
- [Mobile funding card](qa/mobile-funding.png)
- [Original logo size proof](qa/logo-proof.png)
- [Downloaded Finnish PDF render](qa/finnish-pdf.png)

## Reviewing tomorrow

1. Stop the old Streamlit process with **Ctrl+C** in its terminal. Start a fresh process after Python-module or theme changes; reload the browser with **Ctrl+F5**.
2. In PowerShell, run from the exact workspace without needing to activate a PowerShell script:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\tanja\OneDrive\Työpöytä\Uusi kansio\assignment_9\Hankeluotsi_AI'
   .\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
   ```

   Open the local URL printed in that terminal. The normal default database is the existing `hankeluotsi.sqlite3` beside `app.py`. The temporary QA preview, if still running, is at **http://127.0.0.1:8510** and deliberately contains fictional test fixtures instead of the normal records.
3. Inspect the header/logo and workflow at desktop width. Open a saved project, then expand **Start a new project idea** to confirm the input form works without cluttering the saved concept.
4. Submit a fictional idea using the five required fields. For a real local generation check, first start LM Studio at localhost:1234 and load the configured model as described in README. Inspect the visible error if it is unavailable.
5. Reopen the saved concept. Check O/A/R/I links, summary counts, clean/error/warning consistency presentation and the original saved-input/JSON expanders. Compare text to the stored concept if needed.
6. Download the PDF; inspect its A4 page layout and Finnish characters. Long-content pagination is automated-tested; not every possible exported document has been visually inspected.
7. Expand funding research. Explicitly choose **Search Live Funding Calls**; inspect the status reason, uncertain dates, official call link, objectives/conditions and raw evidence details. Then try the separate general programme suggestions. No source request should repeat when inspecting another cached call.
8. Use responsive browser mode at 820 and 390 px. Confirm no horizontal scroll, a usable saved-project selector and PDF button, and genuinely hidden collapsed content.
9. Review the diff and QA screenshots before approving any commit. This continuation has not committed or pushed changes.

## Remaining limitations and prototype checklist

The browser checks used Edge emulation, not physical mobile hardware. Full keyboard/screen-reader coverage, stress/concurrent-click testing, every PDF page variant and every possible funding-site response were not manually tested. CSS targets the pinned Streamlit release; recheck it after an upgrade. Funding source coverage, six-hour snapshot guard, indicative Aurora data and unknown precise/multi-stage deadlines retain their documented limits. Eligibility is never confirmed. No PR7 functionality was added.

Before the HAMK prototype hand-in on **22 November 2026**, the owner should:

- [ ] Review and explain the UI/code changes and approve a small commit when satisfied.
- [ ] Record actual student hours and learning independently; no hours are inferred from agent execution.
- [ ] Verify model/runtime configuration and the benchmark documentation against the laptop.
- [ ] Record a short fictional-data demo covering idea → validated concept → SQLite reopen → visible errors; include optional consistency/PDF/funding evidence as time permits.
- [ ] Confirm the current teacher instructions and submit the required demo/evidence. Draft/review UI is not a blocker for the stated prototype slice.
