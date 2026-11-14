"""Stateful workflow panels, independent of cached branding/presentation helpers."""

import streamlit as st

from hankeluotsi.i18n import localize


WORKFLOW_STAGES = (
    ("idea", "01", "Shape the idea", "A focused starting point"),
    ("concept", "02", "Build the concept", "A structured working draft"),
    ("explore", "03", "Check & explore", "Consistency and official sources"),
    ("draft", "04", "Draft & review", "Draft, review and human approval"),
)


def _ui(message: str) -> str:
    return localize(message, st.session_state.get("ui_language", "en"))


def _remember_workflow_stage() -> None:
    # Native tabs expose their label; only the fixed number is language-independent.
    number = st.session_state["workflow_navigation"].split(" ", 1)[0]
    for stage, candidate, _, _ in WORKFLOW_STAGES:
        if number == candidate:
            st.session_state["workflow_stage"] = stage
            break


def render_workflow_navigation():
    """Keep all four panels mounted: navigating must not discard form edits."""
    stage = st.session_state.get("workflow_stage", "idea")
    if stage not in {item[0] for item in WORKFLOW_STAGES}:
        stage = "idea"
    st.session_state["workflow_stage"] = stage
    labels = [f"{number} {_ui(title)}  \n{_ui(subtitle)}"
              for _, number, title, subtitle in WORKFLOW_STAGES]
    # Labels change with language; reconstruct the widget value from canonical state.
    active = next(index for index, item in enumerate(WORKFLOW_STAGES) if item[0] == stage)
    st.session_state["workflow_navigation"] = labels[active]
    return st.tabs(labels, key="workflow_navigation", on_change=_remember_workflow_stage)
