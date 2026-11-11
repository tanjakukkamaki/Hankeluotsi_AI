# Prototype demo and submission checklist

Prepared 11 November 2026 for the **22 November prototype**, not the complete 13 December workflow. Course dates/times in PLANS say 12:00 Finland time; confirm the current teacher instructions before submission.

QA baseline: `feature/live-funding-search`, commit `f50211b`. See [test evidence, findings and final-stage plan](prototype_qa_report.md). These are review steps; checking a box requires the owner to perform/verify it.

## Before the demonstration

- [ ] Review the QA report and documentation diff. Confirm the reviewed code is the intended submission version; do not assume the default GitHub branch has it.
- [ ] Confirm the teacher's prototype deliverables, submission location and deadline.
- [ ] Record actual student hours, AI assistance, owner decisions and learning separately from planned hours.
- [ ] In LM Studio, verify the actual model artifact, quantization, context, runtime/version and hardware/offload; record verified values in the benchmark documentation. Complete the planned practical-alternative comparison. Do not infer these details from the model display name.
- [ ] Load `qwen3.5-4b`, disable **Enable Thinking**, and start its local server on `http://127.0.0.1:1234/v1`. Do not expose it publicly.
- [ ] Use fictional data only. Keep a previously saved fictional concept/PDF and a short recorded demonstration available in case the model or internet is unavailable.
- [ ] Acknowledge the known matching false positive and accessibility findings. Do not claim eligibility, full accessibility conformance or a completed Draft & Review stage.

## Reproduce from the repository

Open PowerShell **in the repository root**. Inspect Git without modifying it:

```powershell
git status --short --branch
git log -1 --oneline
```

For a new machine/environment, the owner can create/install the documented dependencies with these commands. **This QA did not perform a fresh installation.** Existing working installations can skip this block. It uses the interpreter directly, so `Activate.ps1` and execution-policy changes are unnecessary.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Run the complete offline suite with a temporary default database and live integration disabled. All variables below affect only this PowerShell process; use a separate terminal for the normal application.

```powershell
$env:HANKELUOTSI_DB_PATH = Join-Path $env:TEMP ("hankeluotsi-offline-" + [guid]::NewGuid().ToString() + ".sqlite3")
Remove-Item Env:HANKELUOTSI_LIVE_FUNDING -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Expected at the reviewed baseline: **359 passed, 2 skipped**; execution time varies. The skips are intentional public-source checks. A failing test should be recorded and resolved/reviewed before presenting success.

Start a fresh isolated demo instance with a new database, without touching existing saved projects. Choose another free port if 8516 is already occupied; do not kill an unrelated server.

```powershell
$env:HANKELUOTSI_DB_PATH = Join-Path $env:TEMP ("hankeluotsi-demo-" + [guid]::NewGuid().ToString() + ".sqlite3")
$env:LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LM_STUDIO_MODEL = "qwen3.5-4b"
$appPath = Join-Path (Get-Location).Path "app.py"
.\.venv\Scripts\python.exe -m streamlit run $appPath --server.address=127.0.0.1 --server.port=8516 --browser.gatherUsageStats=false
```

Open `http://127.0.0.1:8516`. Keep the terminal/database path if testing a restart. Stop only this instance with Ctrl+C, then run the same launch command with the **same database path**. Copying `.env.example` alone does not configure this application; it does not load `.env` automatically.

The QA preview `http://127.0.0.1:8514` was left available with seven fictional records for local review. Its temporary data is separate from the normal app at `http://localhost:8501` and may not survive a reboot/temporary-file cleanup. One approved fixture is artificial repository-test setup, not a completed browser approval workflow.

## Suggested 5–7 minute demonstration

1. **Introduce the boundary.** Show the logo, visible draft/eligibility disclaimer and the planned Draft & Review card. Explain that this is an early planning prototype using local inference and fictional data.
2. **Show validation.** Submit an empty form once. Confirm understandable required-field messages and no new saved record.
3. **Generate in Finnish.** Select **Suomi** in the top-right header and use the fictional inputs below. Click **Luo hankekonsepti** once, wait, and show validation/save confirmation. If the call fails, show the recoverable error honestly and reopen a saved example.
4. **Inspect the concept.** Show background, O1/A1/R1/I1 links, indicator/method and consistency results. Explain that a structural pass does not certify quality. Read the indicator critically.
5. **Switch languages and reopen.** Select **English**; headings/buttons change while the saved Finnish body/IDs stay unchanged. Reopen another saved English example if available. Show its unchanged language. A new English concept can be generated separately; switching alone must never regenerate.
6. **Export.** Download the concept PDF in the selected UI language. Show its disclaimer, original content/IDs, readable characters and Page/Sivu footer. Explain that labels follow the interface, not automatic document translation.
7. **Research funding.** Expand the optional funding section. Run general programme research first, leaving online descriptions unchecked. Show six programme guides, official links, unknown call details and the guidance review date.
8. **Optional live search.** Click **Search Live Funding Calls** once. Inspect a title, ID, opening/deadline precision, current versus official status, retrieval timestamp, source evidence and requirements still needing review. Demonstrate relevance/programme/status filters, including Low and empty-selection recovery. Explain partial catalogue coverage and the documented false positive; a high rank is never funding eligibility.
9. **Close with scope.** Show that Draft & Review is planned; summarize the prioritized December work, tests, limitations, owner review and next decisions.

