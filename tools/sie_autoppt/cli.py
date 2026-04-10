from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import shutil
import sys
from pathlib import Path

from .clarifier import DEFAULT_AUDIENCE_HINT, clarify_user_input, derive_planning_context, load_clarifier_session
from .clarify_web import serve_clarifier_web
from .config import (
    DEFAULT_REFERENCE_BODY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_TEMPLATE,
    MAX_BODY_CHAPTERS,
    PROJECT_ROOT,
)
from .content_service import build_deck_spec_from_structure
from .deck_spec_io import write_deck_spec
from .exceptions import AiHealthcheckBlockedError, AiHealthcheckFailedError
from .generator import generate_ppt_artifacts_from_deck_spec
from .healthcheck import run_ai_healthcheck
from .inputs.source_text import extract_source_text
from .models import StructureSpec
from .structure_service import StructureGenerationRequest, generate_structure_with_ai
from .v2 import (
    build_deck_output_path,
    build_log_output_path,
    build_outline_output_path,
    build_ppt_output_path,
    build_semantic_output_path,
    compile_semantic_deck_payload,
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    default_semantic_output_path,
    generate_deck_with_ai,
    generate_outline_with_ai,
    generate_semantic_deck_with_ai,
    generate_ppt as generate_v2_ppt,
    load_deck_document,
    load_outline_document,
    write_semantic_document,
    make_v2_ppt,
    write_deck_document,
    write_outline_document,
)
from .v2.services import DeckGenerationRequest, OutlineGenerationRequest
from .v2.visual_review import iterate_visual_review, review_deck_once
from .v2.io import DEFAULT_V2_OUTPUT_DIR


WORKFLOW_COMMANDS = (
    "demo",
    "make",
    "sie-render",
    "ai-check",
    "clarify",
    "clarify-web",
    "v2-outline",
    "v2-plan",
    "v2-compile",
    "v2-render",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "review",
    "iterate",
)
PRIMARY_COMMANDS = ("make", "review", "iterate")
ADVANCED_COMMANDS = (
    "demo",
    "sie-render",
    "v2-plan",
    "v2-render",
    "v2-compile",
    "v2-outline",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "clarify",
    "clarify-web",
    "ai-check",
)
COMMAND_ALIASES = {
    "review": "v2-review",
    "iterate": "v2-iterate",
}
RECOMMENDED_WORKFLOW_HELP = (
    "Recommended workflows:\n"
    "  demo                  no-AI sample render using the bundled deck\n"
    "  sie-render --topic ... or --structure-json ...  actual SIE template render with optional AI planning\n"
    "  make --topic ...     semantic V2 full generation\n"
    "  review --deck-json   one-pass visual review alias for v2-review\n"
    "  iterate --deck-json  multi-round review alias for v2-iterate\n"
    "Advanced commands:\n"
    f"  {', '.join(ADVANCED_COMMANDS)}\n"
    "Legacy HTML/template generation commands remain retired; use sie-render for actual SIE template delivery."
)

DEMO_SAMPLE_DECK = PROJECT_ROOT / "samples" / "sample_deck_v2.json"


def load_brief_text(brief: str, brief_file: str) -> str:
    parts = []
    if brief.strip():
        parts.append(brief.strip())
    if brief_file.strip():
        parts.append(extract_source_text(Path(brief_file)))
    return "\n\n".join(part for part in parts if part)


def validate_slide_args(args, parser: argparse.ArgumentParser):
    uses_ai_range = bool(args.min_slides or args.max_slides)
    uses_exact_chapters = bool(args.chapters)
    is_ai_command = args.command in {
        "ai-check",
        "make",
        "v2-outline",
        "v2-plan",
        "v2-make",
    } or bool(getattr(args, "full_pipeline", False)) or bool(args.topic.strip() or args.outline_json.strip())

    if uses_ai_range and not is_ai_command:
        parser.error("--min-slides and --max-slides are only supported for AI generation workflows such as make, v2-plan, v2-make, and ai-check.")
    if uses_exact_chapters and uses_ai_range and is_ai_command:
        parser.error("--chapters cannot be combined with --min-slides/--max-slides for AI planning.")
    if args.min_slides and args.max_slides and args.min_slides > args.max_slides:
        parser.error("--min-slides cannot be greater than --max-slides.")


