from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

try:
    from tools.sie_autoppt.sample_registry import VisualReviewCaseConfig, load_visual_review_cases
    from tools.sie_autoppt.v2.ppt_engine import generate_ppt
    from tools.sie_autoppt.v2.visual_review import export_slide_previews
except ImportError:  # pragma: no cover - script mode adds tools/ to sys.path instead of repo root
    from sie_autoppt.sample_registry import VisualReviewCaseConfig, load_visual_review_cases
    from sie_autoppt.v2.ppt_engine import generate_ppt
    from sie_autoppt.v2.visual_review import export_slide_previews


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "projects" / "visual_review"
VisualReviewCase = VisualReviewCaseConfig


def build_review_dir(output_root: Path) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"visual_review_{timestamp}"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: VisualReviewCase, *, review_dir: Path) -> tuple[Path, Path, Path, Path, str]:
    if not case.deck_json.exists():
        raise FileNotFoundError(f"Deck JSON not found for visual review case {case.name}: {case.deck_json}")

    case_dir = review_dir / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = case_dir / "generated.pptx"
    log_path = case_dir / "render.log.txt"

    render_result = generate_ppt(
        _load_json(case.deck_json),
        output_path=pptx_path,
        log_path=log_path,
    )
    warnings_path = render_result.warnings_path or (case_dir / "warnings.json")
    rewrite_log_path = render_result.rewrite_log_path or (case_dir / "rewrite_log.json")
    preview_dir = case_dir / "previews"
    try:
        previews = export_slide_previews(render_result.output_path, preview_dir)
        preview_note = str(preview_dir) if previews else "preview export unavailable; content-only manual review"
    except RuntimeError:
        preview_note = "preview export failed on this machine; content-only manual review"
    return warnings_path, rewrite_log_path, render_result.output_path, log_path, preview_note


def write_summary(review_dir: Path, rows: list[tuple[VisualReviewCase, Path, Path, Path, Path, str]]) -> Path:
    lines = [
        "# Visual Review Batch (V2)",
        "",
        f"Generated at: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"Output dir: {review_dir}",
        "",
        "Global checklist:",
        "- Slides render successfully from the current V2 deck JSON.",
        "- Opening, middle, and closing pages all remain presentation-ready.",
        "- No obvious text overflow, overlap, or misalignment.",
        "- warnings.json and rewrite_log.json exist for each case.",
        "- Preview export should be checked when available; otherwise review is content-only.",
        "",
    ]
    for case, warnings_path, rewrite_log_path, pptx_path, log_path, preview_note in rows:
        lines.extend(
            [
                f"## {case.name}",
                "",
                f"Label: {case.label}",
                "",
                f"Input deck: {case.deck_json}",
                f"PPT: {pptx_path}",
                f"Render log: {log_path}",
                f"Warnings: {warnings_path}",
                f"Rewrite log: {rewrite_log_path}",
                f"Preview: {preview_note}",
                f"Baseline review: {case.baseline_review}" if case.baseline_review else "Baseline review: none",
                "Focus checks:",
                *[f"- {item}" for item in case.focus],
                "",
            ]
        )
    summary_path = review_dir / "VISUAL_REVIEW_CHECKLIST.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a no-AI V2 visual review batch from bundled deck JSON cases.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    review_dir = build_review_dir(output_root)
    review_dir.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[VisualReviewCase, Path, Path, Path, Path, str]] = []
    for case in load_visual_review_cases():
        warnings_path, rewrite_log_path, pptx_path, log_path, preview_note = run_case(case, review_dir=review_dir)
        rows.append((case, warnings_path, rewrite_log_path, pptx_path, log_path, preview_note))

    summary_path = write_summary(review_dir, rows)
    print(str(review_dir))
    print(str(summary_path))


if __name__ == "__main__":
    main()
