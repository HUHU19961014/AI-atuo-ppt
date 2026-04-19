from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from ..clarifier import DEFAULT_AUDIENCE_HINT
from ..config import DEFAULT_OUTPUT_DIR
from ..language_policy import format_language_constraints, get_language_policy, normalize_language_code
from ..llm_openai import OpenAIResponsesClient, load_openai_responses_config
from ..plugins import resolve_model_adapter
from ..prompting import render_prompt_template
from .content_rewriter import rewrite_deck, write_rewrite_log
from .io import (
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    default_semantic_output_path,
    load_outline_document,
    write_deck_document,
    write_outline_document,
    write_semantic_document,
)
from .quality_checks import quality_gate, write_quality_gate_result
from .schema import (
    SUPPORTED_LAYOUTS,
    SUPPORTED_THEMES,
    DeckDocument,
    OutlineDocument,
    ValidatedDeck,
    collect_deck_warnings,
)
from .semantic_compiler import compile_semantic_deck_payload
from .semantic_schema_builder import build_semantic_deck_schema
from .theme_loader import load_theme

SUPPORTED_GENERATION_MODES = ("quick", "deep")
OUTLINE_AUDIENCE_TIERS = ("executive", "management", "practitioner", "mixed", "general")
OUTLINE_NARRATIVE_PACING = ("fast", "balanced", "deep")
OUTLINE_NARRATIVE_PACING_ALIASES = {
    "accelerated": "fast",
    "rapid": "fast",
    "balanced": "balanced",
    "steady": "balanced",
    "deep": "deep",
    "deliberate": "deep",
}
GENERIC_OUTLINE_TITLES = {
    "background",
    "analysis",
    "future outlook",
    "conclusion",
    "summary",
    "overview",
    "introduction",
    "背景",
    "分析",
    "总结",
    "概述",
    "展望",
}
OPENING_SECTION_CUES = (
    "decision",
    "context",
    "judgement",
    "judgment",
    "constraint",
    "现状",
    "判断",
    "决策",
    "问题",
    "机会",
    "结论",
)
CLOSING_SECTION_CUES = (
    "recommend",
    "roadmap",
    "next step",
    "owner",
    "milestone",
    "建议",
    "路线图",
    "行动",
    "落地",
    "结论",
    "决策",
)
MIDDLE_SECTION_CUES = (
    "tradeoff",
    "option",
    "plan",
    "path",
    "execution",
    "risk",
    "resource",
    "方案",
    "路径",
    "执行",
    "举措",
    "风险",
    "成本",
)
PPTMASTER_ROOT_ENV = "SIE_PPTMASTER_ROOT"
PPTMASTER_SCRIPT_PATHS: dict[str, Path] = {
    "total_md_split.py": Path("skills") / "ppt-master" / "scripts" / "total_md_split.py",
    "finalize_svg.py": Path("skills") / "ppt-master" / "scripts" / "finalize_svg.py",
    "svg_to_pptx.py": Path("skills") / "ppt-master" / "scripts" / "svg_to_pptx.py",
}
DEFAULT_EXTERNAL_COMMAND_TIMEOUT_SEC = 120


@dataclass(frozen=True)
class OutlineGenerationRequest:
    topic: str
    brief: str = ""
    audience: str = DEFAULT_AUDIENCE_HINT
    chapter_count: int | None = None
    audience_tier: str | None = None
    narrative_pacing: str = "balanced"
    language: str = "zh-CN"
    theme: str = "sie_consulting_fixed"
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
    theme: str = "sie_consulting_fixed"
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
    svg_project_path: Path | None = None
    svg_final_dir: Path | None = None


@dataclass(frozen=True)
class V2CompiledDeckArtifacts:
    outline: OutlineDocument
    semantic_payload: dict[str, Any]
    validated_deck: ValidatedDeck


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


def _normalize_outline_narrative_pacing(value: str | None) -> str:
    raw = str(value or "balanced").strip().lower()
    normalized = OUTLINE_NARRATIVE_PACING_ALIASES.get(raw, raw)
    if normalized not in OUTLINE_NARRATIVE_PACING:
        allowed = ", ".join(OUTLINE_NARRATIVE_PACING)
        raise ValueError(f"narrative_pacing must be one of {allowed}")
    return normalized


def _infer_audience_tier(audience: str) -> str:
    lowered = str(audience or "").strip().lower()
    if any(token in lowered for token in ("ceo", "cfo", "board", "vp", "executive", "董事", "高管", "决策层")):
        return "executive"
    if any(token in lowered for token in ("manager", "director", "lead", "management", "负责人", "总监", "管理层")):
        return "management"
    if any(token in lowered for token in ("engineer", "operation", "sales", "product", "执行", "运营", "研发", "产品", "销售")):
        return "practitioner"
    if any(token in lowered for token in ("all", "cross-functional", "cross functional", "全员", "跨部门")):
        return "mixed"
    return "general"


