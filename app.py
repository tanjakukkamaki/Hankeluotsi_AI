import os
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import streamlit as st
from pydantic import ValidationError

from hankeluotsi.consistency import (
    ConsistencyFinding,
    FindingSeverity,
    check_concept_consistency,
)
from hankeluotsi.funding import compare_locally, retrieve_funding_opportunities
from hankeluotsi.funding_calls import assess_call_status, compare_call_locally
from hankeluotsi.live_funding import search_live_funding_calls
from hankeluotsi.llm_client import LLMClient
from hankeluotsi.pdf_exporter import concept_pdf_filename, generate_concept_pdf
from hankeluotsi.presentation import (
    ASSET_DIRECTORY,
    PROJECT_ROOT,
    anchor,
    apply_styles,
    render_brand,
    render_intro,
    status_badge,
)
from hankeluotsi.repository import ProjectRecord, ProjectRepository
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


DEFAULT_DATABASE_PATH = Path(os.getenv("HANKELUOTSI_DB_PATH", str(PROJECT_ROOT / "hankeluotsi.sqlite3")))


def _operation_id(operation: str, submission_id: str) -> str:
    return f"pr5:{operation}:{submission_id}"


def _project_label(project: ProjectRecord) -> str:
    state = project.state.value.replace("_", " ")
    return f"{project.idea.title} · {state} · {project.project_id[:8]}"


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
    with st.container(border=False, key="concept_section_" + title.lower().replace(" ", "_")):
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


def _render_consistency_check(concept: ConceptPaper) -> None:
    findings = check_concept_consistency(concept)
    errors = [item for item in findings if item.severity == FindingSeverity.ERROR]
    warnings = [item for item in findings if item.severity == FindingSeverity.WARNING]

    with st.container(border=False, key="consistency_check"):
        st.subheader("Consistency Check")
        st.caption(
            "Deterministic structural checks only. This does not assess content quality "
            "or funding eligibility."
        )
        error_column, warning_column = st.columns(2)
        error_column.metric("Errors", len(errors))
        warning_column.metric("Warnings", len(warnings))

        if errors:
            st.error("Structural validation found errors that need attention.")
        elif warnings:
            st.warning("No broken references found, but some concept elements are disconnected.")
        else:
            st.success("No structural issues detected.")

        for finding in findings:
            display = (
                st.error
                if finding.severity == FindingSeverity.ERROR
                else st.warning
            )
            display(f"{finding.code.value}: {finding.message}")
            affected = f"Affected ID: `{finding.element_id}`" if finding.element_id else None
            related = (
                f"Related IDs: {', '.join(f'`{item}`' for item in finding.related_ids)}"
                if finding.related_ids
                else None
            )
            details = " · ".join(item for item in (affected, related) if item)
            if details:
                st.caption(details)


