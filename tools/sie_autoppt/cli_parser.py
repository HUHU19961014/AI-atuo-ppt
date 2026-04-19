from __future__ import annotations

import argparse

from .clarifier import DEFAULT_AUDIENCE_HINT
from .config import DEFAULT_OUTPUT_DIR, DEFAULT_OUTPUT_PREFIX, MAX_BODY_CHAPTERS

RECOMMENDED_WORKFLOW_HELP = (
    "Recommended workflows:\n"
    "  onepage --structure-json ...\n"
    "                       AI-driven onepage render (strategy selected by model)\n"
    "  make --topic ...     semantic V2 full generation\n"
    "  batch-make --topic ...\n"
    "                       internal batch pipeline (bundle -> pptmaster -> tuning -> QA)\n"
    "  review --deck-json   one-pass visual review alias for v2-review\n"
    "  iterate --deck-json  multi-round review alias for v2-iterate\n"
    "  visual-draft --deck-spec-json ...  HTML visual draft + scoring before PPTX\n"
    "Advanced commands:\n"
    "  onepage, batch-make, v2-plan, v2-render, v2-compile, v2-patch,\n"
    "  v2-outline, v2-make, v2-review, v2-iterate, clarify, clarify-web, ai-check, visual-draft\n"
    "Legacy HTML/template generation commands are removed from primary CLI.\n"
    "Note: onepage is agent-driven only; V2 workflows require a reachable AI endpoint."
)


