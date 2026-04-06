import json
import tempfile
import unittest
from pathlib import Path

from run_regression import discover_regression_cases, run_case, write_summary


class RunRegressionTests(unittest.TestCase):
    def test_discover_cases_and_run_case(self):
        regression_dir = Path("regression")
        cases = discover_regression_cases(regression_dir)
        self.assertGreaterEqual(len(cases), 5)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_case(cases[0], Path(temp_dir))
            self.assertEqual(result.status, "success")
            self.assertTrue(result.pptx_path.endswith("generated.pptx"))

    def test_write_summary_outputs_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = write_summary([], Path(temp_dir))
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_cases"], 0)
            self.assertEqual(payload["results"], [])
