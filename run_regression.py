from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.review_scoring import ReviewScore, evaluate_review, summarize_reviews
from tools.sie_autoppt.v2.ppt_engine import generate_ppt
from tools.sie_autoppt.v2.schema import validate_deck_payload


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REGRESSION_DIR = PROJECT_ROOT / "regression"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "v2_regression"


@dataclass(frozen=True)
class RegressionCaseResult:
    case: str
    success: bool
    ppt_generated: bool
    warning_count: int
    high_count: int
    error_count: int
    review_required: bool
    slides: int
    duration: float
    pptx_path: str
    log_path: str = ""
    warnings_path: str = ""
    auto_score: int = 100
    auto_level: str = "excellent"
    score: int | None = None
    score_level: str = ""
    error: str = ""


@dataclass(frozen=True)
class RegressionReviewResult:
    case: str
    score: int
    level: str
    conclusion: str
    review_path: str


def discover_regression_cases(regression_dir: Path) -> list[Path]:
    if not regression_dir.exists():
        raise FileNotFoundError(f"Regression directory not found: {regression_dir}")
    return sorted(path for path in regression_dir.iterdir() if path.is_dir() and (path / "deck.json").exists())


def _case_output_dir(output_root: Path, case_name: str) -> Path:
    return output_root / case_name


def _read_quality_gate_payload(warnings_path: Path) -> dict[str, Any]:
    if not warnings_path.exists():
        return {
            "passed": False,
            "review_required": False,
            "summary": {"warning_count": 0, "high_count": 0, "error_count": 0},
            "auto_score": 0,
            "auto_level": "unavailable",
        }
    return json.loads(warnings_path.read_text(encoding="utf-8"))


def run_case(case_dir: Path, output_root: Path) -> RegressionCaseResult:
    started_at = time.perf_counter()
    case_name = case_dir.name
    deck_path = case_dir / "deck.json"
    case_output_dir = _case_output_dir(output_root, case_name)
    case_output_dir.mkdir(parents=True, exist_ok=True)

    pptx_path = case_output_dir / "generated.pptx"
    log_path = case_output_dir / "log.txt"
    warnings_path = case_output_dir / "warnings.json"

    payload = json.loads(deck_path.read_text(encoding="utf-8"))
    slides = 0
    validation_error = ""

    try:
        validated = validate_deck_payload(payload)
        slides = len(validated.deck.slides)
    except Exception as exc:
        slides = 0
        validation_error = str(exc).strip()

    try:
        render_result = generate_ppt(payload, output_path=pptx_path, log_path=log_path)
        duration = round(time.perf_counter() - started_at, 2)
        return RegressionCaseResult(
            case=case_name,
            success=render_result.error_count == 0 and render_result.output_path.exists(),
            ppt_generated=render_result.output_path.exists(),
            warning_count=render_result.warning_count,
            high_count=render_result.high_count,
            error_count=render_result.error_count,
            review_required=render_result.review_required,
            slides=render_result.slide_count,
            duration=duration,
            pptx_path=str(render_result.output_path),
            log_path=str(render_result.log_path or log_path),
            warnings_path=str(render_result.warnings_path or warnings_path),
            auto_score=render_result.auto_score,
            auto_level=render_result.auto_level,
        )
    except Exception as exc:
        duration = round(time.perf_counter() - started_at, 2)
        gate_payload = _read_quality_gate_payload(warnings_path)
        summary = gate_payload.get("summary", {})
        combined_error = (
            f"schema_validation_error={validation_error}; render_error={exc}"
            if validation_error
            else str(exc)
        )
        return RegressionCaseResult(
            case=case_name,
            success=False,
            ppt_generated=pptx_path.exists(),
            warning_count=int(summary.get("warning_count", 0)),
            high_count=int(summary.get("high_count", 0)),
            error_count=int(summary.get("error_count", 0)),
            review_required=bool(gate_payload.get("review_required", False)),
            slides=slides,
            duration=duration,
            pptx_path=str(pptx_path),
            log_path=str(log_path),
            warnings_path=str(warnings_path),
            auto_score=int(gate_payload.get("auto_score", 0)),
            auto_level=str(gate_payload.get("auto_level", "unavailable")),
            error=combined_error,
        )


