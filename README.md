# HankeLuotsi AI

AI-assisted EU project planning prototype for the HAMK AI Expert course (2026).

> AI-generated draft. Not a funding eligibility assessment. Verify requirements against the relevant funding programme.

## Current status

The app accepts fictional project ideas, generates validated concepts and reopens saved SQLite records. Saved concepts now also support a bounded application draft, deterministic checks, evidence-linked AI review, explicit human approval and approved Markdown export. These new stages are covered by offline provider mocks and temporary-database UI tests; real-model reliability and professional content quality remain evaluation gates. See [Draft & Review behavior and limitations](docs/draft_review.md), the controlling [PLANS.md](PLANS.md) and [AGENTS.md](AGENTS.md).

## Windows setup

Use Python 3.11 or newer. From the repository root, run these commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

## Interface review

Use the four numbered cards to switch between idea input, concept/PDF, checks/funding and Draft & Review. The active card is highlighted; saved-project selection and in-progress input stay available when returning to earlier steps. See [workflow navigation and verification](docs/workflow_navigation.md).

Draft & Review ends with **Improve the draft** and **Approve and export**. AI review details and technical options start collapsed; explicit approval locks the version and reveals the approved Markdown download. Direct text editing is not available. See [finalization behavior and safeguards](docs/draft_review.md).

Use the **Suomi / English** selector in the top-right header. English is the initial default; the choice persists during Streamlit reruns in the current session. New concept generation requests the selected language from the existing local Qwen model. Switching changes interface/PDF labels, never saved project text, JSON keys or IDs. Official funding content stays in its original language. See [bilingual support and review steps](docs/bilingual_support.md).

For the completed Nordic UI, original logo, browser QA evidence and tomorrow's review checklist, see [UI verification](docs/ui_qa.md). Restart Streamlit after pulling or reviewing changes to Python modules/theme files; this avoids an old imported presentation module remaining in a long-running process. Run from the repository directory so the local theme configuration is loaded. The default database and UI assets are anchored to the project folder; an explicit `HANKELUOTSI_DB_PATH` override is respected.

If Draft & Review reports a missing `StaleProjectError` import after updating files, fully stop and restart the Streamlit process. See [verified startup recovery and isolated demonstration commands](docs/startup_troubleshooting.md).

For a missing navigation import, use the current app's `hankeluotsi.workflow_navigation` integration and one server on port8501. An older IPv6 listener can make `localhost` reach a different process from `127.0.0.1`; the [startup guide](docs/startup_troubleshooting.md) records the verified fix and exact hostname checks.

## Local model setup

For the current Mistral offline checks, professional prompt versions, private planning-quality pilot and exact one-call smoke instructions, see the [Finnish readiness report](docs/mistral_readiness.md). On 14 November the owner reported working Mistral Large 4 authentication and live text generation after supplying a valid API key; the 32-token probe reported usage of 26/32/58 tokens and approximately 1.45 seconds, with completion still marked incomplete. This is owner-reported connectivity evidence, not a validated production ConceptPaper or a model-quality winner. The prepared minimal smoke now defaults to 256 output tokens, with zero retries; it has not been live-run by the agent. See [the exact evidence and limitations](docs/mistral_connectivity_2026-11-14.md). Do not run another paid smoke or comparison without separate explicit owner approval and applicable cost checks.

Start the LM Studio local server at `http://127.0.0.1:1234/v1`, load `qwen3.5-4b`, and disable **Enable Thinking** in the model's inference settings. Local Qwen is the default. Optional Mistral Cloud requires explicit selection, environment configuration and fictional-data/cloud/cost consent; it never activates as a fallback. See [Mistral setup and safe testing](docs/mistral_setup.md). Use fictional information only.

Launch the prototype from the repository root:

```powershell
streamlit run app.py
```

Enter the fictional idea fields and choose **Generate concept**. The app saves the idea before requesting generation, validates the returned `ConceptPaper`, and only saves a valid concept. Reopen a saved record from **Open a saved project**. By default, SQLite is stored in `hankeluotsi.sqlite3` in the repository root; set `HANKELUOTSI_DB_PATH` to use another local file.

Run the offline tests with:

```powershell
python -m pytest -q
```

The offline AppTest suite mocks generation and makes no live model calls. For a live manual test, make sure the local server is running first. Never commit secrets or real project/partner data.

## Optional funding research

Open a saved fictional project and expand **Find Funding Opportunities (optional)**. Choose **Search Live Funding Calls** to retrieve published records from Interreg Aurora's official timetable and the EU Funding & Tenders Portal's Horizon Europe API. This is an explicit online action; project information is not sent to either source. Inspect a record to see its identifier, source wording, dates/precision, official and locally checked status, evidence links, retrieval time and uncertainty. No funding eligibility is confirmed.

The Horizon search retrieves at most two pages of ten source-labelled open grant topics and shows a partial-results notice. Date-only API values do not establish a precise submission time; multi-stage/ambiguous deadlines remain unknown. Aurora includes historical closed calls, uses the currently linked official timetable and preserves its update date. Current statuses become unknown after six hours until another explicit search. No network request is triggered by reruns or selecting an already retrieved call.

Retrieved live calls are ranked locally using the saved idea and available concept objectives. High, Medium, Low and Insufficient Information describe research relevance, with reasons, confidence and a transparent heuristic score; they never confirm eligibility. Relevance/programme/status filters include all records by default, including Low, unmatched and closed results. A closed call can rank highly for its theme; check the separate status or filter to open calls. The small English/Finnish vocabulary and bounded catalogue can miss suitable opportunities. See [matching rules and review steps](docs/funding_matching.md).

Open a saved project and expand **Find Funding Opportunities (optional)**. Submit **Find Funding Opportunities** to compare its saved idea locally with six official programme guides: EURA 2021 EAKR/ESR+/JTF, Interreg Aurora, the EU Funding & Tenders Portal, and Business Finland. A concept is not required.

The separate **general programme suggestions** contain no verified individual calls. Their call titles, dates and open/closed status remain unknown. Guides were checked on 8 November 2026 and may become outdated. Source links, geographic/applicant conditions to check and uncertainty are visible. Business Finland instruments are not necessarily EU-funded.

An optional checkbox retrieves descriptions from four fixed public pages. Requests contain no project information or keywords, use normal TLS validation and do not bypass restrictions. A successful page fetch does not update or verify current calls or the reviewed guidance. Network errors, certificate errors and JavaScript-only pages leave the offline guidance available. Opening the section or rerunning the app does not make requests.

Comparison uses a small English/Finnish topic vocabulary, without AI or eligibility scores. It cannot establish applicant, partnership or geographic eligibility. Results are temporary for the app session and do not change SQLite or approval. See [source investigation and limitations](docs/funding_sources.md).

See [live source contracts, limitations and manual checks](docs/live_funding_search.md). Offline tests skip public-source integration checks. To run those checks separately in PowerShell:

```powershell
$env:HANKELUOTSI_LIVE_FUNDING = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_live_funding_sources.py
Remove-Item Env:HANKELUOTSI_LIVE_FUNDING
```

## Fictional example

For testing and demonstrations, use synthetic information such as:

- **Idea:** Digital skills workshops for small cultural organizations.
- **Need:** Fictional community arts groups in Finland and Sweden have limited capacity to use digital tools.
- **Expected change:** Participants apply at least one new digital practice in their organization.

These details are invented and make no claim about any funding programme or real organization.
