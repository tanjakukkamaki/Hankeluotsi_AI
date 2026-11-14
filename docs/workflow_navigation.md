# Four-stage navigation — 13 November 2026

Select one of the four numbered workflow cards to open its panel. The active card has a teal border and tinted background. Native tab semantics expose the selected state and associate each card with its panel. Focus a card with Tab and use the arrow keys to move between stages. The same controls form a two-column grid on narrow screens.

| Stage | English / Finnish | Existing functionality |
| --- | --- | --- |
| 01 | Shape the idea / Jäsennä idea | New project idea form and explicit concept-generation submission |
| 02 | Build the concept / Laadi konsepti | Selected saved ConceptPaper, structured sections and PDF download |
| 03 | Check & explore / Tarkista ja tutki | Deterministic concept checks, optional funding research and explicitly requested official-source searches |
| 04 | Draft & review / Luonnos ja arviointi | Existing application draft, deterministic draft checks, evidence-linked AI review, explicit human approval and approved Markdown export |

The saved-project selector and saved-input summary remain available outside the panels. Selecting a stage keeps that project selected. The new idea form retains its separate in-progress text; navigation does not copy saved text over it or edit an existing record. Successful new concept generation explicitly opens stage 02 with the newly saved project. Selecting a different saved project keeps the active stage.

Without a saved project, stages 02–04 explain what is needed and offer a button back to 01. A saved idea without a concept can already use funding research in stage 03, while checks and drafting explain their concept prerequisite. The funding section starts expanded in its dedicated panel; opening it does not request online data. Existing explicit generation, cloud consent, replacement, approval and export guards still apply.

## Cause and implementation

Previously the cards were HTML hash links. Without a selected project, three pointed to the same workspace anchor; with a project, they scrolled within one long page. They neither selected a panel nor recorded an active stage. Concept checks were also embedded in the concept display instead of the exploration stage.

