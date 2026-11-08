import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from hankeluotsi.config import DEFAULT_MODEL, get_default_config
from hankeluotsi.llm_client import LLMClient
from hankeluotsi.prompts import build_prompt, prompt_version_for_stage
from hankeluotsi.schemas import ProjectIdea


def test_default_config_uses_local_lm_studio():
    config = get_default_config()

    assert config.base_url == "http://127.0.0.1:1234/v1"
    assert config.default_model == DEFAULT_MODEL
    assert config.stage_to_model == {
        "concept": DEFAULT_MODEL,
        "draft": DEFAULT_MODEL,
        "review": DEFAULT_MODEL,
    }


def test_prompt_version_and_context_are_used_for_each_stage():
    prompt = build_prompt("concept", "Test idea for a digital skills project")

    assert prompt_version_for_stage("concept") == "concept_v1"
    assert "concept_v1" in prompt
    assert "Test idea for a digital skills project" in prompt


def test_generate_success_parses_json_and_validates_pydantic_model():
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                finish_reason="stop",
                                message=SimpleNamespace(
                                    content=json.dumps(
                                        {
                                            "title": "Digital practice labs",
                                            "development_need": "Small arts groups need support with digital practice.",
                                            "target_groups": ["Arts staff and volunteers"],
                                            "expected_change": "Participants will use one new digital tool.",
                                            "geography": "Western Finland",
                                            "partners": ["Fictional arts network"],
                                            "funding_context": "Illustrative local co-operation idea",
                                        }
                                    )
                                ),
                            )
                        ]
                    )
                )
            )
        )
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        client = LLMClient()
        result = client.generate("concept", "Digital skills project idea", response_model=ProjectIdea)

    assert result.model == DEFAULT_MODEL
    assert result.prompt_version == "concept_v1"
    assert result.finish_reason == "stop"
    assert result.truncated is False
    assert result.response_time_seconds >= 0
    assert isinstance(result.data, ProjectIdea)
    assert result.data.title == "Digital practice labs"


def test_generate_records_unknown_finish_reason_after_validating_json():
    payload = {
        "title": "Fictional project",
        "development_need": "Need",
        "target_groups": ["Group A"],
        "expected_change": "Change",
        "geography": "Finland",
    }
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content=json.dumps(payload))
                            )
                        ]
                    )
                )
            )
        )
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        result = LLMClient().generate("concept", "Test idea", response_model=ProjectIdea)

    assert result.finish_reason == "unknown"
    assert result.truncated is False
    assert isinstance(result.data, ProjectIdea)


def test_generate_retries_once_and_records_truncation_metadata():
    payload = {
        "title": "Fictional project",
        "development_need": "Need",
        "target_groups": ["Group A"],
        "expected_change": "Change",
        "geography": "Finland",
    }
    truncated_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content=json.dumps(payload)),
            )
        ]
    )
    mock_create = Mock(side_effect=[truncated_response, truncated_response])
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        with pytest.raises(ValueError, match="truncated response") as error:
            LLMClient().generate("concept", "Test idea", response_model=ProjectIdea)

    assert mock_create.call_count == 2
    assert error.value.stage == "concept"
    assert error.value.model == DEFAULT_MODEL
    assert error.value.prompt_version == "concept_v1"
    assert error.value.finish_reason == "length"
    assert error.value.truncated is True
    assert error.value.response_time_seconds >= 0


def test_generate_raises_on_empty_response():
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="  "))]
                    )
                )
            )
        )
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        client = LLMClient()
        with pytest.raises(ValueError, match="empty response"):
            client.generate("concept", "Test idea", response_model=ProjectIdea)


def test_generate_raises_on_malformed_json():
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="{not valid json}"))]
                    )
                )
            )
        )
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        client = LLMClient()
        with pytest.raises(ValueError, match="JSON"):
            client.generate("concept", "Test idea", response_model=ProjectIdea)


def test_generate_raises_on_schema_validation_error():
    payload = {
        "title": "Fictional project",
        "development_need": "Need",
        "target_groups": [],
        "expected_change": "Change",
        "geography": "Finland",
        "partners": ["Partner A"],
    }
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
                    )
                )
            )
        )
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        client = LLMClient()
        with pytest.raises(ValueError, match="validation"):
            client.generate("concept", "Test idea", response_model=ProjectIdea)


def test_generate_retries_once_on_validation_mismatch():
    first_payload = {
        "title": "bad",
        "development_need": "Need",
        "target_groups": [],
        "expected_change": "Change",
        "geography": "Finland",
    }
    second_payload = {
        "title": "Good project",
        "development_need": "Need",
        "target_groups": ["Group A"],
        "expected_change": "Change",
        "geography": "Finland",
    }

    mock_create = Mock(
        side_effect=[
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(first_payload)))]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(second_payload)))]
            ),
        ]
    )
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
    )

    with patch("hankeluotsi.llm_client.OpenAI", return_value=mock_client):
        client = LLMClient()
        result = client.generate("concept", "Test idea", response_model=ProjectIdea)

    assert mock_create.call_count == 2
    assert result.data.title == "Good project"


def test_local_call_uses_timeout_and_json_schema_format():
    mock_create = Mock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "title": "Small project",
                                "development_need": "Need",
                                "target_groups": ["Group A"],
                                "expected_change": "Change",
                                "geography": "Finland",
                            }
                        )
                    )
                )
            ]
        )
    )
    with patch("hankeluotsi.llm_client.OpenAI") as mock_openai:
        mock_openai.return_value = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
        )
        client = LLMClient(timeout_seconds=30)
        client.generate("concept", "Test idea", response_model=ProjectIdea)

    _, kwargs = mock_openai.call_args
    assert kwargs["base_url"] == "http://127.0.0.1:1234/v1"
    assert kwargs["api_key"] == "not-needed"
    assert mock_create.call_args.kwargs["response_format"]["type"] == "json_schema"
