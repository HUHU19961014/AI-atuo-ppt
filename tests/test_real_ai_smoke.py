import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.healthcheck import run_ai_healthcheck


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


RUN_REAL_AI_TESTS = _env_flag("SIE_AUTOPPT_RUN_REAL_AI_TESTS")
HAS_API_KEY = bool(os.environ.get("OPENAI_API_KEY", "").strip())
SKIP_REASON = "Set SIE_AUTOPPT_RUN_REAL_AI_TESTS=1 and OPENAI_API_KEY to run real AI smoke tests."


@unittest.skipUnless(RUN_REAL_AI_TESTS and HAS_API_KEY, SKIP_REASON)
class RealAiSmokeTests(unittest.TestCase):
    def test_real_ai_healthcheck_smoke(self):
        topic = os.environ.get("SIE_AUTOPPT_REAL_AI_TOPIC", "企业 AI 投资决策汇报健康检查")
        generation_mode = os.environ.get("SIE_AUTOPPT_REAL_AI_GENERATION_MODE", "quick").strip() or "quick"
        with_render = _env_flag("SIE_AUTOPPT_REAL_AI_WITH_RENDER")

        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_ai_healthcheck(
                topic=topic,
                generation_mode=generation_mode,
                with_render=with_render,
                output_dir=Path(temp_dir),
            )

            payload = json.loads(summary.to_json())
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["topic"], topic)
            self.assertEqual(payload["page_count"], 3)
            self.assertTrue(payload["cover_title"].strip())
            self.assertTrue(payload["first_page_title"].strip())

            if with_render:
                self.assertTrue(payload["render_checked"])
                self.assertTrue(payload["pptx_path"])
                self.assertTrue(Path(payload["pptx_path"]).exists())

