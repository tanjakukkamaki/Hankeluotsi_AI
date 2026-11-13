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
from hankeluotsi.funding_calls import compare_call_locally
from hankeluotsi.funding_matching import RELEVANCE_CATEGORIES, rank_funding_calls
from hankeluotsi.live_funding import search_live_funding_calls
from hankeluotsi.mistral_client import CloudConsent, CloudError, check_configuration, select_client
from hankeluotsi.draft_ui import render_draft_review
from hankeluotsi.i18n import language_code, localize
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


def ui(message: str) -> str:
    return localize(message, st.session_state.get("ui_language", "en"))


def system_ui(message: str) -> str:
    return localize(message, st.session_state.get("ui_language", "en"), system_values=True)


def _locale_key(base: str) -> str:
    return base + ("_fi" if st.session_state.get("ui_language") == "fi" else "")


def _date_display(value) -> str:
    from datetime import date
    suffix = " (date only; exact time/timezone unverified)" if type(value.value) is date else ""
    return value.value.isoformat() + ui(suffix)


def _operation_id(operation: str, submission_id: str) -> str:
    return f"pr5:{operation}:{submission_id}"


def _project_label(project: ProjectRecord, language: str = "en") -> str:
    state = localize(project.state.value.replace("_", " "), language)
    return f"{project.idea.title} · {state} · {project.project_id[:8]}"


def _concept_generation_input(idea: ProjectIdea, language: str = "en") -> str:
    return (
        "Fictional project idea:\n"
        f"{idea.model_dump_json()}\n\n"
        "Create a concise ConceptPaper with exactly one objective (O1), one preliminary "
        "activity (A1) linked to O1, one expected result (R1) linked to A1, and one "
        "measurable proposed indicator (I1) linked to R1. Use one target group. Keep "
        "descriptions to one short sentence each. Use empty assumptions and open_questions.\n\n"
        f"Write all human-readable text fields in {'Finnish' if language_code(language) == 'fi' else 'English'}. "
        "Keep JSON field names, schema_version and O/A/R/I identifiers unchanged. Do not translate keys or IDs."
    )


def _render_section_heading(title: str) -> None:
    st.markdown(ui(f"#### {title}"))


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
        f'<span class="concept-relationship">{ui(relationship_label)}: {", ".join(related_ids)}</span>'
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
        heading, error_column, warning_column = st.columns([3, 1, 1], vertical_alignment="center")
        with heading:
            st.subheader(ui("Consistency Check"))
        error_column.metric(ui("Errors"), len(errors))
        warning_column.metric(ui("Warnings"), len(warnings))
        st.caption(
            ui("Deterministic structural checks only. This does not assess content quality "
            "or funding eligibility.")
        )
        if errors:
            st.error(ui("Structural validation found errors that need attention."))
        elif warnings:
            st.warning(ui("No broken references found, but some concept elements are disconnected."))
        else:
            st.success(ui("No structural issues detected."))

        for finding in findings:
            display = (
                st.error
                if finding.severity == FindingSeverity.ERROR
                else st.warning
            )
            display(f"{finding.code.value}: {system_ui(finding.message)}")
            affected = ui(f"Affected ID: `{finding.element_id}`") if finding.element_id else None
            related = (
                ui(f"Related IDs: {', '.join(f'`{item}`' for item in finding.related_ids)}")
                if finding.related_ids
                else None
            )
            details = " · ".join(item for item in (affected, related) if item)
            if details:
                st.caption(details)


