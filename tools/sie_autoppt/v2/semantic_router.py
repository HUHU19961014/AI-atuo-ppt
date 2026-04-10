from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticSlideFeatures:
    slide_id: str
    title: str
    intent: str
    subtitle: str | None
    key_message: str | None
    anti_argument: str | None
    data_sources: tuple[dict[str, str], ...]
    statements: tuple[str, ...]
    bullet_blocks: tuple[dict[str, Any], ...]
    timeline_blocks: tuple[dict[str, Any], ...]
    card_blocks: tuple[dict[str, Any], ...]
    stat_blocks: tuple[dict[str, Any], ...]
    matrix_blocks: tuple[dict[str, Any], ...]
    comparison: dict[str, Any] | None
    image: dict[str, Any] | None
    content_items: tuple[str, ...]


@dataclass(frozen=True)
class SemanticLayoutPlan:
    slide_id: str
    layout: str
    reason: str


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def split_evenly(items: list[str]) -> tuple[list[str], list[str]]:
    midpoint = (len(items) + 1) // 2
    return items[:midpoint], items[midpoint:]


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _strip_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _statement_texts(blocks: list[dict[str, Any]]) -> list[str]:
    return [_strip_text(block.get("text")) for block in blocks if block.get("kind") == "statement" and _strip_text(block.get("text"))]


def _bullet_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [block for block in blocks if block.get("kind") == "bullets"]


def _timeline_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [block for block in blocks if block.get("kind") == "timeline"]


def _card_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [block for block in blocks if block.get("kind") == "cards"]


def _stat_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [block for block in blocks if block.get("kind") == "stats"]


def _matrix_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [block for block in blocks if block.get("kind") == "matrix"]


def _comparison_block(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for block in blocks:
        if block.get("kind") == "comparison":
            return block
    return None


def _image_block(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for block in blocks:
        if block.get("kind") == "image":
            return block
    return None


def _flatten_timeline_block(block: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for stage in block["stages"]:
        text = stage["title"]
        if stage.get("detail"):
            text = f"{text}: {stage['detail']}"
        result.append(text)
    return result


def _flatten_card_block(block: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for card in block["cards"]:
        text = card["title"]
        if card.get("body"):
            text = f"{text}: {card['body']}"
        result.append(text)
    return result


def _flatten_stat_block(block: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for metric in block["metrics"]:
        text = f"{metric['label']}: {metric['value']}"
        if metric.get("note"):
            text = f"{text} ({metric['note']})"
        result.append(text)
    return result


def _flatten_matrix_block(block: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for cell in block["cells"]:
        text = cell["title"]
        if cell.get("body"):
            text = f"{text}: {cell['body']}"
        result.append(text)
    return result


def collect_slide_insights(features: SemanticSlideFeatures, limit: int = 4) -> list[str]:
    insights: list[str] = []
    if features.key_message:
        insights.append(features.key_message)
    insights.extend(features.statements)
    for block in features.bullet_blocks:
        insights.extend(block["items"])
    if features.subtitle:
        insights.append(features.subtitle)
    return dedupe_preserve_order(insights)[:limit]


def slide_annotations(features: SemanticSlideFeatures) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if features.anti_argument:
        payload["anti_argument"] = features.anti_argument
    if features.data_sources:
        payload["data_sources"] = list(features.data_sources)
    return payload


def build_slide_features(slide: dict[str, Any]) -> SemanticSlideFeatures:
    blocks = slide["blocks"]
    statements = tuple(_statement_texts(blocks))
    bullet_blocks = tuple(_bullet_blocks(blocks))
    timeline_blocks = tuple(_timeline_blocks(blocks))
    card_blocks = tuple(_card_blocks(blocks))
    stat_blocks = tuple(_stat_blocks(blocks))
    matrix_blocks = tuple(_matrix_blocks(blocks))
    content_items: list[str] = []
    if slide.get("key_message"):
        content_items.append(slide["key_message"])
    content_items.extend(statements)
    for block in bullet_blocks:
        content_items.extend(block["items"])
    for block in timeline_blocks:
        content_items.extend(_flatten_timeline_block(block))
    for block in card_blocks:
        content_items.extend(_flatten_card_block(block))
    for block in stat_blocks:
        content_items.extend(_flatten_stat_block(block))
    for block in matrix_blocks:
        content_items.extend(_flatten_matrix_block(block))
    if slide.get("subtitle") and not content_items:
        content_items.append(slide["subtitle"])
    return SemanticSlideFeatures(
        slide_id=slide["slide_id"],
        title=slide["title"],
        intent=slide["intent"],
        subtitle=slide.get("subtitle"),
        key_message=slide.get("key_message"),
        anti_argument=slide.get("anti_argument"),
        data_sources=tuple(slide.get("data_sources", [])),
        statements=statements,
        bullet_blocks=bullet_blocks,
        timeline_blocks=timeline_blocks,
        card_blocks=card_blocks,
        stat_blocks=stat_blocks,
        matrix_blocks=matrix_blocks,
        comparison=_comparison_block(blocks),
        image=_image_block(blocks),
        content_items=tuple(item for item in content_items if item),
    )


def plan_semantic_slide_layout(slide: dict[str, Any]) -> SemanticLayoutPlan:
    features = build_slide_features(slide)

    if features.intent in {"cover", "section"}:
        return SemanticLayoutPlan(features.slide_id, "section_break", "section-intent")

    candidates: list[tuple[int, str, str]] = []
    if features.comparison:
        candidates.append((100, "two_columns", "comparison-block"))
    if features.image:
        candidates.append((90, "title_image", "image-block"))
    if features.intent in {"summary", "conclusion"} and not features.bullet_blocks and len(features.statements) <= 1:
        candidates.append((85, "title_only", "single-conclusion-statement"))
    if len(features.matrix_blocks) == 1:
        candidates.append((84, "matrix_grid", "matrix-block"))
    if len(features.stat_blocks) == 1 and len(features.stat_blocks[0]["metrics"]) >= 3:
        candidates.append((83, "stats_dashboard", "stats-block"))
    if len(features.card_blocks) == 1 and len(features.card_blocks[0]["cards"]) >= 3 and not features.bullet_blocks:
        candidates.append((82, "cards_grid", "cards-grid"))
    if len(features.timeline_blocks) == 1:
        candidates.append((81, "timeline", "timeline-block"))
    if len(features.card_blocks) == 1 and len(features.card_blocks[0]["cards"]) == 2 and not features.bullet_blocks:
        candidates.append((80, "two_columns", "cards-pair"))
    if len(features.stat_blocks) == 1 and len(features.stat_blocks[0]["metrics"]) == 2 and not features.bullet_blocks:
        candidates.append((79, "two_columns", "stats-pair"))
    if len(features.bullet_blocks) >= 2:
        candidates.append((78, "two_columns", "multi-block-bullets"))
    if len(features.content_items) > 6:
        candidates.append((70, "two_columns", "dense-content"))
    if features.content_items:
        candidates.append((60, "title_content", "default-content"))
    else:
        candidates.append((50, "title_content", "fallback-content"))

    _, layout, reason = max(candidates, key=lambda item: item[0])
    return SemanticLayoutPlan(features.slide_id, layout, reason)
