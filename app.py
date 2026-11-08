import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import streamlit as st
from pydantic import ValidationError

from hankeluotsi.llm_client import LLMClient
from hankeluotsi.pdf_exporter import concept_pdf_filename, generate_concept_pdf
from hankeluotsi.repository import ProjectRecord, ProjectRepository
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


DEFAULT_DATABASE_PATH = Path(os.getenv("HANKELUOTSI_DB_PATH", "hankeluotsi.sqlite3"))


def _operation_id(operation: str, submission_id: str) -> str:
    return f"pr5:{operation}:{submission_id}"


def _project_label(project: ProjectRecord) -> str:
    return f"{project.idea.title} ({project.state.value})"


def _concept_generation_input(idea: ProjectIdea) -> str:
    return (
        "Fictional project idea:\n"
        f"{idea.model_dump_json()}\n\n"
        "Create a concise ConceptPaper with exactly one objective (O1), one preliminary "
        "activity (A1) linked to O1, one expected result (R1) linked to A1, and one "
        "measurable proposed indicator (I1) linked to R1. Use one target group. Keep "
        "descriptions to one short sentence each. Use empty assumptions and open_questions."
    )


def _render_section_heading(title: str) -> None:
    st.markdown(f"#### {title}")


@contextmanager
def _concept_section(title: str) -> Iterator[None]:
    with st.container(border=True):
        _render_section_heading(title)
        yield


def _render_concept_reference(
    identifier: str,
    relationship_label: str | None = None,
    related_ids: tuple[str, ...] = (),
) -> None:
    relationship = (
        f'<span class="concept-relationship">{relationship_label}: {", ".join(related_ids)}</span>'
        if relationship_label
        else ""
    )
    st.markdown(
        f'<div class="concept-reference-row"><span class="concept-id">{identifier}</span>{relationship}</div>',
        unsafe_allow_html=True,
    )


def _render_saved_project(project: ProjectRecord) -> None:
    st.subheader("Saved project")
    st.caption(f"Status: {project.state.value}")
    with st.container(border=True):
        st.markdown("#### Project idea")
        for label, value in (
            ("Title", project.idea.title),
            ("Development need", project.idea.development_need),
            ("Expected change", project.idea.expected_change),
            ("Geography", project.idea.geography),
        ):
            st.markdown(f"**{label}**")
            st.text(value)
        st.markdown("**Target groups**")
        for target_group in project.idea.target_groups:
            st.text(target_group)
        if project.idea.partners:
            st.markdown("**Potential partners**")
            for partner in project.idea.partners:
                st.text(partner)
        if project.idea.funding_context:
            st.markdown("**Funding context**")
            st.text(project.idea.funding_context)
        with st.expander("Raw project idea JSON", expanded=False):
            st.json(project.idea.model_dump(mode="json"))

    if project.concept is None:
        st.caption("No concept has been saved for this project yet.")
    else:
        concept = project.concept
        concept_heading, pdf_action = st.columns([0.72, 0.28], vertical_alignment="center")
        with concept_heading:
            st.subheader("Concept paper")
            st.caption("AI-generated draft · Pydantic validated")
        with pdf_action:
            st.download_button(
                "Download PDF",
                data=generate_concept_pdf(project.idea.title, concept),
                file_name=concept_pdf_filename(project.idea.title),
                mime="application/pdf",
                key=f"download-concept-{project.project_id}",
                on_click="ignore",
                use_container_width=True,
            )

        with _concept_section("Background"):
            st.text(concept.background_need)

        with _concept_section("Objectives"):
            for objective in concept.objectives:
                _render_concept_reference(objective.id)
                st.text(objective.description)

        with _concept_section("Target groups"):
            for target_group in concept.target_groups:
                st.text(target_group)

        with _concept_section("Activities"):
            for activity in concept.preliminary_activities:
                _render_concept_reference(
                    activity.id, "Linked objectives", tuple(activity.objective_ids)
                )
                st.text(activity.description)

        with _concept_section("Expected results"):
            for result in concept.expected_results:
                _render_concept_reference(
                    result.id, "Linked activities", tuple(result.activity_ids)
                )
                st.text(result.description)

        with _concept_section("Indicators"):
            for indicator in concept.proposed_indicators:
                _render_concept_reference(
                    indicator.id, "Linked results", tuple(indicator.result_ids)
                )
                st.text(indicator.description)
                st.markdown("**Measurement method**")
                st.text(indicator.measurement_method)

        with _concept_section("Assumptions"):
            for assumption in concept.assumptions:
                st.text(assumption)

        with _concept_section("Open questions"):
            for question in concept.open_questions:
                st.text(question)

        with st.expander("Raw ConceptPaper JSON", expanded=False):
            st.json(concept.model_dump(mode="json"))


