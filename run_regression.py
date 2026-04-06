from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.sie_autoppt.v2.ppt_engine import generate_ppt
from tools.sie_autoppt.v2.schema import validate_deck_payload


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REGRESSION_DIR = PROJECT_ROOT / "regression"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "regression"


@dataclass(frozen=True)
class RegressionCaseResult:
    case_name: str
    status: str
    pptx_path: str
    warning_count: int
    error: str = ""


def discover_regression_cases(regression_dir: Path) -> list[Path]:
    if not regression_dir.exists():
        raise FileNotFoundError(f"Regression directory not found: {regression_dir}")
    return sorted(
        path
        for path in regression_dir.iterdir()
        if path.is_dir() and (path / "deck.json").exists()
    )


def run_case(case_dir: Path, output_root: Path) -> RegressionCaseResult:
    case_name = case_dir.name
    deck_path = case_dir / "deck.json"
    case_output_dir = output_root / case_name
    case_output_dir.mkdir(parents=True, exist_ok=True)

    pptx_path = case_output_dir / "generated.pptx"
    log_path = case_output_dir / "log.txt"

    try:
        payload = json.loads(deck_path.read_text(encoding="utf-8"))
        validated = validate_deck_payload(payload)
        render_result = generate_ppt(
            validated,
            output_path=pptx_path,
            log_path=log_path,
        )
        warning_count = len(render_result.warnings) + len(render_result.content_warnings)
        return RegressionCaseResult(
            case_name=case_name,
            status="success",
            pptx_path=str(render_result.output_path),
            warning_count=warning_count,
        )
    except Exception as exc:
        return RegressionCaseResult(
            case_name=case_name,
            status="failed",
            pptx_path=str(pptx_path),
            warning_count=0,
            error=str(exc),
        )


def write_summary(results: list[RegressionCaseResult], output_root: Path) -> Path:
    summary_path = output_root / "summary.json"
    payload = {
        "total_cases": len(results),
        "success_count": sum(1 for item in results if item.status == "success"),
        "failed_count": sum(1 for item in results if item.status == "failed"),
        "total_warning_count": sum(item.warning_count for item in results),
        "results": [asdict(item) for item in results],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def print_results(results: list[RegressionCaseResult], summary_path: Path) -> None:
    for result in results:
        print(f"[{result.case_name}]")
        print(f"status: {result.status}")
        print(f"pptx_path: {result.pptx_path}")
        print(f"warning_count: {result.warning_count}")
        if result.error:
            print(f"error: {result.error}")
        print("")

    success_count = sum(1 for item in results if item.status == "success")
    failed_count = sum(1 for item in results if item.status == "failed")
    total_warning_count = sum(item.warning_count for item in results)

    print("=== Summary ===")
    print(f"total_cases: {len(results)}")
    print(f"success_count: {success_count}")
    print(f"failed_count: {failed_count}")
    print(f"total_warning_count: {total_warning_count}")
    print(f"summary_path: {summary_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V2 PPT regression cases from regression/*/deck.json.")
    parser.add_argument(
        "--regression-dir",
        default=str(DEFAULT_REGRESSION_DIR),
        help="Directory containing regression case folders.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory used for rendered regression outputs.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Optional case folder name filter. Can be passed multiple times.",
    )
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
    summary_path = write_summary(results, output_dir)
    print_results(results, summary_path)
    return 0 if all(item.status == "success" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
