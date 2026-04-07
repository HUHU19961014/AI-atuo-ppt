from __future__ import annotations

import argparse
import datetime
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PROJECT_ROOT / "assets" / "templates" / "sie_template.pptx"
DEFAULT_REFERENCE_BODY = PROJECT_ROOT / "input" / "reference_body_style.pptx"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "projects" / "visual_review"
CLI_ENTRY = PROJECT_ROOT / "tools" / "sie_autoppt_cli.py"


@dataclass(frozen=True)
class VisualReviewCase:
    name: str
    label: str
    html: Path
    focus: tuple[str, ...]


CASES = (
    VisualReviewCase(
        name="uat_plan_sample",
        label="General business deck",
        html=PROJECT_ROOT / "input" / "uat_plan_sample.html",
        focus=(
            "Check cover, directory, body, and ending slide order.",
            "Check active directory highlight changes by chapter.",
            "Check body title and subtitle placement.",
        ),
    ),
    VisualReviewCase(
        name="architecture_program_sample",
        label="Architecture and governance test deck",
        html=PROJECT_ROOT / "input" / "architecture_program_sample.html",
        focus=(
            "Check architecture-heavy content still maps to the right layouts.",
            "Check directory image assets remain intact after generation.",
            "Check architecture, process, and governance pages stay readable.",
        ),
    ),
    VisualReviewCase(
        name="default_erp_blueprint",
        label="ERP architecture, process, and governance",
        html=PROJECT_ROOT / "input" / "default_erp_blueprint.html",
        focus=(
            "Check solution_architecture, process_flow, and org_governance layouts.",
            "Check shapes, color blocks, and text for overlap.",
            "Check governance footer text remains readable.",
        ),
    ),
)


def build_review_dir(output_root: Path) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"visual_review_{timestamp}"


def run_cli(case: VisualReviewCase, *, template: Path, reference_body: Path, review_dir: Path) -> tuple[Path, Path]:
    command = [
        sys.executable,
        str(CLI_ENTRY),
        "--template",
        str(template),
        "--html",
        str(case.html),
        "--reference-body",
        str(reference_body),
        "--output-name",
        f"VisualReview_{case.name}",
        "--output-dir",
        str(review_dir),
        "--chapters",
        "3",
        "--active-start",
        "0",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate visual review case {case.name}: {(result.stderr or result.stdout).strip()}")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"Unexpected CLI output for {case.name}: {result.stdout!r}")
    return Path(lines[0]), Path(lines[1])


def export_preview_if_supported(pptx_path: Path, preview_dir: Path) -> str:
    system = platform.system().lower()
    preview_dir.mkdir(parents=True, exist_ok=True)

    if system == "windows":
        script = (
            "$pptPath = Resolve-Path $args[0];"
            "$imgPath = $args[1];"
            "$ppt = New-Object -ComObject PowerPoint.Application;"
            "$ppt.Visible = -1;"
            "$pres = $ppt.Presentations.Open($pptPath.Path, $false, $false, $false);"
            "$pres.Slides[1].Export($imgPath, 'PNG', 1920, 1080);"
            "$pres.Close();"
            "$ppt.Quit();"
        )
        output = preview_dir / "slide1.png"
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script, str(pptx_path), str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        return str(output if output.exists() else "preview export skipped")

    libreoffice = "soffice"
    output = preview_dir / "slide1.png"
    result = subprocess.run(
        [libreoffice, "--headless", "--convert-to", "png", "--outdir", str(preview_dir), str(pptx_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and output.exists():
        return str(output)
    return "preview export unavailable on this platform"


def write_summary(review_dir: Path, rows: list[tuple[VisualReviewCase, Path, Path, str]]) -> Path:
    lines = [
        "# Visual Review Batch",
        "",
        f"Generated at: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"Output dir: {review_dir}",
        "",
        "Global checklist:",
        "- Cover, directory, body, and ending slides are in the right order.",
        "- Active directory highlight is correct.",
        "- Template visual assets are preserved.",
        "- No obvious text overflow, overlap, or misalignment.",
        "- Both _QA.txt and _QA.json exist.",
        "",
    ]
    for case, report_path, pptx_path, preview_note in rows:
        lines.extend(
            [
                f"## {case.name}",
                "",
                f"Label: {case.label}",
                "",
                f"PPT: {pptx_path}",
                f"QA.txt: {report_path}",
                f"QA.json: {report_path.with_suffix('.json')}",
                f"Preview: {preview_note}",
                "Focus checks:",
                *[f"- {item}" for item in case.focus],
                "",
            ]
        )
    summary_path = review_dir / "VISUAL_REVIEW_CHECKLIST.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a cross-platform visual review batch.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--reference-body", default=str(DEFAULT_REFERENCE_BODY))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template = Path(args.template).resolve()
    reference_body = Path(args.reference_body).resolve()
    output_root = Path(args.output_root).resolve()
    review_dir = build_review_dir(output_root)
    review_dir.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[VisualReviewCase, Path, Path, str]] = []
    for case in CASES:
        report_path, pptx_path = run_cli(case, template=template, reference_body=reference_body, review_dir=review_dir)
        preview_note = export_preview_if_supported(pptx_path, review_dir / case.name)
        rows.append((case, report_path, pptx_path, preview_note))

    summary_path = write_summary(review_dir, rows)
    print(str(review_dir))
    print(str(summary_path))


if __name__ == "__main__":
    main()
