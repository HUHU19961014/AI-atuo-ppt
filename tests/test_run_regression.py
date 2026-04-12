import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run_regression import (
    RegressionCaseResult,
    RegressionReviewResult,
    discover_regression_cases,
    run_case,
    write_report,
    write_summary,
)


class RunRegressionTests(unittest.TestCase):
    def test_discover_cases_and_run_case(self):
        regression_dir = Path("regression")
        cases = discover_regression_cases(regression_dir)
        self.assertGreaterEqual(len(cases), 5)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_case(cases[0], Path(temp_dir))
            self.assertTrue(result.success)
            self.assertTrue(result.ppt_generated)
            self.assertTrue(result.pptx_path.endswith("generated.pptx"))
            self.assertTrue(result.warnings_path.endswith("warnings.json"))

    def test_write_summary_outputs_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = write_summary([], Path(temp_dir))
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_path.name, "regression_summary.json")
            self.assertEqual(payload["total_cases"], 0)
            self.assertEqual(payload["results"], [])

    def test_write_report_outputs_markdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results = [
                RegressionCaseResult(
                    case="01_management_report",
                    success=True,
                    ppt_generated=True,
                    warning_count=1,
                    high_count=0,
                    error_count=0,
                    review_required=False,
                    slides=5,
                    duration=1.23,
                    pptx_path="output/v2_regression/01_management_report/generated.pptx",
                    warnings_path="output/v2_regression/01_management_report/warnings.json",
                    log_path="output/v2_regression/01_management_report/log.txt",
                    auto_score=98,
                    auto_level="优秀",
                    score=22,
                    score_level="优秀",
                )
            ]
            review_results = [
                RegressionReviewResult(
                    case="01_management_report",
                    score=22,
                    level="优秀",
                    conclusion="可直接进入交付或仅需极少润色。",
                    review_path="regression/01_management_report/review.md",
                )
            ]
            report_path = write_report(results, Path(temp_dir), review_results, [])
            content = report_path.read_text(encoding="utf-8")
            self.assertEqual(report_path.name, "regression_report.md")
            self.assertIn("Regression Report", content)
            self.assertIn("01_management_report", content)

    def test_run_case_keeps_validation_error_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case_a"
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "deck.json").write_text("{}", encoding="utf-8")

            with (
                patch("run_regression.validate_deck_payload", side_effect=ValueError("schema mismatch")),
                patch("run_regression.generate_ppt", side_effect=RuntimeError("render failed")),
            ):
                result = run_case(case_dir, Path(temp_dir) / "out")

        self.assertFalse(result.success)
        self.assertIn("schema mismatch", result.error)


if __name__ == "__main__":
    unittest.main()
