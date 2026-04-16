from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .exceptions import AiHealthcheckBlockedError, AiHealthcheckFailedError
from .v2.services import DeckGenerationRequest, OutlineGenerationRequest


@dataclass(frozen=True)
class V2CommandContext:
    resolved_topic: str
    resolved_brief: str
    resolved_audience: str
    resolved_chapters: int | None
    resolved_min_slides: int | None
    resolved_max_slides: int | None
    v2_theme: str
    v2_output_dir: Path
    brief_text: str
    emit_progress: Callable[[bool, str, str], None]
    default_outline_output_path: Callable[[Path], Path]
    default_semantic_output_path: Callable[[Path], Path]
    default_deck_output_path: Callable[[Path], Path]
    default_log_output_path: Callable[[Path], Path]
    default_ppt_output_path: Callable[[Path], Path]
    load_outline_document: Callable[[Path], Any]
    write_outline_document: Callable[[Any, Path], Path]
    write_semantic_document: Callable[[dict[str, Any], Path], Path]
    write_deck_document: Callable[[Any, Path], Path]
    load_deck_document: Callable[[Path], Any]
    compile_semantic_deck_payload: Callable[..., Any]
    generate_outline_with_ai: Callable[..., Any]
    generate_semantic_deck_with_ai: Callable[..., dict[str, Any]]
    generate_semantic_decks_with_ai_batch: Callable[..., Any] | None
    ensure_generation_context: Callable[..., Any]
    make_v2_ppt: Callable[..., Any]
    generate_v2_ppt: Callable[..., Any]
    apply_patch_set: Callable[[Any, dict[str, Any]], Any]
    review_deck_once: Callable[..., Any]
    iterate_visual_review: Callable[..., Any]
    run_ai_healthcheck: Callable[..., Any]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def handle_v2_and_health_command(
    *,
    effective_command: str,
    args: Any,
    parser: Any,
    context: V2CommandContext,
) -> bool:
    resolved_topic = context.resolved_topic
    resolved_brief = context.resolved_brief
    resolved_audience = context.resolved_audience
    resolved_chapters = context.resolved_chapters
    resolved_min_slides = context.resolved_min_slides
    resolved_max_slides = context.resolved_max_slides
    v2_theme = context.v2_theme
    v2_output_dir = context.v2_output_dir
    brief_text = context.brief_text
    emit_progress = context.emit_progress
    default_outline_output_path = context.default_outline_output_path
    default_semantic_output_path = context.default_semantic_output_path
    default_deck_output_path = context.default_deck_output_path
    default_log_output_path = context.default_log_output_path
    default_ppt_output_path = context.default_ppt_output_path
    load_outline_document = context.load_outline_document
    write_outline_document = context.write_outline_document
    write_semantic_document = context.write_semantic_document
    write_deck_document = context.write_deck_document
    load_deck_document = context.load_deck_document
    compile_semantic_deck_payload = context.compile_semantic_deck_payload
    generate_outline_with_ai = context.generate_outline_with_ai
    generate_semantic_deck_with_ai = context.generate_semantic_deck_with_ai
    generate_semantic_decks_with_ai_batch = context.generate_semantic_decks_with_ai_batch
    ensure_generation_context = context.ensure_generation_context
    make_v2_ppt = context.make_v2_ppt
    generate_v2_ppt = context.generate_v2_ppt
    apply_patch_set = context.apply_patch_set
    review_deck_once = context.review_deck_once
    iterate_visual_review = context.iterate_visual_review
    run_ai_healthcheck = context.run_ai_healthcheck
    if effective_command == "v2-outline":
        if not resolved_topic:
            parser.error("--topic is required when command is 'v2-outline'.")
        emit_progress(args.progress, "v2-outline", "calling AI outline planner")
        outline = generate_outline_with_ai(
            OutlineGenerationRequest(
                topic=resolved_topic,
                brief=resolved_brief,
                audience=resolved_audience,
                language=args.language,
                theme=v2_theme,
                exact_slides=resolved_chapters or None,
                min_slides=resolved_min_slides or 6,
                max_slides=resolved_max_slides or 10,
                generation_mode=args.generation_mode,
            ),
            model=args.llm_model or None,
        )
        outline_output = Path(args.outline_output) if args.outline_output else default_outline_output_path(v2_output_dir)
        write_outline_document(outline, outline_output)
        print(str(outline_output))
        return True

    if effective_command == "v2-plan":
        if not resolved_topic and not args.outline_json:
            parser.error("--topic or --outline-json is required when command is 'v2-plan'.")
        shared_context = None
        shared_strategy = None
        plan_outline_output: Path | None = None
        if args.outline_json:
            emit_progress(args.progress, "v2-plan", "loading outline json")
            outline = load_outline_document(Path(args.outline_json))
        else:
            emit_progress(args.progress, "v2-plan", "building strategy context")
            shared_context, shared_strategy = ensure_generation_context(
                topic=resolved_topic,
                brief=resolved_brief,
                audience=resolved_audience,
                language=args.language,
                generation_mode=args.generation_mode,
                structured_context=None,
                strategic_analysis=None,
                model=args.llm_model or None,
            )
            emit_progress(args.progress, "v2-plan", "calling AI outline planner")
            outline = generate_outline_with_ai(
                OutlineGenerationRequest(
                    topic=resolved_topic,
                    brief=resolved_brief,
                    audience=resolved_audience,
                    language=args.language,
                    theme=v2_theme,
                    exact_slides=resolved_chapters or None,
                    min_slides=resolved_min_slides or 6,
                    max_slides=resolved_max_slides or 10,
                    generation_mode=args.generation_mode,
                    structured_context=shared_context,
                    strategic_analysis=shared_strategy,
                ),
                model=args.llm_model or None,
            )
            plan_outline_output = Path(args.outline_output) if args.outline_output else default_outline_output_path(v2_output_dir)
            write_outline_document(outline, plan_outline_output)
        deck_request = DeckGenerationRequest(
            topic=resolved_topic or "AI Auto PPT",
            outline=outline,
            brief=resolved_brief,
            audience=resolved_audience,
            language=args.language,
            theme=v2_theme,
            author=args.author,
            generation_mode=args.generation_mode,
            structured_context=shared_context,
            strategic_analysis=shared_strategy,
        )
        semantic_candidates: list[dict[str, Any]] = []
        requested_batch_size = max(1, int(getattr(args, "batch_size", 1)))
        if requested_batch_size > 1 and generate_semantic_decks_with_ai_batch is not None:
            emit_progress(
                args.progress,
                "v2-plan",
                f"calling AI semantic deck planner in batch mode (size={requested_batch_size})",
            )
            semantic_candidates = asyncio.run(
                generate_semantic_decks_with_ai_batch(
                    [deck_request for _ in range(requested_batch_size)],
                    model=args.llm_model or None,
                    concurrency=min(requested_batch_size, 4),
                )
            )
        if not semantic_candidates:
            emit_progress(args.progress, "v2-plan", "calling AI semantic deck planner")
            semantic_candidates = [
                generate_semantic_deck_with_ai(
                    deck_request,
                    model=args.llm_model or None,
                )
            ]
        semantic_payload = semantic_candidates[0]
        emit_progress(args.progress, "v2-plan", "compiling semantic payload")
        validated_deck = compile_semantic_deck_payload(
            semantic_payload,
            default_title=resolved_topic or "AI Auto PPT",
            default_theme=v2_theme,
            default_language=args.language,
            default_author=args.author,
        )
        semantic_output = Path(args.semantic_output) if args.semantic_output else default_semantic_output_path(v2_output_dir)
        write_semantic_document(semantic_payload, semantic_output)
        if len(semantic_candidates) > 1:
            for index, candidate_payload in enumerate(semantic_candidates[1:], start=2):
                candidate_path = semantic_output.with_name(f"{semantic_output.stem}.candidate_{index}{semantic_output.suffix}")
                write_semantic_document(candidate_payload, candidate_path)
        deck_output = Path(args.plan_output) if args.plan_output else default_deck_output_path(v2_output_dir)
        write_deck_document(validated_deck.deck, deck_output)
        if plan_outline_output is not None:
            print(str(plan_outline_output))
        print(str(semantic_output))
        if len(semantic_candidates) > 1:
            for index in range(2, len(semantic_candidates) + 1):
                candidate_path = semantic_output.with_name(f"{semantic_output.stem}.candidate_{index}{semantic_output.suffix}")
                print(str(candidate_path))
        print(str(deck_output))
        return True

    if effective_command == "v2-compile":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-compile'.")
        deck = load_deck_document(Path(args.deck_json))
        deck_output = Path(args.plan_output) if args.plan_output else default_deck_output_path(v2_output_dir)
        write_deck_document(deck, deck_output)
        print(str(deck_output))
        return True

    if effective_command == "v2-patch":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-patch'.")
        if not args.patch_json:
            parser.error("--patch-json is required when command is 'v2-patch'.")
        emit_progress(args.progress, "v2-patch", "loading deck and patch documents")
        deck = load_deck_document(Path(args.deck_json))
        patch_payload = json.loads(Path(args.patch_json).read_text(encoding="utf-8-sig"))
        if not isinstance(patch_payload, dict):
            parser.exit(status=2, message="invalid v2-patch payload: top-level JSON must be an object.\n")
        try:
            patched_deck = apply_patch_set(deck, patch_payload)
        except ValueError as exc:
            parser.exit(status=2, message=f"invalid v2-patch payload: {exc}\n")
        patch_output = Path(args.plan_output) if args.plan_output else default_deck_output_path(v2_output_dir)
        write_deck_document(patched_deck, patch_output)
        print(str(patch_output))
        return True

    if effective_command == "v2-render":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-render'.")
        log_output = Path(args.log_output) if args.log_output else default_log_output_path(v2_output_dir)
        ppt_output = Path(args.ppt_output) if args.ppt_output else default_ppt_output_path(v2_output_dir)
        deck_path = Path(args.deck_json)
        deck = load_deck_document(deck_path)
        emit_progress(args.progress, "v2-render", "running AI review gate before rendering")
        try:
            ai_review_output_dir = v2_output_dir / "ai_render_gate"
            ai_review_result = review_deck_once(
                deck_path=deck_path,
                output_dir=ai_review_output_dir,
                model=args.llm_model or None,
                theme_name=args.theme.strip() or None,
            )
            reviewed_deck = load_deck_document(ai_review_result.deck_path)
            patch_set = json.loads(ai_review_result.patch_path.read_text(encoding="utf-8-sig"))
            if isinstance(patch_set, dict) and patch_set.get("patches"):
                emit_progress(args.progress, "v2-render", "applying AI-generated blocker patches")
                deck = apply_patch_set(reviewed_deck, patch_set)
                write_deck_document(deck, ai_review_output_dir / "ai_render_gate.patched.deck.json")
            else:
                deck = reviewed_deck
        except Exception as exc:
            parser.exit(
                status=1,
                message=(
                    "AI is mandatory for 'v2-render'. "
                    f"AI review/patch gate failed: {exc}\n"
                ),
            )
        emit_progress(args.progress, "v2-render", "rendering ppt from AI-gated deck json")
        render_result = generate_v2_ppt(
            deck,
            output_path=ppt_output,
            theme_name=args.theme.strip() or None,
            log_path=log_output,
        )
        print(str(render_result.rewrite_log_path))
        print(str(render_result.warnings_path))
        print(str(log_output))
        print(str(render_result.output_path))
        return True

    if effective_command == "v2-make":
        if not resolved_topic and not args.outline_json:
            parser.error("--topic or --outline-json is required when command is 'v2-make'.")
        emit_progress(args.progress, "v2-make", "running full v2 generation pipeline")
        outline_output = (
            Path(args.outline_output)
            if args.outline_output
            else (default_outline_output_path(v2_output_dir) if args.full_pipeline else None)
        )
        semantic_output = (
            Path(args.semantic_output)
            if args.semantic_output
            else (default_semantic_output_path(v2_output_dir) if args.full_pipeline else None)
        )
        deck_output = (
            Path(args.plan_output)
            if args.plan_output
            else (default_deck_output_path(v2_output_dir) if args.full_pipeline else None)
        )
        log_output = (
            Path(args.log_output)
            if args.log_output
            else (default_log_output_path(v2_output_dir) if args.full_pipeline else None)
        )
        ppt_output = (
            Path(args.ppt_output)
            if args.ppt_output
            else (default_ppt_output_path(v2_output_dir) if args.full_pipeline else None)
        )
        try:
            result = make_v2_ppt(
                topic=resolved_topic or "AI Auto PPT",
                brief=resolved_brief,
                audience=resolved_audience,
                language=args.language,
                theme=v2_theme,
                author=args.author,
                exact_slides=resolved_chapters or None,
                min_slides=resolved_min_slides or 6,
                max_slides=resolved_max_slides or 10,
                output_dir=v2_output_dir,
                output_prefix=args.output_name,
                model=args.llm_model or None,
                generation_mode=args.generation_mode,
                outline_output=outline_output,
                semantic_output=semantic_output,
                deck_output=deck_output,
                log_output=log_output,
                ppt_output=ppt_output,
                outline_path=Path(args.outline_json) if args.outline_json else None,
            )
        except TimeoutError:
            parser.exit(
                status=1,
                message=(
                    "AI is mandatory for 'v2-make'. "
                    "Generation timed out.\n"
                ),
            )
        print(str(result.outline_path))
        print(str(result.semantic_path))
        print(str(result.deck_path))
        print(str(result.rewrite_log_path))
        print(str(result.warnings_path))
        print(str(result.log_path))
        print(str(result.pptx_path))
        return True

    if effective_command == "v2-review":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-review'.")
        review_output_dir = Path(args.review_output_dir) if args.review_output_dir else v2_output_dir / "visual_review"
        result = review_deck_once(
            deck_path=Path(args.deck_json),
            output_dir=review_output_dir,
            model=args.llm_model or None,
            theme_name=args.theme.strip() or None,
        )
        print(str(result.review_path))
        print(str(result.patch_path))
        print(str(result.deck_path))
        print(str(result.pptx_path))
        print(str(result.preview_dir))
        return True

    if effective_command == "v2-iterate":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-iterate'.")
        review_output_dir = Path(args.review_output_dir) if args.review_output_dir else v2_output_dir / "visual_review_loop"
        result = iterate_visual_review(
            deck_path=Path(args.deck_json),
            output_dir=review_output_dir,
            model=args.llm_model or None,
            max_rounds=max(1, args.max_rounds),
            theme_name=args.theme.strip() or None,
        )
        print(str(result.final_review_path))
        print(str(result.final_patch_path))
        print(str(result.deck_path))
        print(str(result.pptx_path))
        print(str(result.preview_dir))
        return True

    if effective_command == "ai-check":
        check_topic = args.topic.strip() or "AI AutoPPT health check"
        try:
            emit_progress(args.progress, "ai-check", "running AI healthcheck")
            summary = run_ai_healthcheck(
                topic=check_topic,
                brief=brief_text,
                audience=args.audience,
                language=args.language,
                theme=v2_theme,
                generation_mode=args.generation_mode,
                model=args.llm_model or None,
                with_render=args.with_render,
                output_dir=v2_output_dir if args.with_render else None,
            )
        except AiHealthcheckBlockedError as exc:
            parser.exit(status=1, message=f"AI healthcheck blocked: {exc}\n")
        except AiHealthcheckFailedError as exc:
            parser.exit(status=1, message=f"AI healthcheck failed: {exc}\n")
        print(summary.to_json())
        return True

    return False


__all__ = ["handle_v2_and_health_command"]