def _normalize_outline_audience_tier(value: str | None, audience_hint: str) -> str:
    if value is None or not str(value).strip():
        return _infer_audience_tier(audience_hint)
    normalized = str(value).strip().lower()
    if normalized not in OUTLINE_AUDIENCE_TIERS:
        allowed = ", ".join(OUTLINE_AUDIENCE_TIERS)
        raise ValueError(f"audience_tier must be one of {allowed}")
    return normalized


def _resolve_outline_strategy(request: OutlineGenerationRequest) -> dict[str, Any]:
    min_slides, max_slides = resolve_slide_bounds(request)
    if request.chapter_count is not None:
        chapter_count = _clamp_slide_count(request.chapter_count)
    elif request.exact_slides is not None:
        chapter_count = _clamp_slide_count(request.exact_slides)
    else:
        chapter_count = max(min_slides, min(max_slides, round((min_slides + max_slides) / 2)))
    audience_tier = _normalize_outline_audience_tier(request.audience_tier, request.audience)
    narrative_pacing = _normalize_outline_narrative_pacing(request.narrative_pacing)
    return {
        "chapter_count": chapter_count,
        "audience_tier": audience_tier,
        "narrative_pacing": narrative_pacing,
    }


def _json_block(payload: dict[str, Any] | None, fallback: str = "none") -> str:
    if not payload:
        return fallback
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _create_structured_client(model: str | None = None) -> Any:
    adapter_name = str(os.environ.get("SIE_AUTOPPT_MODEL_ADAPTER", "") or "").strip().lower()
    if adapter_name:
        adapter_factory = resolve_model_adapter(adapter_name)
        if adapter_factory is None:
            raise ValueError(f"Unknown SIE_AUTOPPT_MODEL_ADAPTER: {adapter_name}")
        return adapter_factory(model)
    config = load_openai_responses_config(model=model)
    return OpenAIResponsesClient(config)


def _safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_") or "slide"


def _escape_svg_text(value: str) -> str:
    return escape(str(value), quote=True)


def _resolve_pptmaster_root(*, pptmaster_root: Path | str | None = None) -> Path:
    raw_root = str(pptmaster_root or "").strip() or str(os.environ.get(PPTMASTER_ROOT_ENV, "") or "").strip()
    if not raw_root:
        raise FileNotFoundError(f"{PPTMASTER_ROOT_ENV} is not configured.")
    root = Path(raw_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"{PPTMASTER_ROOT_ENV} does not exist: {root}")
    return root


def _resolve_script_path(*, pptmaster_root: Path, script_name: str) -> Path:
    relative_path = PPTMASTER_SCRIPT_PATHS.get(script_name)
    if relative_path is None:
        raise ValueError(f"Unsupported script lookup: {script_name}")
    candidate = (pptmaster_root / relative_path).resolve()
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Missing required pptmaster script: {candidate}")


def _run_command(command: list[str], *, step_name: str) -> None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_EXTERNAL_COMMAND_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{step_name} timed out after {DEFAULT_EXTERNAL_COMMAND_TIMEOUT_SEC}s") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{step_name} failed: {details or 'unknown error'}")


def _collect_slide_text_lines(slide: Any) -> list[str]:
    lines: list[str] = []
    layout = str(getattr(slide, "layout", ""))
    if layout == "title_content":
        lines.extend(getattr(slide, "content", []))
    elif layout == "two_columns":
        left = getattr(slide, "left", None)
        right = getattr(slide, "right", None)
        if left is not None:
            if getattr(left, "heading", ""):
                lines.append(str(left.heading))
            lines.extend(getattr(left, "items", []))
        if right is not None:
            if getattr(right, "heading", ""):
                lines.append(str(right.heading))
            lines.extend(getattr(right, "items", []))
    elif layout == "title_image":
        lines.extend(getattr(slide, "content", []))
        image = getattr(slide, "image", None)
        if image is not None:
            caption = getattr(image, "caption", None)
            if isinstance(caption, str) and caption:
                lines.append(caption)
    elif layout == "timeline":
        if getattr(slide, "heading", ""):
            lines.append(str(slide.heading))
        for stage in getattr(slide, "stages", []):
            title = getattr(stage, "title", "")
            detail = getattr(stage, "detail", "")
            if title:
                lines.append(str(title))
            if detail:
                lines.append(str(detail))
    elif layout == "stats_dashboard":
        if getattr(slide, "heading", ""):
            lines.append(str(slide.heading))
        for metric in getattr(slide, "metrics", []):
            label = getattr(metric, "label", "")
            value = getattr(metric, "value", "")
            note = getattr(metric, "note", "")
            if label or value:
                lines.append(f"{label}: {value}".strip(": "))
            if note:
                lines.append(str(note))
        lines.extend(getattr(slide, "insights", []))
    elif layout == "matrix_grid":
        if getattr(slide, "heading", ""):
            lines.append(str(slide.heading))
        for cell in getattr(slide, "cells", []):
            title = getattr(cell, "title", "")
            body = getattr(cell, "body", "")
            if title:
                lines.append(str(title))
            if body:
                lines.append(str(body))
    elif layout == "cards_grid":
        if getattr(slide, "heading", ""):
            lines.append(str(slide.heading))
        for card in getattr(slide, "cards", []):
            title = getattr(card, "title", "")
            body = getattr(card, "body", "")
            if title:
                lines.append(str(title))
            if body:
                lines.append(str(body))
    return [line.strip() for line in lines if str(line).strip()]