st.set_page_config(page_title="HankeLuotsi AI", layout="wide", page_icon="⌖")
st.markdown(
    """
    <style>
    :root {
        --hankeluotsi-primary: #15334A;
        --hankeluotsi-accent: #278F91;
        --hankeluotsi-background: #F4F7FA;
        --hankeluotsi-card: #FFFFFF;
        --hankeluotsi-border: #D9E2EC;
        --hankeluotsi-text: #1F2937;
        --hankeluotsi-muted: #667789;
    }
    .stApp, [data-testid="stAppViewContainer"] {
        background: var(--hankeluotsi-background);
        color: var(--hankeluotsi-text);
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding: 2rem 2.5rem 3.5rem;
    }
    h1, h2, h3, h4 {
        color: var(--hankeluotsi-primary) !important;
    }
    h1 {
        font-size: 2.1rem !important;
        margin: 0 0 0.1rem;
    }
    h2 {
        margin: 1.5rem 0 0.65rem;
    }
    .app-subtitle {
        color: var(--hankeluotsi-muted);
        font-size: 0.98rem;
        margin: 0;
    }
    .brand-compass {
        align-items: center;
        background: #E6F1F1;
        border: 1px solid #D0E4E4;
        border-radius: 12px;
        color: var(--hankeluotsi-primary);
        display: flex;
        font-size: 1.65rem;
        height: 3.2rem;
        justify-content: center;
        margin-top: 0.1rem;
        width: 3.2rem;
    }
    .workflow-label {
        color: var(--hankeluotsi-muted);
        font-size: 0.72rem;
        font-weight: 700;
        margin: 0.4rem 0 0.6rem;
        text-transform: uppercase;
    }
    .workflow-card {
        background: var(--hankeluotsi-card);
        border: 1px solid var(--hankeluotsi-border);
        border-radius: 9px;
        min-height: 7.1rem;
        padding: 0.9rem 1rem;
    }
    .workflow-card.available {
        border-top: 3px solid var(--hankeluotsi-accent);
    }
    .workflow-card.planned {
        background: #F8FAFC;
    }
    .workflow-number {
        color: var(--hankeluotsi-accent);
        font-size: 0.73rem;
        font-weight: 700;
    }
    .workflow-title {
        color: var(--hankeluotsi-primary);
        font-size: 0.98rem;
        font-weight: 700;
        margin: 0.25rem 0;
    }
    .workflow-status {
        color: var(--hankeluotsi-muted);
        font-size: 0.8rem;
    }
    .disclaimer-note {
        background: #EAF4FF;
        border-left: 3px solid var(--hankeluotsi-primary);
        border-radius: 5px;
        color: var(--hankeluotsi-text);
        font-size: 0.84rem;
        line-height: 1.45;
        margin: 1.1rem 0 1.3rem;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMarkdownContainer"] h4 {
        color: var(--hankeluotsi-primary) !important;
        font-size: 1rem;
        margin: 0.1rem 0 0.5rem;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--hankeluotsi-card);
        border: 1px solid var(--hankeluotsi-border);
        border-radius: 8px;
        padding: 0.95rem 1.15rem;
    }
    [data-testid="stAlertContentInfo"] {
        background: var(--hankeluotsi-info) !important;
        border: 1px solid #C9DFF3;
        border-radius: 7px;
        color: var(--hankeluotsi-text) !important;
    }
    [data-testid="stAlertContentWarning"] {
        background: var(--hankeluotsi-warning) !important;
        border: 1px solid #E8D697;
        border-radius: 7px;
        color: var(--hankeluotsi-text) !important;
    }
    [data-testid="stForm"] {
        background: var(--hankeluotsi-card);
        border: 1px solid var(--hankeluotsi-border);
        border-radius: 9px;
        padding: 1.2rem 1.35rem;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [role="combobox"] {
        background: var(--hankeluotsi-card);
        color: var(--hankeluotsi-text);
        border: 1px solid var(--hankeluotsi-border);
        border-radius: 6px;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--hankeluotsi-accent);
        box-shadow: 0 0 0 1px var(--hankeluotsi-accent);
    }
    .stButton button[kind="primary"] {
        background: var(--hankeluotsi-accent);
        border: 1px solid var(--hankeluotsi-accent);
        border-radius: 6px;
        color: white;
        font-weight: 600;
        min-height: 2.9rem;
        width: 100%;
    }
    .stButton button[kind="primary"]:hover {
        background: #218579;
        border-color: #218579;
        color: white;
    }
    [data-testid="stExpander"] {
        background: var(--hankeluotsi-card);
        border: 1px solid var(--hankeluotsi-border);
        border-radius: 6px;
    }
    [data-testid="stDownloadButton"] button {
        background: var(--hankeluotsi-primary);
        border: 1px solid var(--hankeluotsi-primary);
        border-radius: 6px;
        color: white;
        font-weight: 600;
        min-height: 2.65rem;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: #214D6D;
        border-color: #214D6D;
        color: white;
    }
    .concept-reference-row {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin: 0.5rem 0 0.25rem;
    }
    .concept-id {
        background: #E5F1F1;
        border: 1px solid #C9E1E1;
        border-radius: 4px;
        color: var(--hankeluotsi-navy);
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.16rem 0.48rem;
    }
    .concept-relationship {
        color: var(--hankeluotsi-muted);
        font-size: 0.86rem;
    }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] {
            padding: 1.1rem 1rem 2rem;
        }
        [data-testid="stForm"] {
            padding: 0.8rem 0.85rem;
        }
        .app-subtitle {
            font-size: 0.9rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.7rem 0.75rem;
        }
        h1 {
            font-size: 1.65rem !important;
        }
        .brand-compass {
            font-size: 1.35rem;
            height: 2.7rem;
            width: 2.7rem;
        }
        .workflow-card {
            min-height: 6.4rem;
            padding: 0.7rem;
        }
        .workflow-title {
            font-size: 0.85rem;
        }
        .workflow-status {
            font-size: 0.72rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
brand_icon, brand_title = st.columns([0.08, 0.92], vertical_alignment="center")
with brand_icon:
    st.markdown('<div class="brand-compass" aria-hidden="true">⌖</div>', unsafe_allow_html=True)
with brand_title:
    st.title("HankeLuotsi AI")
    st.markdown('<p class="app-subtitle">From project idea to structured concept</p>', unsafe_allow_html=True)

st.markdown(
    '<div class="disclaimer-note" role="note"><strong>AI-generated draft.</strong> '
    'Not a funding eligibility assessment. Verify requirements against the relevant funding programme.</div>',
    unsafe_allow_html=True,
)
st.markdown('<p class="workflow-label">Planning workflow</p>', unsafe_allow_html=True)
workflow_columns = st.columns(3, gap="small")
workflow_steps = (
    ("01", "Project idea", "Input and save available", "available"),
    ("02", "Concept paper", "Generate and reopen available", "available"),
    ("03", "Draft & review", "Planned · not available yet", "planned"),
)
for column, (number, title, status, availability) in zip(workflow_columns, workflow_steps):
    with column:
        st.markdown(
            f'<div class="workflow-card {availability}"><div class="workflow-number">{number}</div>'
            f'<div class="workflow-title">{title}</div><div class="workflow-status">{status}</div></div>',
            unsafe_allow_html=True,
        )

try:
    repository = ProjectRepository(DEFAULT_DATABASE_PATH)
    projects = repository.list_projects()
except Exception as error:
    st.error(f"Could not open the local project database: {error}")
    st.stop()

project_by_id = {project.project_id: project for project in projects}
project_options = [None, *project_by_id]
pending_project_id = st.session_state.pop("pr5_pending_project_id", None)
if pending_project_id in project_by_id:
    st.session_state["open_project_id"] = pending_project_id
idea_column, saved_column = st.columns([1.55, 0.9], gap="large")
with idea_column:
    st.subheader("New project idea")
    st.caption("A few structured details are enough to begin.")
    with st.form("project_idea_form", clear_on_submit=False):
        title = st.text_input("Project title", key="idea_title")
        development_need = st.text_area("Development need", key="idea_development_need")
        target_groups = st.text_area(
            "Target groups", help="Separate multiple groups with commas or new lines.", key="idea_target_groups"
        )
        expected_change = st.text_area("Expected change", key="idea_expected_change")
        geography = st.text_input("Geography", key="idea_geography")
        partners = st.text_area(
            "Potential partners (optional)", help="Separate entries with commas or new lines.", key="idea_partners"
        )
        funding_context = st.text_input("Funding context (optional)", key="idea_funding_context")
        submitted = st.form_submit_button("Generate concept", type="primary")

with saved_column:
    with st.container(border=True):
        st.subheader("Saved projects")
        if projects:
            st.caption(f"{len(projects)} saved project{'s' if len(projects) != 1 else ''}")
        else:
            st.caption("Your saved ideas and concepts will appear here.")
        selected_project_id = st.selectbox(
            "Open a saved project",
            options=project_options,
            format_func=lambda project_id: (
                "Select a saved project" if project_id is None else _project_label(project_by_id[project_id])
            ),
            key="open_project_id",
        )

success_message = st.session_state.pop("pr5_success_message", None)
if success_message:
    st.success(success_message)
info_message = st.session_state.pop("pr5_info_message", None)
if info_message:
    st.info(info_message)
if selected_project_id is not None:
    _render_saved_project(project_by_id[selected_project_id])

if submitted:
    try:
        partner_items = [item.strip() for item in partners.replace("\n", ",").split(",") if item.strip()]
        group_items = [item.strip() for item in target_groups.replace("\n", ",").split(",") if item.strip()]
        idea = ProjectIdea.model_validate(
            {
                "title": title,
                "development_need": development_need,
                "target_groups": group_items,
                "expected_change": expected_change,
                "geography": geography,
                "partners": partner_items or None,
                "funding_context": funding_context.strip() or None,
            }
        )
    except ValidationError as error:
        details = "; ".join(
            f"{' / '.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        st.error(f"Please correct the project idea: {details}")
    else:
        submission_id = uuid.uuid4().hex
        idea_operation_id = _operation_id("create", submission_id)
        concept_operation_id = _operation_id("concept", submission_id)
        try:
            project = repository.create_project(idea, operation_id=idea_operation_id)
            if project.concept is not None:
                st.session_state["pr5_pending_project_id"] = project.project_id
                st.session_state["pr5_info_message"] = (
                    "This project already has a saved concept. No duplicate generation was started."
                )
                st.rerun()

            with st.spinner("Generating and validating the concept with the local model..."):
                result = LLMClient().generate(
                    "concept",
                    _concept_generation_input(idea),
                    response_model=ConceptPaper,
                    max_attempts=1,
                )
                concept = ConceptPaper.model_validate(result.data)
                saved_project = repository.save_concept(
                    project.project_id,
                    concept,
                    operation_id=concept_operation_id,
                )
            st.session_state["pr5_pending_project_id"] = saved_project.project_id
            st.session_state["pr5_success_message"] = (
                f"Concept validated and saved for {saved_project.idea.title}. "
                f"Model: {result.model}; prompt: {result.prompt_version}; "
                f"response time: {result.response_time_seconds:.2f} s."
            )
            st.rerun()
        except ValidationError as error:
            st.error(f"The generated concept did not pass validation and was not saved: {error}")
        except Exception as error:
            st.error(f"Concept generation or saving failed. Your valid saved data was preserved: {error}")
