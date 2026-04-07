from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.prepare_visual_review import VisualReviewCase, build_review_dir, write_summary


class PrepareVisualReviewTests(unittest.TestCase):
    def test_build_review_dir_uses_visual_review_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_dir = build_review_dir(Path(temp_dir))
        self.assertEqual(review_dir.parent, Path(temp_dir))
        self.assertTrue(review_dir.name.startswith("visual_review_"))

    def test_write_summary_records_preview_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_dir = Path(temp_dir)
            case = VisualReviewCase(
                name="sample_case",
                label="Sample",
                html=Path("input/sample.html"),
                focus=("Check layout", "Check overflow"),
            )
            report_path = review_dir / "sample.QA.txt"
            pptx_path = review_dir / "sample.pptx"
            summary_path = write_summary(
                review_dir,
                [(case, report_path, pptx_path, "preview export unavailable on this platform")],
            )
            content = summary_path.read_text(encoding="utf-8")

        self.assertIn("sample_case", content)
        self.assertIn("preview export unavailable on this platform", content)
        self.assertIn("QA.json", content)


if __name__ == "__main__":
    unittest.main()
