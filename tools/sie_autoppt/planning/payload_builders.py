import re

from ..models import BodyPagePayload, BodyPageSpec, InputPayload
from ..patterns import infer_pattern
from . import legacy_html_support as _legacy_html_support
from .text_utils import compact_text, concise_text, split_title_detail


DEFAULT_GOVERNANCE_LABEL = "重点"
_ROADMAP_STAGE_PATTERN = re.compile(
    r"^(q[1-4]|q\d{1,2}|h[12]|phase\s*\d+|step\s*\d+|阶段[一二三四五六七八九十\d]+|里程碑\d+|20\d{2}(?:年q\d|h\d)?)$",
    re.IGNORECASE,
)
_KPI_VALUE_PATTERN = re.compile(
    r"([+\-]?\d+(?:\.\d+)?%|[+\-]?\d+(?:\.\d+)?(?:万|亿|k|m|b)?|¥\s*\d+(?:\.\d+)?(?:万|亿)?|\$\s*\d+(?:\.\d+)?(?:k|m|b)?)",
    re.IGNORECASE,
)


def derive_comparison_cards(raw_items: list[str], fallback_title: str, synthetic_tail: tuple[str, str]) -> list[dict[str, str]]:
    cards = []
    for item in raw_items:
        title, detail = split_title_detail(item)
        cards.append(
            {
                "title": compact_text(title or fallback_title, 14),
                "detail": concise_text(detail or title or fallback_title, 34),
            }
        )
    while len(cards) < 3:
        cards.append({"title": fallback_title, "detail": concise_text(fallback_title, 34)})
    cards = cards[:3]
    cards.append({"title": compact_text(synthetic_tail[0], 14), "detail": concise_text(synthetic_tail[1], 34)})
    return cards


def build_architecture_layers(payload: InputPayload) -> list[dict[str, str]]:
    layers = []
    for index, phase in enumerate(payload.phases[:4], start=1):
        title = compact_text(phase.get("name") or f"Layer {index}", 18)
        detail = concise_text(phase.get("func") or phase.get("code") or phase.get("owner") or title, 54)
        layers.append({"label": f"L{index:02d}", "title": title, "detail": detail})
    return layers


def build_process_steps(items: list[str]) -> list[dict[str, str]]:
    steps = []
    for index, item in enumerate(items[:4], start=1):
        title, detail = split_title_detail(item)
        compact_title = compact_text(title or f"Step {index}", 12)
        compact_detail = concise_text(detail or title or compact_title, 30)
        steps.append({"number": f"{index:02d}", "title": compact_title, "detail": compact_detail})
    return steps


def build_governance_cards(items: list[str]) -> list[dict[str, str]]:
    cards = []
    for index, item in enumerate(items[:4], start=1):
        title, detail = split_title_detail(item)
        label_source = title
        if title == detail:
            first_clause = re.split(r"[，、；,\s]", title, maxsplit=1)[0].strip()
            label_source = first_clause or title
        label = compact_text(label_source or f"{DEFAULT_GOVERNANCE_LABEL}{index}", 8)
        cards.append({"label": label, "detail": concise_text(detail or title or label, 40)})
    return cards


