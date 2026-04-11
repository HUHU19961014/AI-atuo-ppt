import shutil
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

from tools.sie_autoppt.config import DEFAULT_TEMPLATE
from tools.sie_autoppt.slide_ops import remove_slide
from tools.template_utils.upgrade_template_pool import format_validation_summary, validate_template_pool


class UpgradeTemplatePoolTests(unittest.TestCase):
    def test_validate_template_pool_accepts_default_template(self):
        summary = validate_template_pool(DEFAULT_TEMPLATE)

        self.assertEqual(summary["slides"], 43)
        self.assertEqual(summary["required_pairs"], 20)
        self.assertEqual(summary["ending_slide_no"], 43)
        self.assertEqual(summary["directory_asset_targets"], 19)
        self.assertEqual(summary["validation_mode"], "python-openxml")

    def test_format_validation_summary_includes_validation_mode(self):
        summary = validate_template_pool(DEFAULT_TEMPLATE)
        rendered = format_validation_summary(summary)

        self.assertIn("mode=python-openxml", rendered)
        self.assertIn("slides=43", rendered)

    def test_validate_template_pool_rejects_missing_ending_slide(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copy_path = Path(temp_dir) / "template_copy.pptx"
            shutil.copy2(DEFAULT_TEMPLATE, copy_path)

            prs = Presentation(str(copy_path))
            remove_slide(prs, len(prs.slides) - 1)
            prs.save(str(copy_path))

            with self.assertRaises((RuntimeError, ValueError)):
                validate_template_pool(copy_path)
