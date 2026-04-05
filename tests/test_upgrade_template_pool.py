import shutil
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

from tools.sie_autoppt.config import DEFAULT_TEMPLATE
from tools.sie_autoppt.slide_ops import remove_slide
from tools.upgrade_template_pool import validate_template_pool


class UpgradeTemplatePoolTests(unittest.TestCase):
    def test_validate_template_pool_accepts_default_template(self):
        summary = validate_template_pool(DEFAULT_TEMPLATE)

        self.assertEqual(summary["slides"], 9)
        self.assertEqual(summary["required_pairs"], 3)
        self.assertEqual(summary["ending_slide_no"], 9)

    def test_validate_template_pool_rejects_missing_ending_slide(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copy_path = Path(temp_dir) / "template_copy.pptx"
            shutil.copy2(DEFAULT_TEMPLATE, copy_path)

            prs = Presentation(str(copy_path))
            remove_slide(prs, len(prs.slides) - 1)
            prs.save(str(copy_path))

            with self.assertRaises((RuntimeError, ValueError)):
                validate_template_pool(copy_path)
