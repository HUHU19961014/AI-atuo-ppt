import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.healthcheck import run_ai_healthcheck


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


RUN_REAL_AI_GOLDEN = _env_flag("SIE_AUTOPPT_RUN_REAL_AI_GOLDEN")
HAS_API_KEY = bool(os.environ.get("OPENAI_API_KEY", "").strip())
SKIP_REASON = "Set SIE_AUTOPPT_RUN_REAL_AI_GOLDEN=1 and OPENAI_API_KEY to run golden dataset tests."
DATASET_PATH = Path(__file__).resolve().parents[1] / "regression" / "real_ai_golden_dataset.json"


@unittest.skipUnless(RUN_REAL_AI_GOLDEN and HAS_API_KEY and DATASET_PATH.exists(), SKIP_REASON)
class RealAiGoldenDatasetTests(unittest.TestCase):
    def test_real_ai_golden_dataset(self):
        dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        cases = dataset.get("cases", [])
        self.assertGreater(len(cases), 0)

        for case in cases:
            with self.subTest(case_id=case["id"]):
                with tempfile.TemporaryDirectory() as temp_dir:
                    summary = run_ai_healthcheck(
                        topic=case["topic"],
                        generation_mode=case.get("generation_mode", "quick"),
                        with_render=False,
                        output_dir=Path(temp_dir),
                    )
                payload = json.loads(summary.to_json())
                self.assertEqual(payload["status"], "ok")
                self.assertGreaterEqual(int(payload["page_count"]), int(case["min_pages"]))
                self.assertLessEqual(int(payload["page_count"]), int(case["max_pages"]))
                self.assertTrue(str(payload["cover_title"]).strip())
                self.assertTrue(str(payload["first_page_title"]).strip())

