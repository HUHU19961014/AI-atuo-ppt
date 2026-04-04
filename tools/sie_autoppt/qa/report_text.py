from pathlib import Path

from .models import QaResult


def _format_font_token(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def format_qa_text(result: QaResult) -> str:
    checks = result.checks
    metrics = result.metrics
    lines = [
        "SIE AutoPPT QA Report",
        f"file: {result.file}",
        f"slides: {result.slides}",
        f"template_name: {result.template_name}",
        f"template_manifest: {result.template_manifest_path}",
        f"template_manifest_version: {result.template_manifest_version}",
        f"check_ending_last: {checks.ending_last}",
        f"expected_directory_pages: {result.expected_directory_pages}",
        f"actual_directory_pages:   {result.actual_directory_pages}",
    ]
    semantic_patterns = result.semantic_patterns
    if semantic_patterns:
        lines.append(f"semantic_patterns: {semantic_patterns}")
    theme_font_token = _format_font_token(result.expected_theme_title_font_pt)
    directory_font_token = _format_font_token(result.expected_directory_title_font_pt)
    lines.extend(
        [
            f"check_theme_title_font_{theme_font_token}: {checks.theme_title_font}",
            f"check_directory_title_font_{directory_font_token}: {checks.directory_title_font}",
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
