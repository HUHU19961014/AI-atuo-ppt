from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import shutil
import sys
from pathlib import Path

from .clarifier import DEFAULT_AUDIENCE_HINT, clarify_user_input, derive_planning_context, load_clarifier_session
from .cli_parser import build_main_parser
from .clarify_web import serve_clarifier_web
from .config import (
    DEFAULT_REFERENCE_BODY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_TEMPLATE,
    PROJECT_ROOT,
)
from .cli_v2_commands import handle_v2_and_health_command
from .content_service import build_deck_spec_from_structure
from .deck_spec_io import load_deck_spec, write_deck_spec
from .exceptions import (
    CliExecutionError,
    CliUserInputError,
)
from .generator import generate_ppt_artifacts_from_deck_spec
from .healthcheck import run_ai_healthcheck
from .inputs.source_text import extract_source_text
from .llm_openai import OpenAIConfigurationError, OpenAIResponsesClient, OpenAIResponsesError, load_openai_responses_config
from .models import BodyPageSpec, DeckSpec, StructureSpec
from .patterns import supported_pattern_ids
from .structure_service import StructureGenerationRequest, generate_structure_with_ai
from .types import JSONDict
from .v2 import (
    build_log_output_path,
    build_ppt_output_path,
    compile_semantic_deck_payload,
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    default_semantic_output_path,
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
from .v2.services import ensure_generation_context
from .v2.visual_review import apply_patch_set, iterate_visual_review, review_deck_once
from .v2.io import DEFAULT_V2_OUTPUT_DIR
from .visual_service import generate_visual_draft_artifacts
from tools.scenario_generators.sie_onepage_designer import build_onepage_brief_from_structure, build_onepage_slide


WORKFLOW_COMMANDS = (
    "demo",
    "make",
    "onepage",
    "sie-render",
    "ai-check",
    "clarify",
    "clarify-web",
    "v2-outline",
    "v2-plan",
    "v2-compile",
    "v2-patch",
    "v2-render",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "review",
    "iterate",
    "visual-draft",
)
PRIMARY_COMMANDS = ("make", "review", "iterate")
ADVANCED_COMMANDS = (
    "demo",
    "onepage",
    "sie-render",
    "v2-plan",
    "v2-render",
    "v2-compile",
    "v2-patch",
    "v2-outline",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "clarify",
    "clarify-web",
    "ai-check",
    "visual-draft",
)
COMMAND_ALIASES = {
    "review": "v2-review",
    "iterate": "v2-iterate",
}
DEFAULT_EXTERNAL_COMMAND_TIMEOUT_SEC = 120
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
        "onepage",
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
    return any(token == option_name or token.startswith(f"{option_name}=") for token in argv)


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
    explicit_theme_values: list[str] = []
    for index, token in enumerate(argv):
        if token == "--theme" and index + 1 < len(argv):
            explicit_theme_values.append(str(argv[index + 1]).strip())
            continue
        if token.startswith("--theme="):
            explicit_theme_values.append(token.split("=", 1)[1].strip())
    if any(value and value != "sie_consulting_fixed" for value in explicit_theme_values):
        parser.error(
            "--theme is fixed to 'sie_consulting_fixed' for SIE consulting workflow."
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


def write_json_artifact(path: Path, payload: JSONDict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def emit_progress(enabled: bool, stage: str, detail: str) -> None:
    """Print a normalized stage marker for long-running command flows."""
    if not enabled:
        return
    print(f"[progress] {stage}: {detail}", file=sys.stderr)


def _build_ai_page_schema(candidate_pattern_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 4, "maxLength": 42},
            "subtitle": {"type": "string", "minLength": 4, "maxLength": 64},
            "bullets": {
                "type": "array",
                "minItems": 3,
                "maxItems": 6,
                "items": {"type": "string", "minLength": 4, "maxLength": 80},
            },
            "pattern_id": {"type": "string", "enum": list(candidate_pattern_ids)},
            "rationale": {"type": "string", "minLength": 12, "maxLength": 200},
        },
        "required": ["title", "subtitle", "bullets", "pattern_id", "rationale"],
        "additionalProperties": False,
    }


def apply_ai_content_layout_to_deck_spec(
    deck_spec: DeckSpec,
    *,
    model: str | None = None,
) -> tuple[DeckSpec, list[dict[str, object]]]:
    candidate_pattern_ids = supported_pattern_ids()
    if not candidate_pattern_ids:
        raise CliUserInputError("no supported pattern ids available for AI layout routing.")

    client = OpenAIResponsesClient(load_openai_responses_config(model=model or None))
    schema = _build_ai_page_schema(candidate_pattern_ids)
    refined_pages: list[BodyPageSpec] = []
    trace: list[dict[str, object]] = []

    for index, page in enumerate(deck_spec.body_pages, start=1):
        developer_prompt = (
            "You are optimizing one SIE PPT body page.\n"
            "Tasks:\n"
            "1) tighten title/subtitle for executive clarity,\n"
            "2) rewrite bullets to concise business evidence,\n"
            "3) choose the best pattern_id for layout semantics.\n"
            "Return JSON only."
        )
        user_prompt = (
            f"Deck cover title: {deck_spec.cover_title}\n"
            f"Page index: {index}\n"
            f"Current title: {page.title}\n"
            f"Current subtitle: {page.subtitle}\n"
            f"Current bullets:\n{chr(10).join(f'- {item}' for item in page.bullets)}\n"
            f"Current pattern_id: {page.pattern_id}\n"
            "Constraints: keep business meaning, avoid fluff, fit one-page reading rhythm."
        )
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="sie_template_page_ai_refine",
            schema=schema,
        )

        new_title = str(payload.get("title", "")).strip()
        new_subtitle = str(payload.get("subtitle", "")).strip()
        new_bullets = [str(item).strip() for item in payload.get("bullets", []) if str(item).strip()]
        new_pattern_id = str(payload.get("pattern_id", "")).strip()
        rationale = str(payload.get("rationale", "")).strip()

        if not new_title or not new_subtitle or len(new_bullets) < 3 or not new_pattern_id:
            raise OpenAIResponsesError(f"AI page refinement produced invalid result at page {index}.")

        refined_pages.append(
            replace(
                page,
                title=new_title,
                subtitle=new_subtitle,
                bullets=new_bullets[:6],
                pattern_id=new_pattern_id,
            )
        )
        trace.append(
            {
                "page_index": index,
                "old_pattern_id": page.pattern_id,
                "new_pattern_id": new_pattern_id,
                "rationale": rationale,
            }
        )

    return replace(deck_spec, body_pages=refined_pages), trace


