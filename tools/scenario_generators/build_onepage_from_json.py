from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

try:
    from sie_autoppt.llm_openai import OpenAIConfigurationError, OpenAIResponsesError
    from sie_autoppt.structure_service import StructureGenerationRequest, generate_structure_with_ai

    from .sie_onepage_designer import (
        BulletItem,
        LawRow,
        OnePageBrief,
        TextFragment,
        build_onepage_brief_from_structure,
        build_onepage_slide,
    )
except ImportError:
    import sys

    # Add the `tools/` directory so `sie_autoppt` and `scenario_generators` are importable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sie_autoppt.llm_openai import OpenAIConfigurationError, OpenAIResponsesError
    from sie_autoppt.structure_service import StructureGenerationRequest, generate_structure_with_ai

    from scenario_generators.sie_onepage_designer import (
        BulletItem,
        LawRow,
        OnePageBrief,
        TextFragment,
        build_onepage_brief_from_structure,
        build_onepage_slide,
    )


def _parse_text_fragment(payload: dict[str, object]) -> TextFragment:
    color_raw = payload.get("color")
    color = tuple(color_raw) if isinstance(color_raw, list) and len(color_raw) == 3 else None
    return TextFragment(
        text=str(payload.get("text", "")),
        bold=bool(payload.get("bold", False)),
        color=color,  # type: ignore[arg-type]
        new_paragraph=bool(payload.get("new_paragraph", False)),
    )


def _parse_law_row(payload: dict[str, object]) -> LawRow:
    runs = tuple(_parse_text_fragment(item) for item in payload.get("runs", []))
    return LawRow(
        number=str(payload.get("number", "")),
        title=str(payload.get("title", "")),
        badge=str(payload.get("badge", "")),
        badge_red=bool(payload.get("badge_red", False)),
        runs=runs,
    )


def _parse_bullet_item(payload: dict[str, object]) -> BulletItem:
    return BulletItem(label=str(payload.get("label", "")), body=str(payload.get("body", "")))


def load_brief_from_json(path: Path) -> OnePageBrief:
    payload = json.loads(path.read_text(encoding="utf-8"))
    layout_overrides = payload.get("layout_overrides")
    if not isinstance(layout_overrides, dict):
        layout_overrides = None
    typography_overrides = payload.get("typography_overrides")
    if not isinstance(typography_overrides, dict):
        typography_overrides = None
    return OnePageBrief(
        title=str(payload["title"]),
        kicker=str(payload.get("kicker", "")),
        summary_fragments=tuple(_parse_text_fragment(item) for item in payload.get("summary_fragments", [])),
        law_rows=tuple(_parse_law_row(item) for item in payload.get("law_rows", [])),
        right_kicker=str(payload.get("right_kicker", "")),
        right_title=str(payload.get("right_title", "")),
        process_steps=tuple(str(step) for step in payload.get("process_steps", [])),
        right_bullets=tuple(_parse_bullet_item(item) for item in payload.get("right_bullets", [])),
        strategy_title=str(payload.get("strategy_title", "")),
        strategy_fragments=tuple(_parse_text_fragment(item) for item in payload.get("strategy_fragments", [])),
        footer=str(payload.get("footer", "STRICTLY CONFIDENTIAL | 2026 SIE One-page Brief")),
        page_no=str(payload.get("page_no", "01")),
        required_terms=tuple(str(term) for term in payload.get("required_terms", [])),
        variant=str(payload.get("variant", "auto")),
        layout_strategy=str(payload.get("layout_strategy", "auto")),
        reference_request=str(payload.get("reference_request", "")),
        banned_phrases=tuple(str(term) for term in payload.get("banned_phrases", [])),
        layout_overrides=layout_overrides,
        typography_overrides=typography_overrides,
    )


def _brief_to_plain_text(brief: OnePageBrief) -> str:
    parts = [
        brief.title,
        brief.kicker,
        brief.right_kicker,
        brief.right_title,
        brief.strategy_title,
        " ".join(fragment.text for fragment in brief.summary_fragments),
        " ".join(row.title for row in brief.law_rows),
        " ".join(fragment.text for row in brief.law_rows for fragment in row.runs),
        " ".join(brief.process_steps),
        " ".join(item.label + item.body for item in brief.right_bullets),
        " ".join(fragment.text for fragment in brief.strategy_fragments),
    ]
    return "\n".join(part for part in parts if part).strip()


