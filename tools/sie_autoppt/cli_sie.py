from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

_AI_CONFIG_HINT = (
    "\n\n"
    "To fix this, configure a reachable AI endpoint via:\n"
    "  - CLI:  --api-key sk-xxx --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --api-style chat_completions\n"
    "  - Env:  set OPENAI_API_KEY=sk-xxx\n"
    "         set OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
    "         set SIE_AUTOPPT_LLM_API_STYLE=chat_completions\n"
    "  - Local: start Ollama (port 11434) or other OpenAI-compatible local server\n"
    "  - Docs:  see docs/TROUBLESHOOTING.md for more options.\n"
)


def handle_pre_v2_command(
    *,
    effective_command: str,
    args: Any,
    parser: Any,
    output_dir: Path,
    v2_output_dir: Path,
    brief_text: str,
    load_clarifier_session: Callable[[str], Any],
    clarify_user_input: Callable[..., Any],
    serve_clarifier_web: Callable[..., Any],
    build_template_output_stem: Callable[[str], str],
    emit_progress: Callable[[bool, str, str], None],
    generate_structure_with_ai: Callable[..., Any],
    structure_spec_cls: Any,
    structure_generation_request_cls: Any,
    openai_configuration_error_cls: type[Exception],
    openai_responses_error_cls: type[Exception],
    build_onepage_brief_from_structure: Callable[..., Any],
    build_onepage_slide: Callable[..., tuple[Path, Path, Path, Any]],
    write_json_artifact: Callable[[Path, dict[str, Any]], Path],
    build_deck_spec_from_structure: Callable[..., Any],
    load_deck_spec: Callable[[Path], Any],
    write_deck_spec: Callable[[Any, Path], Any],
    apply_ai_content_layout_to_deck_spec: Callable[..., tuple[Any, list[dict[str, object]]]],
    generate_ppt_artifacts_from_deck_spec: Callable[..., Any],
    generate_visual_draft_artifacts: Callable[..., Any],
    cli_execution_error_cls: type[Exception],
    cli_user_input_error_cls: type[Exception],
    template_path: Path,
    reference_body_path: Path | None,
) -> bool:

    if effective_command == "clarify":
        if not args.topic.strip():
            parser.error("--topic is required when command is 'clarify'.")
        existing_session = None
        if args.clarifier_state_file:
            state_path = Path(args.clarifier_state_file)
            if state_path.exists():
                existing_session = load_clarifier_session(state_path.read_text(encoding="utf-8"))
        result = clarify_user_input(
            args.topic,
            session=existing_session,
            original_brief=brief_text,
            model=args.llm_model or None,
        )
        if args.clarifier_state_file:
            Path(args.clarifier_state_file).write_text(result.session.to_json(), encoding="utf-8")
        print(result.to_json())
        return True

    if effective_command == "clarify-web":
        serve_clarifier_web(host=args.host, port=args.port)
        return True

    if effective_command == "onepage":
        structure_json = args.structure_json.strip()
        if not structure_json and not args.topic.strip():
            parser.error("--topic or --structure-json is required when command is 'onepage'.")

        output_stem = build_template_output_stem(args.output_name)
        template_output_dir = output_dir
        if structure_json:
            emit_progress(args.progress, "onepage", "loading structure json")
            structure_path = Path(structure_json)
            payload = json.loads(structure_path.read_text(encoding="utf-8-sig"))
            structure = structure_spec_cls.from_dict(payload)
        else:
            emit_progress(args.progress, "onepage", "calling AI structure planner")
            try:
                structure_result = generate_structure_with_ai(
                    structure_generation_request_cls(
                        topic=args.topic.strip(),
                        brief=brief_text,
                        audience=args.audience,
                        language=args.language,
                        sections=args.chapters or 3,
                        min_sections=args.min_slides,
                        max_sections=args.max_slides,
                    ),
                    model=args.llm_model or None,
                )
                structure = structure_result.structure
            except openai_configuration_error_cls as exc:
                parser.exit(
                    status=1,
                    message=(
                        f"AI is required for 'onepage' structure planning. "
                        f"Configuration error: {exc}\n"
                        + _AI_CONFIG_HINT
                    ),
                )
            except openai_responses_error_cls as exc:
                parser.exit(
                    status=1,
                    message=(
                        f"AI structure planning failed for 'onepage': {exc}\n"
                        + _AI_CONFIG_HINT
                    ),
                )

        onepage_brief = build_onepage_brief_from_structure(
            structure,
            topic=args.topic.strip() or structure.core_message,
            footer=f"STRICTLY CONFIDENTIAL | 2026 SIE {output_stem}",
            page_no="01",
            layout_strategy=args.onepage_strategy.strip() or "auto",
        )
        brief_output_path = template_output_dir / f"{output_stem}.onepage_brief.json"
        write_json_artifact(brief_output_path, asdict(onepage_brief))
        onepage_output_path = Path(args.ppt_output) if args.ppt_output else template_output_dir / f"{output_stem}.onepage.pptx"
        try:
            emit_progress(args.progress, "onepage", "rendering onepage PPT")
            built_path, review_path, score_path, _ = build_onepage_slide(
                onepage_brief,
                output_path=onepage_output_path,
                export_review=True,
                model=args.llm_model or None,
                require_ai_strategy=True,
            )
        except openai_configuration_error_cls as exc:
            parser.exit(
                status=1,
                message=(
                    "AI is mandatory for 'onepage' content/layout planning. "
                    f"Configure a reachable AI endpoint first. Details: {exc}\n"
                    + _AI_CONFIG_HINT
                ),
            )
        except openai_responses_error_cls as exc:
            parser.exit(
                status=1,
                message=f"AI strategy selection failed for 'onepage': {exc}\n" + _AI_CONFIG_HINT,
            )
        print(str(brief_output_path))
        print(str(review_path))
        print(str(score_path))
        print(str(built_path))
        return True

    if effective_command == "sie-render":
        structure_json = args.structure_json.strip()
        deck_spec_json = args.deck_spec_json.strip()
        uses_topic_generation = bool(args.topic.strip()) and not structure_json and not deck_spec_json
        specified_inputs = sum(bool(value) for value in (structure_json, deck_spec_json, uses_topic_generation))
        if specified_inputs != 1:
            parser.error(
                "exactly one actual-template input is required when command is 'sie-render': "
                "use --structure-json, --deck-spec-json, or --topic."
            )

        template_output_dir = output_dir
        output_stem = build_template_output_stem(args.output_name)

        if structure_json:
            emit_progress(args.progress, "sie-render", "loading structure json")
            structure_path = Path(structure_json)
            payload = json.loads(structure_path.read_text(encoding="utf-8-sig"))
            structure = structure_spec_cls.from_dict(payload)
            deck_spec = build_deck_spec_from_structure(
                structure,
                topic=args.topic.strip() or structure.core_message,
                cover_title=args.cover_title.strip() or None,
            )
            deck_spec_path = Path(args.deck_spec_output) if args.deck_spec_output else template_output_dir / f"{output_stem}.deck_spec.json"
            write_deck_spec(deck_spec, deck_spec_path)
            render_deck_spec = deck_spec
        elif uses_topic_generation:
            emit_progress(args.progress, "sie-render", "calling AI structure planner")
            try:
                structure_result = generate_structure_with_ai(
                    structure_generation_request_cls(
                        topic=args.topic.strip(),
                        brief=brief_text,
                        audience=args.audience,
                        language=args.language,
                        sections=args.chapters or 3,
                        min_sections=args.min_slides,
                        max_sections=args.max_slides,
                    ),
                    model=args.llm_model or None,
                )
                structure = structure_result.structure
            except openai_configuration_error_cls as exc:
                parser.exit(
                    status=1,
                    message=(
                        f"AI is required for 'sie-render' structure planning. "
                        f"Configuration error: {exc}\n"
                        + _AI_CONFIG_HINT
                    ),
                )
            except openai_responses_error_cls as exc:
                parser.exit(
                    status=1,
                    message=(
                        f"AI structure planning failed for 'sie-render': {exc}\n"
                        + _AI_CONFIG_HINT
                    ),
                )
            deck_spec = build_deck_spec_from_structure(
                structure,
                topic=args.topic.strip(),
                cover_title=args.cover_title.strip() or None,
            )
            deck_spec_path = Path(args.deck_spec_output) if args.deck_spec_output else template_output_dir / f"{output_stem}.deck_spec.json"
            write_deck_spec(deck_spec, deck_spec_path)
            render_deck_spec = deck_spec
        else:
            emit_progress(args.progress, "sie-render", "loading deck spec json")
            deck_spec_path = Path(deck_spec_json)
            render_deck_spec = load_deck_spec(deck_spec_path)

        if len(render_deck_spec.body_pages) == 1:
            parser.exit(
                status=1,
                message=(
                    "Single-page SIE output must use the 'onepage' command to avoid cover/catalog/ending slides.\n"
                ),
            )

        try:
            emit_progress(args.progress, "sie-render", "calling AI content/layout refinement")
            ai_refined_deck_spec, ai_trace = apply_ai_content_layout_to_deck_spec(
                render_deck_spec,
                model=args.llm_model.strip() or None,
            )
        except cli_user_input_error_cls as exc:
            parser.exit(status=2, message=f"invalid sie-render input: {exc}\n")
        except openai_configuration_error_cls as exc:
            parser.exit(
                status=1,
                message=(
                    f"AI is required for 'sie-render' content/layout refinement. "
                    f"Configuration error: {exc}\n"
                    + _AI_CONFIG_HINT
                ),
            )
        except openai_responses_error_cls as exc:
            parser.exit(
                status=1,
                message=(
                    f"AI content/layout refinement failed for 'sie-render': {exc}\n"
                    + _AI_CONFIG_HINT
                ),
            )

        deck_spec_path = Path(args.deck_spec_output) if args.deck_spec_output else template_output_dir / f"{output_stem}.deck_spec.ai.json"
        write_deck_spec(ai_refined_deck_spec, deck_spec_path)
        ai_trace_path = template_output_dir / f"{output_stem}.ai_layout_trace.json"
        write_json_artifact(ai_trace_path, {"pages": ai_trace})

        render_result = generate_ppt_artifacts_from_deck_spec(
            template_path=template_path,
            deck_spec_path=deck_spec_path,
            reference_body_path=reference_body_path,
            output_prefix=args.output_name,
            active_start=max(0, args.active_start),
            output_dir=template_output_dir,
        )
        final_ppt_path = render_result.output_path
        if args.ppt_output:
            requested_ppt_path = Path(args.ppt_output)
            requested_ppt_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(render_result.output_path), str(requested_ppt_path))
            final_ppt_path = requested_ppt_path

        render_trace_path = Path(args.render_trace_output) if args.render_trace_output else template_output_dir / f"{output_stem}.render_trace.json"
        write_json_artifact(render_trace_path, asdict(render_result.render_trace))
        print(str(deck_spec_path))
        print(str(render_trace_path))
        print(str(final_ppt_path))
        return True

    if effective_command == "visual-draft":
        if not args.deck_spec_json.strip():
            parser.error("--deck-spec-json is required when command is 'visual-draft'.")
        try:
            artifacts = generate_visual_draft_artifacts(
                deck_spec=load_deck_spec(Path(args.deck_spec_json)),
                output_dir=output_dir,
                output_name=build_template_output_stem(args.output_name),
                browser_path=args.browser.strip(),
                model=args.llm_model.strip(),
                page_index=max(0, int(args.page_index)),
                layout_hint=args.layout_hint.strip() or "auto",
                with_ai_review=bool(args.with_ai_review),
                visual_rules_path=args.visual_rules_path.strip(),
            )
        except cli_execution_error_cls as exc:
            exit_code = getattr(exc, "exit_code", 1)
            parser.exit(status=exit_code, message=f"visual-draft failed: {exc}\n")
        except Exception as exc:  # pragma: no cover
            parser.exit(status=1, message=f"visual-draft failed: {exc}\n")
        print(str(artifacts.visual_spec_path))
        print(str(artifacts.preview_html_path))
        print(str(artifacts.preview_png_path))
        print(str(artifacts.visual_score_path))
        print(str(artifacts.ai_review_path))
        return True

    return False
