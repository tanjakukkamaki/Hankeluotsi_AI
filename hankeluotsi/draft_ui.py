"""Bilingual explicit draft/review/approval actions; no generation during rendering."""

import uuid
from datetime import date

import streamlit as st
from pydantic import ValidationError

from hankeluotsi.draft_checks import check_draft_consistency
from hankeluotsi.draft_exporter import export_approved_markdown
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport
from hankeluotsi.draft_workflow import WorkflowError, WorkflowService
from hankeluotsi.i18n import localize
from hankeluotsi.mistral_client import CloudConsent, CloudError, check_configuration
from hankeluotsi.repository import ProjectState
from hankeluotsi.planning_quality import check_planning_advisories


def _render_review_summary(review, tr, prefix):
    st.subheader(tr("AI review summary"))
    summary = " ".join(review.overall_assessment.split())
    if len(summary) > 360:
        summary = summary[:357].rsplit(" ", 1)[0] + "…"
    st.text(summary)
    st.caption(tr("AI suggestions: {count} · Information gaps: {gaps} · Uncertainties: {uncertainties}").format(
        count=len(review.findings), gaps=len(review.missing_information), uncertainties=len(review.uncertainties)))
    st.caption(tr("AI suggestions are not applied automatically. Read the details and uncertainties before approval."))
    with st.expander(tr("Review details and evidence"), expanded=False, key=prefix + "-review-details"):
        st.markdown("#### " + tr("Full assessment"))
        st.text(review.overall_assessment)
        for field, label in (("strengths", "Strengths"), ("missing_information", "Missing information"),
                             ("uncertainties", "Uncertainties")):
            st.markdown("#### " + tr(label))
            for text in getattr(review, field):
                st.text(text)
        for finding in review.findings:
            with st.container(border=True):
                st.text(finding.reference + " · " + tr(finding.severity))
                for label, text in (("Evidence quote", finding.evidence_quote), ("Observation", finding.observation),
                                    ("Suggested improvement", finding.suggestion)):
                    st.caption(tr(label))
                    st.text(text)


