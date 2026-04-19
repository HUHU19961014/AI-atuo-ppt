from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ..clarifier import DEFAULT_AUDIENCE_HINT
from ..v2.services import (
    DeckGenerationRequest,
    OutlineGenerationRequest,
    generate_outline_with_ai,
    generate_semantic_deck_with_ai,
    generate_semantic_decks_with_ai_batch,
    select_best_semantic_candidate,
)
from .contracts import ContentBundle, InputEnvelope
from .hashing import sha256_text


def compute_content_bundle_hash(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "bundle_hash"}
    return sha256_text(json.dumps(normalized, ensure_ascii=False, sort_keys=True))


def build_content_bundle(
    *,
    run_id: str = "standalone",
    topic: str,
    brief: str,
    audience: str,
    language: str,
    theme: str,
    model: str | None,
    chapters: int | None = None,
    min_slides: int | None = None,
    max_slides: int | None = None,
    clarify_result: dict[str, Any] | None = None,
    input_envelope: dict[str, Any] | None = None,
    semantic_candidate_count: int = 1,
) -> dict[str, Any]:
    normalized_audience = audience or DEFAULT_AUDIENCE_HINT
    resolved_min_slides = min_slides if min_slides is not None else 6
    resolved_max_slides = max_slides if max_slides is not None else 10
    outline = generate_outline_with_ai(
        OutlineGenerationRequest(
            topic=topic,
            brief=brief,
            audience=normalized_audience,
            language=language,
            theme=theme,
            exact_slides=chapters,
            min_slides=resolved_min_slides,
            max_slides=resolved_max_slides,
        ),
        model=model,
    )

    source_index, images = _derive_sources_from_input(
        topic=topic,
        brief=brief,
        input_envelope=input_envelope,
    )
    source_refs = [entry["source_ref"] for entry in source_index] or ["src-topic"]

    deck_request = DeckGenerationRequest(
        topic=topic,
        outline=outline,
        brief=brief,
        audience=normalized_audience,
        language=language,
        theme=theme,
    )
    semantic_candidates = _generate_semantic_candidates(
        request=deck_request,
        model=model,
        candidate_count=semantic_candidate_count,
    )
    semantic_payload, _selected_candidate_index, _score_report = select_best_semantic_candidate(
        semantic_candidates,
        request=deck_request,
    )

    semantic_slides = semantic_payload.get("slides", [])
    story_outline: list[dict[str, Any]] = []
    for index, page in enumerate(outline.to_list()):
        semantic_slide = semantic_slides[index] if index < len(semantic_slides) else {}
        if not isinstance(semantic_slide, dict):
            semantic_slide = {}
        story_outline.append(
            {
                "slide_ref": semantic_slide.get("slide_id") or f"s-{page['page_no']:03d}",
                "intent": semantic_slide.get("intent") or semantic_slide.get("layout") or "content",
                "title": page["title"],
                "goal": page["goal"],
                "source_refs": source_refs,
                "argument_refs": _extract_story_argument_refs(
                    semantic_slide=semantic_slide,
                    slide_ref=semantic_slide.get("slide_id") or f"s-{page['page_no']:03d}",
                    goal=page["goal"],
                    source_refs=source_refs,
                ),
            }
        )

    bundle_payload = {
        "run_id": run_id,
        "bundle_version": 1,
        "topic": topic,
        "audience": normalized_audience,
        "language": language,
        "theme": theme,
        "source_index": source_index,
        "text_summary": {
            "summary": brief or topic,
            "key_points": [topic],
            "source_refs": source_refs,
        },
        "images": images,
        "story_plan": {
            "outline": story_outline,
        },
        "clarify_result": dict(clarify_result) if isinstance(clarify_result, dict) else None,
        "semantic_payload": semantic_payload,
    }
    bundle_payload["bundle_hash"] = compute_content_bundle_hash(bundle_payload)
    return ContentBundle.model_validate(bundle_payload).model_dump(mode="json")


def _generate_semantic_candidates(
    *,
    request: DeckGenerationRequest,
    model: str | None,
    candidate_count: int,
) -> list[dict[str, Any]]:
    requested_count = max(1, int(candidate_count))
    try:
        return asyncio.run(
            generate_semantic_decks_with_ai_batch(
                [request for _ in range(requested_count)],
                model=model,
                concurrency=min(requested_count, 4),
            )
        )
    except RuntimeError:
        pass

    return [
        generate_semantic_deck_with_ai(
            request,
            model=model,
        )
        for _ in range(requested_count)
    ]