def collect_review_scores(case_dirs: list[Path]) -> tuple[list[RegressionReviewResult], dict[str, ReviewScore], list[str]]:
    review_results: list[RegressionReviewResult] = []
    review_scores_by_case: dict[str, ReviewScore] = {}
    review_errors: list[str] = []

    for case_dir in case_dirs:
        review_path = case_dir / "review.md"
        if not review_path.exists():
            continue
        try:
            review_score = evaluate_review(review_path)
        except Exception as exc:
            review_errors.append(f"{case_dir.name}: {exc}")
            continue
        review_scores_by_case[case_dir.name] = review_score
        review_results.append(
            RegressionReviewResult(
                case=case_dir.name,
                score=review_score.total_score,
                level=review_score.rating,
                conclusion=review_score.conclusion,
                review_path=str(review_path),
            )
        )

    return review_results, review_scores_by_case, review_errors


def merge_review_scores(results: list[RegressionCaseResult], review_scores_by_case: dict[str, ReviewScore]) -> list[RegressionCaseResult]:
    merged: list[RegressionCaseResult] = []
    for result in results:
        review_score = review_scores_by_case.get(result.case)
        if review_score is None:
            merged.append(result)
            continue
        merged.append(
            RegressionCaseResult(
                case=result.case,
                success=result.success,
                ppt_generated=result.ppt_generated,
                warning_count=result.warning_count,
                high_count=result.high_count,
                error_count=result.error_count,
                review_required=result.review_required,
                slides=result.slides,
                duration=result.duration,
                pptx_path=result.pptx_path,
                log_path=result.log_path,
                warnings_path=result.warnings_path,
                auto_score=result.auto_score,
                auto_level=result.auto_level,
                score=review_score.total_score,
                score_level=review_score.rating,
                error=result.error,
            )
        )
    return merged


