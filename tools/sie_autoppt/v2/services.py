from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..clarifier import DEFAULT_AUDIENCE_HINT
from ..config import DEFAULT_OUTPUT_DIR
from ..llm_openai import OpenAIResponsesClient, load_openai_responses_config
from ..prompting import render_prompt_template
from .io import (
    build_deck_output_path,
    build_log_output_path,
    build_outline_output_path,
    build_ppt_output_path,
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    load_outline_document,
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


@dataclass(frozen=True)
class DeckGenerationRequest:
    topic: str
    outline: OutlineDocument
    brief: str = ""
    audience: str = DEFAULT_AUDIENCE_HINT
    language: str = "zh-CN"
    theme: str = "business_red"
    author: str = "Enterprise AI PPT"


@dataclass(frozen=True)
class V2MakeArtifacts:
    outline_path: Path
    deck_path: Path
    log_path: Path
    rewrite_log_path: Path
    warnings_path: Path
    pptx_path: Path
    deck: DeckDocument
    warnings: tuple[str, ...] = ()


def _clamp_slide_count(value: int) -> int:
    return max(3, min(int(value), 20))


def resolve_slide_bounds(request: OutlineGenerationRequest) -> tuple[int, int]:
    if request.exact_slides is not None:
        exact = _clamp_slide_count(request.exact_slides)
        return exact, exact
    minimum = _clamp_slide_count(request.min_slides)
    maximum = _clamp_slide_count(request.max_slides)
    if minimum > maximum:
        raise ValueError("min_slides cannot be greater than max_slides.")
    return minimum, maximum


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
        "Return only JSON."
    )
    return developer_prompt, user_prompt


def build_deck_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 80},
                    "theme": {"type": "string", "enum": list(SUPPORTED_THEMES)},
                    "language": {"type": "string", "minLength": 2, "maxLength": 16},
                    "author": {"type": "string", "minLength": 1, "maxLength": 40},
                    "version": {"type": "string", "minLength": 1, "maxLength": 10},
                },
                "required": ["title", "theme", "language", "author", "version"],
                "additionalProperties": False,
            },
            "slides": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                                "layout": {"const": "section_break"},
                                "title": {"type": "string", "minLength": 2, "maxLength": 60},
                                "subtitle": {"type": "string", "maxLength": 80},
                            },
                            "required": ["slide_id", "layout", "title"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                                "layout": {"const": "title_only"},
                                "title": {"type": "string", "minLength": 2, "maxLength": 60},
                            },
                            "required": ["slide_id", "layout", "title"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                                "layout": {"const": "title_content"},
                                "title": {"type": "string", "minLength": 2, "maxLength": 60},
                                "content": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 10,
                                    "items": {"type": "string", "minLength": 2, "maxLength": 60},
                                },
                            },
                            "required": ["slide_id", "layout", "title", "content"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                                "layout": {"const": "two_columns"},
                                "title": {"type": "string", "minLength": 2, "maxLength": 60},
                                "left": {
                                    "type": "object",
                                    "properties": {
                                        "heading": {"type": "string", "minLength": 1, "maxLength": 24},
                                        "items": {
                                            "type": "array",
                                            "minItems": 1,
                                            "maxItems": 6,
                                            "items": {"type": "string", "minLength": 2, "maxLength": 50},
                                        },
                                    },
                                    "required": ["heading", "items"],
                                    "additionalProperties": False,
                                },
                                "right": {
                                    "type": "object",
                                    "properties": {
                                        "heading": {"type": "string", "minLength": 1, "maxLength": 24},
                                        "items": {
                                            "type": "array",
                                            "minItems": 1,
                                            "maxItems": 6,
                                            "items": {"type": "string", "minLength": 2, "maxLength": 50},
                                        },
                                    },
                                    "required": ["heading", "items"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["slide_id", "layout", "title", "left", "right"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "slide_id": {"type": "string", "minLength": 1, "maxLength": 40},
                                "layout": {"const": "title_image"},
                                "title": {"type": "string", "minLength": 2, "maxLength": 60},
                                "content": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 8,
                                    "items": {"type": "string", "minLength": 2, "maxLength": 60},
                                },
                                "image": {
                                    "type": "object",
                                    "properties": {
                                        "mode": {"type": "string", "enum": ["placeholder", "local_path"]},
                                        "caption": {"type": "string", "maxLength": 40},
                                        "path": {"type": "string", "maxLength": 240},
                                    },
                                    "required": ["mode"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["slide_id", "layout", "title", "content", "image"],
                            "additionalProperties": False,
                        },
                    ]
                },
            },
        },
        "required": ["meta", "slides"],
        "additionalProperties": False,
    }


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
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_outline_prompts(request, validation_feedback=feedback)
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="ppt_outline_v2",
            schema=build_outline_schema(request),
        )
        try:
            return _validate_outline_response(payload, request)
        except ValueError as exc:
            feedback = (str(exc),)
    raise ValueError("Outline generation failed validation after 3 attempts: " + "; ".join(feedback))


def generate_deck_with_ai(
    request: DeckGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> ValidatedDeck:
    if request.theme not in SUPPORTED_THEMES:
        raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
    config = load_openai_responses_config(model=model)
    client = OpenAIResponsesClient(config)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_deck_prompts(request, validation_feedback=feedback)
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="ppt_deck_v2",
            schema=build_deck_schema(),
        )
        try:
            return validate_deck_payload(
                payload,
                default_title=request.topic,
                default_theme=request.theme,
                default_language=request.language,
                default_author=request.author,
            )
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
    outline_output: Path | None = None,
    deck_output: Path | None = None,
    log_output: Path | None = None,
    ppt_output: Path | None = None,
    outline_path: Path | None = None,
) -> V2MakeArtifacts:
    final_output_dir = output_dir or DEFAULT_OUTPUT_DIR
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
            ),
            model=model,
        )
        final_outline_output = outline_output or default_outline_output_path(final_output_dir)
        write_outline_document(outline, final_outline_output)

    validated_deck = generate_deck_with_ai(
        DeckGenerationRequest(
            topic=topic,
            outline=outline,
            brief=brief,
            audience=audience,
            language=language,
            theme=theme,
            author=author,
        ),
        model=model,
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
        deck_path=render_result.deck_path or final_deck_output,
        log_path=final_log_output,
        rewrite_log_path=render_result.rewrite_log_path or (final_log_output.parent / "rewrite_log.json"),
        warnings_path=render_result.warnings_path or (final_log_output.parent / "warnings.json"),
        pptx_path=render_result.output_path,
        deck=render_result.final_deck,
        warnings=tuple(collect_deck_warnings(render_result.final_deck)),
    )
