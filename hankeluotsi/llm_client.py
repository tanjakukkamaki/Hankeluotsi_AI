import json
import time
from dataclasses import dataclass
from typing import Any, Type, TypeVar

from openai import OpenAI

from hankeluotsi.config import get_default_config
from hankeluotsi.prompts import build_prompt, prompt_version_for_stage


T = TypeVar("T")


@dataclass
class GenerationResult:
    stage: str
    model: str
    prompt_version: str
    data: Any
    finish_reason: str = "unknown"
    truncated: bool = False
    incomplete_output: bool = False
    response_time_seconds: float = 0.0
    json_valid: bool = True
    pydantic_valid: bool | None = None
    attempt_count: int = 1
    provider: str = "local"
    reported_model: str | None = None
    usage: dict[str, int | None] | None = None


class GenerationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        model: str,
        prompt_version: str,
        finish_reason: str,
        truncated: bool,
        incomplete_output: bool,
        response_time_seconds: float,
        json_valid: bool,
        pydantic_valid: bool | None,
        attempt_count: int,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.model = model
        self.prompt_version = prompt_version
        self.finish_reason = finish_reason
        self.truncated = truncated
        self.incomplete_output = incomplete_output
        self.response_time_seconds = response_time_seconds
        self.json_valid = json_valid
        self.pydantic_valid = pydantic_valid
        self.attempt_count = attempt_count


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: int | None = None,
        stage_to_model: dict[str, str] | None = None,
    ) -> None:
        config = get_default_config()
        self.base_url = base_url or config.base_url
        self.api_key = api_key or "not-needed"
        self.default_model = default_model or config.default_model
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else config.timeout_seconds
        self.stage_to_model = dict(config.stage_to_model)
        if stage_to_model:
            self.stage_to_model.update(stage_to_model)

    def _openai_client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout_seconds)

    def _model_for_stage(self, stage: str) -> str:
        return self.stage_to_model.get(stage, self.default_model)

    def _parse_json_content(self, content: str) -> Any:
        if content is None or not str(content).strip():
            raise ValueError("empty response")

        try:
            return json.loads(str(content))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON response: {exc.msg}") from exc

    def _response_format(self, response_model: Type[T] | None):
        if response_model is None:
            return {"type": "text"}

        return {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__.lower(),
                "schema": response_model.model_json_schema(),
            },
        }

    def generate(
        self,
        stage: str,
        user_input: str,
        response_model: Type[T] | None = None,
        *,
        model: str | None = None,
        max_attempts: int = 2,
    ) -> GenerationResult:
        if max_attempts not in (1, 2):
            raise ValueError("max_attempts must be 1 or 2")

        stage_name = stage.lower()
        prompt_version = prompt_version_for_stage(stage_name)
        prompt = build_prompt(stage_name, user_input)
        selected_model = model or self._model_for_stage(stage_name)

        last_error: ValueError | None = None
        last_metadata: dict[str, Any] = {
            "finish_reason": "unknown",
            "truncated": False,
            "incomplete_output": True,
            "response_time_seconds": 0.0,
            "json_valid": False,
            "pydantic_valid": False if response_model is not None else None,
            "attempt_count": 0,
        }
        for attempt in range(max_attempts):
            started_at = time.perf_counter()
            response = self._openai_client().chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": "Return a valid JSON object only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=512,
                response_format=self._response_format(response_model),
            )
            response_time_seconds = time.perf_counter() - started_at
            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None) or "unknown"
            truncated = finish_reason == "length"
            last_metadata = {
                "finish_reason": finish_reason,
                "truncated": truncated,
                "incomplete_output": finish_reason != "stop",
                "response_time_seconds": response_time_seconds,
                "json_valid": False,
                "pydantic_valid": False if response_model is not None else None,
                "attempt_count": attempt + 1,
            }

            message = choice.message.content
            validated: Any = None
            try:
                parsed = self._parse_json_content(message)
            except ValueError as exc:
                last_error = exc
            else:
                last_metadata["json_valid"] = True
                if response_model is None:
                    validated = parsed
                else:
                    last_metadata["pydantic_valid"] = False
                    try:
                        validated = response_model.model_validate(parsed)
                    except Exception as exc:  # pragma: no cover - asserted through benchmark metadata
                        last_error = ValueError(f"response validation failed: {exc}")
                    else:
                        last_metadata["pydantic_valid"] = True

            if truncated:
                last_error = ValueError("truncated response (finish_reason=length)")
            elif last_metadata["json_valid"] and (
                response_model is None or last_metadata["pydantic_valid"] is True
            ):
                return GenerationResult(
                    stage=stage_name,
                    model=selected_model,
                    prompt_version=prompt_version,
                    data=validated,
                    finish_reason=finish_reason,
                    truncated=truncated,
                    incomplete_output=last_metadata["incomplete_output"],
                    response_time_seconds=response_time_seconds,
                    json_valid=last_metadata["json_valid"],
                    pydantic_valid=last_metadata["pydantic_valid"],
                    attempt_count=attempt + 1,
                    provider="local",
                )

            if attempt + 1 < max_attempts:
                last_error = None
                continue
            break

        raise GenerationError(
            str(last_error or f"response validation failed for stage {stage_name}"),
            stage=stage_name,
            model=selected_model,
            prompt_version=prompt_version,
            **last_metadata,
        ) from last_error
