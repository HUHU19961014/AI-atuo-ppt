from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_OUTPUT_PREFIX
from .inputs.source_text import extract_source_text
from .types import JSONDict


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
        parser.error(
            "--min-slides and --max-slides are only supported for AI generation workflows such as make, v2-plan, v2-make, and ai-check."
        )
    if uses_exact_chapters and uses_ai_range and is_ai_command:
        parser.error("--chapters cannot be combined with --min-slides/--max-slides for AI planning.")
    if args.min_slides and args.max_slides and args.min_slides > args.max_slides:
        parser.error("--min-slides cannot be greater than --max-slides.")


def build_template_output_stem(output_name: str) -> str:
    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in output_name.strip())
    return safe_name.strip("._") or DEFAULT_OUTPUT_PREFIX


def write_json_artifact(path: Path, payload: JSONDict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def emit_progress(enabled: bool, stage: str, detail: str) -> None:
    if not enabled:
        return
    print(f"[progress] {stage}: {detail}", file=sys.stderr)
