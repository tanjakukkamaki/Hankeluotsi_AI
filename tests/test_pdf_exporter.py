import json
import math
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics

from hankeluotsi.pdf_exporter import concept_pdf_filename, generate_concept_pdf
from hankeluotsi.schemas import ConceptPaper


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "concept_paper.json"


def load_concept_data():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def test_concept_pdf_filename_is_ascii_safe():
    assert concept_pdf_filename("Fictional Ääni & Arts") == "fictional-ni-arts-concept-paper.pdf"
    assert concept_pdf_filename("!!!") == "hankeluotsi-concept-paper.pdf"