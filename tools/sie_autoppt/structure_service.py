from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clarifier import DEFAULT_AUDIENCE_HINT
from .config import MAX_BODY_CHAPTERS
from .llm_openai import OpenAIResponsesClient, load_openai_responses_config
from .models import StructureSpec
from .prompting import render_prompt_template


STRUCTURE_TYPE_ENUM = (
    "industry_analysis",
    "problem_analysis",
    "solution_design",
    "strategy_report",
    "comparison_analysis",
    "process_plan",
    "general",
)

_WEAK_PHRASES = (
    "非常重要",
    "意义重大",
    "未来可期",
    "具有很大潜力",
    "值得关注",
    "不容忽视",
)


@dataclass(frozen=True)
class StructureGenerationRequest:
    topic: str
    brief: str = ""
    audience: str = DEFAULT_AUDIENCE_HINT
    language: str = "zh-CN"
    sections: int | None = None
    min_sections: int | None = None
    max_sections: int | None = None


@dataclass(frozen=True)
class StructureBounds:
    min_sections: int
    max_sections: int

    @property
    def is_exact(self) -> bool:
        return self.min_sections == self.max_sections


@dataclass(frozen=True)
class StructureValidationResult:
    is_valid: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructureGenerationResult:
    structure: StructureSpec
    attempts_used: int
    validation_issues: tuple[str, ...] = ()


def _clamp_section_count(value: int) -> int:
    return max(3, min(int(value), MAX_BODY_CHAPTERS))


def resolve_structure_bounds(request: StructureGenerationRequest) -> StructureBounds:
    exact = request.sections if request.sections and request.sections > 0 else None
    min_sections = request.min_sections if request.min_sections and request.min_sections > 0 else None
    max_sections = request.max_sections if request.max_sections and request.max_sections > 0 else None

    if exact is not None and (min_sections is not None or max_sections is not None):
        raise ValueError("Use either sections or min_sections/max_sections, not both.")
    if exact is not None:
        exact = _clamp_section_count(exact)
        return StructureBounds(min_sections=exact, max_sections=exact)

    resolved_min = _clamp_section_count(min_sections if min_sections is not None else 3)
    resolved_max = _clamp_section_count(max_sections if max_sections is not None else 5)
    if resolved_min > resolved_max:
        raise ValueError("min_sections cannot be greater than max_sections.")
    return StructureBounds(min_sections=resolved_min, max_sections=resolved_max)


def build_structure_schema(bounds: StructureBounds) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "core_message": {"type": "string", "minLength": 6, "maxLength": 80},
            "structure_type": {"type": "string", "enum": list(STRUCTURE_TYPE_ENUM)},
            "sections": {
                "type": "array",
                "minItems": bounds.min_sections,
                "maxItems": bounds.max_sections,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 6, "maxLength": 28},
                        "key_message": {"type": "string", "minLength": 8, "maxLength": 80},
                        "arguments": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 4,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "point": {"type": "string", "minLength": 4, "maxLength": 40},
                                    "evidence": {"type": "string", "maxLength": 80},
                                },
                                "required": ["point", "evidence"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["title", "key_message", "arguments"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["core_message", "structure_type", "sections"],
        "additionalProperties": False,
    }


def build_structure_prompts(
    request: StructureGenerationRequest,
    bounds: StructureBounds | None = None,
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    bounds = bounds or resolve_structure_bounds(request)
    section_rule = (
        f"Return exactly {bounds.min_sections} first-level sections."
        if bounds.is_exact
        else f"Return {bounds.min_sections}-{bounds.max_sections} first-level sections."
    )
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(f"- {item}" for item in validation_feedback)

    developer_prompt = render_prompt_template(
        "prompts/system/structure.md",
        section_rule=section_rule,
        structure_type_enum=", ".join(STRUCTURE_TYPE_ENUM),
        weak_phrases=", ".join(_WEAK_PHRASES),
        feedback_block=feedback_block,
        language=request.language.strip() or "zh-CN",
    )
    user_prompt = (
        f"Topic:\n{request.topic.strip()}\n\n"
        f"Audience:\n{(request.audience or DEFAULT_AUDIENCE_HINT).strip()}\n\n"
        f"Brief:\n{request.brief.strip() or 'none'}\n\n"
        "Return only the structure JSON."
    )
    return developer_prompt, user_prompt


def validate_structure_payload(data: dict[str, Any]) -> StructureValidationResult:
    issues: list[str] = []
    core_message = str(data.get("core_message", "")).strip()
    if not core_message:
        issues.append("core_message is required.")

    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        issues.append("sections must be a list.")
        return StructureValidationResult(is_valid=False, issues=tuple(issues))

    if len(raw_sections) < 3:
        issues.append("sections must contain at least 3 items.")

    seen_titles: set[str] = set()
    for index, raw_section in enumerate(raw_sections, start=1):
        if not isinstance(raw_section, dict):
            issues.append(f"section {index} must be an object.")
            continue

        title = str(raw_section.get("title", "")).strip()
        key_message = str(raw_section.get("key_message", "")).strip()
        arguments = raw_section.get("arguments", [])

        if not title:
            issues.append(f"section {index} title is required.")
        elif len(title) > 28:
            issues.append(f"section {index} title exceeds 28 characters.")
        else:
            normalized_title = "".join(title.split()).lower()
            if normalized_title in seen_titles:
                issues.append(f"section {index} title is duplicated.")
            seen_titles.add(normalized_title)

        if not key_message:
            issues.append(f"section {index} key_message is required.")

        for weak_phrase in _WEAK_PHRASES:
            if weak_phrase in title or weak_phrase in key_message:
                issues.append(f"section {index} contains weak phrasing: {weak_phrase}")

        if not isinstance(arguments, list):
            issues.append(f"section {index} arguments must be a list.")
            continue
        if len(arguments) < 2:
            issues.append(f"section {index} must contain at least 2 arguments.")
        for argument_index, raw_argument in enumerate(arguments, start=1):
            if not isinstance(raw_argument, dict):
                issues.append(f"section {index} argument {argument_index} must be an object.")
                continue
            point = str(raw_argument.get("point", "")).strip()
            if not point:
                issues.append(f"section {index} argument {argument_index} point is required.")

    return StructureValidationResult(is_valid=not issues, issues=tuple(issues))


def generate_structure_with_ai(
    request: StructureGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> StructureGenerationResult:
    bounds = resolve_structure_bounds(request)
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()

    for attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_structure_prompts(request, bounds=bounds, validation_feedback=feedback)
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="structure_plan",
            schema=build_structure_schema(bounds),
        )
        validation = validate_structure_payload(payload)
        if validation.is_valid:
            return StructureGenerationResult(
                structure=StructureSpec.from_dict(payload),
                attempts_used=attempt,
                validation_issues=validation.issues,
            )
        feedback = validation.issues

    raise ValueError("Structure generation failed validation after 3 attempts: " + "; ".join(feedback))