def build_ai_brief_from_source_text(
    *,
    topic: str,
    source_text: str,
    model: str | None,
    sections: int = 3,
) -> OnePageBrief:
    request = StructureGenerationRequest(topic=topic.strip(), brief=source_text.strip(), sections=sections)
    structure_result = generate_structure_with_ai(request, model=model)
    return build_onepage_brief_from_structure(
        structure_result.structure,
        topic=topic.strip(),
        layout_strategy="auto",
    )


def apply_ai_content_reframe(brief: OnePageBrief, model: str | None, sections: int = 3) -> OnePageBrief:
    ai_brief = build_ai_brief_from_source_text(
        topic=brief.title,
        source_text=_brief_to_plain_text(brief),
        model=model,
        sections=sections,
    )
    return replace(
        ai_brief,
        footer=brief.footer,
        page_no=brief.page_no,
        required_terms=brief.required_terms or ai_brief.required_terms,
        reference_request=brief.reference_request,
        banned_phrases=brief.banned_phrases,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a one-page SIE PPT in AI-mandatory mode (no fallback paths)."
    )
    parser.add_argument("--brief-json", help="Path to JSON brief file (UTF-8).")
    parser.add_argument("--source-text-file", help="Path to UTF-8 source text used for AI content planning.")
    parser.add_argument("--topic", help="Topic title used when --source-text-file is provided.")
    parser.add_argument("--output", required=True, help="Output PPTX path.")
    parser.add_argument(
        "--ai-mode",
        choices=("host", "openai", "off"),
        default="openai",
        help="AI execution mode. Mandatory setting is openai.",
    )
    parser.add_argument(
        "--ai-content",
        choices=("off", "on"),
        default="on",
        help="Enable AI content planning. Mandatory setting is on.",
    )
    parser.add_argument(
        "--ai-strategy",
        choices=("off", "on"),
        default="on",
        help="Enable AI layout strategy selection. Mandatory setting is on.",
    )
    parser.add_argument("--ai-model", default=None, help="Override AI model id.")
    parser.add_argument("--skip-review", action="store_true", help="Skip post-generation review.")

    args = parser.parse_args()
    if not args.brief_json and not args.source_text_file:
        parser.error("Either --brief-json or --source-text-file is required.")
    if args.source_text_file and not args.topic:
        parser.error("--topic is required when using --source-text-file.")

    # Enforce AI-only behavior explicitly.
    if args.ai_mode != "openai":
        parser.error("AI mandatory mode requires --ai-mode openai.")
    if args.ai_content != "on":
        parser.error("AI mandatory mode requires --ai-content on.")
    if args.ai_strategy != "on":
        parser.error("AI mandatory mode requires --ai-strategy on.")
    return args


def main() -> None:
    args = parse_args()

    try:
        if args.source_text_file:
            source_text = Path(args.source_text_file).resolve().read_text(encoding="utf-8")
            brief = build_ai_brief_from_source_text(
                topic=str(args.topic),
                source_text=source_text,
                model=args.ai_model,
                sections=3,
            )
        else:
            brief = load_brief_from_json(Path(args.brief_json).resolve())
            brief = apply_ai_content_reframe(brief, model=args.ai_model, sections=3)
    except (OpenAIConfigurationError, OpenAIResponsesError, ValueError) as exc:
        raise SystemExit(f"AI mandatory mode failed during content planning: {exc}") from exc

    try:
        built, review_path, score_path, score = build_onepage_slide(
            brief,
            output_path=Path(args.output).resolve(),
            export_review=not args.skip_review,
            model=args.ai_model,
            require_ai_strategy=True,
        )
    except (OpenAIConfigurationError, OpenAIResponsesError, ValueError) as exc:
        raise SystemExit(f"AI mandatory mode failed during layout/render planning: {exc}") from exc

    print(str(built))
    print(str(review_path) if review_path else "")
    print(str(score_path))
    print(f"score={score.total}, level={score.level}, variant={score.selected_variant}")


if __name__ == "__main__":
    main()
