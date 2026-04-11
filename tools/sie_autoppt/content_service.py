from __future__ import annotations

import re

from .models import DeckSpec, StructureArgument, StructureSection, StructureSpec
from .planning.deck_planner import (
    build_body_page_spec,
    resolve_page_layout,
)
from .planning.payload_builders import (
    build_claim_items,
    build_dashboard_insights,
    build_kpi_metrics,
    build_process_steps,
    build_risk_items,
    build_roadmap_stages,
)
from .planning.text_utils import compact_text, concise_text, shorten_for_nav


_COMPARISON_KEYWORDS = ("对比", "比较", "差异", "升级", "替代", "现状 vs", "before", "after", "vs")
_PROCESS_KEYWORDS = ("路径", "阶段", "步骤", "推进", "路线", "roadmap", "phase", "实施")
_CONCLUSION_KEYWORDS = ("结论", "判断", "核心观点", "总体判断", "关键结论", "总结")
_ROADMAP_KEYWORDS = ("路线图", "里程碑", "时间轴", "roadmap", "milestone", "季度")
_DASHBOARD_KEYWORDS = ("kpi", "指标", "仪表盘", "经营", "表现", "增长", "dashboard", "scorecard")
_RISK_KEYWORDS = ("风险", "概率", "影响", "矩阵", "risk")
_CLAIM_KEYWORDS = ("索赔", "金额", "拆解", "claim", "成本", "预算")


def _argument_text(argument: StructureArgument) -> str:
    if argument.evidence:
        return f"{argument.point}: {argument.evidence}"
    return argument.point


def map_structure_to_slide_schema(
    structure_type: str,
    title: str,
    key_message: str = "",
    arguments: list[StructureArgument] | None = None,
) -> str:
    normalized_text = f"{structure_type} {title} {key_message}".lower()
    argument_count = len(arguments or [])

    if any(keyword.lower() in normalized_text for keyword in _ROADMAP_KEYWORDS):
        return "roadmap"
    if any(keyword.lower() in normalized_text for keyword in _PROCESS_KEYWORDS):
        return "process"
    if argument_count >= 4 and any(keyword.lower() in normalized_text for keyword in _COMPARISON_KEYWORDS):
        return "comparison"
    if any(keyword.lower() in normalized_text for keyword in _DASHBOARD_KEYWORDS):
        return "dashboard"
    if any(keyword.lower() in normalized_text for keyword in _CLAIM_KEYWORDS):
        return "claim"
    if any(keyword.lower() in normalized_text for keyword in _RISK_KEYWORDS):
        return "risk"
    if any(keyword.lower() in normalized_text for keyword in _CONCLUSION_KEYWORDS):
        return "conclusion"
    if structure_type in {"comparison_analysis"} and argument_count >= 4:
        return "comparison"
    if structure_type in {"process_plan", "solution_design"} and any(keyword.lower() in normalized_text for keyword in _PROCESS_KEYWORDS):
        return "process"
    return "cards"


def _comparison_labels(section: StructureSection) -> tuple[str, str]:
    normalized = section.title.lower()
    if "现状" in normalized or "当前" in normalized:
        return "现状", "目标"
    if "旧" in normalized or "新" in normalized:
        return "旧模式", "新模式"
    return "对比一侧", "对比另一侧"


