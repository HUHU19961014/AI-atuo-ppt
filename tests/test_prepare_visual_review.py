import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.prepare_visual_review as visual_batch


class PrepareVisualReviewTests(unittest.TestCase):
    def test_load_registry_cases_use_deck_json(self):
        cases = visual_batch.load_visual_review_cases()

        self.assertTrue(cases)
        self.assertTrue(all(case.deck_json.suffix == ".json" for case in cases))
        self.assertTrue(all(case.deck_json.exists() for case in cases))

    def test_run_case_renders_case_and_exports_preview_note(self):
        case = visual_batch.load_visual_review_cases()[0]
        fake_render = type(
            "FakeRender",
            (),
            {
                "warnings_path": Path("warnings.json"),
                "rewrite_log_path": Path("rewrite_log.json"),
                "output_path": Path("generated.pptx"),
            },
        )()

        with tempfile.TemporaryDirectory() as temp_dir:
            review_dir = Path(temp_dir)
            with (
                patch("tools.prepare_visual_review.generate_ppt", return_value=fake_render),
                patch("tools.prepare_visual_review.export_slide_previews", return_value=[]),
            ):
                warnings_path, rewrite_log_path, pptx_path, log_path, preview_note = visual_batch.run_case(case, review_dir=review_dir)

        self.assertEqual(warnings_path, Path("warnings.json"))
        self.assertEqual(rewrite_log_path, Path("rewrite_log.json"))
        self.assertEqual(pptx_path, Path("generated.pptx"))
        self.assertTrue(str(log_path).endswith("render.log.txt"))
        self.assertIn("content-only", preview_note)

    def test_write_summary_includes_input_and_outputs(self):
        case = visual_batch.load_visual_review_cases()[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            review_dir = Path(temp_dir)
            summary_path = visual_batch.write_summary(
                review_dir,
                [
                    (
                        case,
                        Path("warnings.json"),
                        Path("rewrite_log.json"),
                        Path("generated.pptx"),
                        Path("render.log.txt"),
                        "preview export unavailable; content-only manual review",
                    )
                ],
            )
            content = summary_path.read_text(encoding="utf-8")

        self.assertIn("Visual Review Batch (V2)", content)
        self.assertIn("Input deck:", content)
        self.assertIn("Warnings:", content)
        self.assertIn(case.name, content)