def _looks_like_stage_label(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(_ROADMAP_STAGE_PATTERN.match(compact))


def build_roadmap_stages(items: list[str], max_items: int = 5) -> list[dict[str, str]]:
    stages = []
    for index, item in enumerate(items[:max_items], start=1):
        title, detail = split_title_detail(item)
        if _looks_like_stage_label(title):
            period = compact_text(title, 10)
            stage_title = compact_text(detail or title, 16)
            stage_detail = concise_text(detail or item, 28)
        else:
            period = f"阶段{index}"
            stage_title = compact_text(title or f"阶段{index}", 16)
            stage_detail = concise_text(detail or item, 28)
        stages.append({"period": period, "title": stage_title, "detail": stage_detail})
    return stages


def _extract_metric_value(text: str) -> str:
    match = _KPI_VALUE_PATTERN.search(text)
    if match:
        return compact_text(match.group(1).replace(" ", ""), 12)
    return compact_text(text, 12)


def build_kpi_metrics(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    metrics = []
    for index, item in enumerate(items[:max_items], start=1):
        label, detail = split_title_detail(item)
        value = _extract_metric_value(detail or label)
        remainder = (detail or item).replace(value, "", 1).strip(" ：:;，,")
        metrics.append(
            {
                "label": compact_text(label or f"KPI {index}", 14),
                "value": value or "--",
                "detail": concise_text(remainder or detail or item, 22),
            }
        )
    return metrics


def build_dashboard_insights(items: list[str], max_items: int = 3) -> list[str]:
    insights = [concise_text(item, 26) for item in items[:max_items]]
    while len(insights) < max_items:
        insights.append("")
    return insights[:max_items]


def build_risk_items(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    default_quadrants = ("high_high", "low_high", "high_low", "low_low")
    risk_items = []
    for index, item in enumerate(items[:max_items]):
        title, detail = split_title_detail(item)
        risk_items.append(
            {
                "title": compact_text(title or f"风险{index + 1}", 16),
                "detail": concise_text(detail or item, 34),
                "quadrant": default_quadrants[index % len(default_quadrants)],
            }
        )
    return risk_items


def build_claim_items(items: list[str], max_items: int = 4) -> list[dict[str, str]]:
    claim_items = []
    for index, item in enumerate(items[:max_items], start=1):
        label, detail = split_title_detail(item)
        value = _extract_metric_value(detail or label)
        remainder = (detail or item).replace(value, "", 1).strip(" ：:;，,")
        claim_items.append(
            {
                "label": compact_text(label or f"项目{index}", 14),
                "value": value or "--",
                "detail": concise_text(remainder or detail or item, 20),
            }
        )
    return claim_items


def build_generic_page_payload(page: BodyPageSpec, pattern_id: str, payload: InputPayload) -> BodyPagePayload:
    page_items = page.bullets if page.page_key.startswith("slide_") else []
    if pattern_id == "solution_architecture":
        layers = [] if page_items else build_architecture_layers(payload)
        if layers:
            return {"layers": layers, "banner_text": compact_text(page.title, 16)}
        return {}
    if pattern_id == "process_flow":
        return {"steps": build_process_steps(page_items or payload.scenarios or page.bullets)}
    if pattern_id == "roadmap_timeline":
        source_items = page_items or _legacy_html_support.build_phase_detail_bullets(payload) or page.bullets
        return {
            "headline": concise_text(page.subtitle or "按阶段推进关键任务与里程碑", 34),
            "footer": concise_text(payload.footer or page.subtitle or "路线图用于统一预期与执行节奏。", 34),
            "stages": build_roadmap_stages(source_items),
        }
    if pattern_id == "kpi_dashboard":
        source_items = page_items or payload.notes or page.bullets
        insight_source = source_items[4:] or page.bullets or payload.scenarios
        return {
            "headline": concise_text(page.subtitle or "核心指标与阶段表现", 34),
            "footer": concise_text(payload.footer or page.subtitle or "通过统一指标口径追踪经营与执行成效。", 34),
            "metrics": build_kpi_metrics(source_items),
            "insights": build_dashboard_insights(insight_source),
        }
    if pattern_id == "risk_matrix":
        source_items = page_items or payload.notes or payload.scenarios or page.bullets
        return {
            "headline": concise_text(page.subtitle or "从概率与影响两个维度识别优先风险", 34),
            "footer": concise_text(payload.footer or page.subtitle or "高概率高影响事项优先纳入治理闭环。", 34),
            "items": build_risk_items(source_items),
        }
    if pattern_id == "claim_breakdown":
        source_items = page_items or payload.notes or page.bullets
        return {
            "headline": concise_text(page.subtitle or "关键金额项目与构成拆解", 34),
            "footer": concise_text(payload.footer or page.subtitle or "先明确主要金额构成，再讨论优先处置路径。", 34),
            "claims": build_claim_items(source_items),
            "summary": concise_text((payload.footer or page.subtitle or "聚焦金额最大、影响最大的主项。").strip(), 56),
        }
    if pattern_id == "org_governance":
        payload_data: dict[str, object] = {
            "cards": build_governance_cards(page_items or payload.notes or page.bullets),
            "label_prefix": DEFAULT_GOVERNANCE_LABEL,
        }
        if payload.footer and not page_items:
            payload_data["footer_text"] = concise_text(payload.footer, 72)
        return payload_data
    return {}


def resolve_requested_pattern(pattern_id: str, title: str, bullets: list[str]) -> str:
    return pattern_id or infer_pattern(title, bullets)


__all__ = [
    "DEFAULT_GOVERNANCE_LABEL",
    "build_architecture_layers",
    "build_claim_items",
    "build_dashboard_insights",
    "build_generic_page_payload",
    "build_governance_cards",
    "build_kpi_metrics",
    "build_process_steps",
    "build_risk_items",
    "build_roadmap_stages",
    "derive_comparison_cards",
    "resolve_requested_pattern",
]