def command_was_explicit(argv: list[str]) -> bool:
    for token in argv:
        if token.startswith("-"):
            continue
        return token in WORKFLOW_COMMANDS
    return False


def normalize_command_alias(command_name: str) -> str:
    return COMMAND_ALIASES.get(command_name, command_name)


def validate_command_name(command_name: str, parser: argparse.ArgumentParser) -> None:
    normalized = normalize_command_alias(command_name)
    if normalized in WORKFLOW_COMMANDS:
        return
    parser.error(
        "unknown command "
        f"'{command_name}'. Use one of the primary commands ({', '.join(PRIMARY_COMMANDS)}) "
        f"or advanced commands ({', '.join(ADVANCED_COMMANDS)})."
    )


def resolve_effective_command(argv: list[str], args) -> tuple[str, bool]:
    explicit = command_was_explicit(argv)
    normalized_command = normalize_command_alias(args.command)
    if args.full_pipeline or normalized_command == "make":
        return "v2-make", explicit
    if explicit:
        return normalized_command, explicit
    if args.topic.strip() or args.outline_json.strip():
        return "v2-make", explicit
    return normalized_command, explicit


def emit_command_notice(explicit: bool, parsed_command: str, effective_command: str) -> None:
    if parsed_command in COMMAND_ALIASES:
        print(
            f"INFO: '{parsed_command}' maps to '{effective_command}'.",
            file=sys.stderr,
        )
    if effective_command == "v2-make" and parsed_command == "make":
        print(
            "INFO: 'make' routes to semantic v2-make; legacy template generation has been removed.",
            file=sys.stderr,
        )
        return


def option_was_explicit(argv: list[str], option_name: str) -> bool:
    return option_name in argv


def is_v2_command(command_name: str) -> bool:
    return command_name.startswith("v2-")


def validate_v2_option_compatibility(
    argv: list[str],
    *,
    effective_command: str,
    parser: argparse.ArgumentParser,
) -> None:
    if not (is_v2_command(effective_command) or effective_command == "make"):
        return
    if option_was_explicit(argv, "--template"):
        parser.error(
            "--template is no longer supported. Use --theme with the V2 semantic workflow."
        )


def resolve_v2_clarified_context(
    args,
    *,
    brief_text: str,
    effective_command: str,
    parser: argparse.ArgumentParser,
) -> tuple[str, str, str, int | None, int | None, int | None, str]:
    if not args.topic.strip():
        return (
            "",
            brief_text,
            args.audience,
            args.chapters,
            args.min_slides,
            args.max_slides,
            args.theme.strip() or "business_red",
        )

    context = derive_planning_context(
        topic=args.topic,
        brief=brief_text,
        audience=args.audience,
        theme=args.theme.strip(),
        chapters=args.chapters,
        min_slides=args.min_slides,
        max_slides=args.max_slides,
        prefer_llm=False,
    )

    if context.requirements.template:
        parser.exit(
            status=1,
            message=(
                "V2 workflows do not support PPTX templates. "
                f"Requested template: {context.requirements.template}. "
                "Use --theme instead.\n"
            ),
        )

    if context.status == "needs_clarification" and not context.skipped:
        parser.exit(
            status=1,
            message=f"Clarification required before '{effective_command}':\n{context.message}\n",
        )

    return (
        context.topic,
        context.brief or brief_text,
        context.audience.strip() or DEFAULT_AUDIENCE_HINT,
        context.chapters,
        context.min_slides,
        context.max_slides,
        args.theme.strip() or context.requirements.theme or "business_red",
    )


