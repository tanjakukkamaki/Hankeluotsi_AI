# HankeLuotsi AI

AI-assisted EU project planning prototype for the HAMK AI Expert course (2026).

> AI-generated draft. Not a funding eligibility assessment. Verify requirements against the relevant funding programme.

## Current status

The PR5 prototype accepts a fictional project idea, generates a `ConceptPaper` with the local LM Studio model, validates it with Pydantic, saves it to SQLite, and lets you reopen saved projects. Later workflow stages are not part of this prototype. The planned workflow is documented in [PLANS.md](PLANS.md); the project and data boundaries are in [AGENTS.md](AGENTS.md).

## Windows setup

Use Python 3.11 or newer. From the repository root, run these commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

## Local model setup

Start the LM Studio local server at `http://127.0.0.1:1234/v1`, load `qwen3.5-4b`, and disable **Enable Thinking** in the model's inference settings. The app uses only the configured local endpoint; it does not call cloud APIs. Use fictional information only.

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

## Fictional example

For testing and demonstrations, use synthetic information such as:

- **Idea:** Digital skills workshops for small cultural organizations.
- **Need:** Fictional community arts groups in Finland and Sweden have limited capacity to use digital tools.
- **Expected change:** Participants apply at least one new digital practice in their organization.

These details are invented and make no claim about any funding programme or real organization.