def _normalize_argument_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _extract_block_arguments(block: dict[str, Any]) -> list[str]:
    kind = str(block.get("kind") or "").strip().lower()
    arguments: list[str] = []
    if kind == "statement":
        arguments.append(_normalize_argument_text(block.get("text")))
    elif kind == "bullets":
        for item in block.get("items", []):
            normalized_item = _normalize_argument_text(item)
            if normalized_item:
                arguments.append(normalized_item)
    elif kind == "comparison":
        arguments.extend(
            _normalize_argument_text(item)
            for item in [*(block.get("left_items") or []), *(block.get("right_items") or [])]
            if _normalize_argument_text(item)
        )
    elif kind == "timeline":
        for stage in block.get("stages", []):
            if not isinstance(stage, dict):
                continue
            title = _normalize_argument_text(stage.get("title"))
            detail = _normalize_argument_text(stage.get("detail"))
            arguments.append(f"{title}: {detail}".strip(": ").strip())
    elif kind == "cards":
        for card in block.get("cards", []):
            if not isinstance(card, dict):
                continue
            title = _normalize_argument_text(card.get("title"))
            body = _normalize_argument_text(card.get("body"))
            arguments.append(f"{title}: {body}".strip(": ").strip())
    elif kind == "stats":
        for metric in block.get("metrics", []):
            if not isinstance(metric, dict):
                continue
            label = _normalize_argument_text(metric.get("label"))
            value = _normalize_argument_text(metric.get("value"))
            note = _normalize_argument_text(metric.get("note"))
            arguments.append(f"{label}: {value}".strip(": ").strip())
            if note:
                arguments.append(note)
    elif kind == "matrix":
        for cell in block.get("cells", []):
            if not isinstance(cell, dict):
                continue
            title = _normalize_argument_text(cell.get("title"))
            body = _normalize_argument_text(cell.get("body"))
            arguments.append(f"{title}: {body}".strip(": ").strip())
    elif kind == "image":
        caption = _normalize_argument_text(block.get("caption"))
        if caption:
            arguments.append(caption)

    return [item for item in arguments if item]


def _extract_story_argument_refs(
    *,
    semantic_slide: dict[str, Any],
    slide_ref: str,
    goal: str,
    source_refs: list[str],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen_arguments: set[str] = set()

    goal_text = _normalize_argument_text(goal)
    if goal_text:
        refs.append({"argument": goal_text, "source_refs": list(source_refs), "block_ref": f"{slide_ref}#goal"})
        seen_arguments.add(goal_text.lower())

    data_sources = semantic_slide.get("data_sources")
    if isinstance(data_sources, list):
        for source_index, source in enumerate(data_sources, start=1):
            if not isinstance(source, dict):
                continue
            claim = _normalize_argument_text(source.get("claim"))
            if not claim:
                continue
            lowered = claim.lower()
            if lowered in seen_arguments:
                continue
            refs.append(
                {
                    "argument": claim,
                    "source_refs": list(source_refs),
                    "block_ref": f"{slide_ref}#src{source_index}",
                }
            )
            seen_arguments.add(lowered)

    blocks = semantic_slide.get("blocks")
    if isinstance(blocks, list):
        for block_index, block in enumerate(blocks, start=1):
            if not isinstance(block, dict):
                continue
            for argument in _extract_block_arguments(block):
                lowered = argument.lower()
                if lowered in seen_arguments:
                    continue
                refs.append(
                    {
                        "argument": argument,
                        "source_refs": list(source_refs),
                        "block_ref": f"{slide_ref}#b{block_index}",
                    }
                )
                seen_arguments.add(lowered)

    return refs


def load_content_bundle_artifact(*, path, run_id: str | None = None) -> dict[str, Any]:
    raw_payload = json.loads(Path(path).read_text(encoding="utf-8"))
    bundle_payload = ContentBundle.model_validate(raw_payload).model_dump(mode="json")
    if run_id and bundle_payload["run_id"] != run_id:
        bundle_payload["run_id"] = run_id
    bundle_payload["bundle_hash"] = compute_content_bundle_hash(bundle_payload)
    return ContentBundle.model_validate(bundle_payload).model_dump(mode="json")


def _derive_sources_from_input(
    *,
    topic: str,
    brief: str,
    input_envelope: dict[str, Any] | None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if input_envelope is None:
        source_text = "\n".join(part for part in (topic.strip(), brief.strip()) if part).strip() or topic
        source_hash = sha256_text(source_text)
        return (
            [
                {
                    "source_ref": "src-topic",
                    "type": "text",
                    "content_hash": source_hash,
                }
            ],
            [],
        )

    envelope = InputEnvelope.model_validate(input_envelope)
    source_index = [
        {
            "source_ref": source.source_ref,
            "type": source.type,
            "content_hash": source.content_hash,
        }
        for source in envelope.inputs
    ]
    if not source_index:
        source_text = "\n".join(part for part in (topic.strip(), brief.strip()) if part).strip() or topic
        source_index = [
            {
                "source_ref": "src-topic",
                "type": "text",
                "content_hash": sha256_text(source_text),
            }
        ]

    images: list[dict[str, Any]] = []
    image_index = 1
    for source in envelope.inputs:
        if source.type != "image":
            continue
        images.append(
            {
                "image_ref": f"img-{image_index:03d}",
                "content_hash": source.content_hash,
                "ocr_text": "",
                "description": "",
                "source_refs": [source.source_ref],
            }
        )
        image_index += 1
    return source_index, images
