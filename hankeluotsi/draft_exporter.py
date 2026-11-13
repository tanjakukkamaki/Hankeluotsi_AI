"""Plain Markdown export through the durable human-approval gate."""

import html
import re

from hankeluotsi.draft_checks import check_draft_consistency, validate_review_evidence
from hankeluotsi.draft_schemas import ApplicationDraft, ReviewReport


DISCLAIMER = "AI-generated draft. Not a funding eligibility assessment. Verify requirements against the relevant funding programme."


def _text(value):
    value = html.escape(str(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|\->])", r"\\\1", value)


def export_approved_markdown(repository, project_id, *, language="en"):
    if language not in ("fi", "en"):
        raise ValueError("Export language must be fi or en")
    project = repository.load_for_export(project_id)
    draft = ApplicationDraft.model_validate(project.draft)
    review = ReviewReport.model_validate(project.review)
    validate_review_evidence(draft, review)
    findings = [item.to_dict() for item in check_draft_consistency(draft)]
    if findings != project.deterministic_findings or any(item["severity"] == "error" for item in findings):
        raise ValueError("Current validated draft and deterministic review are required for export")
    labels = {
        "Project summary": "Hankkeen yhteenveto", "Development need": "Kehittämistarve",
        "Target groups": "Kohderyhmät", "Beneficiaries": "Hyödynsaajat", "General objective": "Yleistavoite",
        "Objectives": "Tavoitteet", "Work packages": "Työpaketit", "Activities": "Toimenpiteet",
        "Outputs": "Tuotokset", "Expected results": "Odotetut tulokset", "Longer-term impact": "Pitkän aikavälin vaikutukset",
        "Indicators": "Mittarit", "Partner roles": "Kumppanien tehtävät", "Preliminary timeline": "Alustava aikataulu",
        "Risks and mitigation": "Riskit ja hallintakeinot", "Assumptions": "Oletukset", "Sustainability": "Jatkuvuus",
        "Open questions": "Avoimet kysymykset", "Deterministic findings": "Deterministiset havainnot",
        "AI review suggestions": "Tekoälyn arviointiehdotukset", "Strengths": "Vahvuudet",
        "Missing information": "Puuttuvat tiedot", "Uncertainties": "Epävarmuudet", "Generation metadata": "Generoinnin metatiedot",
        "Human approved": "Ihmisen hyväksymä", "None provided": "Ei annettu",
    }
    def label(value):
        return labels.get(value, value) if language == "fi" else value

    lines = ["# " + _text(project.idea.title), "", DISCLAIMER, "",
        label("Human approved") + ": " + _text(project.approved_at), "", "Project ID: " + _text(project.project_id)]

    def section(title, items):
        lines.extend(["", "## " + label(title), ""])
        if isinstance(items, str):
            lines.append(_text(items))
        else:
            lines.extend("- " + _text(item) for item in items)
            if not items:
                lines.append(label("None provided"))

    section("Project summary", draft.project_summary)
    section("Development need", draft.background_need)
    section("Target groups", draft.target_groups)
    section("Beneficiaries", draft.beneficiaries)
    section("General objective", draft.general_objective)
    section("Objectives", [f"{x.id}: {x.description}" for x in draft.objectives])
    section("Work packages", [f"{x.id}: {x.description} ({', '.join(x.objective_ids)})" for x in draft.work_packages])
    section("Activities", [f"{x.id}: {x.description} ({x.work_package_id}; {', '.join(x.objective_ids)})" for x in draft.activities])
    section("Outputs", draft.outputs)
    section("Expected results", [f"{x.id}: {x.description} ({', '.join(x.activity_ids)})" for x in draft.expected_results])
    section("Longer-term impact", draft.longer_term_impact)
    section("Indicators", [f"{x.id}: {x.description} ({', '.join(x.result_ids)}). {x.measurement_method}" for x in draft.proposed_indicators])
    section("Partner roles", [f"{x.partner} [{x.status}]: {x.role}" for x in draft.partner_roles])
    section("Preliminary timeline", [f"{x.work_package_id}: {x.period}" for x in draft.timeline])
    section("Risks and mitigation", [f"{x.description} — {x.mitigation}" for x in draft.risks])
    section("Assumptions", draft.assumptions)
    section("Sustainability", draft.sustainability)
    section("Open questions", draft.open_questions)
    section("Deterministic findings", [f"{x['code']} [{x['severity']}]: {x['message']}" for x in findings])
    section("AI review suggestions", review.overall_assessment)
    section("Strengths", review.strengths)
    for finding in review.findings:
        lines.extend(["", f"### {_text(finding.reference)} [{_text(finding.severity)}]", "",
            _text(finding.evidence_quote), "", _text(finding.observation), "", _text(finding.suggestion)])
    section("Missing information", review.missing_information)
    section("Uncertainties", review.uncertainties)
    metadata = []
    for stage, document in (("draft", draft), ("review", review)):
        item = document.generation_metadata
        if item is not None:
            metadata.append(f"{stage}: {item.provider}; {item.model}; {item.prompt_version}; finish={item.finish_reason}; incomplete/unknown={item.incomplete_output}")
    section("Generation metadata", metadata)
    return "\n".join(lines) + "\n"