def _build_comparison_payload(section: StructureSection) -> dict[str, object]:
    arguments = list(section.arguments[:4])
    midpoint = max(1, len(arguments) // 2)
    left_args = arguments[:midpoint]
    right_args = arguments[midpoint:]
    if not right_args:
        right_args = arguments[:]
    left_label, right_label = _comparison_labels(section)
    return {
        "headline": concise_text(section.key_message, 36),
        "left_label": left_label,
        "right_label": right_label,
        "left_cards": [
            {
                "title": compact_text(argument.point, 14),
                "detail": concise_text(argument.evidence or argument.point, 34),
            }
            for argument in left_args
        ],
        "right_cards": [
            {
                "title": compact_text(argument.point, 14),
                "detail": concise_text(argument.evidence or argument.point, 34),
            }
            for argument in right_args
        ],
        "center_kicker": "STRUCTURED COMPARISON",
        "center_title": compact_text(section.title, 18),
        "center_subtitle": concise_text(section.key_message, 36),
        "center_bottom_footer": concise_text(section.key_message, 24),
    }


def _build_process_payload(section: StructureSection) -> dict[str, object]:
    return {
        "steps": build_process_steps([_argument_text(argument) for argument in section.arguments]),
    }


def _build_roadmap_payload(section: StructureSection) -> dict[str, object]:
    items = [_argument_text(argument) for argument in section.arguments]
    return {
        "headline": concise_text(section.key_message, 34),
        "footer": concise_text(section.key_message, 34),
        "stages": build_roadmap_stages(items),
    }


def _build_dashboard_payload(section: StructureSection) -> dict[str, object]:
    items = [_argument_text(argument) for argument in section.arguments]
    return {
        "headline": concise_text(section.key_message, 34),
        "footer": concise_text(section.key_message, 34),
        "metrics": build_kpi_metrics(items),
        "insights": build_dashboard_insights(items[4:] or items),
    }


def _build_risk_payload(section: StructureSection) -> dict[str, object]:
    items = [_argument_text(argument) for argument in section.arguments]
    return {
        "headline": concise_text(section.key_message, 34),
        "footer": concise_text(section.key_message, 34),
        "items": build_risk_items(items),
    }


def _build_claim_payload(section: StructureSection) -> dict[str, object]:
    items = [_argument_text(argument) for argument in section.arguments]
    return {
        "headline": concise_text(section.key_message, 34),
        "footer": concise_text(section.key_message, 34),
        "claims": build_claim_items(items),
        "summary": concise_text(section.key_message, 56),
    }


def _pattern_for_schema(schema_id: str, section: StructureSection) -> str:
    if schema_id == "roadmap":
        return "roadmap_timeline"
    if schema_id == "dashboard":
        return "kpi_dashboard"
    if schema_id == "risk":
        return "risk_matrix"
    if schema_id == "claim":
        return "claim_breakdown"
    if schema_id == "process":
        return "process_flow"
    if schema_id == "comparison":
        return "comparison_upgrade"
    if schema_id == "cards" and any(keyword in section.title for keyword in ("问题", "痛点", "瓶颈", "障碍")):
        return "pain_cards"
    return "general_business"


def _payload_for_schema(schema_id: str, section: StructureSection) -> dict[str, object]:
    if schema_id == "roadmap":
        return _build_roadmap_payload(section)
    if schema_id == "dashboard":
        return _build_dashboard_payload(section)
    if schema_id == "risk":
        return _build_risk_payload(section)
    if schema_id == "claim":
        return _build_claim_payload(section)
    if schema_id == "process":
        return _build_process_payload(section)
    if schema_id == "comparison":
        return _build_comparison_payload(section)
    if schema_id == "cards":
        if any(keyword in section.title for keyword in ("问题", "痛点", "瓶颈", "障碍")):
            cards = []
            for argument in section.arguments[:3]:
                cards.append(
                    {
                        "title": compact_text(argument.point, 14),
                        "detail": concise_text(argument.evidence or argument.point, 32),
                        "points": [compact_text(argument.evidence or argument.point, 18)] if argument.evidence else [],
                    }
                )
            return {
                "lead": concise_text(section.key_message, 34),
                "bottom_banner": compact_text(section.title, 18),
                "cards": cards,
            }
    return {}


def build_deck_spec_from_structure(
    structure: StructureSpec,
    topic: str,
    cover_title: str | None = None,
) -> DeckSpec:
    body_pages = []
    resolved_cover_title = (cover_title or topic or structure.core_message).strip() or "结构化汇报"

    for index, section in enumerate(structure.sections, start=1):
        schema_id = map_structure_to_slide_schema(
            structure_type=structure.structure_type,
            title=section.title,
            key_message=section.key_message,
            arguments=section.arguments,
        )
        pattern_id = _pattern_for_schema(schema_id, section)
        bullets = [compact_text(argument.point, 36) for argument in section.arguments[:4]]
        payload = _payload_for_schema(schema_id, section)
        pattern_id, layout_variant, layout_hints, _ = resolve_page_layout(pattern_id, section.title, bullets)
        page = build_body_page_spec(
            page_key=f"struct_page_{index:02d}",
            title=compact_text(section.title, 28),
            subtitle=concise_text(section.key_message, 52),
            bullets=bullets,
            pattern_id=pattern_id,
            nav_title=shorten_for_nav(section.title),
            payload=payload,
            layout_variant=layout_variant,
            slide_role="body",
            layout_hints={
                **layout_hints,
                "slide_schema": schema_id,
                "structure_type": structure.structure_type,
            },
        )
        body_pages.append(page)

    return DeckSpec(
        cover_title=resolved_cover_title,
        body_pages=body_pages,
    )
