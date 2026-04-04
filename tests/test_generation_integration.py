import json
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, INPUT_DIR
from tools.sie_autoppt.generator import generate_ppt
from tools.sie_autoppt.qa import write_qa_report


class GenerationIntegrationTests(unittest.TestCase):
    def test_generate_ppt_and_qa_reports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out, pattern_ids, chapter_lines = generate_ppt(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "uat_plan_sample.html",
                reference_body_path=None,
                output_prefix="Unit_Test_Generation",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )

            self.assertTrue(out.exists())
            self.assertEqual(out.suffix, ".pptx")
            self.assertEqual(len(pattern_ids), 3)
            self.assertEqual(len(chapter_lines), 5)

            report = write_qa_report(
                out,
                len(pattern_ids),
                pattern_ids=pattern_ids,
                chapter_lines=chapter_lines,
                template_path=DEFAULT_TEMPLATE,
            )
            json_report = report.with_suffix(".json")

            self.assertTrue(report.exists())
            self.assertTrue(json_report.exists())

            qa = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(qa["template_name"], "sie_template")
            self.assertEqual(qa["schema_version"], "1.1")
            self.assertEqual(qa["checks"]["ending_last"], "PASS")
            self.assertEqual(qa["checks"]["theme_title_font"], "PASS")
            self.assertEqual(qa["checks"]["directory_title_font"], "PASS")