def _write_svg_project(deck: DeckDocument, *, project_path: Path) -> Path:
    theme = load_theme(deck.meta.theme)
    width = int(round(theme.page.width * 120))
    height = int(round(theme.page.height * 120))
    title_font = theme.fonts.title
    body_font = theme.fonts.body

    svg_output_dir = project_path / "svg_output"
    notes_dir = project_path / "notes"
    svg_output_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)

    note_sections: list[str] = []
    for index, slide in enumerate(deck.slides, start=1):
        slide_slug = _safe_stem(f"{slide.slide_id}_{index:02d}")
        slide_stem = f"slide_{index:02d}_{slide_slug}"
        svg_path = svg_output_dir / f"{slide_stem}.svg"
        lines = _collect_slide_text_lines(slide)
        title = _escape_svg_text(getattr(slide, "title", f"Slide {index}"))

        title_text_element = (
            f'<text x="84" y="96" fill="{theme.colors.primary}" '
            f'font-family="{_escape_svg_text(title_font)}" font-size="42" '
            f'font-weight="700">{title}</text>'
        )
        text_elements = [title_text_element]
        y = 160
        for item in lines[:10]:
            safe_item = _escape_svg_text(item)
            text_elements.append(
                f'<text x="116" y="{y}" fill="{theme.colors.text_main}" '
                f'font-family="{_escape_svg_text(body_font)}" font-size="26">{safe_item}</text>'
            )
            y += 58

        svg_payload = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">\n'
            f'  <rect width="{width}" height="{height}" fill="{theme.colors.bg}"/>\n'
            f'  <rect x="72" y="56" width="{width - 144}" height="{height - 112}" '
            f'rx="18" fill="{theme.colors.card_bg}" stroke="{theme.colors.line}" stroke-width="2"/>\n'
            f"  {' '.join(text_elements)}\n"
            "</svg>\n"
        )
        svg_path.write_text(svg_payload, encoding="utf-8")

        notes_body = "\n".join(f"- {line}" for line in lines[:8]) or "- N/A"
        note_sections.append(f"# {slide_stem}\n{notes_body}")

    (notes_dir / "total.md").write_text("\n\n".join(note_sections).strip() + "\n", encoding="utf-8")
    return project_path


def _run_svg_pipeline(
    *,
    project_path: Path,
    final_ppt_output: Path,
    pptmaster_root: Path | str | None = None,
) -> None:
    resolved_root = _resolve_pptmaster_root(pptmaster_root=pptmaster_root)
    split_script = _resolve_script_path(pptmaster_root=resolved_root, script_name="total_md_split.py")
    finalize_script = _resolve_script_path(pptmaster_root=resolved_root, script_name="finalize_svg.py")
    export_script = _resolve_script_path(pptmaster_root=resolved_root, script_name="svg_to_pptx.py")
    final_ppt_output.parent.mkdir(parents=True, exist_ok=True)

    _run_command([sys.executable, str(split_script), str(project_path)], step_name="svg split notes")
    _run_command([sys.executable, str(finalize_script), str(project_path)], step_name="svg finalize")
    _run_command(
        [sys.executable, str(export_script), str(project_path), "-s", "final", "-o", str(final_ppt_output)],
        step_name="svg export",
    )


