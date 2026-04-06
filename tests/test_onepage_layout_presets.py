import unittest

from tools.sie_autoppt.onepage_layout_presets import (
    DEFAULT_ONEPAGE_PRESET_ID,
    get_onepage_layout_preset,
    list_onepage_layout_presets,
)


class OnePageLayoutPresetTests(unittest.TestCase):
    def test_default_preset_resolves(self):
        preset = get_onepage_layout_preset()
        self.assertEqual(preset.preset_id, DEFAULT_ONEPAGE_PRESET_ID)
        self.assertIn("title_font_size", preset.renderer_hints)

    def test_known_presets_are_listed(self):
        preset_ids = {preset.preset_id for preset in list_onepage_layout_presets()}
        self.assertIn("decision_oriented", preset_ids)
        self.assertIn("professional_modular_cards", preset_ids)
        self.assertIn("info_dense", preset_ids)

    def test_unknown_preset_raises_helpful_error(self):
        with self.assertRaises(KeyError) as ctx:
            get_onepage_layout_preset("not_exists")
        self.assertIn("Supported presets", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