def build_fallback_structure_spec(topic: str, brief_text: str) -> StructureSpec:
    brief_lines = [line.strip(" -?\t") for line in brief_text.splitlines() if line.strip()]
    while len(brief_lines) < 3:
        brief_lines.append("")

    return StructureSpec.from_dict(
        {
            "core_message": (brief_lines[0] or topic or "one-page briefing").strip(),
            "structure_type": "general",
            "sections": [
                {
                    "title": "Core Conclusion",
                    "key_message": (brief_lines[0] or f"{topic}: clarify the key judgement first.").strip(),
                    "arguments": [
                        {"point": "Theme focus", "evidence": topic.strip() or "one-page briefing"},
                        {"point": "Business background", "evidence": brief_lines[1] or "add business context to refine"},
                    ],
                },
                {
                    "title": "Key Support",
                    "key_message": (brief_lines[1] or "organize support around facts, actions, and constraints.").strip(),
                    "arguments": [
                        {"point": "Facts", "evidence": brief_lines[0] or "summarize current inputs"},
                        {"point": "Execution", "evidence": brief_lines[2] or "extract 2-3 priority actions"},
                    ],
                },
                {
                    "title": "Action Plan",
                    "key_message": (brief_lines[2] or "define next actions and rollout cadence.").strip(),
                    "arguments": [
                        {"point": "Next step", "evidence": "compress into one-page action items"},
                        {"point": "Usage", "evidence": "fit management review and business communication"},
                    ],
                },
            ],
        }
    )