def run_demo_render(
    *,
    output_dir: Path,
    output_prefix: str,
    theme_name: str | None = None,
    log_output: Path | None = None,
    ppt_output: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    if not DEMO_SAMPLE_DECK.exists():
        raise FileNotFoundError(f"bundled demo deck not found: {DEMO_SAMPLE_DECK}")

    demo_output_dir = output_dir / "demo"
    demo_prefix = f"{output_prefix}_demo"
    final_log_output = log_output or build_log_output_path(demo_output_dir, demo_prefix)
    final_ppt_output = ppt_output or build_ppt_output_path(demo_output_dir, demo_prefix)
    deck = load_deck_document(DEMO_SAMPLE_DECK)
    render_result = generate_v2_ppt(
        deck,
        output_path=final_ppt_output,
        theme_name=theme_name,
        log_path=final_log_output,
    )
    return DEMO_SAMPLE_DECK, render_result.rewrite_log_path, render_result.warnings_path, final_log_output, render_result.output_path


def build_template_output_stem(output_name: str) -> str:
    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in output_name.strip())
    return safe_name.strip("._") or DEFAULT_OUTPUT_PREFIX


def write_json_artifact(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Generate enterprise PPTs with V2 semantics or the actual SIE template delivery path.",
        epilog=RECOMMENDED_WORKFLOW_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        metavar="command",
        default="make",
        help="Primary commands: make, review, iterate. Use sie-render when you need the actual SIE PPTX template path.",
    )
    parser.add_argument("--template", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--deck-json",
        default="",
        help="Path to a compiled deck JSON or V2 semantic deck JSON, depending on the command.",
    )
    parser.add_argument("--structure-json", default="", help="Path to a StructureSpec JSON file for actual SIE template rendering.")
    parser.add_argument("--deck-spec-json", default="", help="Path to a DeckSpec JSON file for actual SIE template rendering.")
    parser.add_argument("--deck-spec-output", default="", help="Optional output path for the generated DeckSpec JSON.")
    parser.add_argument("--topic", default="", help="Topic or natural-language request used by the AI planner.")
    parser.add_argument("--outline-json", default="", help="Path to a V2 outline JSON file.")
    parser.add_argument("--outline-output", default="", help="Optional output path for the generated V2 outline JSON.")
    parser.add_argument("--semantic-output", default="", help="Optional output path for the generated V2 semantic deck JSON.")
    parser.add_argument("--brief", default="", help="Optional extra business context passed to the AI planner.")
    parser.add_argument("--brief-file", default="", help="Optional path to a text/markdown file with extra source material.")
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE_HINT, help="Target audience hint for the AI planner.")
    parser.add_argument("--llm-model", default="", help="Optional model override for the AI planner or clarifier.")
    parser.add_argument("--theme", default="", help="Optional V2 theme name.")
    parser.add_argument("--language", default="zh-CN", help="Language used by V2 outline/deck generation.")
    parser.add_argument(
        "--generation-mode",
        default="deep",
        choices=("quick", "deep"),
        help="V2 generation mode: 'quick' skips strategic analysis, 'deep' adds structured context and strategy analysis.",
    )
    parser.add_argument("--author", default="AI Auto PPT", help="Author metadata used by V2 deck generation.")
    parser.add_argument("--plan-output", default="", help="Optional output path for the generated compiled deck JSON.")
    parser.add_argument("--log-output", default="", help="Optional output path for the generated V2 render log.")
    parser.add_argument("--ppt-output", default="", help="Optional output path for the generated V2 PPTX.")
    parser.add_argument("--render-trace-output", default="", help="Optional output path for the actual-template render trace JSON.")
    parser.add_argument("--review-output-dir", default="", help="Optional output directory for visual review artifacts.")
    parser.add_argument("--max-rounds", type=int, default=2, help="Maximum auto-fix review rounds for v2-iterate.")
    parser.add_argument(
        "--clarifier-state-file",
        default="",
        help="Optional JSON file used to resume or persist clarifier session state.",
    )
    parser.add_argument("--min-slides", type=int, default=None, help=f"Optional AI planner lower bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--max-slides", type=int, default=None, help=f"Optional AI planner upper bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated artifacts.")
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run the V2 full pipeline (outline -> deck -> quality gate -> PPT render) with standardized output filenames.",
    )
    parser.add_argument(
        "--chapters",
        type=int,
        default=None,
        help=f"Optional exact number of body chapters to generate (1-{MAX_BODY_CHAPTERS}).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host used by local web services such as clarify-web.")
    parser.add_argument("--port", type=int, default=8765, help="Port used by local web services such as clarify-web.")
    parser.add_argument(
        "--with-render",
        action="store_true",
        help="For ai-check only: run the healthcheck through the PPT render step and emit render quality summary fields.",
    )
    parser.add_argument("--cover-title", default="", help="Optional cover title override for sie-render.")
    parser.add_argument("--template-path", default="", help="Optional PPTX template override for sie-render.")
    parser.add_argument("--reference-body-path", default="", help="Optional reference body PPTX override for sie-render.")
    parser.add_argument("--active-start", type=int, default=0, help="Actual-template directory highlight offset used by sie-render.")
    raw_argv = sys.argv[1:]
    args = parser.parse_args()
    validate_command_name(args.command, parser)
    validate_slide_args(args, parser)
    effective_command, explicit_command = resolve_effective_command(raw_argv, args)
    validate_v2_option_compatibility(raw_argv, effective_command=effective_command, parser=parser)
    emit_command_notice(explicit_command, args.command, effective_command)

    output_dir = Path(args.output_dir)
    brief_text = load_brief_text(args.brief, args.brief_file)
    v2_theme = args.theme.strip() or "business_red"
    v2_output_dir = DEFAULT_V2_OUTPUT_DIR if output_dir == DEFAULT_OUTPUT_DIR else output_dir
    resolved_topic = args.topic.strip()
    resolved_brief = brief_text
    resolved_audience = args.audience
    resolved_chapters = args.chapters
    resolved_min_slides = args.min_slides
    resolved_max_slides = args.max_slides

    if effective_command in {"v2-outline", "v2-plan", "v2-make"} and args.topic.strip():
        (
            resolved_topic,
            resolved_brief,
            resolved_audience,
            resolved_chapters,
            resolved_min_slides,
            resolved_max_slides,
            v2_theme,
        ) = resolve_v2_clarified_context(
            args,
            brief_text=brief_text,
            effective_command=effective_command,
            parser=parser,
        )

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
        return

    if effective_command == "clarify-web":
        serve_clarifier_web(host=args.host, port=args.port)
        return

    if effective_command == "demo":
        demo_sample_path, rewrite_log_path, warnings_path, log_output, ppt_output = run_demo_render(
            output_dir=v2_output_dir,
            output_prefix=args.output_name,
            theme_name=args.theme.strip() or None,
            log_output=Path(args.log_output) if args.log_output else None,
            ppt_output=Path(args.ppt_output) if args.ppt_output else None,
        )
        print(str(demo_sample_path))
        print(str(rewrite_log_path))
        print(str(warnings_path))
        print(str(log_output))
        print(str(ppt_output))
        return

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

        template_path = Path(args.template_path) if args.template_path else DEFAULT_TEMPLATE
        reference_body_path = (
            Path(args.reference_body_path)
            if args.reference_body_path
            else (DEFAULT_REFERENCE_BODY if DEFAULT_REFERENCE_BODY.exists() else None)
        )
        template_output_dir = output_dir
        output_stem = build_template_output_stem(args.output_name)

        if structure_json:
            structure_path = Path(structure_json)
            payload = json.loads(structure_path.read_text(encoding="utf-8-sig"))
            structure = StructureSpec.from_dict(payload)
            deck_spec = build_deck_spec_from_structure(
                structure,
                topic=args.topic.strip() or structure.core_message,
                cover_title=args.cover_title.strip() or None,
            )
            deck_spec_path = (
                Path(args.deck_spec_output)
                if args.deck_spec_output
                else template_output_dir / f"{output_stem}.deck_spec.json"
            )
            write_deck_spec(deck_spec, deck_spec_path)
        elif uses_topic_generation:
            structure_result = generate_structure_with_ai(
                StructureGenerationRequest(
                    topic=args.topic.strip(),
                    brief=brief_text,
                    audience=args.audience,
                    language=args.language,
                    sections=args.chapters,
                    min_sections=args.min_slides,
                    max_sections=args.max_slides,
                ),
                model=args.llm_model or None,
            )
            deck_spec = build_deck_spec_from_structure(
                structure_result.structure,
                topic=args.topic.strip(),
                cover_title=args.cover_title.strip() or None,
            )
            deck_spec_path = (
                Path(args.deck_spec_output)
                if args.deck_spec_output
                else template_output_dir / f"{output_stem}.deck_spec.json"
            )
            write_deck_spec(deck_spec, deck_spec_path)
        else:
            deck_spec_path = Path(deck_spec_json)

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

        render_trace_path = (
            Path(args.render_trace_output)
            if args.render_trace_output
            else template_output_dir / f"{output_stem}.render_trace.json"
        )
        write_json_artifact(render_trace_path, asdict(render_result.render_trace))
        print(str(deck_spec_path))
        print(str(render_trace_path))
        print(str(final_ppt_path))
        return

    if effective_command == "v2-outline":
        if not resolved_topic:
            parser.error("--topic is required when command is 'v2-outline'.")
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
        return

    if effective_command == "v2-plan":
        if not resolved_topic and not args.outline_json:
            parser.error("--topic or --outline-json is required when command is 'v2-plan'.")
        if args.outline_json:
            outline = load_outline_document(Path(args.outline_json))
            outline_output = None
        else:
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
        semantic_payload = generate_semantic_deck_with_ai(
            DeckGenerationRequest(
                topic=resolved_topic or "AI Auto PPT",
                outline=outline,
                brief=resolved_brief,
                audience=resolved_audience,
                language=args.language,
                theme=v2_theme,
                author=args.author,
                generation_mode=args.generation_mode,
            ),
            model=args.llm_model or None,
        )
        validated_deck = compile_semantic_deck_payload(
            semantic_payload,
            default_title=resolved_topic or "AI Auto PPT",
            default_theme=v2_theme,
            default_language=args.language,
            default_author=args.author,
        )
        semantic_output = Path(args.semantic_output) if args.semantic_output else default_semantic_output_path(v2_output_dir)
        write_semantic_document(semantic_payload, semantic_output)
        deck_output = Path(args.plan_output) if args.plan_output else default_deck_output_path(v2_output_dir)
        write_deck_document(validated_deck.deck, deck_output)
        if outline_output is not None:
            print(str(outline_output))
        print(str(semantic_output))
        print(str(deck_output))
        return

    if effective_command == "v2-compile":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-compile'.")
        deck = load_deck_document(Path(args.deck_json))
        deck_output = Path(args.plan_output) if args.plan_output else default_deck_output_path(v2_output_dir)
        write_deck_document(deck, deck_output)
        print(str(deck_output))
        return

    if effective_command == "v2-render":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'v2-render'.")
        log_output = Path(args.log_output) if args.log_output else default_log_output_path(v2_output_dir)
        ppt_output = Path(args.ppt_output) if args.ppt_output else default_ppt_output_path(v2_output_dir)
        deck = load_deck_document(Path(args.deck_json))
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
        return

    if effective_command == "v2-make":
        if not resolved_topic and not args.outline_json:
            parser.error("--topic or --outline-json is required when command is 'v2-make'.")
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
            outline_output=(
                Path(args.outline_output)
                if args.outline_output
                else (default_outline_output_path(v2_output_dir) if args.full_pipeline else None)
            ),
            semantic_output=(
                Path(args.semantic_output)
                if args.semantic_output
                else (default_semantic_output_path(v2_output_dir) if args.full_pipeline else None)
            ),
            deck_output=(
                Path(args.plan_output)
                if args.plan_output
                else (default_deck_output_path(v2_output_dir) if args.full_pipeline else None)
            ),
            log_output=(
                Path(args.log_output)
                if args.log_output
                else (default_log_output_path(v2_output_dir) if args.full_pipeline else None)
            ),
            ppt_output=(
                Path(args.ppt_output)
                if args.ppt_output
                else (default_ppt_output_path(v2_output_dir) if args.full_pipeline else None)
            ),
            outline_path=Path(args.outline_json) if args.outline_json else None,
        )
        print(str(result.outline_path))
        print(str(result.semantic_path))
        print(str(result.deck_path))
        print(str(result.rewrite_log_path))
        print(str(result.warnings_path))
        print(str(result.log_path))
        print(str(result.pptx_path))
        return

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
        return

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
        return

    if effective_command == "ai-check":
        check_topic = args.topic.strip() or "AI AutoPPT 健康检查"
        try:
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
        return
    parser.error(f"unsupported command '{effective_command}'.")


if __name__ == "__main__":
    main()
