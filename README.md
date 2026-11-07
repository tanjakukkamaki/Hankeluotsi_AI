# HankeLuotsi AI

AI-assisted EU project planning prototype for the HAMK AI Expert course (2026).

> AI-generated draft. Not a funding eligibility assessment. Verify requirements against the relevant funding programme.

## Current status

This repository currently contains the PR0 setup shell. It does not yet generate or save project content. The planned workflow is documented in [PLANS.md](PLANS.md); the project and data boundaries are in [AGENTS.md](AGENTS.md).

## Windows setup

Use Python 3.11 or newer. From the repository root, run these commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

Run the offline smoke tests with:

```powershell
python -m pytest -q
```

The initial shell does not contact a model or require credentials. `.env.example` is a placeholder for later local configuration; copy it to `.env` only when needed. Never commit secrets or real project/partner data.

## Fictional example

For testing and demonstrations, use synthetic information such as:

- **Idea:** Digital skills workshops for small cultural organizations.
- **Need:** Fictional community arts groups in Finland and Sweden have limited capacity to use digital tools.
- **Expected change:** Participants apply at least one new digital practice in their organization.

These details are invented and make no claim about any funding programme or real organization.
