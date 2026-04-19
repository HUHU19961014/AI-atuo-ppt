from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

_AI_CONFIG_HINT = (
    "\n\n"
    "To fix this, configure a reachable AI endpoint via:\n"
    "  - CLI:  --api-key sk-xxx --base-url "
    "https://dashscope.aliyuncs.com/compatible-mode/v1 --api-style chat_completions\n"
    "  - Env:  set OPENAI_API_KEY=sk-xxx\n"
    "         set OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
    "         set SIE_AUTOPPT_LLM_API_STYLE=chat_completions\n"
    "  - Local: start Ollama (port 11434) or other OpenAI-compatible local server\n"
    "  - Docs:  see docs/TROUBLESHOOTING.md for more options.\n"
)


def _matches_exc(exc: Exception, expected_type: type[Exception], expected_name: str) -> bool:
    return isinstance(exc, expected_type) or exc.__class__.__name__ == expected_name


def handle_pre_v2_command(
    *,
    effective_command: str,
    args: Any,
    parser: Any,
    output_dir: Path,
    brief_text: str,
    load_clarifier_session: Callable[[str], Any],
    clarify_user_input: Callable[..., Any],
    serve_clarifier_web: Callable[..., Any],
    build_template_output_stem: Callable[[str], str],
    emit_progress: Callable[[bool, str, str], None],
    structure_spec_cls: Any,
    openai_configuration_error_cls: type[Exception],
    openai_responses_error_cls: type[Exception],
    build_onepage_brief_from_structure: Callable[..., Any],
    build_onepage_slide: Callable[..., tuple[Path, Path, Path, Any]],
    write_json_artifact: Callable[[Path, dict[str, Any]], Path],
    load_deck_spec: Callable[[Path], Any],
    generate_visual_draft_artifacts: Callable[..., Any],
    cli_execution_error_cls: type[Exception],
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
        if not structure_json:
            parser.error("--structure-json is required for command 'onepage' in agent-driven mode.")
        strategy = args.onepage_strategy.strip().lower() or "auto"
        if strategy != "auto":
            parser.error(
                "--onepage-strategy must stay 'auto' for command 'onepage' "
                "to enforce AI-driven strategy selection."
            )

        output_stem = build_template_output_stem(args.output_name)
        template_output_dir = output_dir
        emit_progress(args.progress, "onepage", "loading structure json")
        structure_path = Path(structure_json)
        payload = json.loads(structure_path.read_text(encoding="utf-8-sig"))
        structure = structure_spec_cls.from_dict(payload)

        onepage_brief = build_onepage_brief_from_structure(
            structure,
            topic=args.topic.strip() or structure.core_message,
            footer=f"STRICTLY CONFIDENTIAL | 2026 SIE {output_stem}",
            page_no="01",
            layout_strategy="auto",
        )
        brief_output_path = template_output_dir / f"{output_stem}.onepage_brief.json"
        write_json_artifact(brief_output_path, asdict(onepage_brief))
        onepage_output_path = (
            Path(args.ppt_output)
            if args.ppt_output
            else template_output_dir / f"{output_stem}.onepage.pptx"
        )
        try:
            emit_progress(args.progress, "onepage", "rendering onepage PPT")
            built_path, review_path, score_path, _ = build_onepage_slide(
                onepage_brief,
                output_path=onepage_output_path,
                export_review=True,
                model=args.llm_model or None,
                require_ai_strategy=True,
            )
        except Exception as exc:
            if _matches_exc(exc, openai_configuration_error_cls, "OpenAIConfigurationError"):
                parser.exit(
                    status=1,
                    message=(
                        "AI is mandatory for 'onepage' content/layout planning. "
                        f"Configure a reachable AI endpoint first. Details: {exc}\n"
                        + _AI_CONFIG_HINT
                    ),
                )
            if _matches_exc(exc, openai_responses_error_cls, "OpenAIResponsesError"):
                parser.exit(
                    status=1,
                    message=f"AI strategy selection failed for 'onepage': {exc}\n" + _AI_CONFIG_HINT,
                )
            raise
        print(str(brief_output_path))
        print(str(review_path))
        print(str(score_path))
        print(str(built_path))
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
