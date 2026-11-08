import hashlib
import json
import os
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from hankeluotsi.llm_client import LLMClient
from hankeluotsi.repository import ProjectRecord, ProjectRepository
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


DEFAULT_DATABASE_PATH = Path(os.getenv("HANKELUOTSI_DB_PATH", "hankeluotsi.sqlite3"))


def _operation_id(operation: str, payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"pr5:{operation}:{digest}"


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


def _render_saved_project(project: ProjectRecord) -> None:
    st.subheader("Saved project")
    st.caption(f"Status: {project.state.value}")
    st.json(project.idea.model_dump(mode="json"))
    if project.concept is None:
        st.info("No concept has been saved for this project yet.")
    else:
        st.subheader("Validated concept paper")
        st.json(project.concept.model_dump(mode="json"))


st.set_page_config(page_title="HankeLuotsi AI")
st.title("HankeLuotsi AI")
st.warning(
    "AI-generated draft. Not a funding eligibility assessment. "
    "Verify requirements against the relevant funding programme."
)
st.caption("Prototype: enter a fictional project idea to generate and save a validated concept.")
st.info("Use fictional project data only. The local model creates an unreviewed planning draft.")

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

st.header("Project idea")
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
        idea_data = idea.model_dump(mode="json")
        idea_operation_id = _operation_id("create", idea_data)
        concept_operation_id = _operation_id("concept", idea_data)
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
