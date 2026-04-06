from __future__ import annotations

import argparse
from pathlib import Path

from .clarifier import DEFAULT_AUDIENCE_HINT, clarify_user_input, load_clarifier_session
from .config import (
    DEFAULT_HTML,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_REFERENCE_BODY,
    DEFAULT_TEMPLATE,
    MAX_BODY_CHAPTERS,
)
from .inputs.source_text import extract_source_text
from .planning.ai_planner import AiPlanningRequest, resolve_external_planner_command
from .services import (
    AiHealthcheckBlockedError,
    AiHealthcheckFailedError,
    AiWorkflowError,
    generate_plan_from_html,
    generate_plan_with_ai,
    render_from_ai_plan,
    render_from_deck_spec,
    render_from_html,
    run_ai_healthcheck,
)


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
    is_ai_command = args.command in {"ai-plan", "ai-make", "ai-check"}

    if uses_ai_range and not is_ai_command:
        parser.error("--min-slides and --max-slides are only supported for ai-plan, ai-make, and ai-check.")
    if uses_exact_chapters and uses_ai_range and is_ai_command:
        parser.error("--chapters cannot be combined with --min-slides/--max-slides for AI planning.")
    if args.min_slides and args.max_slides and args.min_slides > args.max_slides:
        parser.error("--min-slides cannot be greater than --max-slides.")


def main():
    parser = argparse.ArgumentParser(
        description="Plan and render SIE template-driven PPT from HTML, DeckSpec JSON, or natural-language AI input."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("make", "plan", "render", "ai-plan", "ai-make", "ai-check", "clarify"),
        default="make",
        help="Workflow stage to execute. Defaults to 'make' for backward compatibility.",
    )
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to template PPTX.")
    parser.add_argument("--html", default=str(DEFAULT_HTML), help="Path to source HTML file.")
    parser.add_argument("--deck-json", default="", help="Path to planned DeckSpec JSON file.")
    parser.add_argument("--topic", default="", help="Topic or natural-language request used by the AI planner.")
    parser.add_argument("--brief", default="", help="Optional extra business context passed to the AI planner.")
    parser.add_argument("--brief-file", default="", help="Optional path to a text/markdown file with extra source material.")
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE_HINT, help="Target audience hint for the AI planner.")
    parser.add_argument("--llm-model", default="", help="Optional model override for the AI planner or clarifier.")
    parser.add_argument(
        "--planner-command",
        default="",
        help="Optional external planner command. Reads JSON from stdin and must print JSON to stdout.",
    )
    parser.add_argument("--plan-output", default="", help="Optional output path for the generated DeckSpec JSON.")
    parser.add_argument(
        "--clarifier-state-file",
        default="",
        help="Optional JSON file used to resume or persist clarifier session state.",
    )
    parser.add_argument("--min-slides", type=int, default=None, help=f"Optional AI planner lower bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--max-slides", type=int, default=None, help=f"Optional AI planner upper bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument(
        "--reference-body",
        default=str(DEFAULT_REFERENCE_BODY),
        help="Optional reference PPTX used as a body slide style library.",
    )
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated artifacts.")
    parser.add_argument(
        "--chapters",
        type=int,
        default=None,
        help=f"Optional exact number of body chapters to generate (1-{MAX_BODY_CHAPTERS}). If omitted, HTML <slide> input uses all detected pages.",
    )
    parser.add_argument("--active-start", type=int, default=0, help="Directory active chapter start index (0-based).")
    args = parser.parse_args()
    validate_slide_args(args, parser)

    template_path = Path(args.template)
    html_path = Path(args.html)
    output_dir = Path(args.output_dir)
    reference_body_path = Path(args.reference_body) if args.reference_body else None
    brief_text = load_brief_text(args.brief, args.brief_file)
    planner_command = resolve_external_planner_command(args.planner_command)

    if args.command == "clarify":
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

    if args.command == "plan":
        plan_output = generate_plan_from_html(
            html_path=html_path,
            chapters=args.chapters,
            output_dir=output_dir,
            output_prefix=args.output_name,
            plan_output=Path(args.plan_output) if args.plan_output else None,
        )
        print(str(plan_output))
        return

    if args.command == "ai-plan":
        if not args.topic.strip():
            parser.error("--topic is required when command is 'ai-plan'.")
        try:
            plan_output = generate_plan_with_ai(
                request=AiPlanningRequest(
                    topic=args.topic,
                    chapters=args.chapters or None,
                    min_slides=args.min_slides or None,
                    max_slides=args.max_slides or None,
                    audience=args.audience,
                    brief=brief_text,
                ),
                output_dir=output_dir,
                output_prefix=args.output_name,
                model=args.llm_model or None,
                planner_command=planner_command or None,
                plan_output=Path(args.plan_output) if args.plan_output else None,
                template_path=template_path,
            )
        except AiWorkflowError as exc:
            parser.exit(status=1, message=f"AI planning failed: {exc}\n")
        print(str(plan_output))
        return

    if args.command == "ai-check":
        check_topic = args.topic.strip() or "AI AutoPPT 健康检查"
        try:
            summary = run_ai_healthcheck(
                request=AiPlanningRequest(
                    topic=check_topic,
                    chapters=1,
                    audience=args.audience,
                    brief=brief_text,
                ),
                model=args.llm_model or None,
                planner_command=planner_command or None,
                template_path=template_path,
            )
        except AiHealthcheckBlockedError as exc:
            parser.exit(status=1, message=f"AI healthcheck blocked: {exc}\n")
        except AiHealthcheckFailedError as exc:
            parser.exit(status=1, message=f"AI healthcheck failed: {exc}\n")
        print(summary.to_json())
        return

    if args.command == "render":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'render'.")
        result = render_from_deck_spec(
            template_path=template_path,
            deck_spec_path=Path(args.deck_json),
            reference_body_path=reference_body_path,
            output_prefix=args.output_name,
            active_start=args.active_start,
            output_dir=output_dir,
        )
    elif args.command == "ai-make":
        if not args.topic.strip():
            parser.error("--topic is required when command is 'ai-make'.")
        try:
            result = render_from_ai_plan(
                template_path=template_path,
                request=AiPlanningRequest(
                    topic=args.topic,
                    chapters=args.chapters or None,
                    min_slides=args.min_slides or None,
                    max_slides=args.max_slides or None,
                    audience=args.audience,
                    brief=brief_text,
                ),
                reference_body_path=reference_body_path,
                output_prefix=args.output_name,
                active_start=args.active_start,
                output_dir=output_dir,
                model=args.llm_model or None,
                planner_command=planner_command or None,
                plan_output=Path(args.plan_output) if args.plan_output else None,
            )
        except AiWorkflowError as exc:
            parser.exit(status=1, message=f"AI planning failed: {exc}\n")
    else:
        result = render_from_html(
            template_path=template_path,
            html_path=html_path,
            reference_body_path=reference_body_path,
            output_prefix=args.output_name,
            chapters=args.chapters,
            active_start=args.active_start,
            output_dir=output_dir,
        )

    print(str(result.report_path))
    print(str(result.output_path))


if __name__ == "__main__":
    main()
