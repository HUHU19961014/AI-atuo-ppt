from __future__ import annotations

from typing import Any

from .schema import ValidatedDeck, validate_deck_payload
from .semantic_router import (
    SemanticLayoutPlan,
    build_slide_features,
    collect_slide_insights,
    plan_semantic_slide_layout,
    slide_annotations,
    split_evenly,
)
from .semantic_schema_builder import SUPPORTED_SLIDE_INTENTS


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _strip_text(item)
        if text:
            result.append(text)
    return result


def _normalize_timeline_stages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _strip_text(item.get("title"))
        detail = _strip_text(item.get("detail"))
        if title:
            result.append({"title": title, **({"detail": detail} if detail else {})})
    return result


def _normalize_cards(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _strip_text(item.get("title"))
        body = _strip_text(item.get("body"))
        if title:
            result.append({"title": title, **({"body": body} if body else {})})
    return result


def _normalize_metrics(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _strip_text(item.get("label"))
        metric_value = _strip_text(item.get("value"))
        note = _strip_text(item.get("note"))
        if label and metric_value:
            result.append({"label": label, "value": metric_value, **({"note": note} if note else {})})
    return result


def _normalize_matrix_cells(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _strip_text(item.get("title"))
        body = _strip_text(item.get("body"))
        if title:
            result.append({"title": title, **({"body": body} if body else {})})
    return result


def _normalize_data_sources(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        claim = _strip_text(item.get("claim"))
        source = _strip_text(item.get("source"))
        confidence = _strip_text(item.get("confidence")).lower() or "medium"
        if not claim or not source:
            continue
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        result.append({"claim": claim, "source": source, "confidence": confidence})
    return result


def normalize_semantic_payload(
    payload: dict[str, Any],
    *,
    default_title: str,
    default_theme: str,
    default_language: str,
    default_author: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("semantic deck payload must be a JSON object.")

    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    normalized_meta = {
        "title": _strip_text(meta.get("title")) or default_title,
        "theme": _strip_text(meta.get("theme")) or default_theme,
        "language": _strip_text(meta.get("language")) or default_language,
        "author": _strip_text(meta.get("author")) or default_author,
        "version": _strip_text(meta.get("version")) or "2.0",
    }

    raw_slides = payload.get("slides", [])
    if not isinstance(raw_slides, list):
        raise ValueError("slides must be a list.")

    normalized_slides: list[dict[str, Any]] = []
    for index, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            raise ValueError(f"slide {index} must be an object.")
        slide_id = _strip_text(raw_slide.get("slide_id")) or f"s{index}"
        title = _strip_text(raw_slide.get("title"))
        intent = _strip_text(raw_slide.get("intent"))
        subtitle = _strip_text(raw_slide.get("subtitle")) or None
        key_message = _strip_text(raw_slide.get("key_message")) or None
        anti_argument = _strip_text(raw_slide.get("anti_argument")) or None
        data_sources = _normalize_data_sources(raw_slide.get("data_sources"))
        raw_blocks = raw_slide.get("blocks", [])
        if not isinstance(raw_blocks, list):
            raise ValueError(f"slide {slide_id} blocks must be a list.")

        blocks: list[dict[str, Any]] = []
        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                raise ValueError(f"slide {slide_id} contains a non-object block.")
            kind = _strip_text(raw_block.get("kind"))
            if kind == "bullets":
                items = _string_list(raw_block.get("items"))
                if not items:
                    raise ValueError(f"slide {slide_id} bullets block must include items.")
                blocks.append({"kind": "bullets", "heading": _strip_text(raw_block.get("heading")) or None, "items": items})
            elif kind == "comparison":
                left_items = _string_list(raw_block.get("left_items"))
                right_items = _string_list(raw_block.get("right_items"))
                if not left_items or not right_items:
                    raise ValueError(f"slide {slide_id} comparison block must include both columns.")
                blocks.append(
                    {
                        "kind": "comparison",
                        "left_heading": _strip_text(raw_block.get("left_heading")),
                        "left_items": left_items,
                        "right_heading": _strip_text(raw_block.get("right_heading")),
                        "right_items": right_items,
                    }
                )
            elif kind == "image":
                mode = _strip_text(raw_block.get("mode")) or "placeholder"
                blocks.append(
                    {
                        "kind": "image",
                        "mode": mode,
                        "caption": _strip_text(raw_block.get("caption")) or None,
                        "path": _strip_text(raw_block.get("path")) or None,
                    }
                )
            elif kind == "statement":
                text = _strip_text(raw_block.get("text"))
                if not text:
                    raise ValueError(f"slide {slide_id} statement block must include text.")
                blocks.append({"kind": "statement", "text": text})
            elif kind == "timeline":
                stages = _normalize_timeline_stages(raw_block.get("stages"))
                if len(stages) < 2:
                    raise ValueError(f"slide {slide_id} timeline block must include at least 2 stages.")
                blocks.append({"kind": "timeline", "heading": _strip_text(raw_block.get("heading")) or None, "stages": stages})
            elif kind == "cards":
                cards = _normalize_cards(raw_block.get("cards"))
                if len(cards) < 2:
                    raise ValueError(f"slide {slide_id} cards block must include at least 2 cards.")
                blocks.append({"kind": "cards", "heading": _strip_text(raw_block.get("heading")) or None, "cards": cards})
            elif kind == "stats":
                metrics = _normalize_metrics(raw_block.get("metrics"))
                if len(metrics) < 2:
                    raise ValueError(f"slide {slide_id} stats block must include at least 2 metrics.")
                blocks.append({"kind": "stats", "heading": _strip_text(raw_block.get("heading")) or None, "metrics": metrics})
            elif kind == "matrix":
                cells = _normalize_matrix_cells(raw_block.get("cells"))
                if len(cells) < 2:
                    raise ValueError(f"slide {slide_id} matrix block must include at least 2 cells.")
                blocks.append(
                    {
                        "kind": "matrix",
                        "heading": _strip_text(raw_block.get("heading")) or None,
                        "x_axis": _strip_text(raw_block.get("x_axis")) or None,
                        "y_axis": _strip_text(raw_block.get("y_axis")) or None,
                        "cells": cells,
                    }
                )
            else:
                raise ValueError(f"slide {slide_id} has unsupported block kind: {kind}")

        normalized_slides.append(
            {
                "slide_id": slide_id,
                "title": title,
                "intent": intent,
                "subtitle": subtitle,
                "key_message": key_message,
                "anti_argument": anti_argument,
                "data_sources": data_sources,
                "blocks": blocks,
            }
        )

    return {"meta": normalized_meta, "slides": normalized_slides}


def diversify_layout_plan(
    plan: SemanticLayoutPlan,
    features,
    *,
    previous_layout: str | None = None,
) -> SemanticLayoutPlan:
    if previous_layout != plan.layout:
        return plan
    if plan.layout == "title_content" and len(features.content_items) >= 4:
        return SemanticLayoutPlan(features.slide_id, "two_columns", "diversity:title_content-to-two_columns")
    if plan.layout == "two_columns" and plan.reason == "dense-content":
        return SemanticLayoutPlan(features.slide_id, "title_content", "diversity:two_columns-to-title_content")
    return plan


def compile_semantic_slide(slide: dict[str, Any], *, previous_layout: str | None = None) -> dict[str, Any]:
    features = build_slide_features(slide)
    plan = diversify_layout_plan(plan_semantic_slide_layout(slide), features, previous_layout=previous_layout)

    if plan.layout == "section_break":
        payload = {"slide_id": features.slide_id, "layout": "section_break", "title": features.title, **slide_annotations(features)}
        if features.subtitle or features.key_message:
            payload["subtitle"] = features.subtitle or features.key_message
        return payload

    if plan.layout == "two_columns" and features.comparison:
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": features.comparison["left_heading"], "items": features.comparison["left_items"]},
            "right": {"heading": features.comparison["right_heading"], "items": features.comparison["right_items"]},
        }

    if plan.layout == "title_image" and features.image:
        content = list(features.content_items)[:8]
        if not content:
            content = [features.subtitle or features.title]
        return {
            "slide_id": features.slide_id,
            "layout": "title_image",
            "title": features.title,
            **slide_annotations(features),
            "content": content,
            "image": {
                "mode": features.image.get("mode", "placeholder"),
                **({"caption": features.image["caption"]} if features.image.get("caption") else {}),
                **({"path": features.image["path"]} if features.image.get("path") else {}),
            },
        }

    if plan.layout == "title_only":
        return {
            "slide_id": features.slide_id,
            "layout": "title_only",
            "title": features.statements[0] if features.statements else (features.key_message or features.title),
            **slide_annotations(features),
        }

    if plan.layout == "timeline" and len(features.timeline_blocks) == 1:
        block = features.timeline_blocks[0]
        return {
            "slide_id": features.slide_id,
            "layout": "timeline",
            "title": features.title,
            **slide_annotations(features),
            "heading": block.get("heading") or features.key_message or features.subtitle,
            "stages": block["stages"],
        }

    if plan.layout == "stats_dashboard" and len(features.stat_blocks) == 1:
        block = features.stat_blocks[0]
        return {
            "slide_id": features.slide_id,
            "layout": "stats_dashboard",
            "title": features.title,
            **slide_annotations(features),
            "heading": block.get("heading") or features.key_message or features.subtitle,
            "metrics": block["metrics"],
            "insights": collect_slide_insights(features, limit=4),
        }

    if plan.layout == "matrix_grid" and len(features.matrix_blocks) == 1:
        block = features.matrix_blocks[0]
        return {
            "slide_id": features.slide_id,
            "layout": "matrix_grid",
            "title": features.title,
            **slide_annotations(features),
            "heading": block.get("heading") or features.key_message or features.subtitle,
            "x_axis": block.get("x_axis"),
            "y_axis": block.get("y_axis"),
            "cells": block["cells"],
        }

    if plan.layout == "cards_grid" and len(features.card_blocks) == 1:
        block = features.card_blocks[0]
        return {
            "slide_id": features.slide_id,
            "layout": "cards_grid",
            "title": features.title,
            **slide_annotations(features),
            "heading": block.get("heading") or features.key_message or features.subtitle,
            "cards": block["cards"],
        }

    if plan.layout == "two_columns" and len(features.card_blocks) == 1 and len(features.card_blocks[0]["cards"]) == 2:
        left_card, right_card = features.card_blocks[0]["cards"]
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": left_card["title"], "items": [left_card.get("body") or left_card["title"]]},
            "right": {"heading": right_card["title"], "items": [right_card.get("body") or right_card["title"]]},
        }

    if plan.layout == "two_columns" and len(features.stat_blocks) == 1 and len(features.stat_blocks[0]["metrics"]) == 2:
        left_metric, right_metric = features.stat_blocks[0]["metrics"]
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": left_metric["label"], "items": [left_metric["value"]] + ([left_metric["note"]] if left_metric.get("note") else [])},
            "right": {"heading": right_metric["label"], "items": [right_metric["value"]] + ([right_metric["note"]] if right_metric.get("note") else [])},
        }

    if plan.layout == "two_columns" and len(features.matrix_blocks) == 1:
        cells = features.matrix_blocks[0]["cells"]
        left_cells, right_cells = split_evenly(cells)

        def _cell_items(group: list[dict[str, str]]) -> list[str]:
            items: list[str] = []
            for cell in group:
                items.append(cell["title"])
                if cell.get("body"):
                    items.append(cell["body"])
            return items[:6]

        x_axis = features.matrix_blocks[0].get("x_axis")
        y_axis = features.matrix_blocks[0].get("y_axis")
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": x_axis or features.matrix_blocks[0].get("heading") or "Matrix Left", "items": _cell_items(left_cells)},
            "right": {"heading": y_axis or "Matrix Right", "items": _cell_items(right_cells or left_cells)},
        }

    if plan.layout == "two_columns" and len(features.bullet_blocks) >= 2:
        left_block = features.bullet_blocks[0]
        right_block = features.bullet_blocks[1]
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": left_block.get("heading") or "核心要点", "items": left_block["items"][:6]},
            "right": {"heading": right_block.get("heading") or "补充说明", "items": right_block["items"][:6]},
        }

    content_items = list(features.content_items)
    if plan.layout == "two_columns" and content_items:
        left_items, right_items = split_evenly(content_items)
        heading = features.bullet_blocks[0].get("heading") if features.bullet_blocks else ""
        return {
            "slide_id": features.slide_id,
            "layout": "two_columns",
            "title": features.title,
            **slide_annotations(features),
            "left": {"heading": heading or "核心要点", "items": left_items[:6]},
            "right": {"heading": "进一步展开", "items": right_items[:6] or [features.subtitle or features.title]},
        }

    if not content_items:
        content_items = [features.subtitle or features.title]

    return {
        "slide_id": features.slide_id,
        "layout": "title_content",
        "title": features.title,
        **slide_annotations(features),
        "content": content_items[:10],
    }