def _render_live_funding_calls(project: ProjectRecord) -> None:
    st.markdown("#### Live funding calls from official sources")
    st.caption(
        "Search the official Aurora timetable and Horizon Europe grant topics. "
        "Only fixed public requests are sent; project text stays local."
    )
    if st.button("Search Live Funding Calls", key=f"live-funding-search-{project.project_id}", type="primary"):
        with st.spinner("Reading official funding sources..."):
            result = search_live_funding_calls()
        st.session_state["live_funding_result"] = (
            project.project_id, project.idea.model_dump_json(), result, datetime.now(timezone.utc),
        )
    cached = st.session_state.get("live_funding_result")
    if not cached or cached[:2] != (project.project_id, project.idea.model_dump_json()):
        st.caption("No live search has been run for this saved idea. General programme suggestions are available below.")
        return
    result, attempted_at = cached[2:]
    st.caption(f"Last explicit search completed: {attempted_at.isoformat()}. Results last for this app session.")
    if result.notices:
        st.warning("\n\n".join(result.notices))
    if not result.calls:
        st.info("No live call records could be verified. Use the official sources and general programme guidance below.")
        st.link_button("Official Aurora calls", "https://www.interregaurora.eu/projects/calls-for-applications-2/")
        st.link_button("Official EU funding calls", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals")
        return
    now = datetime.now(timezone.utc)
    statuses = {f"{item.source}:{item.identifier}": assess_call_status(item, now=now) for item in result.calls}
    st.caption(
        f"{len(result.calls)} published call/topic records. "
        + "; ".join(f"{status}: {sum(value[0] == status for value in statuses.values())}" for status in ("open", "upcoming", "closed", "unknown"))
    )
    st.caption(
        "Statuses are checked locally against official labels and dates. Date-only boundaries "
        "remain conservative; snapshots older than six hours become unknown. Refresh explicitly."
    )
    by_id = {f"{item.source}:{item.identifier}": item for item in result.calls}
    order = {"open": 0, "upcoming": 1, "closed": 2, "unknown": 3}
    options = sorted(by_id, key=lambda key: (order[statuses[key][0]], by_id[key].identifier))
    selected = st.selectbox(
        "Inspect a live call",
        options=options,
        format_func=lambda key: f"{statuses[key][0]} | {by_id[key].identifier} | {by_id[key].title}",
        key=f"live-call-selection-{project.project_id}",
    )
    call = by_id[selected]
    with st.container(border=False, key="live_call_card"):
        status_badge(statuses[selected][0].capitalize(), tone="teal" if statuses[selected][0] == "open" else "neutral")
        with st.container(key="live_call_title"):
            st.text(call.title)
        st.text(f"Programme: {call.programme}")
        st.text(f"Official identifier: {call.identifier}")
        if call.call_identifier:
            st.text(f"Parent call identifier: {call.call_identifier}")
        st.text(f"Current status: {statuses[selected][0]}")
        st.text(statuses[selected][1])
        st.text(f"Published source status: {call.official_status}")
        st.text("Opening: " + (call.opening.display if call.opening else "Unknown"))
        st.text("Deadline: " + (call.deadline.display if call.deadline else "Unknown"))
        for label, value in (("Opening source value", call.opening), ("Deadline source value", call.deadline)):
            if value:
                st.text(f"{label}: {value.raw}")
        st.link_button("Official call page", call.source_url)
        st.link_button("Retrieved source evidence", call.evidence_url)
        st.caption(f"Call record retrieved: {call.retrieved_at.isoformat()}")
        st.caption("Source updated: " + (call.source_updated_on.isoformat() if call.source_updated_on else "Unknown"))
        st.markdown("**Local comparison and requirements to check**")
        topics = compare_call_locally(project.idea, call)
        st.text("Shared vocabulary topics: " + (", ".join(topics) or "No overlap detected"))
        st.caption("Topics overlap in the saved idea and call title/objectives. This does not establish suitability or eligibility.")
        for label, value in (
            ("Funding objectives / source excerpt", call.objectives),
            ("Geographical area", call.geographic_area),
            ("Applicant requirements / source excerpt", call.applicant_requirements),
        ):
            st.markdown(f"**{label}**")
            st.text(value or "Unknown — check the official call documents.")
        for uncertainty in call.uncertainties:
            st.text(uncertainty)
        st.caption("Source excerpts may be incomplete. Verify all requirements and exact submission deadlines in the official call documents.")


def _render_funding_research(project: ProjectRecord) -> None:
    anchor("funding-opportunities")
    with st.expander("Find Funding Opportunities (optional)", expanded=False, key="funding_research"):
        st.caption(
            "Official live calls and preliminary programme research. "
            "This does not assess funding eligibility. Project information stays local."
        )
        _render_live_funding_calls(project)
        st.markdown("#### General programme suggestions")
        with st.form(f"funding-search-{project.project_id}"):
            retrieve_live = st.checkbox(
                "Retrieve public programme page descriptions online",
                value=False,
                help="Requests four fixed official pages, with no project text or search terms. May take about 20 seconds on timeouts.",
                key=f"funding-live-{project.project_id}",
            )
            search = st.form_submit_button("Find Funding Opportunities")
        # These are temporary research results. The saved idea is always read from
        # SQLite; a changed idea invalidates its previous local research display.
        research_key = "funding_research_result"
        idea_snapshot = project.idea.model_dump_json()
        if search:
            with st.spinner("Loading official programme guidance and comparing locally..."):
                records = retrieve_funding_opportunities(retrieve_live=retrieve_live)
            st.session_state[research_key] = (project.project_id, idea_snapshot, records)
        saved_research = st.session_state.get(research_key)
        if not saved_research or saved_research[:2] != (project.project_id, idea_snapshot):
            st.caption("Choose Find Funding Opportunities to compare the saved idea with programme guidance.")
            return
        records = saved_research[2]
        st.warning(
            "Programme guidance only — these general suggestions contain no verified current calls. Call titles, dates and "
            "open/closed status are unknown. General guidance was checked on 8 November 2026 "
            "and may become outdated."
        )
        st.caption(
            "Comparison uses a small English/Finnish topic vocabulary locally. Shared topics "
            "are research clues, not scores. Geography, applicant conditions and partnerships "
            "require manual checking. Results last only for this app session."
        )
        # Six static guide names/topic labels need no dataframe runtime.
        st.markdown(
            "| Programme | Shared topics | Call status |\n| --- | --- | --- |\n"
            + "\n".join(
                f"| {item.funding_programme} | "
                f"{', '.join(compare_locally(project.idea, item)) or 'No vocabulary overlap detected'} | "
                f"{item.status} |"
                for item in records
            )
        )
        for item in records:
            with st.container(border=False, key=f"programme_card_{item.record_id}"):
                status_badge("Programme guide · call details unknown")
                st.text(item.funding_programme)
                st.link_button("Official calls / funding source", item.official_source_url)
                with st.expander("Programme details & evidence", expanded=False, key=f"programme_details_{item.record_id}"):
                    st.text("Call title: " + (item.call_title or "Unknown — no individual call retrieved"))
                    st.text("Application dates: " + (item.application_dates or "Unknown — check the official call"))
                    st.text(f"Call status: {item.status}")
                    st.markdown("**Objectives and priorities**")
                    for objective in item.objectives_and_priorities:
                        st.text(objective)
                    st.markdown("**Geographic scope to check**")
                    st.text(item.geographic_eligibility)
                    st.markdown("**Applicant requirements to check**")
                    st.text(item.applicant_requirements)
                    st.caption(f"General guidance verified: {item.guidance_verified_on.isoformat()}")
                    for index, url in enumerate(item.guidance_urls, start=1):
                        st.link_button(f"Guidance source {index}", url)
                    if item.retrieval_state == "retrieved":
                        st.caption(f"Page description retrieved: {item.information_retrieved_at.isoformat()}")
                        st.link_button("Retrieved programme page", item.retrieved_from_url)
                        st.text(item.source_excerpt)
                        st.caption("Page metadata only; it does not update or verify the guidance or call conditions above.")
                    elif item.retrieval_state == "unavailable":
                        st.caption("Live programme page description unavailable. Showing reviewed guidance and official links.")
                    else:
                        st.caption("Live retrieval not requested. Showing reviewed guidance and official links.")
                    for uncertainty in item.uncertainty:
                        st.text(uncertainty)


def _render_project_context(project: ProjectRecord) -> None:
    with st.container(key="project_context"):
        st.subheader("Saved project")
        st.caption(f"Status: {project.state.value}")
        with st.expander("Project idea · saved input", expanded=False):
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


def _render_saved_project(project: ProjectRecord) -> None:
    anchor("concept-paper")
    if project.concept is None:
        st.info("Your project idea is saved. A concept has not been generated for this record yet.")
        return
    concept = project.concept
    with st.container(key="concept_document"):
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
        with st.container(key="concept_document_title"):
            st.text(project.idea.title)
        with st.container(key="concept_summary"):
            columns = st.columns(4)
            for column, label, count in zip(columns,
                ("Objectives", "Activities", "Results", "Indicators"),
                (len(concept.objectives), len(concept.preliminary_activities), len(concept.expected_results), len(concept.proposed_indicators))):
                column.metric(label, count)
        _render_consistency_check(concept)
        with st.container(key="concept_body"):
            with _concept_section("Background"):
                st.text(concept.background_need)
            objective_column, group_column = st.columns(2, gap="large")
            with objective_column, _concept_section("Objectives"):
                for objective in concept.objectives:
                    _render_concept_reference(objective.id)
                    st.text(objective.description)
            with group_column, _concept_section("Target groups"):
                for target_group in concept.target_groups:
                    st.text(target_group)
            activity_column, result_column = st.columns(2, gap="large")
            with activity_column, _concept_section("Activities"):
                for activity in concept.preliminary_activities:
                    _render_concept_reference(activity.id, "Linked objectives", tuple(activity.objective_ids))
                    st.text(activity.description)
            with result_column, _concept_section("Expected results"):
                for result in concept.expected_results:
                    _render_concept_reference(result.id, "Linked activities", tuple(result.activity_ids))
                    st.text(result.description)
            with _concept_section("Indicators"):
                for indicator in concept.proposed_indicators:
                    _render_concept_reference(indicator.id, "Linked results", tuple(indicator.result_ids))
                    st.text(indicator.description)
                    st.markdown("**Measurement method**")
                    st.text(indicator.measurement_method)
            assumption_column, question_column = st.columns(2, gap="large")
            with assumption_column, _concept_section("Assumptions"):
                for assumption in concept.assumptions:
                    st.text(assumption)
                if not concept.assumptions:
                    st.caption("None provided.")
            with question_column, _concept_section("Open questions"):
                for question in concept.open_questions:
                    st.text(question)
                if not concept.open_questions:
                    st.caption("None provided.")
        with st.expander("Raw ConceptPaper JSON", expanded=False):
            st.json(concept.model_dump(mode="json"))


st.set_page_config(
    page_title="HankeLuotsi AI",
    layout="wide",
    page_icon=str(ASSET_DIRECTORY / "hankeluotsi-mark.svg"),
)
apply_styles()
render_brand()
render_intro()

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
anchor("project-workspace")
with st.container(key="project_workspace"):
    idea_column, saved_column = st.columns([2.05, 1], gap="large")
    with saved_column:
        with st.container(key="saved_projects"):
            st.subheader("Saved projects")
            if projects:
                st.caption(f"{len(projects)} saved project{'s' if len(projects) != 1 else ''}")
            else:
                st.caption("Your saved ideas and concepts will appear here.")
                st.caption("Consistency results appear when you generate or open a concept.")
            selected_project_id = st.selectbox(
                "Open a saved project",
                options=project_options,
                format_func=lambda project_id: (
                    "Select a saved project" if project_id is None else _project_label(project_by_id[project_id])
                ),
                key="open_project_id",
            )
            if selected_project_id is not None:
                current = project_by_id[selected_project_id]
                st.caption(f"Saved {current.updated_at[:10]} · Stored on this device")
            else:
                st.caption("Reopen your work at any time. Your ideas stay in the local workspace.")
    with idea_column:
        context = st.expander("Start a new project idea", expanded=False, key="new_idea") if selected_project_id is not None else nullcontext()
        with context:
            st.subheader("New project idea")
            st.caption("Start with fictional information. A few structured details are enough.")
            with st.form("project_idea_form", clear_on_submit=False):
                title = st.text_input("Project title", key="idea_title", placeholder="e.g. Fictional Nordic creative futures")
                development_need = st.text_area("Development need", key="idea_development_need", height=88, placeholder="What needs to change, and why?")
                group_column, geography_column = st.columns([1.2, 1], gap="medium")
                with group_column:
                    target_groups = st.text_area(
                        "Target groups", help="Separate multiple groups with commas or new lines.", key="idea_target_groups", height=80,
                    )
                with geography_column:
                    geography = st.text_input("Geography", key="idea_geography", placeholder="e.g. Fictional Finland and Sweden")
                expected_change = st.text_area("Expected change", key="idea_expected_change", height=80, placeholder="What will be different for the target groups?")
                partner_column, funding_column = st.columns(2, gap="medium")
                with partner_column:
                    partners = st.text_area(
                        "Potential partners (optional)", help="Separate entries with commas or new lines.", key="idea_partners", height=68,
                    )
                with funding_column:
                    funding_context = st.text_input("Funding context (optional)", key="idea_funding_context")
                submitted = st.form_submit_button("Generate concept", type="primary", use_container_width=True)
        if selected_project_id is not None:
            _render_project_context(project_by_id[selected_project_id])

success_message = st.session_state.pop("pr5_success_message", None)
if success_message:
    st.success(success_message)
info_message = st.session_state.pop("pr5_info_message", None)
if info_message:
    st.info(info_message)
if selected_project_id is not None:
    _render_saved_project(project_by_id[selected_project_id])
    _render_funding_research(project_by_id[selected_project_id])

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

if selected_project_id is None:
    anchor("concept-paper")
    anchor("funding-opportunities")
st.markdown('<div class="workspace-footer"><span>HankeLuotsi AI · A clearer direction for project ideas.</span><span>Fictional data only · Human review required</span></div>', unsafe_allow_html=True)
