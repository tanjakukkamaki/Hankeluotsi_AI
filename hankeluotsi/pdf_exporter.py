import re
from io import BytesIO
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from hankeluotsi.schemas import ConceptPaper


DISCLAIMER = (
    "AI-generated draft. Not a funding eligibility assessment. "
    "Verify requirements against the relevant funding programme."
)
PRIMARY = colors.HexColor("#163A5F")
ACCENT = colors.HexColor("#2A9D8F")
TEXT = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#667789")
BORDER = colors.HexColor("#D9E2EC")
PALE_BLUE = colors.HexColor("#EAF4FF")


def _register_fonts() -> None:
    font_directory = Path(reportlab.__file__).resolve().parent / "fonts"
    fonts = {
        "HankeVera": font_directory / "Vera.ttf",
        "HankeVera-Bold": font_directory / "VeraBd.ttf",
    }
    for font_name, font_path in fonts.items():
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def _paragraph_text(value: str) -> str:
    return escape(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "HankeTitle",
            parent=styles["Title"],
            fontName="HankeVera-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_LEFT,
            textColor=PRIMARY,
            spaceAfter=1.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeSubtitle",
            parent=styles["Normal"],
            fontName="HankeVera",
            fontSize=9.5,
            leading=12,
            textColor=MUTED,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeSection",
            parent=styles["Heading2"],
            fontName="HankeVera-Bold",
            fontSize=12,
            leading=15,
            textColor=PRIMARY,
            spaceBefore=2 * mm,
            spaceAfter=1 * mm,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeBody",
            parent=styles["BodyText"],
            fontName="HankeVera",
            fontSize=9,
            leading=12,
            textColor=TEXT,
            spaceBefore=0,
            spaceAfter=0.8 * mm,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeEntry",
            parent=styles["HankeBody"],
            leftIndent=2.5 * mm,
            spaceBefore=0.5 * mm,
            spaceAfter=0.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeDisclaimer",
            parent=styles["HankeBody"],
            fontName="HankeVera-Bold",
            fontSize=8,
            leading=10.5,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "HankeEmpty",
            parent=styles["HankeBody"],
            fontName="HankeVera",
            fontSize=9,
            textColor=MUTED,
            italic=True,
        )
    )
    return styles


def _section(story: list[Flowable], title: str, entries: Iterable[Flowable], styles) -> None:
    story.append(Paragraph(escape(title), styles["HankeSection"]))
    story.extend(entries)


def _text_entry(value: str, styles) -> Paragraph:
    return Paragraph(_paragraph_text(value), styles["HankeBody"])


def _linked_entry(identifier: str, description: str, relation_label: str | None, related_ids, styles,
                  *, measurement_method: str | None = None):
    reference = f" <font color='{MUTED.hexval()}'>{escape(relation_label)}: {escape(', '.join(related_ids))}</font>" if relation_label else ""
    label = Paragraph(
        f"<font name='HankeVera-Bold' color='{ACCENT.hexval()}'>{escape(identifier)}</font>{reference}",
        styles["HankeEntry"],
    )
    label.keepWithNext = True
    body = Paragraph(_paragraph_text(description), styles["HankeEntry"])
    entries = [label, body]
    if measurement_method is not None:
        method_label = Paragraph("Measurement method", styles["HankeEntry"])
        method_label.keepWithNext = True
        entries.extend([method_label, Paragraph(_paragraph_text(measurement_method), styles["HankeEntry"])])
    # Ordinary entries move as a single block. ReportLab can still split an
    # exceptionally large entry that exceeds a full page instead of overflowing.
    return KeepTogether(entries)


def _draw_page(canvas, document) -> None:
    canvas.saveState()
    page_width, _ = A4
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 15 * mm, page_width - 20 * mm, 15 * mm)
    canvas.setFont("HankeVera", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(page_width - 20 * mm, 9.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def generate_concept_pdf(project_title: str, concept: ConceptPaper) -> bytes:
    """Render a validated concept paper as an in-memory A4 PDF."""
    _register_fonts()
    styles = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=project_title,
        author="HankeLuotsi AI",
        subject="AI-generated concept paper",
    )
    story: list[Flowable] = [
        Paragraph(_paragraph_text(project_title), styles["HankeTitle"]),
        Paragraph("Concept paper", styles["HankeSubtitle"]),
        HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=3 * mm),
    ]
    disclaimer = Table(
        [[Paragraph(_paragraph_text(DISCLAIMER), styles["HankeDisclaimer"])]],
        colWidths=[document.width],
    )
    disclaimer.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    story.extend([disclaimer, Spacer(1, 1.5 * mm)])

    _section(story, "Background", [_text_entry(concept.background_need, styles)], styles)
    _section(
        story,
        "Objectives",
        [
            _linked_entry(objective.id, objective.description, None, (), styles)
            for objective in concept.objectives
        ],
        styles,
    )
    _section(
        story,
        "Target groups",
        [_text_entry(group, styles) for group in concept.target_groups],
        styles,
    )
    _section(
        story,
        "Activities",
        [
            _linked_entry(
                activity.id,
                activity.description,
                "Linked objectives",
                activity.objective_ids,
                styles,
            )
            for activity in concept.preliminary_activities
        ],
        styles,
    )
    _section(
        story,
        "Expected results",
        [
            _linked_entry(
                result.id,
                result.description,
                "Linked activities",
                result.activity_ids,
                styles,
            )
            for result in concept.expected_results
        ],
        styles,
    )
    indicator_entries: list[Flowable] = []
    for indicator in concept.proposed_indicators:
        indicator_entries.append(
            _linked_entry(
                indicator.id,
                indicator.description,
                "Linked results",
                indicator.result_ids,
                styles,
                measurement_method=indicator.measurement_method,
            )
        )
    _section(story, "Indicators", indicator_entries, styles)

    assumptions = [
        _text_entry(item, styles) for item in concept.assumptions
    ] or [Paragraph("None provided.", styles["HankeEmpty"])]
    _section(story, "Assumptions", assumptions, styles)
    questions = [
        _text_entry(item, styles) for item in concept.open_questions
    ] or [Paragraph("None provided.", styles["HankeEmpty"])]
    _section(story, "Open questions", questions, styles)

    document.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()


def concept_pdf_filename(project_title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project_title.casefold()).strip("-")
    return f"{slug or 'hankeluotsi'}-concept-paper.pdf"