def build_main_parser() -> argparse.ArgumentParser:
    """Build and return the CLI parser used by `sie-autoppt` commands."""
    parser = argparse.ArgumentParser(
        description="Generate enterprise PPTs with V2 semantic workflows.",
        epilog=RECOMMENDED_WORKFLOW_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        metavar="command",
        default="make",
        help=(
            "Primary commands: make, batch-make, review, iterate. "
            "Use onepage for a single SIE body slide (agent-driven)."
        ),
    )
    parser.add_argument("--template", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--deck-json",
        default="",
        help="Path to a compiled deck JSON or V2 semantic deck JSON, depending on the command.",
    )
    parser.add_argument(
        "--patch-json", default="", help="Path to patch JSON used by v2-patch for incremental deck edits."
    )
    parser.add_argument("--structure-json", default="", help="Path to a StructureSpec JSON file.")
    parser.add_argument("--deck-spec-json", default="", help="Path to a DeckSpec JSON file.")
    parser.add_argument(
        "--content-bundle-json",
        default="",
        help="Path to a batch content_bundle.json artifact. For batch-make this skips internal AI preprocessing.",
    )
    parser.add_argument("--deck-spec-output", default="", help="Optional output path for the generated DeckSpec JSON.")
    parser.add_argument("--topic", default="", help="Topic or natural-language request used by the AI planner.")
    parser.add_argument("--outline-json", default="", help="Path to a V2 outline JSON file.")
    parser.add_argument("--outline-output", default="", help="Optional output path for the generated V2 outline JSON.")
    parser.add_argument(
        "--semantic-output", default="", help="Optional output path for the generated V2 semantic deck JSON."
    )
    parser.add_argument("--brief", default="", help="Optional extra business context passed to the AI planner.")
    parser.add_argument(
        "--brief-file", default="", help="Optional path to a text/markdown file with extra source material."
    )
    parser.add_argument(
        "--link",
        action="append",
        default=[],
        help="Optional external links. Repeatable for multiple URL inputs in batch-make.",
    )
    parser.add_argument(
        "--image-file",
        action="append",
        default=[],
        help="Optional local image file input for batch-make. Repeatable.",
    )
    parser.add_argument(
        "--attachment-file",
        action="append",
        default=[],
        help="Optional local attachment input for batch-make. Repeatable.",
    )
    parser.add_argument(
        "--structured-data-json",
        default="",
        help="Optional structured JSON input for batch-make.",
    )
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE_HINT, help="Target audience hint for the AI planner.")
    parser.add_argument("--llm-model", default="", help="Optional model override for the AI planner or clarifier.")
    parser.add_argument(
        "--llm-mode",
        default="agent_first",
        choices=("agent_first", "runtime_api"),
        help=(
            "LLM execution mode: agent_first (default, skip local API-key precheck) "
            "or runtime_api (strict endpoint/API-key validation)."
        ),
    )
    parser.add_argument("--theme", default="", help="Optional V2 theme name.")
    parser.add_argument("--language", default="zh-CN", help="Language used by V2 outline/deck generation.")
    parser.add_argument(
        "--generation-mode",
        default="deep",
        choices=("quick", "deep"),
        help=(
            "V2 generation mode: 'quick' skips strategic analysis, "
            "'deep' adds structured context and strategy analysis."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help=(
            "For v2-plan/batch-make: number of semantic candidates generated in parallel (>=1). "
            "The best candidate is selected automatically."
        ),
    )
    parser.add_argument("--author", default="AI Auto PPT", help="Author metadata used by V2 deck generation.")
    parser.add_argument("--plan-output", default="", help="Optional output path for the generated compiled deck JSON.")
    parser.add_argument(
        "--progress", action="store_true", help="Print stage progress to stderr for long-running generation flows."
    )
    parser.add_argument("--log-output", default="", help="Optional output path for the generated V2 render log.")
    parser.add_argument("--ppt-output", default="", help="Optional output path for the generated V2 PPTX.")
    parser.add_argument("--render-trace-output", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--review-output-dir", default="", help="Optional output directory for visual review artifacts."
    )
    parser.add_argument(
        "--browser", default="", help="Optional Edge/Chrome executable path for visual-draft screenshot."
    )
    parser.add_argument("--page-index", type=int, default=0, help="Zero-based page index for visual-draft.")
    parser.add_argument(
        "--layout-hint",
        default="auto",
        choices=("auto", "sales_proof", "risk_to_value", "executive_summary"),
        help="Layout hint for visual-draft.",
    )
    parser.add_argument(
        "--with-ai-review",
        action="store_true",
        help=(
            "For visual-draft: enable model-based visual review and one auto-revision "
            "round when score is below configured auto_revise_threshold. "
            "For batch-make: enable post-export review patch stage and emit review artifacts."
        ),
    )
    parser.add_argument(
        "--visual-rules-path", default="", help="Optional TOML path overriding visual-draft scoring rules."
    )
    parser.add_argument("--max-rounds", type=int, default=2, help="Maximum auto-fix review rounds for v2-iterate.")
    parser.add_argument(
        "--clarifier-state-file",
        default="",
        help="Optional JSON file used to resume or persist clarifier session state.",
    )
    parser.add_argument(
        "--min-slides",
        type=int,
        default=None,
        help=f"Optional AI planner lower bound for body pages (1-{MAX_BODY_CHAPTERS}).",
    )
    parser.add_argument(
        "--max-slides",
        type=int,
        default=None,
        help=f"Optional AI planner upper bound for body pages (1-{MAX_BODY_CHAPTERS}).",
    )
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated artifacts.")
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help=(
            "Run the V2 full pipeline (outline -> deck -> quality gate -> PPT render) "
            "with standardized output filenames."
        ),
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
        help=(
            "For ai-check only: run the healthcheck through the PPT render step and "
            "emit render quality summary fields."
        ),
    )
    parser.add_argument("--cover-title", default="", help=argparse.SUPPRESS)
    parser.add_argument("--template-path", default="", help=argparse.SUPPRESS)
    parser.add_argument("--reference-body-path", default="", help=argparse.SUPPRESS)
    parser.add_argument("--active-start", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument(
        "--onepage-strategy",
        default="auto",
        help="One-page strategy setting for onepage. Keep 'auto' to force AI strategy selection.",
    )
    parser.add_argument(
        "--delivery-target",
        default="auto",
        choices=("auto", "v2"),
        help="Delivery route preference: auto (default) or v2 semantic flow.",
    )
    parser.add_argument(
        "--isolate-output",
        action="store_true",
        help="For v2-make: write outputs into output-dir/runs/<run-id>.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run id used with --isolate-output. If omitted, a timestamp-based id is generated.",
    )
    parser.add_argument(
        "--pptmaster-root",
        default="",
        help="Absolute path to the external pptmaster repository root. Overrides SIE_PPTMASTER_ROOT.",
    )
    parser.add_argument(
        "--api-key", default="", help="AI API key override. If set, takes precedence over OPENAI_API_KEY env var."
    )
    parser.add_argument(
        "--base-url", default="", help="AI base URL override. If set, takes precedence over OPENAI_BASE_URL env var."
    )
    parser.add_argument(
        "--api-style",
        default="",
        choices=("responses", "chat_completions", "auto"),
        help="LLM API style override. If set, takes precedence over SIE_AUTOPPT_LLM_API_STYLE env var.",
    )
    return parser


__all__ = ["RECOMMENDED_WORKFLOW_HELP", "build_main_parser"]