def main():
    parser = build_main_parser()
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
            structure = StructureSpec.from_dict(payload)
        else:
            try:
                emit_progress(args.progress, "onepage", "calling AI structure planner")
                structure_result = generate_structure_with_ai(
                    StructureGenerationRequest(
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
            except OpenAIConfigurationError as exc:
                parser.exit(
                    status=1,
                    message=(
                        "AI is mandatory for 'onepage' content/layout planning. "
                        f"Configure a reachable AI endpoint first. Details: {exc}\n"
                    ),
                )
            except OpenAIResponsesError as exc:
                parser.exit(status=1, message=f"AI planning failed for 'onepage': {exc}\n")

        onepage_brief = build_onepage_brief_from_structure(
            structure,
            topic=args.topic.strip() or structure.core_message,
            footer=f"STRICTLY CONFIDENTIAL | 2026 SIE {output_stem}",
            page_no="01",
            layout_strategy=args.onepage_strategy.strip() or "auto",
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
        except OpenAIConfigurationError as exc:
            parser.exit(
                status=1,
                message=(
                    "AI is mandatory for 'onepage' content/layout planning. "
                    f"Configure a reachable AI endpoint first. Details: {exc}\n"
                ),
            )
        except OpenAIResponsesError as exc:
            parser.exit(status=1, message=f"AI strategy selection failed for 'onepage': {exc}\n")
        print(str(brief_output_path))
        print(str(review_path))
        print(str(score_path))
        print(str(built_path))
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
            emit_progress(args.progress, "sie-render", "loading structure json")
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
            render_deck_spec = deck_spec
        elif uses_topic_generation:
            try:
                emit_progress(args.progress, "sie-render", "calling AI structure planner")
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
            except OpenAIConfigurationError as exc:
                parser.exit(
                    status=1,
                    message=(
                        "AI is mandatory for 'sie-render' content/layout planning. "
                        f"Configure a reachable AI endpoint first. Details: {exc}\n"
                    ),
                )
            except OpenAIResponsesError as exc:
                parser.exit(status=1, message=f"AI planning failed for 'sie-render': {exc}\n")
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
        except CliUserInputError as exc:
            parser.exit(status=2, message=f"invalid sie-render input: {exc}\n")
        except OpenAIConfigurationError as exc:
            parser.exit(
                status=1,
                message=(
                    "AI is mandatory for 'sie-render' content/layout planning. "
                    f"Configure a reachable AI endpoint first. Details: {exc}\n"
                ),
            )
        except OpenAIResponsesError as exc:
            parser.exit(
                status=1,
                message=f"AI content/layout refinement failed for 'sie-render': {exc}\n",
            )

        deck_spec_path = (
            Path(args.deck_spec_output)
            if args.deck_spec_output
            else template_output_dir / f"{output_stem}.deck_spec.ai.json"
        )
        write_deck_spec(ai_refined_deck_spec, deck_spec_path)
        render_deck_spec = ai_refined_deck_spec
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
        except CliExecutionError as exc:
            parser.exit(status=exc.exit_code, message=f"visual-draft failed: {exc}\n")
        except Exception as exc:  # pragma: no cover - normalized user-facing error handling
            parser.exit(status=1, message=f"visual-draft failed: {exc}\n")
        print(str(artifacts.visual_spec_path))
        print(str(artifacts.preview_html_path))
        print(str(artifacts.preview_png_path))
        print(str(artifacts.visual_score_path))
        print(str(artifacts.ai_review_path))
        return

    if handle_v2_and_health_command(
        effective_command=effective_command,
        args=args,
        parser=parser,
        resolved_topic=resolved_topic,
        resolved_brief=resolved_brief,
        resolved_audience=resolved_audience,
        resolved_chapters=resolved_chapters,
        resolved_min_slides=resolved_min_slides,
        resolved_max_slides=resolved_max_slides,
        v2_theme=v2_theme,
        v2_output_dir=v2_output_dir,
        brief_text=brief_text,
        emit_progress=emit_progress,
        default_outline_output_path=default_outline_output_path,
        default_semantic_output_path=default_semantic_output_path,
        default_deck_output_path=default_deck_output_path,
        default_log_output_path=default_log_output_path,
        default_ppt_output_path=default_ppt_output_path,
        load_outline_document=load_outline_document,
        write_outline_document=write_outline_document,
        write_semantic_document=write_semantic_document,
        write_deck_document=write_deck_document,
        load_deck_document=load_deck_document,
        compile_semantic_deck_payload=compile_semantic_deck_payload,
        generate_outline_with_ai=generate_outline_with_ai,
        generate_semantic_deck_with_ai=generate_semantic_deck_with_ai,
        ensure_generation_context=ensure_generation_context,
        make_v2_ppt=make_v2_ppt,
        generate_v2_ppt=generate_v2_ppt,
        apply_patch_set=apply_patch_set,
        review_deck_once=review_deck_once,
        iterate_visual_review=iterate_visual_review,
        run_ai_healthcheck=run_ai_healthcheck,
    ):
        return
    parser.error(f"unsupported command '{effective_command}'.")


if __name__ == "__main__":
    main()