def _render_live_funding_calls(project: ProjectRecord) -> None:
    st.markdown(ui("#### Live funding calls from official sources"))
    st.caption(
        ui("Search the official Aurora timetable and Horizon Europe grant topics. "
        "Only fixed public requests are sent; project text stays local.")
    )
    if st.button(ui("Search Live Funding Calls"), key=f"live-funding-search-{project.project_id}", type="primary"):
        with st.spinner(ui("Reading official funding sources...")):
            result = search_live_funding_calls()
        st.session_state["live_funding_result"] = (
            project.project_id, project.idea.model_dump_json(), result, datetime.now(timezone.utc),
        )
        st.session_state.pop(_locale_key(f"ranked-live-call-selection-{project.project_id}"), None)
    cached = st.session_state.get("live_funding_result")
    if not cached or cached[:2] != (project.project_id, project.idea.model_dump_json()):
        st.caption(ui("No live search has been run for this saved idea. General programme suggestions are available below."))
        return
    result, attempted_at = cached[2:]
    st.caption(ui(f"Last explicit search completed: {attempted_at.isoformat()}. Results last for this app session."))
    if result.notices:
        st.warning("\n\n".join(system_ui(notice) for notice in result.notices))
    if not result.calls:
        st.info(ui("No live call records could be verified. Use the official sources and general programme guidance below."))
        st.link_button(ui("Official Aurora calls"), "https://www.interregaurora.eu/projects/calls-for-applications-2/")
        st.link_button(ui("Official EU funding calls"), "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals")
        return
    now = datetime.now(timezone.utc)
    ranked = rank_funding_calls(project.idea, result.calls, concept=project.concept, now=now)
    statuses = {f"{item.call.source}:{item.call.identifier}": (item.status, item.status_reason) for item in ranked}
    st.caption(
        ui(f"{len(result.calls)} published call/topic records. ")
        + "; ".join(f"{ui(status)}: {sum(value[0] == status for value in statuses.values())}" for status in ("open", "upcoming", "closed", "unknown"))
    )
    st.caption(
        ui("Statuses are checked locally against official labels and dates. Date-only boundaries "
        "remain conservative; snapshots older than six hours become unknown. Refresh explicitly.")
    )
    st.caption(
        ui("Sorted by local research relevance, then score, then status. High/Medium/Low describe "
        "wording overlap, never eligibility or a funding probability. All categories and statuses "
        "are included by default. Ranking covers this retrieved window, not every EU call.")
    )
    st.caption(" · ".join(f"{ui(category)}: {sum(item.category == category for item in ranked)}" for category in RELEVANCE_CATEGORIES))
    if not any(item.category in ("High", "Medium") for item in ranked):
        st.info(ui("No High or Medium relevance found in this snapshot. Low and unmatched records remain available; try the official sources and programme guides for wider research."))
    relevance_column, programme_column, status_column = st.columns(3)
    with relevance_column:
        relevance_filter = st.multiselect(ui("Relevance"), options=RELEVANCE_CATEGORIES,
            default=list(RELEVANCE_CATEGORIES), format_func={value: ui(value) for value in RELEVANCE_CATEGORIES}.get, key=_locale_key(f"live-relevance-{project.project_id}"))
    programmes = sorted({item.call.programme for item in ranked})
    programme_key = f"live-programme-{project.project_id}"
    if programme_key in st.session_state:
        previous_programmes = st.session_state[programme_key]
        remaining_programmes = [value for value in previous_programmes if value in programmes]
        st.session_state[programme_key] = remaining_programmes or (programmes if previous_programmes else [])
    with programme_column:
        programme_filter = st.multiselect(ui("Funding programme"), options=programmes,
            default=programmes, key=programme_key)
    with status_column:
        status_filter = st.multiselect(ui("Call status"), options=("open", "upcoming", "closed", "unknown"),
            default=["open", "upcoming", "closed", "unknown"], format_func={value: ui(value) for value in ("open", "upcoming", "closed", "unknown")}.get, key=_locale_key(f"live-status-{project.project_id}"))
    visible = [item for item in ranked if item.category in relevance_filter
               and item.call.programme in programme_filter and item.status in status_filter]
    st.caption(ui(f"Showing {len(visible)} of {len(ranked)} retrieved records. All relevance levels remain available in the filters."))
    if not visible:
        st.info(ui("No calls match these filters. Include Low, Insufficient Information or other statuses/programmes to see more records."))
        return
    by_id = {f"{item.call.source}:{item.call.identifier}": item for item in visible}
    options = list(by_id)
    selection_key = _locale_key(f"ranked-live-call-selection-{project.project_id}")
    if st.session_state.get(selection_key) not in options:
        st.session_state[selection_key] = options[0]
    selected = st.selectbox(
        ui("Inspect a live call"),
        options=options,
        format_func={key: f"{ui(ui(by_id[key].category) + ' relevance')} | {ui(statuses[key][0])} | {by_id[key].call.identifier} | {by_id[key].call.title}" for key in options}.get,
        key=selection_key,
    )
    match = by_id[selected]
    call = match.call
    with st.container(border=False, key="live_call_card"):
        status_badge(ui(f"{ui(match.category)} relevance"), tone="teal" if match.category == "High" else "neutral")
        st.text(ui(f"Local relevance score: {match.score}/100" if match.score is not None else "Local relevance score: not assigned — insufficient evidence"))
        st.caption(ui(f"Matching confidence: {ui(match.confidence)}. A heuristic evidence assessment, not confirmed eligibility."))
        status_badge(ui(statuses[selected][0].capitalize()), tone="teal" if statuses[selected][0] == "open" else "neutral")
        with st.container(key="live_call_title"):
            st.text(call.title)
        st.text(ui(f"Programme: {call.programme}"))
        st.text(ui(f"Official identifier: {call.identifier}"))
        st.text(ui(f"Current status: {ui(statuses[selected][0])}"))
        st.text(system_ui(statuses[selected][1]))
        opening_column, deadline_column = st.columns(2)
        with opening_column:
            st.text(ui("Opening: " + (_date_display(call.opening) if call.opening else ui("Unknown"))))
        with deadline_column:
            st.text(ui("Deadline: " + (_date_display(call.deadline) if call.deadline else ui("Unknown"))))
        st.link_button(ui("Official call page"), call.source_url)
        retrieved_display = call.retrieved_at.astimezone(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC" if st.session_state.get("ui_language") == "fi" else "%d %b %Y, %H:%M UTC")
        st.caption(ui(f"Call record retrieved: {retrieved_display}"))
        st.caption(ui("Official-source reference matches a supported retrieval adapter; availability is not rechecked on reruns."
                   if match.source_reference_confirmed else "Official-source reference unconfirmed. This record is not verified."))
        st.markdown(ui("**Local comparison and requirements to check**"))
        for reason in match.reasons:
            st.text(system_ui(reason))
        for caution in match.cautions:
            st.text(system_ui(caution))
        with st.expander(ui("How this local match was calculated"), expanded=False):
            st.text(ui("Rule version 1: theme coverage (up to 80), named geography (-5 to 10), explicit partner-type wording (-5 to 10). Target groups do not establish an applicant type."))
            if match.score is not None:
                st.text(ui(f"Theme points: {match.thematic_points}; geography points: {match.geography_points}; partner-type points: {match.applicant_points}. Total is bounded to 0–100."))
            st.text(ui("Core idea and concept objectives weigh twice target-group-only themes. Call title evidence weighs 1; objectives excerpt weighs 0.8. Broad digital/research/innovation words alone cannot produce Medium or High relevance."))
            st.text(ui("Known non-art phrases such as state-of-the-art and innovation culture are ignored for cultural matching. An unsupported specialist title without a specific shared title theme caps theme points at 24."))
            st.text(ui("High requires at least 55 theme points and two specific shared themes; Medium requires at least 25 and one specific theme. Missing descriptions or differing named conditions cap High at Medium. Missing/unconfirmed evidence can leave a record unscored."))
        topics = compare_call_locally(project.idea, call)
        st.text(ui("Shared vocabulary topics: " + (", ".join(ui(topic) for topic in topics) or ui("No overlap detected"))))
        st.caption(ui("Source text is shown in its original language and is not automatically translated."))
        st.caption(ui("Topics overlap in the saved idea and call title/objectives. This does not establish suitability or eligibility."))
        st.caption(ui("Source excerpts may be incomplete. Verify all requirements and exact submission deadlines in the official call documents."))
        with st.expander(ui("Objectives & applicant information"), expanded=False):
            for label, value in (
                ("Funding objectives / source excerpt", call.objectives),
                ("Geographical area", call.geographic_area),
                ("Applicant requirements / source excerpt", call.applicant_requirements),
            ):
                st.markdown(ui(f"**{label}**"))
                st.text(value if value else ui("Unknown — check the official call documents."))
            for uncertainty in call.uncertainties:
                st.text(system_ui(uncertainty))
        with st.expander(ui("Source evidence & original dates"), expanded=False):
            if call.call_identifier:
                st.text(ui(f"Parent call identifier: {call.call_identifier}"))
            st.text(ui(f"Published source status: {ui(call.official_status)}"))
            for label, value in (("Opening source value", call.opening), ("Deadline source value", call.deadline)):
                if value:
                    st.text(f"{ui(label)}: {value.raw}")
            st.link_button(ui("Retrieved source evidence"), call.evidence_url)
            st.caption(ui(f"Original retrieval timestamp: {call.retrieved_at.isoformat()}"))
            st.caption(ui("Source updated: " + (call.source_updated_on.isoformat() if call.source_updated_on else ui("Unknown"))))


def _render_funding_research(project: ProjectRecord) -> None:
    anchor("funding-opportunities")
    with st.expander(ui("Find Funding Opportunities (optional)"), expanded=False, key="funding_research"):
        st.caption(
            ui("Official live calls and preliminary programme research. "
            "This does not assess funding eligibility. Project information stays local.")
        )
        _render_live_funding_calls(project)
        st.markdown(ui("#### General programme suggestions"))
        with st.form(f"funding-search-{project.project_id}"):
            retrieve_live = st.checkbox(
                ui("Retrieve public programme page descriptions online"),
                value=False,
                help=ui("Requests four fixed official pages, with no project text or search terms. May take about 20 seconds on timeouts."),
                key=f"funding-live-{project.project_id}",
            )
            search = st.form_submit_button(ui("Find Funding Opportunities"))
        # These are temporary research results. The saved idea is always read from
        # SQLite; a changed idea invalidates its previous local research display.
        research_key = "funding_research_result"
        idea_snapshot = project.idea.model_dump_json()
        if search:
            with st.spinner(ui("Loading official programme guidance and comparing locally...")):
                records = retrieve_funding_opportunities(retrieve_live=retrieve_live)
            st.session_state[research_key] = (project.project_id, idea_snapshot, records)
        saved_research = st.session_state.get(research_key)
        if not saved_research or saved_research[:2] != (project.project_id, idea_snapshot):
            st.caption(ui("Choose Find Funding Opportunities to compare the saved idea with programme guidance."))
            return
        records = saved_research[2]
        st.warning(
            ui("Programme guidance only — these general suggestions contain no verified current calls. Call titles, dates and "
            "open/closed status are unknown. General guidance was checked on 8 November 2026 "
            "and may become outdated.")
        )
        st.caption(
            ui("Comparison uses a small English/Finnish topic vocabulary locally. Shared topics "
            "are research clues, not scores. Geography, applicant conditions and partnerships "
            "require manual checking. Results last only for this app session.")
        )
        # Six static guide names/topic labels need no dataframe runtime.
        st.markdown(
            f"| {ui('Programme')} | {ui('Shared topics')} | {ui('Call status')} |\n| --- | --- | --- |\n"
            + "\n".join(
                f"| {item.funding_programme} | "
                f"{', '.join(ui(topic) for topic in compare_locally(project.idea, item)) or ui('No vocabulary overlap detected')} | "
                f"{ui(item.status)} |"
                for item in records
            )
        )
        for item in records:
            with st.container(border=False, key=f"programme_card_{item.record_id}"):
                status_badge(ui("Programme guide · call details unknown"))
                st.text(item.funding_programme)
                st.link_button(ui("Official calls / funding source"), item.official_source_url)
                description_status = {
                    "not_requested": "Offline guide",
                    "retrieved": "Page description retrieved",
                    "unavailable": "Live description unavailable",
                }[item.retrieval_state]
                st.caption(ui(f"Guidance checked {item.guidance_verified_on.isoformat()} · {ui(description_status)}"))
                with st.expander(ui("Programme details & evidence"), expanded=False, key=f"programme_details_{item.record_id}"):
                    st.text(ui("Call title: " + (item.call_title or ui("Unknown — no individual call retrieved"))))
                    st.text(ui("Application dates: " + (item.application_dates or ui("Unknown — check the official call"))))
                    st.text(ui(f"Call status: {ui(item.status)}"))
                    st.caption(ui("Source text is shown in its original language and is not automatically translated."))
                    st.markdown(ui("**Objectives and priorities**"))
                    for objective in item.objectives_and_priorities:
                        st.text(objective)
                    st.markdown(ui("**Geographic scope to check**"))
                    st.text(item.geographic_eligibility)
                    st.markdown(ui("**Applicant requirements to check**"))
                    st.text(item.applicant_requirements)
                    st.caption(ui(f"General guidance verified: {item.guidance_verified_on.isoformat()}"))
                    for index, url in enumerate(item.guidance_urls, start=1):
                        st.link_button(ui(f"Guidance source {index}"), url)
                    if item.retrieval_state == "retrieved":
                        st.caption(ui(f"Page description retrieved: {item.information_retrieved_at.isoformat()}"))
                        st.link_button(ui("Retrieved programme page"), item.retrieved_from_url)
                        st.text(item.source_excerpt)
                        st.caption(ui("Page metadata only; it does not update or verify the guidance or call conditions above."))
                    elif item.retrieval_state == "unavailable":
                        st.caption(ui("Live programme page description unavailable. Showing reviewed guidance and official links."))
                    else:
                        st.caption(ui("Live retrieval not requested. Showing reviewed guidance and official links."))
                    for uncertainty in item.uncertainty:
                        st.text(system_ui(uncertainty))


def _render_project_context(project: ProjectRecord) -> None:
    with st.container(key="project_context"):
        st.subheader(ui("Saved project"))
        st.caption(ui(f"Status: {ui(project.state.value)}"))
        with st.expander(ui("Project idea · saved input"), expanded=False):
            st.markdown(ui("#### Project idea"))
            for label, value in (
                ("Title", project.idea.title),
                ("Development need", project.idea.development_need),
                ("Expected change", project.idea.expected_change),
                ("Geography", project.idea.geography),
            ):
                st.markdown(ui(f"**{label}**"))
                st.text(value)
            st.markdown(ui("**Target groups**"))
            for target_group in project.idea.target_groups:
                st.text(target_group)
            if project.idea.partners:
                st.markdown(ui("**Potential partners**"))
                for partner in project.idea.partners:
                    st.text(partner)
            if project.idea.funding_context:
                st.markdown(ui("**Funding context**"))
                st.text(project.idea.funding_context)
            with st.expander(ui("Raw project idea JSON"), expanded=False):
                st.json(project.idea.model_dump(mode="json"))


def _render_saved_project(project: ProjectRecord) -> None:
    anchor("concept-paper")
    if project.concept is None:
        st.info(ui("Your project idea is saved. A concept has not been generated for this record yet."))
        return
    concept = project.concept
    with st.container(key="concept_document"):
        concept_heading, pdf_action = st.columns([0.72, 0.28], vertical_alignment="center")
        with concept_heading:
            st.subheader(ui("Concept paper"))
            st.caption(ui("AI-generated draft · Pydantic validated"))
        with pdf_action:
            st.download_button(
                ui("Download PDF"),
                data=generate_concept_pdf(project.idea.title, concept, language=st.session_state.get("ui_language", "en")),
                file_name=concept_pdf_filename(project.idea.title),
                mime="application/pdf",
                key=f"download-concept-{project.project_id}",
                on_click="ignore",
                use_container_width=True,
            )
            st.caption(ui("PDF labels follow the interface language; saved document text is unchanged."))
        with st.container(key="concept_document_title"):
            st.text(project.idea.title)
        with st.container(key="concept_summary"):
            columns = st.columns(4)
            for column, label, count in zip(columns,
                ("Objectives", "Activities", "Results", "Indicators"),
                (len(concept.objectives), len(concept.preliminary_activities), len(concept.expected_results), len(concept.proposed_indicators))):
                column.metric(ui(label), count)
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
                    st.markdown(ui("**Measurement method**"))
                    st.text(indicator.measurement_method)
            assumption_column, question_column = st.columns(2, gap="large")
            with assumption_column, _concept_section("Assumptions"):
                for assumption in concept.assumptions:
                    st.text(assumption)
                if not concept.assumptions:
                    st.caption(ui("None provided."))
            with question_column, _concept_section("Open questions"):
                for question in concept.open_questions:
                    st.text(question)
                if not concept.open_questions:
                    st.caption(ui("None provided."))
        with st.expander(ui("Raw ConceptPaper JSON"), expanded=False):
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
    st.error(ui(f"Could not open the local project database: {error}"))
    st.stop()

project_by_id = {project.project_id: project for project in projects}
project_options = [None, *project_by_id]
pending_project_id = st.session_state.pop("pr5_pending_project_id", None)
if pending_project_id in project_by_id:
    st.session_state[_locale_key("open_project_id")] = pending_project_id
anchor("project-workspace")
with st.container(key="project_workspace"):
    idea_column, saved_column = st.columns([2.05, 1], gap="large")
    with saved_column:
        with st.container(key="saved_projects"):
            st.subheader(ui("Saved projects"))
            if projects:
                st.caption(ui(f"{len(projects)} saved project{'s' if len(projects) != 1 else ''}"))
            else:
                st.caption(ui("Your saved ideas and concepts will appear here."))
                st.caption(ui("Consistency results appear when you generate or open a concept."))
            selected_project_id = st.selectbox(
                ui("Open a saved project"),
                options=project_options,
                format_func={None: ui("Select a saved project"), **{
                    project_id: _project_label(project, st.session_state.get("ui_language", "en"))
                    for project_id, project in project_by_id.items()
                }}.get,
                key=_locale_key("open_project_id"),
            )
            if selected_project_id is not None:
                current = project_by_id[selected_project_id]
                st.caption(ui(f"Saved {current.updated_at[:10]} · Stored on this device"))
            else:
                st.caption(ui("Reopen your work at any time. Your ideas stay in the local workspace."))
    with idea_column:
        context = st.expander(ui("Start a new project idea"), expanded=False, key="new_idea") if selected_project_id is not None else nullcontext()
        with context:
            st.subheader(ui("New project idea"))
            provider = st.selectbox(
                ui("Generation provider"), options=("local", "mistral"),
                format_func={"local": ui("Local Qwen (default)"), "mistral": ui("Mistral Cloud (optional)")}.get,
                key="generation_provider",
                on_change=lambda: st.session_state.pop("cloud_consent", None),
            )
            cloud_ready = True
            consent = CloudConsent()
            if provider == "mistral":
                st.warning(ui("Mistral sends this new idea to an external cloud service and may incur charges. Use fictional data only. Saved projects are not sent."))
                try:
                    cloud_model = check_configuration()
                    st.caption(ui(f"Cloud model: {cloud_model}"))
                except CloudError as error:
                    cloud_ready = False
                    st.info(ui(str(error)))
                confirmed = st.checkbox(
                    ui("I confirm all entered data is fictional and consent to Mistral cloud processing and possible charges for this submission."),
                    key="cloud_consent", disabled=not cloud_ready,
                )
                consent = CloudConsent(fictional_data=confirmed, cloud_processing=confirmed)
                cloud_ready = cloud_ready and confirmed
            st.caption(ui("Start with fictional information. A few structured details are enough."))
            with st.form("project_idea_form", clear_on_submit=False):
                title = st.text_input(ui("Project title"), key="idea_title", placeholder=ui("e.g. Fictional Nordic creative futures"))
                development_need = st.text_area(ui("Development need"), key="idea_development_need", height=88, placeholder=ui("What needs to change, and why?"))
                group_column, geography_column = st.columns([1.2, 1], gap="medium")
                with group_column:
                    target_groups = st.text_area(
                        ui("Target groups"), help=ui("Separate multiple groups with commas or new lines."), key="idea_target_groups", height=80,
                    )
                with geography_column:
                    geography = st.text_input(ui("Geography"), key="idea_geography", placeholder=ui("e.g. Fictional Finland and Sweden"))
                expected_change = st.text_area(ui("Expected change"), key="idea_expected_change", height=80, placeholder=ui("What will be different for the target groups?"))
                partner_column, funding_column = st.columns(2, gap="medium")
                with partner_column:
                    partners = st.text_area(
                        ui("Potential partners (optional)"), help=ui("Separate entries with commas or new lines."), key="idea_partners", height=68,
                    )
                with funding_column:
                    funding_context = st.text_input(ui("Funding context (optional)"), key="idea_funding_context")
                submitted = st.form_submit_button(ui("Generate concept"), type="primary", use_container_width=True,
                    disabled=provider == "mistral" and not cloud_ready)
        if selected_project_id is not None:
            _render_project_context(project_by_id[selected_project_id])

success_message = st.session_state.pop("pr5_success_message", None)
if success_message:
    st.success(ui(success_message))
info_message = st.session_state.pop("pr5_info_message", None)
if info_message:
    st.info(ui(info_message))
if selected_project_id is not None:
    _render_saved_project(project_by_id[selected_project_id])
    render_draft_review(repository, selected_project_id, st.session_state.get("ui_language", "en"))
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
        if st.session_state.get("ui_language") == "fi":
            field_labels = {"title": "Project title", "development_need": "Development need",
                "target_groups": "Target groups", "expected_change": "Expected change", "geography": "Geography",
                "partners": "Potential partners", "funding_context": "Funding context"}
            details = "; ".join(
                ui(field_labels.get(str(item["loc"][0]), str(item["loc"][0]))) + ": "
                + ui("This field is required." if item["type"] == "missing" else "Check the value.")
                for item in error.errors()
            )
        st.error(ui(f"Please correct the project idea: {details}"))
    else:
        submission_id = uuid.uuid4().hex
        idea_operation_id = _operation_id("create", submission_id)
        concept_operation_id = _operation_id("concept", submission_id)
        try:
            # Enforce consent/configuration again at the service boundary before saving/calling.
            client = select_client(provider, consent=consent)
            project = repository.create_project(idea, operation_id=idea_operation_id)
            if project.concept is not None:
                st.session_state["pr5_pending_project_id"] = project.project_id
                st.session_state["pr5_info_message"] = (
                    "This project already has a saved concept. No duplicate generation was started."
                )
                st.rerun()

            progress = "Generating and validating the concept with the local model..." if provider == "local" else "Generating and validating the concept with Mistral Cloud..."
            with st.spinner(ui(progress)):
                result = client.generate(
                    "concept",
                    _concept_generation_input(idea, st.session_state.get("ui_language", "en")),
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
        except CloudError as error:
            st.error(ui(str(error)))
            if error.http_status is not None:
                st.caption("HTTP " + str(error.http_status))
        except ValidationError as error:
            st.error(ui(f"The generated concept did not pass validation and was not saved: {error}"))
        except Exception as error:
            st.error(ui(f"Concept generation or saving failed. Your valid saved data was preserved: {error}"))

if selected_project_id is None:
    anchor("concept-paper")
    anchor("funding-opportunities")
    anchor("draft-review")
    st.caption(ui("Open a saved concept to generate an application draft and AI review."))
st.markdown('<div class="workspace-footer"><span>HankeLuotsi AI · ' + ui('A clearer direction for project ideas.') + '</span><span>' + ui('Fictional data only · Human review required') + '</span></div>', unsafe_allow_html=True)