The current implementation reuses each existing renderer exactly once in native stateful `st.tabs`, supported by the pinned Streamlit 1.64.0 installation. Canonical `workflow_stage` stores idea/concept/explore/draft in session state. The tab callback maps its fixed stage number to that value, and localized labels are rebuilt from it before each render. Language changes therefore preserve the stage. The [official Streamlit tab reference](https://docs.streamlit.io/develop/api-reference/layout/st.tabs) describes stateful tabs and session-state control; this project uses the locally verified 1.64 API, without newer query-parameter features.

All panels are rendered on each rerun, including inactive panels. Their widgets stay mounted to preserve pending form edits, provider/consent controls and research filters/results; only one panel is visible. Rendering calls no model or funding service automatically. The original concept consistency renderer moved to 03; PDF remains in 02 and the existing Draft & Review component remains in 04. No model, prompt, schema, repository contract or stored project changed.

This is session navigation, not durable document history or a URL router. Unsaved input and stage choices are not promised to survive a new browser session or a server restart; saved projects remain in SQLite. After Python module changes, use the [full-process restart procedure](startup_troubleshooting.md).

## Verification

- Added 14 navigation cases covering component placement, FI/EN labels and callbacks, active-panel state, prerequisites/return actions, project/input/research preservation, reruns and successful generation opening 02. Updated the obsolete anchor-link test to verify real panels and prerequisites.
- AppTest has no native tab-click helper in this installed version. Automated tests set canonical stage state, inspect the actual selected panel index and invoke ordinary buttons; separate callback tests cover the label-to-stage mapping. Real clicks and keyboard behavior were independently exercised in Edge.
- Initial focused UI/navigation suite: **60 passed in 20.27 s**. Final complete offline suite after opening the funding panel by default: **648 passed, 2 skipped in 34.95 s**, with live funding disabled, a temporary default SQLite path and bytecode writes disabled. Skips are opt-in public-source tests.
- Follow-up navigation/i18n checks after harmonizing the Finnish return-button wording: **31 passed in 10.30 s**. `git diff --check` and new-file whitespace checks passed.
- Real headless Edge, separate synthetic database and browser profile: unsubmitted title/need survived 01 → 02 → 03 → 04 → 01; an opened saved concept stayed selected during returns; only the intended panel was visible; Finnish language rerun preserved the active stage and input; offline funding results survived returns; ArrowRight selected the next tab; all four cards fitted a 390-pixel viewport in two rows. The test database records were unchanged, with zero model/cloud calls. Private screenshots and observations remain ignored local evidence.
- The verified project server was cold-restarted to load the new presentation module. Separate browser smoke checks rendered both a cold temporary instance and localhost:8501 with title/footer present and zero Streamlit exceptions. No saved-project actions were performed on the owner's server.

These checks establish the tested navigation behavior, not a complete screen-reader/accessibility audit or slow-model UX evaluation. Existing model-quality and paid-provider evaluation gates remain separate.

## Follow-up: real hostname startup and module boundary

The reported `render_workflow_navigation` ImportError was reproduced in a real browser at `localhost:8501` and `[::1]:8501`, while `127.0.0.1:8501` rendered successfully. Two different project processes were listening: the older wildcard IPv4/IPv6 server still exposed the earlier presentation API, while a newer IPv4-only server had current imports. The earlier smoke used the numeric IPv4 URL; its reference to a successful localhost startup was too broad. See the explicit before/after [startup diagnosis](startup_troubleshooting.md).

Moved the existing navigation implementation unchanged into **`hankeluotsi/workflow_navigation.py`** and changed the application import to that module. Presentation no longer supplies the navigation API. The canonical stage, tab keys, localized labels, mounting strategy and original components remain unchanged. There is no duplicated navigation implementation, fallback alias or importlib reload. Adapted the existing navigation tests to this module and restored the cached-presentation regression to a module that genuinely lacks the helper. A new fresh-process test audits every project import in app.py without opening SQLite.

Follow-up focused startup/navigation/presentation/i18n suite: **46 passed in 16.60 s**. Full offline command `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, with temporary default SQLite, live funding disabled and bytecode writes disabled: **649 passed, 2 skipped in 36.55 s**. The two skips are opt-in public-source checks.

Real headless Edge launched the actual Streamlit application with a separate temporary SQLite database and synthetic saved concept. It verified stages01–04 and returns, correct visible components, unsubmitted title/need, selected project, research cache, English → Finnish → English reruns, keyboard navigation and390px layout. The final test reconnected through both the hostname and numeric IPv4 URL: four tabs, title/footer, zero exceptions. Temporary records were unchanged and model/cloud calls remained zero. One extra direct-IPv6 assertion initially failed because this installed runtime's explicit localhost binding supplied IPv4 only; the final supported setup binds127.0.0.1 and checks that no competing IPv6 listener remains, rather than claiming direct IPv6 support.

Both verified old project8501 servers were cold-replaced by **one loopback server**. Real browser checks of the owner's exact `http://localhost:8501` URL and numeric IPv4 URL now pass with zero exceptions; no project actions/content inspection were performed there. The old IPv6 listener is absent. All functional interaction tests used the separate fictional database. Private before/after flags, logs and synthetic screenshots remain ignored local evidence. `git diff --check` and preservation results are recorded in the development log. No paid call, credential/model/prompt/schema/data edit or commit/push/merge occurred.

The current browser session preserves navigation/input across reruns, not across server restarts or new sessions. Direct IPv6 startup, full assistive-technology review, slow-call UX and new real-model generation are not claimed by this repair.

## Finalization follow-up: retain the project after approval

The finalization browser test found a further state issue: approval/download succeeded, but changing stages afterwards could clear the project selector when its formatted status label changed to approved. Unit tests alone had not reproduced that frontend reset. The app now keeps a separate canonical session project ID, updates it through an explicit selector callback or pending new project, and restores it before registering the status-labelled widget. Missing records clear it safely; deliberate user deselection still works. SQLite remains the durable record source. The UI never writes a record merely to preserve selection.

FI/EN regressions cover approval's label change, a recreated widget's empty default, deliberate deselection, normal reruns and export availability. Real-browser finalization tests verify returning to earlier stages after approval/download still shows the correct project's export, with immutable draft/review contents. See the current [finalization flow](draft_review.md).
