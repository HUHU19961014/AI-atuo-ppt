from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..clarifier import DEFAULT_AUDIENCE_HINT
from ..config import DEFAULT_OUTPUT_DIR
from ..llm_openai import OpenAIResponsesClient, load_openai_responses_config
from ..prompting import render_prompt_template
from .deck_director import build_semantic_deck_schema, compile_semantic_deck_payload
from .io import (
    build_deck_output_path,
    build_log_output_path,
    build_outline_output_path,
    build_ppt_output_path,
    build_semantic_output_path,
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    default_semantic_output_path,
    load_outline_document,
    write_semantic_document,
    write_outline_document,
)
from .ppt_engine import generate_ppt
from .schema import (
    DeckDocument,
    OutlineDocument,
    SUPPORTED_LAYOUTS,
    SUPPORTED_THEMES,
    ValidatedDeck,
    collect_deck_warnings,
    validate_deck_payload,
)

SUPPORTED_GENERATION_MODES = ("quick", "deep")


@dataclass(frozen=True)
class OutlineGenerationRequest:
    topic: str
    brief: str = ""
    audience: str = DEFAULT_AUDIENCE_HINT
    language: str = "zh-CN"
    theme: str = "business_red"
    exact_slides: int | None = None
    min_slides: int = 6
    max_slides: int = 10
    generation_mode: str = "deep"
    structured_context: dict[str, Any] | None = None
    strategic_analysis: dict[str, Any] | None = None


@dataclass(frozen=True)
class DeckGenerationRequest:
    topic: str
    outline: OutlineDocument
    brief: str = ""
    audience: str = DEFAULT_AUDIENCE_HINT
    language: str = "zh-CN"
    theme: str = "business_red"
    author: str = "Enterprise AI PPT"
    generation_mode: str = "deep"
    structured_context: dict[str, Any] | None = None
    strategic_analysis: dict[str, Any] | None = None


@dataclass(frozen=True)
class V2MakeArtifacts:
    outline_path: Path
    semantic_path: Path
    deck_path: Path
    log_path: Path
    rewrite_log_path: Path
    warnings_path: Path
    pptx_path: Path
    deck: DeckDocument
    warnings: tuple[str, ...] = ()


def _clamp_slide_count(value: int) -> int:
    return max(3, min(int(value), 20))


def normalize_generation_mode(value: str | None) -> str:
    normalized = str(value or "deep").strip().lower()
    if normalized not in SUPPORTED_GENERATION_MODES:
        raise ValueError(f"generation_mode must be one of {', '.join(SUPPORTED_GENERATION_MODES)}")
    return normalized


def resolve_slide_bounds(request: OutlineGenerationRequest) -> tuple[int, int]:
    if request.exact_slides is not None:
        exact = _clamp_slide_count(request.exact_slides)
        return exact, exact
    minimum = _clamp_slide_count(request.min_slides)
    maximum = _clamp_slide_count(request.max_slides)
    if minimum > maximum:
        raise ValueError("min_slides cannot be greater than max_slides.")
    return minimum, maximum


def _json_block(payload: dict[str, Any] | None, fallback: str = "none") -> str:
    if not payload:
        return fallback
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_context_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "industry": {"type": "string", "minLength": 1, "maxLength": 40},
            "business_stage": {"type": "string", "minLength": 1, "maxLength": 40},
            "constraints": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 60},
            },
            "pain_points": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 60},
            },
            "known_data": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 80},
            },
            "taboo_topics": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 40},
            },
            "audience_priorities": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 60},
            },
            "decision_focus": {"type": "string", "minLength": 1, "maxLength": 60},
        },
        "required": [
            "industry",
            "business_stage",
            "constraints",
            "pain_points",
            "known_data",
            "taboo_topics",
            "audience_priorities",
            "decision_focus",
        ],
        "additionalProperties": False,
    }


