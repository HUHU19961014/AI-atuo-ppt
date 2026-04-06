import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.style_guide import deep_merge_dict, parse_style_guide_markdown


class StyleGuideTests(unittest.TestCase):
    def test_parse_style_guide_markdown_supports_lists_and_nested_keys(self):
        content = """
        # Demo

        theme_name: Demo Theme
        accent_rgb: 1, 2, 3
        density_thresholds.compact: 50
        density_thresholds.dense: 90

        tone_keywords:
        - bold
        - precise
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "style_guide.md"
            path.write_text(content, encoding="utf-8")
            parsed = parse_style_guide_markdown(path)

        self.assertEqual(parsed["theme_name"], "Demo Theme")
        self.assertEqual(parsed["accent_rgb"], [1, 2, 3])
        self.assertEqual(parsed["density_thresholds"]["compact"], 50)
        self.assertEqual(parsed["density_thresholds"]["dense"], 90)
        self.assertEqual(parsed["tone_keywords"], ["bold", "precise"])

    def test_deep_merge_dict_merges_nested_content(self):
        merged = deep_merge_dict(
            {"style_guide": {"body_max_chars": 100, "density_thresholds": {"compact": 60}}},
            {"style_guide": {"density_thresholds": {"dense": 120}}},
        )

        self.assertEqual(merged["style_guide"]["body_max_chars"], 100)
        self.assertEqual(merged["style_guide"]["density_thresholds"]["compact"], 60)
        self.assertEqual(merged["style_guide"]["density_thresholds"]["dense"], 120)
