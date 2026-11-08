PROMPT_VERSIONS = {
    "concept": "concept_v1",
    "draft": "draft_v1",
    "review": "review_v1",
}


def prompt_version_for_stage(stage: str) -> str:
    try:
        return PROMPT_VERSIONS[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported stage: {stage}") from exc


def build_prompt(stage: str, user_input: str) -> str:
    version = prompt_version_for_stage(stage)
    return (
        "You are a careful EU project-planning assistant. "
        f"Prompt version: {version}.\n"
        "Return only valid JSON that matches the expected schema. "
        "Do not include markdown fences or explanatory text.\n\n"
        "Stage: "
        f"{stage}\n\n"
        "User input:\n"
        f"{user_input}\n"
    )
