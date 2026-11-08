import os
from dataclasses import dataclass, field


LOCAL_LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen3.5-4b"
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TOKENS = 512


@dataclass(frozen=True)
class LLMSettings:
    base_url: str = field(default_factory=lambda: os.getenv("LM_STUDIO_BASE_URL", LOCAL_LM_STUDIO_BASE_URL))
    default_model: str = field(default_factory=lambda: os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL))
    timeout_seconds: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
    stage_to_model: dict[str, str] = field(
        default_factory=lambda: {
            "concept": os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL),
            "draft": os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL),
            "review": os.getenv("LM_STUDIO_MODEL", DEFAULT_MODEL),
        }
    )


def get_default_config() -> LLMSettings:
    return LLMSettings()