def build_strategy_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "context_assessment": {"type": "string", "minLength": 1, "maxLength": 200},
            "core_tension": {"type": "string", "minLength": 1, "maxLength": 120},
            "elephant_in_the_room": {"type": "string", "minLength": 1, "maxLength": 120},
            "audience_goal": {"type": "string", "minLength": 1, "maxLength": 100},
            "likely_objections": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "strongest_argument_for": {"type": "string", "minLength": 1, "maxLength": 140},
            "strongest_argument_against": {"type": "string", "minLength": 1, "maxLength": 140},
            "preemptive_response": {"type": "string", "minLength": 1, "maxLength": 140},
            "recommended_narrative_arc": {"type": "string", "minLength": 1, "maxLength": 140},
            "slides_to_omit_and_why": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "data_to_verify": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "riskiest_claim": {"type": "string", "minLength": 1, "maxLength": 120},
            "pivot_for_skeptical_audience": {"type": "string", "minLength": 1, "maxLength": 120},
        },
        "required": [
            "context_assessment",
            "core_tension",
            "elephant_in_the_room",
            "audience_goal",
            "likely_objections",
            "strongest_argument_for",
            "strongest_argument_against",
            "preemptive_response",
            "recommended_narrative_arc",
            "slides_to_omit_and_why",
            "data_to_verify",
            "riskiest_claim",
            "pivot_for_skeptical_audience",
        ],
        "additionalProperties": False,
    }


def build_context_prompts(
    *,
    topic: str,
    brief: str,
    audience: str,
    language: str,
) -> tuple[str, str]:
    developer_prompt = (
        "You convert raw presentation requirements into structured business context JSON.\n"
        f"Use {language}.\n"
        "Do not invent facts. If information is missing, use '未知' for strings and [] for arrays.\n"
        "Extract only from the provided topic, brief, and audience."
    )
    user_prompt = (
        f"Topic:\n{topic.strip()}\n\n"
        f"Audience:\n{audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{brief.strip() or 'none'}\n\n"
        "Return only JSON."
    )
    return developer_prompt, user_prompt


