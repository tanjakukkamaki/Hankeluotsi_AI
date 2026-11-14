"""Actual outgoing schema contracts, not a claim of remote model compatibility."""

from datetime import date
import json
from pathlib import Path

import httpx2
import pytest

from hankeluotsi.draft_checks import check_draft_consistency
from hankeluotsi.draft_schemas import ApplicationDraft
from hankeluotsi.mistral_client import CloudConsent, MistralClient
from hankeluotsi.planning_quality import check_planning_advisories
from hankeluotsi.review_evidence import ReviewSelection, build_evidence_catalog
from hankeluotsi.schemas import ConceptPaper


DATA = Path(__file__).parent / "fixtures"


def _fixture(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _schema_nodes(child)


def _response_instance(model):
    if model is ConceptPaper:
        return model.model_validate(_fixture("concept_paper.json"))
    draft = ApplicationDraft.model_validate(_fixture("application_draft.json"))
    if model is ApplicationDraft:
        return draft
    catalogue = build_evidence_catalog(draft)
    return ReviewSelection(
        strengths=["A fictional test draft is available."],
        findings=[dict(evidence_id=catalogue["entries"][0]["evidence_id"],
            observation="This is a synthetic schema-contract observation.",
            suggestion="Have a human assess the actual planning content.", severity="question")],
        missing_information=[], overall_assessment="Offline contract fixture only.",
        uncertainties=["No live model or independent human assessment was performed."],
    )


@pytest.mark.parametrize("stage,model,optional", [
    ("concept", ConceptPaper, {"schema_version", "assumptions", "open_questions"}),
    ("draft", ApplicationDraft, {"schema_version", "generation_metadata"}),
    ("review", ReviewSelection, {"schema_version", "generation_metadata"}),
], ids=["concept", "draft", "review-selection"])
def test_actual_cloud_request_preserves_pydantic_schema_contract(monkeypatch, stage, model, optional):
    monkeypatch.setenv("MISTRAL_API_KEY", "fictional-schema-contract-key")
    monkeypatch.setenv("MISTRAL_MODEL", "fictional-schema-contract-model")
    instance = _response_instance(model)
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json={"model": "fictional-schema-contract-model",
            "choices": [{"finish_reason": "stop", "message": {"content": instance.model_dump_json()}}]})

    original_client = httpx2.Client

    def mocked_client(**kwargs):
        configured_transport = kwargs.pop("transport", None)
        if configured_transport is not None:
            configured_transport.close()
        return original_client(transport=httpx2.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx2, "Client", mocked_client)
    result = MistralClient(CloudConsent(True, True)).generate(
        stage, "Fictional project data for an offline schema-contract test.", response_model=model)

    assert result.data == instance and len(requests) == 1
    response_format = requests[0]["response_format"]
    assert response_format["type"] == "json_schema"
    envelope = response_format["json_schema"]
    assert envelope["name"] == model.__name__.lower()
    assert envelope["schema"] == model.model_json_schema()
    # Mistral's strict flag is optional. Preserve this route's existing omission,
    # rather than rewriting persisted contracts around another provider's rules.
    assert "strict" not in envelope
    schema = envelope["schema"]
    assert set(schema["properties"]) - set(schema["required"]) == optional
    assert schema["properties"]["schema_version"]["default"] == 1
    if model is not ConceptPaper:
        metadata = schema["properties"]["generation_metadata"]
        assert metadata["default"] is None
        assert {"type": "null"} in metadata["anyOf"]
    for node in _schema_nodes(schema):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) <= set(node.get("properties", {}))
        if "$ref" in node:
            assert node["$ref"].startswith("#/")
            target = schema
            for token in node["$ref"][2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
            assert isinstance(target, dict)


@pytest.mark.parametrize("period,expected", [
    ("2025", "TIMELINE_YEARS_IN_PAST"),
    ("2025-05-01 to 2025-05-02", "TIMELINE_DATES_IN_PAST"),
], ids=["past-year", "past-absolute-dates"])
def test_explicit_2025_timeline_is_read_only_advisory_not_a_graph_failure(period, expected):
    case = _fixture("planning_quality_cases_v1.json")["cases"][0]
    draft = ApplicationDraft.model_validate(case["draft"])
    draft.timeline[0].period = period
    before = draft.model_dump_json()
    observations = check_planning_advisories(draft, reference_date=date(2026, 11, 13))
    assert expected in {item.code for item in observations}
    assert all(item.severity.value == "warning" for item in observations)
    assert check_draft_consistency(draft) == []
    assert draft.model_dump_json() == before