Fictional Finnish input:

| Field | Example |
| --- | --- |
| Hankkeen nimi | Kuvitteellinen Ääni — kulttuuri ja digitaidot |
| Kehittämistarve | Kuvitteelliset taideyhdistykset tarvitsevat tukea saavutettavien digitaalisten työvälineiden käyttöön. |
| Kohderyhmät | Kuvitteellisten yhdistysten työntekijät ja vapaaehtoiset |
| Tavoiteltu muutos | Osallistujat osaavat yhden arjessa hyödyllisen digitaalisen tehtävän. |
| Maantieteellinen alue | Kuvitteelliset yhteisöt Suomessa ja Ruotsissa |

Leave optional partners/funding context empty or explicitly fictional. Do not paste employer, partner, personal or real application information. English comparison example: **Fictional community arts skills**; need: fictional arts groups need accessible digital skills; target: fictional volunteers; change: participants complete one digital task; geography: fictional Finland and Sweden.

## Focused acceptance checks

- [ ] **Persistence:** Record the project title/short ID; restart only the isolated demo using the same database path; reopen it and compare the original text/IDs. No generation should run automatically.
- [ ] **Language:** FI/EN/FI switches preserve the selected record and content. Expect official source excerpts and some framework/native diagnostics to retain their original language.
- [ ] **PDF:** Short examples may fit one A4 page; longer content may span several. Indicator and method stay together where practical. Verify `ä ö å Ä Ö Å`, no clipped text, correct label language and page numbers. Do not expect identical page counts for arbitrary content.
- [ ] **Funding:** Confirm all individual call facts on the official call documents. Date-only/multi-stage/stale results can remain unknown. Aurora's historical calls and prizes are not necessarily suitable project grants. EURA/Business Finland have no live adapters in this version.
- [ ] **Reruns:** Change filters/language and inspect the same search timestamp. A new explicit search can change source order/counts. Resetting a session loses temporary research results, not SQLite projects.
- [ ] **Services unavailable:** In a separate isolated launch, an unreachable local model should leave the idea saved without a concept and display an actionable error. Do not stop the owner's normal model or change system network settings for the demonstration. Funding-source failures should leave official links/programme guidance; never present an invented opportunity.
- [ ] **Layout:** Review desktop and a narrow browser/device view. Check selector access, form labels, focus, disclaimer, source links and downloads. QA covered 320/390/820/1440 px, but physical mobile and screen-reader checks remain outstanding.
- [ ] **Privacy/Git:** Run `git status --short --branch`, `git diff --check` and `git ls-files`. Do not stage `.env`, keys, SQLite files, caches or temporary test evidence. Keep fictional submission evidence separate from live private data.

Optional official-source integration tests, separate from offline pytest:

```powershell
$env:HANKELUOTSI_LIVE_FUNDING = "1"
try {
    .\.venv\Scripts\python.exe -m pytest -q tests/integration/test_live_funding_sources.py
} finally {
    Remove-Item Env:HANKELUOTSI_LIVE_FUNDING -ErrorAction SilentlyContinue
}
```

These contact public sources and may fail when a source is unavailable or its contract changes. Record the result and timestamp; do not substitute the 11 November catalogue for current information.

## Hand-in review

- [ ] Owner reviewed/explained the implementation, test evidence and open findings.
- [ ] Model/settings evidence and benchmark limitations are accurately recorded; no invented quality scores or hardware details.
- [ ] Short video/screenshots show fictional inputs, validation, local generation, reopen, error behavior and scope limits. Record the actual code version/date.
- [ ] README/setup instructions and requirements accompany the reviewed code; confirm teacher/reviewer access to the intended repository version.
- [ ] Explain what is working for 22 November and what remains for 13 December. Do not label the full workflow complete.
- [ ] Confirm the final submission against current teacher instructions and record the submission acknowledgment.

No commit, push, merge, branch switch or submission is authorized by this checklist. Those actions remain subject to owner review.
