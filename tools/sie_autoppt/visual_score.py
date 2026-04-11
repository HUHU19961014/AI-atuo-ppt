from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .llm_openai import OpenAIResponsesClient, load_openai_responses_config
from .visual_rule_config import VisualRuleConfig, load_visual_rule_config_from_path
from .visual_spec import SUPPORTED_COMPONENT_TYPES, SUPPORTED_LAYOUT_TYPES, VisualSpec


@dataclass(frozen=True)
class RuleIssue:
    severity: str
    dimension: str
    message: str


@dataclass(frozen=True)
class RuleScore:
    score: int
    level: str
    issues: list[RuleIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass(frozen=True)
class AiReview:
    score: int
    decision: str
    summary: str
    strengths: list[str]
    issues: list[str]
    fixes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _score_level(score: int, config: VisualRuleConfig) -> str:
    if score >= config.scoring.pass_threshold:
        return "pass"
    if score >= config.scoring.pass_with_notes_threshold:
        return "pass_with_notes"
    return "revise"


def score_visual_draft(
    spec: VisualSpec,
    html: str,
    screenshot_path: Path | None = None,
    *,
    rules_path: str = "",
    rule_config: VisualRuleConfig | None = None,
) -> RuleScore:
    config = rule_config or load_visual_rule_config_from_path(rules_path)
    penalties = config.penalties
    limits = config.limits
    score = 100
    issues: list[RuleIssue] = []
    types = [component.type for component in spec.components]

    if "headline" not in types:
        score -= penalties.missing_headline
        issues.append(RuleIssue("high", "message_clarity", "Missing headline component."))
    if "hero_claim" not in types and "value_band" not in types:
        score -= penalties.missing_claim
        issues.append(RuleIssue("medium", "message_clarity", "Missing hero_claim/value_band."))
    if sum(1 for component_type in types if component_type in {"proof_card", "risk_card"}) > limits.max_cards:
        score -= penalties.too_many_cards
        issues.append(RuleIssue("medium", "density", "Too many cards for single-page readability."))
    if any(len(component.detail) > limits.max_detail_chars for component in spec.components if component.detail):
        score -= penalties.detail_too_long
        issues.append(RuleIssue("medium", "readability", "Card detail text is too long."))
    if any(component_type not in SUPPORTED_COMPONENT_TYPES for component_type in types):
        score -= penalties.unsupported_component
        issues.append(RuleIssue("high", "layout_balance", "Unsupported component type appears in VisualSpec."))
    if 'class="slide"' not in html:
        score -= penalties.missing_slide_root
        issues.append(RuleIssue("high", "layout_balance", "HTML missing .slide root container."))
    if "overflow: hidden" not in html:
        score -= penalties.missing_overflow_hidden
        issues.append(RuleIssue("high", "layout_balance", "Slide overflow is not locked; scrolling risk exists."))
    if re.search(r"https?://", html):
        score -= penalties.external_assets
        issues.append(RuleIssue("high", "brand", "HTML references external network assets."))
    if spec.layout.type not in SUPPORTED_LAYOUT_TYPES:
        score -= penalties.unknown_layout
        issues.append(RuleIssue("high", "layout_balance", "Unknown layout type."))
    if screenshot_path is not None and not screenshot_path.exists():
        score -= penalties.missing_screenshot
        issues.append(RuleIssue("medium", "conversion_readiness", "Screenshot file is missing."))

    font_sizes = [int(match.group(1)) for match in re.finditer(r"font-size\s*:\s*(\d+)px", html)]
    if font_sizes and min(font_sizes) < limits.min_font_px:
        score -= penalties.too_small_font
        issues.append(RuleIssue("medium", "readability", "Some text font sizes are below 12px."))

    colors = {match.group(0).lower() for match in re.finditer(r"#[0-9a-fA-F]{6}", html)}
    if len(colors) > limits.max_colors:
        score -= penalties.too_many_colors
        issues.append(RuleIssue("low", "brand", "Too many unique colors in one slide draft."))

    safe_area_match = re.search(
        r"\.slide-body\{[^}]*left:(\d+)px;[^}]*right:(\d+)px;[^}]*top:(\d+)px;[^}]*bottom:(\d+)px;",
        html,
    )
    if safe_area_match:
        left, right, top, bottom = [int(value) for value in safe_area_match.groups()]
        safe = spec.canvas.safe_area
        if left < safe.left or right < safe.right or top < safe.top or bottom < safe.bottom:
            score -= penalties.safe_area_violation
            issues.append(
                RuleIssue(
                    "high",
                    "safe_area",
                    "Slide body boundary violates configured safe area.",
                )
            )
    else:
        score -= penalties.safe_area_uncheckable
        issues.append(RuleIssue("medium", "safe_area", "Unable to validate safe-area boundary from HTML."))

    score = max(0, score)
    return RuleScore(score=score, level=_score_level(score, config), issues=issues)


def _build_ai_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "decision": {"type": "string", "enum": ["pass", "pass_with_notes", "revise"]},
            "summary": {"type": "string", "minLength": 2, "maxLength": 240},
            "strengths": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 120}},
            "issues": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 120}},
            "fixes": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 180}},
        },
        "required": ["score", "decision", "summary", "strengths", "issues", "fixes"],
        "additionalProperties": False,
    }


def _normalize_ai_review(payload: dict[str, Any]) -> AiReview:
    score = int(payload.get("score", 0))
    score = max(0, min(100, score))
    decision = str(payload.get("decision", "")).strip().lower()
    if decision not in {"pass", "pass_with_notes", "revise"}:
        decision = _score_level(score, load_visual_rule_config_from_path(""))
    summary = str(payload.get("summary", "")).strip() or "No summary provided."
    strengths = [str(item).strip() for item in payload.get("strengths", []) if str(item).strip()]
    issues = [str(item).strip() for item in payload.get("issues", []) if str(item).strip()]
    fixes = [str(item).strip() for item in payload.get("fixes", []) if str(item).strip()]
    return AiReview(
        score=score,
        decision=decision,
        summary=summary,
        strengths=strengths,
        issues=issues,
        fixes=fixes,
    )


def review_visual_draft_with_ai(
    spec: VisualSpec,
    html_path: Path,
    screenshot_path: Path | None,
    *,
    model: str = "",
) -> AiReview:
    client = OpenAIResponsesClient(load_openai_responses_config(model=model or None))
    user_items: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Review this single-slide visual draft for enterprise sales quality. "
                "Give strict feedback and concrete fixes.\n\n"
                f"VisualSpec:\n{json.dumps(spec.to_dict(), ensure_ascii=False, indent=2)}\n\n"
                f"HTML:\n{html_path.read_text(encoding='utf-8')[:8000]}"
            ),
        }
    ]
    if screenshot_path is not None and screenshot_path.exists():
        user_items.append({"type": "image_path", "path": str(screenshot_path)})
    response = client.create_structured_json_with_user_items(
        developer_prompt=(
            "You are a strict business-slide visual reviewer. "
            "Return JSON only. Focus on clarity, hierarchy, persuasion, density, and brand fitness."
        ),
        user_items=user_items,
        schema_name="visual_draft_review",
        schema=_build_ai_schema(),
    )
    return _normalize_ai_review(response)