def render_draft_review(repository, project_id, language="en"):
    tr = lambda message: localize(message, language)
    prefix = "workflow-" + project_id
    project, source = repository.load_snapshot(project_id)
    consent_key = prefix + "-cloud-consent-" + source
    if st.session_state.pop(prefix + "-reset-consent", False):
        st.session_state.pop(consent_key, None)
    service = WorkflowService(repository)
    st.markdown('<div id="draft-review" class="section-anchor"></div>', unsafe_allow_html=True)
    st.subheader(tr("Draft & Review"))
    st.caption(tr("Drafts and AI suggestions need human verification. No funding eligibility is confirmed."))
    notice = st.session_state.pop(prefix + "-notice", None)
    if notice:
        (st.success if notice[0] else st.error)(tr(notice[1]))
        if len(notice) > 2 and notice[2] is not None:
            st.caption("HTTP " + str(notice[2]))
    if project.concept is None:
        st.info(tr("Generate and save a validated concept before creating an application draft."))
        return
    draft = review = None
    findings = []
    try:
        if project.draft is not None:
            draft = ApplicationDraft.model_validate(project.draft)
        if project.review is not None:
            review = ReviewReport.model_validate(project.review)
    except ValidationError:
        st.error(tr("This saved draft or review uses an unsupported contract. It has not been changed."))
        return
    st.caption(tr("Workflow status: ") + tr(project.state.value))
    if draft:
        with st.container(border=True, key=prefix + "-document"):
            st.subheader(tr("Application draft"))
            for field, label in (("project_summary", "Project summary"), ("background_need", "Needs and justification"),
                ("target_groups", "Target groups"), ("beneficiaries", "Beneficiaries"),
                ("general_objective", "General objective"), ("objectives", "Specific objectives"),
                ("work_packages", "Work packages"), ("activities", "Activities"), ("outputs", "Outputs"),
                ("expected_results", "Expected results"), ("proposed_indicators", "Indicators"),
                ("longer_term_impact", "Longer-term impact"), ("partner_roles", "Partner responsibilities"),
                ("timeline", "Preliminary timeline"), ("risks", "Risks and mitigation"),
                ("assumptions", "Assumptions"), ("sustainability", "Sustainability"), ("open_questions", "Open questions")):
                st.markdown("#### " + tr(label))
                value = getattr(draft, field)
                for item in value if isinstance(value, list) else [value]:
                    if hasattr(item, "model_dump"):
                        for key, text in item.model_dump().items():
                            labels = {"id": "ID", "objective_ids": "Linked objectives", "activity_ids": "Linked activities",
                                "work_package_id": "Work package", "result_ids": "Linked results", "measurement_method": "Measurement method",
                                "description": "Description", "partner": "Partner", "role": "Responsibility", "status": "Status",
                                "period": "Period", "mitigation": "Mitigation"}
                            if key == "status":
                                text = tr(text)
                            st.text(tr(labels.get(key, key)) + ": " +
                                (", ".join(text) if isinstance(text, list) else str(text)))
                    else:
                        st.text(item)
                if not value:
                    st.caption(tr("None provided."))
            if draft.generation_metadata:
                with st.expander(tr("Generation details")):
                    st.text(draft.generation_metadata.model_dump_json())
        st.markdown("#### " + tr("Draft consistency findings"))
        findings = check_draft_consistency(draft)
        if not findings:
            st.success(tr("No structural issues detected."))
        if findings:
            errors = sum(item.severity.value == "error" for item in findings)
            warnings = len(findings) - errors
            if errors:
                st.error(tr("Approval is blocked by {count} structural errors. Open the check details.").format(count=errors))
            if warnings:
                st.warning(tr("{count} structural warnings need your attention.").format(count=warnings))
            with st.expander(tr("Structural check details"), expanded=False, key=prefix + "-check-details"):
                for finding in findings:
                    (st.error if finding.severity.value == "error" else st.warning)(finding.code + ": " + finding.message)
    if draft:
        reference_date = date.today()
        observations = check_planning_advisories(draft, reference_date=reference_date)
        if observations:
            st.warning(tr("{count} planning observations need a context check.").format(count=len(observations)))
            with st.expander(tr("Planning observations (advisory)"), expanded=False, key=prefix + "-planning-observations"):
                st.caption(tr("Reference date: {date}. Advisory checks do not change the saved draft or approval.").format(date=reference_date.isoformat()))
                for observation in observations:
                    st.text(observation.code + ": " + tr(observation.message))
    if review:
        _render_review_summary(review, tr, prefix)
    if project.state == ProjectState.APPROVED:
        st.subheader(tr("Approve and export"))
        st.success(tr("Human-approved and locked. To make changes, create a new project record."))
        try:
            markdown = export_approved_markdown(repository, project_id, language=language)
        except Exception:
            st.error(tr("This record could not be safely exported. Saved data was preserved."))
            return
        st.download_button(tr("Download approved draft"), data=markdown,
            file_name="hankeluotsi-approved-" + project_id[:8] + ".md", mime="text/markdown",
            key=prefix + "-export", on_click="ignore", type="primary", use_container_width=True)
        st.caption(tr("Exports a Markdown (.md) file."))
        return
    # Reserve the main controls above Advanced, but read provider/consent before
    # calculating whether any generation action is safe to enable.
    main_controls = st.container(border=True, key=prefix + "-finalization")
    action = None
    approve_requested = False
    with st.expander(tr("Advanced options"), expanded=False, key=prefix + "-advanced"):
        st.caption(tr("Local native generation disables reasoning per request. Unknown completion status remains recorded; validation is not expert quality assurance."))
        provider = st.selectbox(tr("Draft and review provider"), ("local", "mistral"),
            format_func={"local": tr("Local Qwen (default)"), "mistral": tr("Mistral Cloud (optional)")}.get,
            key=prefix + "-provider", on_change=lambda: st.session_state.pop(consent_key, None))
        ready, confirmed = True, False
        if provider == "mistral":
            st.warning(tr("This action sends the saved fictional idea, concept and available draft to Mistral and may incur charges."))
            try:
                check_configuration()
            except CloudError as error:
                ready = False
                st.info(tr(str(error)))
            confirmed = st.checkbox(tr("I confirm the saved source material is fictional and consent to cloud processing and possible charges for the next stage."),
                key=consent_key, disabled=not ready)
            ready = ready and confirmed
        consent = CloudConsent(confirmed, confirmed)
        if draft:
            st.warning(tr("Generating a replacement overwrites this draft and removes its AI review. No draft history is kept."))
            replace_draft = st.checkbox(tr("Replace the current draft and invalidate its review. No draft history is kept."), key=prefix + "-replace-" + source)
            if st.button(tr("Regenerate draft"), key=prefix + "-draft", disabled=not ready or not replace_draft) and ready and replace_draft:
                action = "draft"
        if review:
            st.warning(tr("A new AI review replaces the current review and requires a fresh approval confirmation."))
            replace_review = st.checkbox(tr("Replace the current AI review"), key=prefix + "-replace-review-" + source)
            if st.button(tr("Review draft"), key=prefix + "-review", disabled=not ready or not replace_review) and ready and replace_review:
                action = "review"
    with main_controls:
        if not draft:
            st.subheader(tr("Create an application draft"))
            st.caption(tr("Generate a draft first, then review it before approval. Optional generation settings are in Advanced options."))
            if st.button(tr("Generate draft"), key=prefix + "-draft", disabled=not ready, type="primary") and ready:
                action = "draft"
        else:
            st.subheader(tr("Finish your draft"))
            choice_key = prefix + "-finalization-choice"
            if choice_key not in st.session_state:
                st.session_state[choice_key] = "approve" if review else "improve"
            choice = st.radio(tr("What would you like to do next?"), ("improve", "approve"),
                format_func={"improve": tr("Improve the draft"), "approve": tr("Approve and export")}.get,
                key=choice_key, index=None, horizontal=True)
            if choice == "improve":
                st.info(tr("Direct text editing is not available here yet. Read the suggestions to plan improvements. To generate a replacement, use Advanced options."))
                if not review:
                    if st.button(tr("Review draft"), key=prefix + "-review", disabled=not ready, type="primary") and ready:
                        action = "review"
                else:
                    st.caption(tr("Open Review details and evidence above to inspect each suggestion. You decide which changes are useful."))
            else:
                st.info(tr("Approval locks this version. To change an approved draft, create a new project record. After approval, download the approved draft here."))
                if not review:
                    st.warning(tr("Create an AI review under Improve the draft before approval."))
                blocked = not review or any(item.severity.value == "error" for item in findings)
                approved = st.checkbox(tr("I reviewed this exact draft, all findings and uncertainties and approve it for export."),
                    key=prefix + "-approve-consent-" + source, disabled=blocked)
                approve_requested = st.button(tr("Approve and prepare export"), disabled=blocked or not approved,
                    key=prefix + "-approve", type="primary", use_container_width=True) and approved and not blocked
    if action:
        operation_key = prefix + "-" + action + "-" + source
        operation = st.session_state.setdefault(operation_key, uuid.uuid4().hex)
        try:
            with st.spinner(tr("Generating and validating. Your last valid saved state is preserved on failure...")):
                method = service.generate_draft if action == "draft" else service.review_draft
                method(project_id, provider=provider, language=language, consent=consent,
                    operation_id=operation, expected_source=source)
            st.session_state[prefix + "-notice"] = (True, "Stage validated and saved.")
        except CloudError as error:
            st.session_state[prefix + "-notice"] = (False, str(error), error.http_status)
        except WorkflowError as error:
            st.session_state[prefix + "-notice"] = (False, str(error))
        except Exception:
            st.session_state[prefix + "-notice"] = (False, "The stage could not be validated or saved. Reload and check the provider or source; your saved data was preserved.")
        st.session_state[prefix + "-reset-consent"] = True
        st.rerun()
    if approve_requested:
        try:
            service.approve(project_id, operation_id=uuid.uuid4().hex, expected_source=source)
            st.session_state[prefix + "-notice"] = (True, "Current reviewed draft approved and locked.")
        except Exception:
            st.session_state[prefix + "-notice"] = (False, "Approval was blocked. Check deterministic errors and reload the current reviewed draft.")
        st.rerun()
