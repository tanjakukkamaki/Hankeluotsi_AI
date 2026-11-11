import json
import math
import re
from pathlib import Path

import pytest
from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table

from hankeluotsi import pdf_exporter
from hankeluotsi.pdf_exporter import concept_pdf_filename, generate_concept_pdf
from hankeluotsi.schemas import ConceptPaper


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "concept_paper.json"


def load_concept_data():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def render_with_page_trace(monkeypatch, concept):
    """Record actual laid-out paragraphs/pages without an extra PDF dependency."""
    paragraphs, footers = [], []
    draw_right_string = Canvas.drawRightString

    def record_content(document, flowable):
        if isinstance(flowable, Paragraph):
            paragraphs.append((document.page, flowable.getPlainText(), flowable.style))
        elif isinstance(flowable, Table):
            for row in flowable._cellvalues:
                for cell in row:
                    for child in cell if isinstance(cell, (tuple, list)) else [cell]:
                        record_content(document, child)

    def record_footer(canvas, x, y, text, *args, **kwargs):
        if text.startswith("Page "):
            footers.append((canvas.getPageNumber(), text))
        return draw_right_string(canvas, x, y, text, *args, **kwargs)

    monkeypatch.setattr(pdf_exporter.SimpleDocTemplate, "afterFlowable", record_content)
    monkeypatch.setattr(Canvas, "drawRightString", record_footer)
    pdf = generate_concept_pdf("Fictional Ääni — community arts", concept)
    return pdf, paragraphs, footers


def padded_concept(repeats):
    payload = load_concept_data()
    payload["background_need"] += " " + (
        "Fictional community participants practise digital skills through accessible arts workshops. "
        * repeats
    )
    return ConceptPaper.model_validate(payload)


def test_concept_pdf_is_a4_has_embedded_unicode_font_and_preserves_input():
    payload = load_concept_data()
    payload["background_need"] = "Fictional Finnish need: ä, ö, å, Ä, Ö, Å; English: community arts."
    payload["open_questions"] = ["Mitä tukea tarvitaan?", "How can volunteers continue?"]
    concept = ConceptPaper.model_validate(payload)
    original = concept.model_dump(mode="json")

    pdf = generate_concept_pdf("Fictional Ääni & Arts", concept)

    assert pdf.startswith(b"%PDF-")
    assert b"/FontFile2" in pdf
    assert b"/ToUnicode" in pdf
    assert concept.model_dump(mode="json") == original
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1
    media_box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    assert media_box is not None
    assert math.isclose(float(media_box.group(1)), A4[0], abs_tol=0.001)
    assert math.isclose(float(media_box.group(2)), A4[1], abs_tol=0.001)
    unicode_font = pdfmetrics.getFont("HankeVera")
    for character in "äöåÄÖÅ":
        assert unicode_font.face.charToGlyph[ord(character)] != 0


def test_concept_pdf_paginated_for_long_existing_content():
    payload = load_concept_data()
    payload["open_questions"] = [
        f"Fictional question {index}: How can participants continue using the selected digital practice?"
        for index in range(80)
    ]
    concept = ConceptPaper.model_validate(payload)

    pdf = generate_concept_pdf("Fictional long concept", concept)

    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) >= 2


def test_near_one_page_concept_fits_without_smaller_type_or_lost_content(monkeypatch):
    concept = padded_concept(3)  # Previously two pages, with only a short tail on page 2.
    original = concept.model_dump(mode="json")
    pdf, trace, footers = render_with_page_trace(monkeypatch, concept)
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1
    rendered = " ".join(text for _, text, _ in trace)
    for value in (concept.background_need, *concept.target_groups, *concept.assumptions, *concept.open_questions):
        assert value in rendered
    for entry in (*concept.objectives, *concept.preliminary_activities, *concept.expected_results, *concept.proposed_indicators):
        assert entry.description in rendered
        assert re.search(r"\b" + entry.id + r"\b", rendered)
    for indicator in concept.proposed_indicators:
        assert indicator.measurement_method in rendered
    assert pdf_exporter.DISCLAIMER in rendered
    body_styles = [style for _, _, style in trace if style.name in ("HankeBody", "HankeEntry")]
    assert body_styles and all(style.fontSize >= 9 and style.leading >= 12 for style in body_styles)
    assert footers == [(1, "Page 1")]
    assert concept.model_dump(mode="json") == original


@pytest.mark.parametrize("repeats", [12, 17, 24, 35])
def test_indicator_id_description_and_measurement_stay_on_same_page(monkeypatch, repeats):
    concept = padded_concept(repeats)
    pdf, trace, footers = render_with_page_trace(monkeypatch, concept)
    pages = len(re.findall(rb"/Type\s*/Page\b", pdf))
    assert pages >= 2
    for indicator in concept.proposed_indicators:
        id_pages = [page for page, text, _ in trace if re.match(re.escape(indicator.id) + r"\b", text)]
        description_pages = [page for page, text, _ in trace if text == indicator.description]
        method_index = next(index for index, (_, text, _) in enumerate(trace) if text == indicator.measurement_method)
        method_page = trace[method_index][0]
        assert id_pages == description_pages == [method_page]
        assert trace[method_index - 1][:2] == (method_page, "Measurement method")
    assert footers == [(page, f"Page {page}") for page in range(1, pages + 1)]
    assert {page for page, _, _ in trace} == set(range(1, pages + 1))


def test_indicator_larger_than_a_page_splits_naturally_without_losing_its_end(monkeypatch):
    # Uncompressed content allows checking actual PDF text: getPlainText() is
    # empty on ReportLab's already-split paragraphs, even though they render.
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    payload = load_concept_data()
    payload["proposed_indicators"][0]["description"] = (
        "Fictional description_probe participants demonstrate a skill in a supported arts workshop. " * 100
        + "FICTIONAL_DESCRIPTION_END"
    )
    payload["proposed_indicators"][0]["measurement_method"] = (
        "Fictional measurement_probe observers record an accessible practical demonstration. " * 100
        + "FICTIONAL_MEASUREMENT_END ä ö å Ä Ö Å"
    )
    concept = ConceptPaper.model_validate(payload)
    original = concept.model_dump(mode="json")
    pdf, trace, footers = render_with_page_trace(monkeypatch, concept)
    pages = len(re.findall(rb"/Type\s*/Page\b", pdf))
    assert pages >= 3
    rendered = " ".join(text for _, text, _ in trace)
    assert b"FICTIONAL_DESCRIPTION_END" in pdf
    assert b"FICTIONAL_MEASUREMENT_END" in pdf
    assert pdf.count(b"description_probe") == pdf.count(b"measurement_probe") == 100
    assert concept.proposed_indicators[1].measurement_method in rendered
    assert footers == [(page, f"Page {page}") for page in range(1, pages + 1)]
    assert {page for page, _, _ in trace} == set(range(1, pages + 1))
    assert concept.model_dump(mode="json") == original


def test_concept_pdf_filename_is_ascii_safe():
    assert concept_pdf_filename("Fictional Ääni & Arts") == "fictional-ni-arts-concept-paper.pdf"
    assert concept_pdf_filename("!!!") == "hankeluotsi-concept-paper.pdf"