def _build_worst_cases(results: list[RegressionCaseResult], limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(
        results,
        key=lambda item: (
            item.success,
            item.ppt_generated,
            -item.error_count,
            -item.high_count,
            item.auto_score,
            -item.warning_count,
        ),
    )
    worst_cases: list[dict[str, Any]] = []
    for item in ranked[:limit]:
        reasons: list[str] = []
        if not item.ppt_generated:
            reasons.append("PPT not generated")
        if item.error_count > 0:
            reasons.append(f"{item.error_count} error")
        if item.high_count > 0:
            reasons.append(f"{item.high_count} high")
        if item.review_required:
            reasons.append("manual review required")
        if not reasons:
            reasons.append("lower auto score")
        worst_cases.append(
            {
                "case": item.case,
                "auto_score": item.auto_score,
                "score_level": item.score_level,
                "reason": "; ".join(reasons),
            }
        )
    return worst_cases


def write_summary(
    results: list[RegressionCaseResult],
    output_root: Path,
    review_results: list[RegressionReviewResult] | None = None,
    review_errors: list[str] | None = None,
) -> Path:
    review_results = review_results or []
    review_errors = review_errors or []
    summary_path = output_root / "regression_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    total_cases = len(results)
    success_count = sum(1 for item in results if item.success)
    review_required_count = sum(1 for item in results if item.review_required)
    human_review_summary = summarize_reviews(
        [
            ReviewScore(
                review_path=Path(item.review_path),
                scores=(),
                total_score=item.score,
                rating=item.level,
                conclusion=item.conclusion,
            )
            for item in review_results
        ]
    )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_cases": total_cases,
        "success_count": success_count,
        "failed_count": total_cases - success_count,
        "success_rate": round(success_count / total_cases, 4) if total_cases else 0.0,
        "average_warning_count": round(sum(item.warning_count for item in results) / total_cases, 2) if total_cases else 0.0,
        "average_high_count": round(sum(item.high_count for item in results) / total_cases, 2) if total_cases else 0.0,
        "review_required_count": review_required_count,
        "review_required_rate": round(review_required_count / total_cases, 4) if total_cases else 0.0,
        "average_auto_score": round(sum(item.auto_score for item in results) / total_cases, 2) if total_cases else 0.0,
        "worst_cases": _build_worst_cases(results),
        "review_results": [asdict(item) for item in review_results],
        "review_errors": review_errors,
        "human_review_summary": human_review_summary.to_dict() if human_review_summary else None,
        "results": [asdict(item) for item in results],
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def write_report(
    results: list[RegressionCaseResult],
    output_root: Path,
    review_results: list[RegressionReviewResult],
    review_errors: list[str],
) -> Path:
    report_path = output_root / "regression_report.md"
    total_cases = len(results)
    success_count = sum(1 for item in results if item.success)
    review_required_count = sum(1 for item in results if item.review_required)
    average_warning_count = round(sum(item.warning_count for item in results) / total_cases, 2) if total_cases else 0.0
    worst_cases = _build_worst_cases(results)
    review_summary = summarize_reviews(
        [
            ReviewScore(
                review_path=Path(item.review_path),
                scores=(),
                total_score=item.score,
                rating=item.level,
                conclusion=item.conclusion,
            )
            for item in review_results
        ]
    )

    lines = [
        "# Regression Report",
        "",
        "## Overview",
        "",
        f"- Total cases: {total_cases}",
        f"- Success rate: {success_count}/{total_cases} ({(success_count / total_cases * 100):.1f}%)" if total_cases else "- Success rate: 0/0 (0.0%)",
        f"- Average warnings: {average_warning_count}",
        f"- Manual review ratio: {review_required_count}/{total_cases} ({(review_required_count / total_cases * 100):.1f}%)"
        if total_cases
        else "- Manual review ratio: 0/0 (0.0%)",
        "",
        "## Worst Cases",
        "",
    ]

    if worst_cases:
        for item in worst_cases:
            lines.append(f"- {item['case']}: {item['reason']} (auto_score={item['auto_score']})")
    else:
        lines.append("- None")

    lines.extend(["", "## Case Details", ""])
    for item in results:
        detail = (
            f"- {item.case}: success={item.success}, ppt_generated={item.ppt_generated}, "
            f"warnings={item.warning_count}, high={item.high_count}, errors={item.error_count}, "
            f"review_required={item.review_required}, slides={item.slides}, auto_score={item.auto_score}"
        )
        if item.score is not None:
            detail += f", human_score={item.score}({item.score_level})"
        if item.error:
            detail += f", error={item.error}"
        lines.append(detail)

    lines.extend(["", "## Human Review Summary", ""])

    if review_summary is None:
        lines.append("- No human review scores")
    else:
        lines.append(f"- Average score: {review_summary.average_score}")
        lines.append(f"- Excellent ratio: {review_summary.excellent_ratio * 100:.1f}%")
        lines.append(f"- Qualified ratio: {review_summary.qualified_ratio * 100:.1f}%")
        lines.append(f"- Unqualified ratio: {review_summary.unqualified_ratio * 100:.1f}%")
        lines.append(f"- Lowest-score case: {review_summary.lowest_score_case} ({review_summary.lowest_score})")

    if review_results:
        lines.extend(["", "### Review Details", ""])
        for item in review_results:
            lines.append(f"- {item.case}: score={item.score}, level={item.level}")

    if review_errors:
        lines.extend(["", "## Review Parsing Errors", ""])
        for item in review_errors:
            lines.append(f"- {item}")

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def print_results(results: list[RegressionCaseResult], summary_path: Path, report_path: Path) -> None:
    for result in results:
        print(f"[{result.case}]")
        print(f"success: {result.success}")
        print(f"ppt_generated: {result.ppt_generated}")
        print(f"warning_count: {result.warning_count}")
        print(f"high_count: {result.high_count}")
        print(f"error_count: {result.error_count}")
        print(f"review_required: {result.review_required}")
        print(f"slides: {result.slides}")
        print(f"duration: {result.duration}")
        print(f"auto_score: {result.auto_score}")
        if result.score is not None:
            print(f"score: {result.score}")
            print(f"score_level: {result.score_level}")
        if result.error:
            print(f"error: {result.error}")
        print("")

    print("=== Summary ===")
    print(f"total_cases: {len(results)}")
    print(f"failed_cases: {sum(1 for item in results if not item.success)}")
    print(f"summary_path: {summary_path}")
    print(f"report_path: {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V2 PPT regression cases from regression/*/deck.json.")
    parser.add_argument("--regression-dir", default=str(DEFAULT_REGRESSION_DIR), help="Directory containing regression case folders.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used for V2 regression outputs.")
    parser.add_argument("--case", action="append", default=[], help="Optional case folder name filter. Can be passed multiple times.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    regression_dir = Path(args.regression_dir)
    output_dir = Path(args.output_dir)

    case_dirs = discover_regression_cases(regression_dir)
    if args.case:
        requested = set(args.case)
        case_dirs = [path for path in case_dirs if path.name in requested]

    if not case_dirs:
        print("No regression cases found.")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    results = [run_case(case_dir, output_dir) for case_dir in case_dirs]
    review_results, review_scores_by_case, review_errors = collect_review_scores(case_dirs)
    merged_results = merge_review_scores(results, review_scores_by_case)
    summary_path = write_summary(merged_results, output_dir, review_results, review_errors)
    report_path = write_report(merged_results, output_dir, review_results, review_errors)
    print_results(merged_results, summary_path, report_path)

    has_failure = any(item.error_count > 0 or not item.ppt_generated for item in merged_results)
    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