def _ensure_svg_export_dependency(*, pptmaster_root: Path | str | None = None) -> None:
    resolved_root = _resolve_pptmaster_root(pptmaster_root=pptmaster_root)
    _resolve_script_path(pptmaster_root=resolved_root, script_name="svg_to_pptx.py")


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
    policy = get_language_policy(language)
    language_constraints = format_language_constraints(policy)
    developer_prompt = (
        "You convert raw presentation requirements into structured business context JSON.\n"
        f"Use {policy.code}.\n"
        f"Do not invent facts. If information is missing, use '{policy.unknown_token}' for strings and [] for arrays.\n"
        f"{language_constraints}\n"
        "Extract only from the provided topic, brief, and audience."
    )
    user_prompt = (
        f"Topic:\n{topic.strip()}\n\n"
        f"Audience:\n{audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{brief.strip() or policy.none_token}\n\n"
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
    policy = get_language_policy(language)
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(
            f"- {item}" for item in validation_feedback
        )
    developer_prompt = render_prompt_template(
        "prompts/system/v2_strategy.md",
        language=policy.code,
        language_constraints=format_language_constraints(policy),
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{topic.strip()}\n\n"
        f"Audience:\n{audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{brief.strip() or policy.none_token}\n\n"
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
    normalized_language = normalize_language_code(language)
    client = _create_structured_client(model=model)
    developer_prompt, user_prompt = build_context_prompts(
        topic=topic,
        brief=brief,
        audience=audience,
        language=normalized_language,
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
    normalized_language = normalize_language_code(language)
    client = _create_structured_client(model=model)
    feedback: tuple[str, ...] = ()
    for _attempt in range(1, max_attempts + 1):
        developer_prompt, user_prompt = build_strategy_prompts(
            topic=topic,
            brief=brief,
            audience=audience,
            language=normalized_language,
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
            },
            "story_rationale": {"type": "string", "minLength": 12, "maxLength": 280},
            "outline_strategy": {
                "type": "object",
                "properties": {
                    "chapter_count": {
                        "type": "integer",
                        "minimum": min_slides,
                        "maximum": max_slides,
                    },
                    "audience_tier": {
                        "type": "string",
                        "enum": list(OUTLINE_AUDIENCE_TIERS),
                    },
                    "narrative_pacing": {
                        "type": "string",
                        "enum": list(OUTLINE_NARRATIVE_PACING),
                    },
                },
                "required": ["chapter_count", "audience_tier", "narrative_pacing"],
                "additionalProperties": False,
            },
        },
        "required": ["pages", "story_rationale", "outline_strategy"],
        "additionalProperties": False,
    }


def build_outline_prompts(
    request: OutlineGenerationRequest,
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    policy = get_language_policy(request.language)
    min_slides, max_slides = resolve_slide_bounds(request)
    strategy = _resolve_outline_strategy(request)
    slide_rule = (
        f"Return exactly {min_slides} pages."
        if min_slides == max_slides
        else f"Return {min_slides}-{max_slides} pages."
    )
    chapter_rule = f"Target chapter_count={strategy['chapter_count']} and keep it consistent with page count."
    strategy_line = (
        f"chapter_count={strategy['chapter_count']}; "
        f"audience_tier={strategy['audience_tier']}; "
        f"narrative_pacing={strategy['narrative_pacing']}"
    )
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(
            f"- {item}" for item in validation_feedback
        )
    developer_prompt = render_prompt_template(
        "prompts/system/v2_outline.md",
        slide_rule=slide_rule,
        chapter_rule=chapter_rule,
        audience_tier=strategy["audience_tier"],
        narrative_pacing=strategy["narrative_pacing"],
        outline_strategy_line=strategy_line,
        language=policy.code,
        language_constraints=format_language_constraints(policy),
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{request.topic.strip()}\n\n"
        f"Audience:\n{request.audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{request.brief.strip() or policy.none_token}\n\n"
        "Structured Context JSON:\n"
        f"{_json_block(request.structured_context)}\n\n"
        "Strategic Analysis JSON:\n"
        f"{_json_block(request.strategic_analysis)}\n\n"
        "Outline Strategy JSON:\n"
        f"{json.dumps(strategy, ensure_ascii=False, indent=2)}\n\n"
        "Return only JSON."
    )
    return developer_prompt, user_prompt


def build_deck_schema() -> dict[str, Any]:
    return build_semantic_deck_schema()


def build_deck_prompts(
    request: DeckGenerationRequest,
    validation_feedback: tuple[str, ...] = (),
) -> tuple[str, str]:
    policy = get_language_policy(request.language)
    feedback_block = ""
    if validation_feedback:
        feedback_block = "\nPrevious attempt failed validation:\n" + "\n".join(
            f"- {item}" for item in validation_feedback
        )
    developer_prompt = render_prompt_template(
        "prompts/system/v2_slides.md",
        language=policy.code,
        language_constraints=format_language_constraints(policy),
        theme_name=request.theme,
        supported_layouts=", ".join(SUPPORTED_LAYOUTS),
        feedback_block=feedback_block,
    )
    user_prompt = (
        f"Topic:\n{request.topic.strip()}\n\n"
        f"Audience:\n{request.audience.strip() or DEFAULT_AUDIENCE_HINT}\n\n"
        f"Brief:\n{request.brief.strip() or policy.none_token}\n\n"
        "Structured Context JSON:\n"
        f"{_json_block(request.structured_context)}\n\n"
        "Strategic Analysis JSON:\n"
        f"{_json_block(request.strategic_analysis)}\n\n"
        "Outline JSON:\n"
        f"{json.dumps(request.outline.to_list(), ensure_ascii=False, indent=2)}\n\n"
        "Return only the deck JSON object."
    )
    return developer_prompt, user_prompt


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _normalized_text(text)
    return any(keyword in normalized for keyword in keywords)


def _is_generic_title(title: str) -> bool:
    normalized = _normalized_text(title)
    return normalized in GENERIC_OUTLINE_TITLES


def _has_minimum_title_readability(title: str) -> bool:
    text = str(title or "").strip()
    if not text:
        return False
    if len(text) > 32:
        return False
    alnum_or_cjk_chars = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", text)
    if not alnum_or_cjk_chars:
        return False
    if len(alnum_or_cjk_chars) < 2:
        return False
    punctuation_count = len([ch for ch in text if ch in "._-/:;,|()[]{}"])
    return punctuation_count <= max(4, len(text) // 2)


def _collect_outline_quality_errors(outline: OutlineDocument, request: OutlineGenerationRequest) -> list[str]:
    errors: list[str] = []
    titles: list[str] = []

    if not outline.story_rationale or len(outline.story_rationale.strip()) < 12:
        errors.append("story_rationale is required and must be at least 12 characters.")

    if outline.outline_strategy is None:
        errors.append("outline_strategy is required and must include chapter_count/audience_tier/narrative_pacing.")
    else:
        min_slides, max_slides = resolve_slide_bounds(request)
        chapter_count = int(outline.outline_strategy.chapter_count)
        if not (min_slides <= chapter_count <= max_slides):
            errors.append(f"outline_strategy.chapter_count must be between {min_slides} and {max_slides}.")
        if request.audience_tier and str(request.audience_tier).strip():
            expected_audience_tier = _normalize_outline_audience_tier(request.audience_tier, request.audience)
            if outline.outline_strategy.audience_tier != expected_audience_tier:
                errors.append(
                    "outline_strategy.audience_tier must align with requested audience tier "
                    f"'{expected_audience_tier}'."
                )
        expected_pacing = _normalize_outline_narrative_pacing(request.narrative_pacing)
        if outline.outline_strategy.narrative_pacing != expected_pacing:
            errors.append(
                "outline_strategy.narrative_pacing must align with requested pacing "
                f"'{expected_pacing}'."
            )

    for page in outline.pages:
        title = page.title.strip()
        titles.append(title)
        if _is_generic_title(title):
            errors.append(
                f"page {page.page_no} title '{title}' is too generic; use a conclusion-led business title."
            )
        if not _has_minimum_title_readability(title):
            errors.append(f"page {page.page_no} title '{title}' is not readable enough.")

    normalized_titles = [_normalized_text(item) for item in titles]
    if len(normalized_titles) != len(set(normalized_titles)):
        errors.append("outline titles must be unique.")

    if outline.pages:
        opening_text = f"{outline.pages[0].title} {outline.pages[0].goal}"
        if not _contains_any_keyword(opening_text, OPENING_SECTION_CUES):
            errors.append("first page must establish context and decision lens, not generic framing.")

    if len(outline.pages) >= 2:
        closing_text = f"{outline.pages[-1].title} {outline.pages[-1].goal}"
        if not _contains_any_keyword(closing_text, CLOSING_SECTION_CUES):
            errors.append("last page must close with recommendation, roadmap, or decision ask.")

    if len(outline.pages) >= 4:
        middle_pages = outline.pages[1:-1]
        if middle_pages:
            has_argument_progress = any(
                _contains_any_keyword(f"{page.title} {page.goal}", MIDDLE_SECTION_CUES) for page in middle_pages
            )
            if not has_argument_progress:
                errors.append("middle pages must advance execution argument with options/tradeoffs/path.")

    return errors


def _validate_outline_response(payload: dict[str, Any], request: OutlineGenerationRequest) -> OutlineDocument:
    outline = OutlineDocument.model_validate(payload)
    min_slides, max_slides = resolve_slide_bounds(request)
    if not (min_slides <= len(outline.pages) <= max_slides):
        raise ValueError(f"outline page count must be between {min_slides} and {max_slides}.")
    quality_errors = _collect_outline_quality_errors(outline, request)
    if quality_errors:
        raise ValueError("; ".join(quality_errors))
    return outline


def generate_outline_with_ai(
    request: OutlineGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> OutlineDocument:
    if request.theme not in SUPPORTED_THEMES:
        raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
    normalized_language = normalize_language_code(request.language)
    generation_mode = normalize_generation_mode(request.generation_mode)
    if request.audience_tier and str(request.audience_tier).strip():
        _normalize_outline_audience_tier(request.audience_tier, request.audience)
    resolved_narrative_pacing = _normalize_outline_narrative_pacing(request.narrative_pacing)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=normalized_language,
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
        chapter_count=request.chapter_count,
        audience_tier=request.audience_tier,
        narrative_pacing=resolved_narrative_pacing,
        language=normalized_language,
        theme=request.theme,
        exact_slides=request.exact_slides,
        min_slides=request.min_slides,
        max_slides=request.max_slides,
        generation_mode=generation_mode,
        structured_context=structured_context,
        strategic_analysis=strategic_analysis,
    )
    client = _create_structured_client(model=model)
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
    raise ValueError(f"Outline generation failed validation after {max_attempts} attempts: " + "; ".join(feedback))


def generate_deck_with_ai(
    request: DeckGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> ValidatedDeck:
    normalized_language = normalize_language_code(request.language)
    semantic_payload = generate_semantic_deck_with_ai(
        request=request,
        model=model,
        max_attempts=max_attempts,
    )
    return compile_semantic_deck_payload(
        semantic_payload,
        default_title=request.topic,
        default_theme=request.theme,
        default_language=normalized_language,
        default_author=request.author,
    )


def generate_semantic_deck_with_ai(
    request: DeckGenerationRequest,
    model: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if request.theme not in SUPPORTED_THEMES:
        raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
    normalized_language = normalize_language_code(request.language)
    generation_mode = normalize_generation_mode(request.generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=normalized_language,
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
        language=normalized_language,
        theme=request.theme,
        author=request.author,
        generation_mode=generation_mode,
        structured_context=structured_context,
        strategic_analysis=strategic_analysis,
    )
    client = _create_structured_client(model=model)
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


def _extract_semantic_slides(payload: dict[str, Any]) -> list[dict[str, Any]]:
    slides = payload.get("slides")
    if not isinstance(slides, list):
        return []
    return [slide for slide in slides if isinstance(slide, dict)]


def _semantic_candidate_score(
    payload: dict[str, Any],
    *,
    request: DeckGenerationRequest,
) -> tuple[float, dict[str, Any]]:
    expected_pages = len(request.outline.pages)
    slides = _extract_semantic_slides(payload)
    slide_count = len(slides)

    structure_gap = abs(slide_count - expected_pages)
    structure_score = max(0.0, 45.0 - (structure_gap * 18.0))
    if expected_pages > 0 and slide_count == expected_pages:
        structure_score += 8.0

    slides_with_blocks = 0
    slides_with_sources = 0
    block_count = 0
    data_source_count = 0
    intents: set[str] = set()
    for slide in slides:
        intent = str(slide.get("intent", "")).strip()
        if intent:
            intents.add(intent)
        blocks = slide.get("blocks")
        if isinstance(blocks, list):
            valid_blocks = [block for block in blocks if isinstance(block, dict)]
            if valid_blocks:
                slides_with_blocks += 1
                block_count += len(valid_blocks)
        data_sources = slide.get("data_sources")
        if isinstance(data_sources, list):
            valid_sources = [source for source in data_sources if isinstance(source, dict)]
            if valid_sources:
                slides_with_sources += 1
                data_source_count += len(valid_sources)

    evidence_slides = max(slides_with_blocks, slides_with_sources)
    evidence_coverage = evidence_slides / max(1, expected_pages)
    evidence_score = min(24.0, evidence_coverage * 16.0) + min(10.0, float(data_source_count * 2))
    renderability_bonus = 0.0
    renderable = False
    render_error = ""
    try:
        compile_semantic_deck_payload(
            payload,
            default_title=request.topic,
            default_theme=request.theme,
            default_language=request.language,
            default_author=request.author,
        )
        renderable = True
        renderability_bonus = 28.0
    except ValueError as exc:
        render_error = str(exc)
        renderability_bonus = -160.0

    diversity_score = min(8.0, float(len(intents) * 2))
    density_score = min(8.0, float(block_count))
    total_score = structure_score + evidence_score + diversity_score + density_score + renderability_bonus

    return total_score, {
        "slide_count": slide_count,
        "expected_pages": expected_pages,
        "structure_gap": structure_gap,
        "evidence_coverage": round(evidence_coverage, 4),
        "data_source_count": data_source_count,
        "block_count": block_count,
        "intent_count": len(intents),
        "renderable": renderable,
        "render_error": render_error,
    }


def select_best_semantic_candidate(
    candidates: list[dict[str, Any]],
    *,
    request: DeckGenerationRequest,
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    if not candidates:
        raise ValueError("semantic candidates cannot be empty")

    scored: list[tuple[float, int, dict[str, Any], dict[str, Any]]] = []
    score_report: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        score, metrics = _semantic_candidate_score(candidate, request=request)
        score_report.append(
            {
                "candidate_index": index,
                "score": round(score, 4),
                "metrics": metrics,
            }
        )
        scored.append((score, -index, candidate, metrics))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected_candidate = scored[0][2]
    selected_index = -scored[0][1]
    return selected_candidate, selected_index, score_report


def generate_compiled_v2_deck(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    theme: str = "sie_consulting_fixed",
    author: str = "Enterprise AI PPT",
    exact_slides: int | None = None,
    min_slides: int = 6,
    max_slides: int = 10,
    model: str | None = None,
    generation_mode: str = "deep",
    outline: OutlineDocument | None = None,
) -> V2CompiledDeckArtifacts:
    normalized_language = normalize_language_code(language)
    resolved_generation_mode = normalize_generation_mode(generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=topic,
        brief=brief,
        audience=audience,
        language=normalized_language,
        generation_mode=resolved_generation_mode,
        structured_context=None,
        strategic_analysis=None,
        model=model,
    )

    resolved_outline = outline or generate_outline_with_ai(
        OutlineGenerationRequest(
            topic=topic,
            brief=brief,
            audience=audience,
            chapter_count=exact_slides,
            language=normalized_language,
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

    semantic_payload = generate_semantic_deck_with_ai(
        DeckGenerationRequest(
            topic=topic,
            outline=resolved_outline,
            brief=brief,
            audience=audience,
            language=normalized_language,
            theme=theme,
            author=author,
            generation_mode=resolved_generation_mode,
            structured_context=structured_context,
            strategic_analysis=strategic_analysis,
        ),
        model=model,
    )

    validated_deck = compile_semantic_deck_payload(
        semantic_payload,
        default_title=topic,
        default_theme=theme,
        default_language=normalized_language,
        default_author=author,
    )

    return V2CompiledDeckArtifacts(
        outline=resolved_outline,
        semantic_payload=semantic_payload,
        validated_deck=validated_deck,
    )


async def generate_semantic_decks_with_ai_batch(
    requests: list[DeckGenerationRequest],
    *,
    model: str | None = None,
    concurrency: int = 4,
) -> list[dict[str, Any]]:
    if not requests:
        return []
    bounded = max(1, int(concurrency))
    semaphore = asyncio.Semaphore(bounded)
    results: list[dict[str, Any] | None] = [None] * len(requests)
    normalized_requests: list[DeckGenerationRequest] = []
    for request in requests:
        if request.theme not in SUPPORTED_THEMES:
            raise ValueError(f"theme must be one of {', '.join(SUPPORTED_THEMES)}")
        normalized_language = normalize_language_code(request.language)
        generation_mode = normalize_generation_mode(request.generation_mode)
        structured_context, strategic_analysis = ensure_generation_context(
            topic=request.topic,
            brief=request.brief,
            audience=request.audience,
            language=normalized_language,
            generation_mode=generation_mode,
            structured_context=request.structured_context,
            strategic_analysis=request.strategic_analysis,
            model=model,
        )
        normalized_requests.append(
            DeckGenerationRequest(
                topic=request.topic,
                outline=request.outline,
                brief=request.brief,
                audience=request.audience,
                language=normalized_language,
                theme=request.theme,
                author=request.author,
                generation_mode=generation_mode,
                structured_context=structured_context,
                strategic_analysis=strategic_analysis,
            )
        )

    client = _create_structured_client(model=model)
    if hasattr(client, "acreate_structured_json_batch"):
        batch_requests: list[dict[str, Any]] = []
        for normalized in normalized_requests:
            developer_prompt, user_prompt = build_deck_prompts(normalized)
            batch_requests.append(
                {
                    "developer_prompt": developer_prompt,
                    "user_items": [{"type": "text", "text": user_prompt}],
                    "schema_name": "ppt_deck_v2",
                    "schema": build_deck_schema(),
                }
            )
        payloads = await client.acreate_structured_json_batch(batch_requests, concurrency=bounded)
        for index, payload in enumerate(payloads):
            normalized = normalized_requests[index]
            compile_semantic_deck_payload(
                payload,
                default_title=normalized.topic,
                default_theme=normalized.theme,
                default_language=normalized.language,
                default_author=normalized.author,
            )
            results[index] = payload
        return [item for item in results if item is not None]

    async def _run(index: int, normalized: DeckGenerationRequest) -> None:
        developer_prompt, user_prompt = build_deck_prompts(normalized)
        async with semaphore:
            payload = await asyncio.to_thread(
                client.create_structured_json,
                developer_prompt=developer_prompt,
                user_prompt=user_prompt,
                schema_name="ppt_deck_v2",
                schema=build_deck_schema(),
            )
        compile_semantic_deck_payload(
            payload,
            default_title=normalized.topic,
            default_theme=normalized.theme,
            default_language=normalized.language,
            default_author=normalized.author,
        )
        results[index] = payload

    await asyncio.gather(*(_run(index, normalized) for index, normalized in enumerate(normalized_requests)))
    return [item for item in results if item is not None]


def run_pre_render_quality_gate(
    *,
    validated_deck: ValidatedDeck,
    rewrite_log_path: Path,
    warnings_path: Path,
) -> ValidatedDeck:
    initial_quality = quality_gate(validated_deck)
    rewrite_result = rewrite_deck(validated_deck, initial_quality)
    write_rewrite_log(rewrite_result, rewrite_log_path)
    write_quality_gate_result(rewrite_result.final_quality_gate, warnings_path)

    rewritten_validated = rewrite_result.validated_deck or validated_deck
    if rewritten_validated is None:
        raise ValueError("Schema validation failed; SVG pipeline was skipped.")
    if not rewrite_result.final_quality_gate.passed:
        raise ValueError(
            "Quality gate failed: "
            f"{rewrite_result.final_quality_gate.summary['error_count']} error(s) found. "
            "SVG pipeline was skipped."
        )
    return rewritten_validated


def build_svg_project_from_deck(*, deck: DeckDocument, output_dir: Path, output_prefix: str) -> Path:
    safe_prefix = _safe_stem(output_prefix)
    svg_project_path = output_dir / "svg_projects" / f"{safe_prefix}_ppt169"
    _write_svg_project(deck, project_path=svg_project_path)
    return svg_project_path


def write_v2_make_log(*, log_path: Path, svg_project_path: Path, final_ppt_output: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            (
                "INFO: make_v2_ppt routes through SVG primary pipeline.",
                f"INFO: svg_project={svg_project_path}",
                "INFO: svg_stage=final",
                f"INFO: output_pptx={final_ppt_output}",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def make_v2_ppt(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    theme: str = "sie_consulting_fixed",
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
    pptmaster_root: Path | str | None = None,
) -> V2MakeArtifacts:
    final_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    provided_outline = load_outline_document(outline_path) if outline_path is not None else None
    if outline_path is not None:
        final_outline_output = outline_path
    else:
        final_outline_output = outline_output or default_outline_output_path(final_output_dir)

    compiled_artifacts = generate_compiled_v2_deck(
        topic=topic,
        brief=brief,
        audience=audience,
        language=language,
        theme=theme,
        author=author,
        exact_slides=exact_slides,
        min_slides=min_slides,
        max_slides=max_slides,
        model=model,
        generation_mode=generation_mode,
        outline=provided_outline,
    )
    if provided_outline is None:
        write_outline_document(compiled_artifacts.outline, final_outline_output)

    final_semantic_output = semantic_output or default_semantic_output_path(final_output_dir)
    write_semantic_document(compiled_artifacts.semantic_payload, final_semantic_output)
    validated_deck = compiled_artifacts.validated_deck
    final_deck_output = deck_output or default_deck_output_path(final_output_dir)
    final_log_output = log_output or default_log_output_path(final_output_dir)
    final_ppt_output = ppt_output or default_ppt_output_path(final_output_dir)
    rewrite_log_path = final_log_output.parent / "rewrite_log.json"
    warnings_path = final_log_output.parent / "warnings.json"

    rewritten_validated = run_pre_render_quality_gate(
        validated_deck=validated_deck,
        rewrite_log_path=rewrite_log_path,
        warnings_path=warnings_path,
    )

    final_deck = rewritten_validated.deck
    write_deck_document(final_deck, final_deck_output)

    svg_project_path = build_svg_project_from_deck(
        deck=final_deck,
        output_dir=final_output_dir,
        output_prefix=output_prefix,
    )
    _run_svg_pipeline(
        project_path=svg_project_path,
        final_ppt_output=final_ppt_output,
        pptmaster_root=pptmaster_root,
    )

    write_v2_make_log(
        log_path=final_log_output,
        svg_project_path=svg_project_path,
        final_ppt_output=final_ppt_output,
    )
    return V2MakeArtifacts(
        outline_path=final_outline_output,
        semantic_path=final_semantic_output,
        deck_path=final_deck_output,
        log_path=final_log_output,
        rewrite_log_path=rewrite_log_path,
        warnings_path=warnings_path,
        pptx_path=final_ppt_output,
        deck=final_deck,
        warnings=tuple(collect_deck_warnings(final_deck)),
        svg_project_path=svg_project_path,
        svg_final_dir=svg_project_path / "svg_final",
    )