def build_strategy_prompts(
    *,
    topic: str,
    brief: str,
    audience: str,
    language: str,
    structured_context: dict[str, Any],
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(f"- {item}" for item in validation_feedback)
    developer_prompt = render_prompt_template(
        "prompts/system/v2_strategy.md",
        language=language,
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{topic.strip()}\n\n"
        f"Audience:\n{audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{brief.strip() or 'none'}\n\n"
        "Structured Context JSON:\n"
        f"{_json_block(structured_context)}\n\n"
        "Return only JSON."
    )
    return developer_prompt, user_prompt


def extract_structured_context(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    model: str | None = None,
) -> dict[str, Any]:
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    developer_prompt, user_prompt = build_context_prompts(
        topic=topic,
        brief=brief,
        audience=audience,
        language=language,
    )
    return client.create_structured_json(
        developer_prompt=developer_prompt,
        user_prompt=user_prompt,
        schema_name="ppt_context_v2",
        schema=build_context_schema(),
    )


def generate_strategy_with_ai(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    structured_context: dict[str, Any],
    model: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_strategy_prompts(
            topic=topic,
            brief=brief,
            audience=audience,
            language=language,
            structured_context=structured_context,
            validation_feedback=feedback,
        )
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="ppt_strategy_v2",
            schema=build_strategy_schema(),
        )
        if payload.get("core_tension") and payload.get("recommended_narrative_arc"):
            return payload
        feedback = ("strategy output must include core_tension and recommended_narrative_arc.",)
    raise ValueError("Strategy generation failed validation after 3 attempts: " + "; ".join(feedback))


def ensure_generation_context(
    *,
    topic: str,
    brief: str,
    audience: str,
    language: str,
    generation_mode: str,
    structured_context: dict[str, Any] | None,
    strategic_analysis: dict[str, Any] | None,
    model: str | None,
    max_attempts: int = 3,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved_mode = normalize_generation_mode(generation_mode)
    if resolved_mode == "quick" and structured_context is None and strategic_analysis is None:
        return {}, {}
    resolved_context = structured_context or extract_structured_context(
        topic=topic,
        brief=brief,
        audience=audience,
        language=language,
        model=model,
    )
    resolved_strategy = strategic_analysis or generate_strategy_with_ai(
        topic=topic,
        brief=brief,
        audience=audience,
        language=language,
        structured_context=resolved_context,
        model=model,
        max_attempts=max_attempts,
    )
    return resolved_context, resolved_strategy


def build_outline_schema(request: OutlineGenerationRequest) -> dict[str, Any]:
    min_slides, max_slides = resolve_slide_bounds(request)
    return {
        "type": "object",
        "properties": {
            "pages": {
                "type": "array",
                "minItems": min_slides,
                "maxItems": max_slides,
                "items": {
                    "type": "object",
                    "properties": {
                        "page_no": {"type": "integer", "minimum": 1, "maximum": 20},
                        "title": {"type": "string", "minLength": 2, "maxLength": 32},
                        "goal": {"type": "string", "minLength": 4, "maxLength": 80},
                    },
                    "required": ["page_no", "title", "goal"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["pages"],
        "additionalProperties": False,
    }


def build_outline_prompts(
    request: OutlineGenerationRequest,
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    min_slides, max_slides = resolve_slide_bounds(request)
    slide_rule = f"Return exactly {min_slides} pages." if min_slides == max_slides else f"Return {min_slides}-{max_slides} pages."
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(f"- {item}" for item in validation_feedback)
    developer_prompt = render_prompt_template(
        "prompts/system/v2_outline.md",
        slide_rule=slide_rule,
        language=request.language,
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{request.topic.strip()}\n\n"
        f"Audience:\n{request.audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{request.brief.strip() or 'none'}\n\n"
        "Structured Context JSON:\n"
        f"{_json_block(request.structured_context)}\n\n"
        "Strategic Analysis JSON:\n"
        f"{_json_block(request.strategic_analysis)}\n\n"
        "Return only JSON."
    )
    return developer_prompt, user_prompt


def build_deck_schema() -> dict[str, Any]:
    return build_semantic_deck_schema()


def build_deck_prompts(
    request: DeckGenerationRequest,
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(f"- {item}" for item in validation_feedback)
    developer_prompt = render_prompt_template(
        "prompts/system/v2_slides.md",
        language=request.language,
        theme_name=request.theme,
        supported_layouts=", ".join(SUPPORTED_LAYOUTS),
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{request.topic.strip()}\n\n"
        f"Audience:\n{request.audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{request.brief.strip() or 'none'}\n\n"
        "Structured Context JSON:\n"
        f"{_json_block(request.structured_context)}\n\n"
        "Strategic Analysis JSON:\n"
        f"{_json_block(request.strategic_analysis)}\n\n"
        "Outline JSON:\n"
        f"{json.dumps(request.outline.to_list(), ensure_ascii=False, indent=2)}\n\n"
        "Return only the deck JSON object."
    )
    return developer_prompt, user_prompt


def _validate_outline_response(payload: dict[str, Any], request: OutlineGenerationRequest) -> OutlineDocument:
    outline = OutlineDocument.model_validate(payload)
    min_slides, max_slides = resolve_slide_bounds(request)
    if not (min_slides <= len(outline.pages) <= max_slides):
        raise ValueError(f"outline page count must be between {min_slides} and {max_slides}.")
    return outline


def generate_outline_with_ai(
    request: OutlineGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> OutlineDocument:
    if request.theme not in SUPPORTED_THEMES:
        raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
    generation_mode = normalize_generation_mode(request.generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=request.language,
        generation_mode=generation_mode,
        structured_context=request.structured_context,
        strategic_analysis=request.strategic_analysis,
        model=model,
        max_attempts=max_attempts,
    )
    enriched_request = OutlineGenerationRequest(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=request.language,
        theme=request.theme,
        exact_slides=request.exact_slides,
        min_slides=request.min_slides,
        max_slides=request.max_slides,
        generation_mode=generation_mode,
        structured_context=structured_context,
        strategic_analysis=strategic_analysis,
    )
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_outline_prompts(enriched_request, validation_feedback=feedback)
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="ppt_outline_v2",
            schema=build_outline_schema(enriched_request),
        )
        try:
            return _validate_outline_response(payload, enriched_request)
        except ValueError as exc:
            feedback = (str(exc),)
    raise ValueError("Outline generation failed validation after 3 attempts: " + "; ".join(feedback))


def generate_deck_with_ai(
    request: DeckGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> ValidatedDeck:
    semantic_payload = generate_semantic_deck_with_ai(
        request=request,
        model=model,
        max_attempts=max_attempts,
    )
    return compile_semantic_deck_payload(
        semantic_payload,
        default_title=request.topic,
        default_theme=request.theme,
        default_language=request.language,
        default_author=request.author,
    )


def generate_semantic_deck_with_ai(
    request: DeckGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if request.theme not in SUPPORTED_THEMES:
        raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
    generation_mode = normalize_generation_mode(request.generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=request.language,
        generation_mode=generation_mode,
        structured_context=request.structured_context,
        strategic_analysis=request.strategic_analysis,
        model=model,
        max_attempts=max_attempts,
    )
    enriched_request = DeckGenerationRequest(
        topic=request.topic,
        outline=request.outline,
        brief=request.brief,
        audience=request.audience,
        language=request.language,
        theme=request.theme,
        author=request.author,
        generation_mode=generation_mode,
        structured_context=structured_context,
        strategic_analysis=strategic_analysis,
    )
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_deck_prompts(enriched_request, validation_feedback=feedback)
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="ppt_deck_v2",
            schema=build_deck_schema(),
        )
        try:
            compile_semantic_deck_payload(
                payload,
                default_title=enriched_request.topic,
                default_theme=enriched_request.theme,
                default_language=enriched_request.language,
                default_author=enriched_request.author,
            )
            return payload
        except ValueError as exc:
            feedback = (str(exc),)
    raise ValueError("Deck generation failed validation after 3 attempts: " + "; ".join(feedback))


def make_v2_ppt(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    theme: str = "business_red",
    author: str = "Enterprise AI PPT",
    exact_slides: int | None = None,
    min_slides: int = 6,
    max_slides: int = 10,
    output_dir: Path | None = None,
    output_prefix: str = "Enterprise-AI-PPT-V2",
    model: str | None = None,
    generation_mode: str = "deep",
    outline_output: Path | None = None,
    semantic_output: Path | None = None,
    deck_output: Path | None = None,
    log_output: Path | None = None,
    ppt_output: Path | None = None,
    outline_path: Path | None = None,
) -> V2MakeArtifacts:
    final_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    resolved_generation_mode = normalize_generation_mode(generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=topic,
        brief=brief,
        audience=audience,
        language=language,
        generation_mode=resolved_generation_mode,
        structured_context=None,
        strategic_analysis=None,
        model=model,
    )
    if outline_path is not None:
        outline = load_outline_document(outline_path)
        final_outline_output = outline_path
    else:
        outline = generate_outline_with_ai(
            OutlineGenerationRequest(
                topic=topic,
                brief=brief,
                audience=audience,
                language=language,
                theme=theme,
                exact_slides=exact_slides,
                min_slides=min_slides,
                max_slides=max_slides,
                generation_mode=resolved_generation_mode,
                structured_context=structured_context,
                strategic_analysis=strategic_analysis,
            ),
            model=model,
        )
        final_outline_output = outline_output or default_outline_output_path(final_output_dir)
        write_outline_document(outline, final_outline_output)

    semantic_payload = generate_semantic_deck_with_ai(
        DeckGenerationRequest(
            topic=topic,
            outline=outline,
            brief=brief,
            audience=audience,
            language=language,
            theme=theme,
            author=author,
            generation_mode=resolved_generation_mode,
            structured_context=structured_context,
            strategic_analysis=strategic_analysis,
        ),
        model=model,
    )
    final_semantic_output = semantic_output or default_semantic_output_path(final_output_dir)
    write_semantic_document(semantic_payload, final_semantic_output)
    validated_deck = compile_semantic_deck_payload(
        semantic_payload,
        default_title=topic,
        default_theme=theme,
        default_language=language,
        default_author=author,
    )
    final_deck_output = deck_output or default_deck_output_path(final_output_dir)

    final_log_output = log_output or default_log_output_path(final_output_dir)
    final_ppt_output = ppt_output or default_ppt_output_path(final_output_dir)
    render_result = generate_ppt(
        validated_deck,
        output_path=final_ppt_output,
        theme_name=theme,
        log_path=final_log_output,
        deck_output_path=final_deck_output,
    )
    return V2MakeArtifacts(
        outline_path=final_outline_output,
        semantic_path=final_semantic_output,
        deck_path=render_result.deck_path or final_deck_output,
        log_path=final_log_output,
        rewrite_log_path=render_result.rewrite_log_path or (final_log_output.parent / "rewrite_log.json"),
        warnings_path=render_result.warnings_path or (final_log_output.parent / "warnings.json"),
        pptx_path=render_result.output_path,
        deck=render_result.final_deck,
        warnings=tuple(collect_deck_warnings(render_result.final_deck)),
    )