def compile_semantic_deck_payload(
    payload: dict[str, Any],
    *,
    default_title: str = "AI Auto PPT",
    default_theme: str = "business_red",
    default_language: str = "zh-CN",
    default_author: str = "AI Auto PPT",
) -> ValidatedDeck:
    normalized = normalize_semantic_payload(
        payload,
        default_title=default_title,
        default_theme=default_theme,
        default_language=default_language,
        default_author=default_author,
    )
    slides = normalized["slides"]
    for slide in slides:
        if slide["intent"] not in SUPPORTED_SLIDE_INTENTS:
            raise ValueError(f"unsupported slide intent: {slide['intent']}")
        if not slide["title"]:
            raise ValueError(f"slide {slide['slide_id']} title cannot be empty.")

    compiled_slides: list[dict[str, Any]] = []
    previous_layout: str | None = None
    for slide in slides:
        compiled_slide = compile_semantic_slide(slide, previous_layout=previous_layout)
        compiled_slides.append(compiled_slide)
        previous_layout = str(compiled_slide.get("layout", ""))

    compiled = {"meta": normalized["meta"], "slides": compiled_slides}
    return validate_deck_payload(
        compiled,
        default_title=default_title,
        default_theme=default_theme,
        default_language=default_language,
        default_author=default_author,
    )
