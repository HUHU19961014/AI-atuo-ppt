import argparse
from pathlib import Path

from .config import DEFAULT_HTML, DEFAULT_OUTPUT_DIR, DEFAULT_OUTPUT_PREFIX, DEFAULT_REFERENCE_BODY, DEFAULT_TEMPLATE, MAX_BODY_CHAPTERS
from .generator import generate_ppt
from .qa import write_qa_report


def main():
    parser = argparse.ArgumentParser(description="Generate SIE template-driven PPT from HTML.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to template PPTX.")
    parser.add_argument("--html", default=str(DEFAULT_HTML), help="Path to source HTML file.")
    parser.add_argument(
        "--reference-body",
        default=str(DEFAULT_REFERENCE_BODY),
        help="Optional reference PPTX used as a body slide style library.",
    )
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for generated PPT and QA files.")
    parser.add_argument("--chapters", type=int, default=3, help=f"Number of body chapters to generate (1-{MAX_BODY_CHAPTERS}).")
    parser.add_argument("--active-start", type=int, default=0, help="Directory active chapter start index (0-based).")
    args = parser.parse_args()

    out, pattern_ids, chapter_lines = generate_ppt(
        template_path=Path(args.template),
        html_path=Path(args.html),
        reference_body_path=Path(args.reference_body) if args.reference_body else None,
        output_prefix=args.output_name,
        chapters=args.chapters,
        active_start=args.active_start,
        output_dir=Path(args.output_dir),
    )
    report = write_qa_report(
        out,
        len(pattern_ids),
        pattern_ids=pattern_ids,
        chapter_lines=chapter_lines,
    )
    print(str(report))
    print(str(out))


if __name__ == "__main__":
    main()
