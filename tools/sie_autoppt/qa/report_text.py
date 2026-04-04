from pathlib import Path

from .models import QaResult


def format_qa_text(result: QaResult) -> str:
    checks = result.checks
    metrics = result.metrics
    lines = [
        "SIE AutoPPT QA Report",
        f"file: {result.file}",
        f"slides: {result.slides}",
        f"check_ending_last: {checks.ending_last}",
        f"expected_directory_pages: {result.expected_directory_pages}",
        f"actual_directory_pages:   {result.actual_directory_pages}",
    ]
    semantic_patterns = result.semantic_patterns
    if semantic_patterns:
        lines.append(f"semantic_patterns: {semantic_patterns}")
    lines.extend(
        [
            f"check_theme_title_font_40: {checks.theme_title_font_40}",
            f"check_directory_title_font_24: {checks.directory_title_font_24}",
            f"check_directory_assets_preserved: {checks.directory_assets_preserved}",
            f"overflow_risk_boxes: {metrics.overflow_risk_boxes}",
        ]
    )
    for note in result.notes:
        lines.append(f"note: {note}")
    return "\n".join(lines)


def write_qa_text_report(result: QaResult, pptx_path: Path) -> Path:
    report = pptx_path.with_name(pptx_path.stem + "_QA.txt")
    report.write_text(format_qa_text(result), encoding="utf-8")
    return report
