from __future__ import annotations

import argparse

from .clarifier import DEFAULT_AUDIENCE_HINT
from .config import DEFAULT_OUTPUT_DIR, DEFAULT_OUTPUT_PREFIX, MAX_BODY_CHAPTERS

RECOMMENDED_WORKFLOW_HELP = (
    "Recommended workflows:\n"
    "  onepage --topic ...   single SIE body page with adaptive business layout\n"
    "  sie-render --topic ... or --structure-json ...  actual SIE template render with AI planning\n"
    "  make --topic ...     semantic V2 full generation\n"
    "  review --deck-json   one-pass visual review alias for v2-review\n"
    "  iterate --deck-json  multi-round review alias for v2-iterate\n"
    "  visual-draft --deck-spec-json ...  HTML visual draft + scoring before PPTX\n"
    "Advanced commands:\n"
    "  onepage, sie-render, v2-plan, v2-render, v2-compile, v2-patch, v2-outline, v2-make, v2-review, v2-iterate, clarify, clarify-web, ai-check, visual-draft\n"
    "Legacy HTML/template generation commands remain retired; use sie-render for actual SIE template delivery.\n"
    "Note: All generation commands require a reachable AI endpoint (OPENAI_API_KEY + OPENAI_BASE_URL)."
)


def build_main_parser() -> argparse.ArgumentParser:
    """Build and return the CLI parser used by `sie-autoppt` commands."""
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
        help="Primary commands: make, review, iterate. Use onepage for a single SIE body slide, or sie-render for the actual SIE PPTX template path.",
    )
    parser.add_argument("--template", default="", help=argparse.SUPPRESS)
    parser.add_argument("--deck-json", default="", help="Path to a compiled deck JSON or V2 semantic deck JSON, depending on the command.")
    parser.add_argument("--patch-json", default="", help="Path to patch JSON used by v2-patch for incremental deck edits.")
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
    parser.add_argument("--generation-mode", default="deep", choices=("quick", "deep"), help="V2 generation mode: 'quick' skips strategic analysis, 'deep' adds structured context and strategy analysis.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="For v2-plan only: number of semantic deck candidates to generate in parallel (>=1).",
    )
    parser.add_argument("--author", default="AI Auto PPT", help="Author metadata used by V2 deck generation.")
    parser.add_argument("--plan-output", default="", help="Optional output path for the generated compiled deck JSON.")
    parser.add_argument("--progress", action="store_true", help="Print stage progress to stderr for long-running generation flows.")
    parser.add_argument("--log-output", default="", help="Optional output path for the generated V2 render log.")
    parser.add_argument("--ppt-output", default="", help="Optional output path for the generated V2 PPTX.")
    parser.add_argument("--render-trace-output", default="", help="Optional output path for the actual-template render trace JSON.")
    parser.add_argument("--review-output-dir", default="", help="Optional output directory for visual review artifacts.")
    parser.add_argument("--browser", default="", help="Optional Edge/Chrome executable path for visual-draft screenshot.")
    parser.add_argument("--page-index", type=int, default=0, help="Zero-based page index for visual-draft.")
    parser.add_argument("--layout-hint", default="auto", choices=("auto", "sales_proof", "risk_to_value", "executive_summary"), help="Layout hint for visual-draft.")
    parser.add_argument("--with-ai-review", action="store_true", help="For visual-draft: enable model-based visual review and one auto-revision round when score is below configured auto_revise_threshold.")
    parser.add_argument("--visual-rules-path", default="", help="Optional TOML path overriding visual-draft scoring rules.")
    parser.add_argument("--max-rounds", type=int, default=2, help="Maximum auto-fix review rounds for v2-iterate.")
    parser.add_argument("--clarifier-state-file", default="", help="Optional JSON file used to resume or persist clarifier session state.")
    parser.add_argument("--min-slides", type=int, default=None, help=f"Optional AI planner lower bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--max-slides", type=int, default=None, help=f"Optional AI planner upper bound for body pages (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated artifacts.")
    parser.add_argument("--full-pipeline", action="store_true", help="Run the V2 full pipeline (outline -> deck -> quality gate -> PPT render) with standardized output filenames.")
    parser.add_argument("--chapters", type=int, default=None, help=f"Optional exact number of body chapters to generate (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--host", default="127.0.0.1", help="Host used by local web services such as clarify-web.")
    parser.add_argument("--port", type=int, default=8765, help="Port used by local web services such as clarify-web.")
    parser.add_argument("--with-render", action="store_true", help="For ai-check only: run the healthcheck through the PPT render step and emit render quality summary fields.")
    parser.add_argument("--cover-title", default="", help="Optional cover title override for sie-render.")
    parser.add_argument("--template-path", default="", help="Optional PPTX template override for sie-render.")
    parser.add_argument("--reference-body-path", default="", help="Optional reference body PPTX override for sie-render.")
    parser.add_argument("--active-start", type=int, default=0, help="Actual-template directory highlight offset used by sie-render.")
    parser.add_argument("--onepage-strategy", default="auto", help="Optional one-page strategy override. Default is auto.")
    parser.add_argument(
        "--delivery-target",
        default="auto",
        choices=("auto", "v2", "sie-template"),
        help="Delivery route preference: auto (default), v2 semantic flow, or sie-template actual template flow.",
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
    parser.add_argument("--api-key", default="", help="AI API key override. If set, takes precedence over OPENAI_API_KEY env var.")
    parser.add_argument("--base-url", default="", help="AI base URL override. If set, takes precedence over OPENAI_BASE_URL env var.")
    parser.add_argument(
        "--api-style",
        default="",
        choices=("responses", "chat_completions", "auto"),
        help="LLM API style override. If set, takes precedence over SIE_AUTOPPT_LLM_API_STYLE env var.",
    )
    return parser


__all__ = ["RECOMMENDED_WORKFLOW_HELP", "build_main_parser"]
