import argparse
import datetime
import json
import re
from pathlib import Path

from .config import (
    DEFAULT_HTML,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_REFERENCE_BODY,
    DEFAULT_TEMPLATE,
    MAX_BODY_CHAPTERS,
)
from .deck_spec_io import write_deck_spec
from .generator import generate_ppt_artifacts_from_deck_plan, generate_ppt_artifacts_from_deck_spec, generate_ppt_artifacts_from_html
from .inputs.source_text import extract_source_text
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesError,
    load_openai_responses_config,
)
from .pipeline import build_deck_plan, plan_deck_from_html
from .planning.ai_planner import (
    AiPlanningRequest,
    ExternalPlannerError,
    plan_deck_spec_with_ai,
    resolve_external_planner_command,
)
from .qa import write_qa_report


def build_plan_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\\\|?*]+', "_", output_prefix).strip(" ._") or "SIE_AutoPPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.deck.json"


def load_brief_text(brief: str, brief_file: str) -> str:
    parts = []
    if brief.strip():
        parts.append(brief.strip())
    if brief_file.strip():
        parts.append(extract_source_text(Path(brief_file)))
    return "\n\n".join(part for part in parts if part)


def main():
    parser = argparse.ArgumentParser(
        description="Plan and render SIE template-driven PPT from HTML or DeckSpec JSON."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("make", "plan", "render", "ai-plan", "ai-make", "ai-check"),
        default="make",
        help="Workflow stage to execute. Defaults to 'make' for backward compatibility.",
    )
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to template PPTX.")
    parser.add_argument("--html", default=str(DEFAULT_HTML), help="Path to source HTML file.")
    parser.add_argument("--deck-json", default="", help="Path to planned DeckSpec JSON file.")
    parser.add_argument("--topic", default="", help="Topic or natural-language request used by the AI planner.")
    parser.add_argument("--brief", default="", help="Optional extra business context passed to the AI planner.")
    parser.add_argument("--brief-file", default="", help="Optional path to a text/markdown file with extra source material.")
    parser.add_argument("--audience", default="管理层 + 业务负责人", help="Target audience hint for the AI planner.")
    parser.add_argument("--llm-model", default="", help="Optional model override for the AI planner.")
    parser.add_argument("--planner-command", default="", help="Optional external planner command. Reads JSON from stdin and must print JSON to stdout.")
    parser.add_argument("--plan-output", default="", help="Optional output path for the generated DeckSpec JSON.")
    parser.add_argument(
        "--reference-body",
        default=str(DEFAULT_REFERENCE_BODY),
        help="Optional reference PPTX used as a body slide style library.",
    )
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated artifacts.")
    parser.add_argument("--chapters", type=int, default=3, help=f"Number of body chapters to generate (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--active-start", type=int, default=0, help="Directory active chapter start index (0-based).")
    args = parser.parse_args()

    template_path = Path(args.template)
    html_path = Path(args.html)
    output_dir = Path(args.output_dir)
    reference_body_path = Path(args.reference_body) if args.reference_body else None
    brief_text = load_brief_text(args.brief, args.brief_file)
    planner_command = resolve_external_planner_command(args.planner_command)

    if args.command == "plan":
        deck_plan = plan_deck_from_html(html_path, args.chapters)
        plan_output = Path(args.plan_output) if args.plan_output else build_plan_output_path(output_dir, args.output_name)
        write_deck_spec(deck_plan.deck, plan_output)
        print(str(plan_output))
        return

    if args.command == "ai-plan":
        if not args.topic.strip():
            parser.error("--topic is required when command is 'ai-plan'.")
        try:
            deck = plan_deck_spec_with_ai(
                AiPlanningRequest(
                    topic=args.topic,
                    chapters=args.chapters,
                    audience=args.audience,
                    brief=brief_text,
                ),
                model=args.llm_model or None,
                planner_command=planner_command or None,
            )
        except (OpenAIConfigurationError, OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
            parser.exit(status=1, message=f"AI planning failed: {exc}\n")
        plan_output = Path(args.plan_output) if args.plan_output else build_plan_output_path(output_dir, args.output_name)
        write_deck_spec(deck, plan_output)
        print(str(plan_output))
        return

    if args.command == "ai-check":
        check_topic = args.topic.strip() or "AI AutoPPT 健康检查"
        try:
            config = load_openai_responses_config(model=args.llm_model or None) if not planner_command else None
            deck = plan_deck_spec_with_ai(
                AiPlanningRequest(
                    topic=check_topic,
                    chapters=1,
                    audience=args.audience,
                    brief=brief_text,
                ),
                model=args.llm_model or None,
                planner_command=planner_command or None,
            )
        except OpenAIConfigurationError as exc:
            parser.exit(status=1, message=f"AI healthcheck blocked: {exc}\n")
        except (OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
            parser.exit(status=1, message=f"AI healthcheck failed: {exc}\n")

        summary = {
            "status": "ok",
            "model": (config.model if config else "external-command"),
            "base_url": (config.base_url if config else ""),
            "api_style": (config.api_style if config else "external_command"),
            "topic": check_topic,
            "cover_title": deck.cover_title,
            "page_count": len(deck.body_pages),
            "first_page_title": deck.body_pages[0].title if deck.body_pages else "",
        }
        if planner_command:
            summary["planner_command"] = planner_command
        print(json.dumps(summary, ensure_ascii=False))
        return

    if args.command == "render":
        if not args.deck_json:
            parser.error("--deck-json is required when command is 'render'.")
        artifacts = generate_ppt_artifacts_from_deck_spec(
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
            deck = plan_deck_spec_with_ai(
                AiPlanningRequest(
                    topic=args.topic,
                    chapters=args.chapters,
                    audience=args.audience,
                    brief=brief_text,
                ),
                model=args.llm_model or None,
                planner_command=planner_command or None,
            )
        except (OpenAIConfigurationError, OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
            parser.exit(status=1, message=f"AI planning failed: {exc}\n")
        if args.plan_output:
            write_deck_spec(deck, Path(args.plan_output))
        artifacts = generate_ppt_artifacts_from_deck_plan(
            deck_plan=build_deck_plan(deck),
            input_kind="ai_topic",
            template_path=template_path,
            reference_body_path=reference_body_path,
            output_prefix=args.output_name,
            active_start=args.active_start,
            output_dir=output_dir,
        )
    else:
        artifacts = generate_ppt_artifacts_from_html(
            template_path=template_path,
            html_path=html_path,
            reference_body_path=reference_body_path,
            output_prefix=args.output_name,
            chapters=args.chapters,
            active_start=args.active_start,
            output_dir=output_dir,
        )

    report = write_qa_report(
        artifacts.output_path,
        len(artifacts.deck_plan.pattern_ids),
        pattern_ids=artifacts.deck_plan.pattern_ids,
        chapter_lines=artifacts.deck_plan.chapter_lines,
        template_path=template_path,
        render_trace=artifacts.render_trace,
    )
    print(str(report))
    print(str(artifacts.output_path))


if __name__ == "__main__":
    main()
