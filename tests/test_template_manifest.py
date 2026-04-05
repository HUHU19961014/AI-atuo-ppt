import json
import tempfile
from dataclasses import replace
import unittest
from pathlib import Path

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, DEFAULT_TEMPLATE_MANIFEST
from tools.sie_autoppt.generator import validate_slide_pool_configuration
from tools.sie_autoppt.template_manifest import EMU_PER_CM, ShapeBounds, load_template_manifest, resolve_template_manifest_path


class _FakeShape:
    def __init__(self, top: int, width: int):
        self.top = top
        self.width = width


class TemplateManifestTests(unittest.TestCase):
    def test_default_manifest_loads(self):
        manifest = load_template_manifest()

        self.assertEqual(manifest.template_name, "sie_template")
        self.assertEqual(manifest.version, "1.1")
        self.assertEqual(manifest.slide_roles.theme, 1)
        self.assertEqual(manifest.slide_roles.directory, 2)
        self.assertEqual(manifest.fonts.theme_title_pt, 40.0)
        self.assertEqual(manifest.fonts.directory_title_pt, 24.0)
        self.assertEqual(manifest.slide_pools.directory, (2, 4, 6))
        self.assertEqual(manifest.slide_pools.body, (3, 5, 7))
        self.assertEqual(manifest.slide_pools.ending, 8)
        self.assertIn("general_business", manifest.render_layouts)

    def test_template_path_resolves_to_adjacent_manifest(self):
        self.assertEqual(resolve_template_manifest_path(DEFAULT_TEMPLATE), DEFAULT_TEMPLATE_MANIFEST)

    def test_shape_bounds_matches_expected_geometry(self):
        bounds = ShapeBounds(min_top=100, max_top=200, min_width=300)

        self.assertTrue(bounds.matches(_FakeShape(top=150, width=400)))
        self.assertFalse(bounds.matches(_FakeShape(top=90, width=400)))
        self.assertFalse(bounds.matches(_FakeShape(top=150, width=250)))

    def test_slide_pool_validation_rejects_invalid_indices(self):
        manifest = load_template_manifest()
        invalid_pool = replace(manifest.slide_pools, ending=99)
        invalid_manifest = replace(manifest, slide_pools=invalid_pool)

        with self.assertRaises(ValueError):
            validate_slide_pool_configuration(invalid_manifest, body_page_count=3, slide_count=9)

    def test_manifest_supports_cm_units_for_geometry(self):
        data = json.loads(DEFAULT_TEMPLATE_MANIFEST.read_text(encoding="utf-8"))
        data["fallback_boxes"]["body_title"]["left"] = "1.5cm"
        data["selectors"]["theme_title"]["min_top"] = "2cm"
        data["render_layouts"]["general_business"]["origin_left"] = "3cm"
        data["render_layouts"]["general_business"]["gap_x"] = "0.5cm"

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "temp.manifest.json"
            manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            manifest = load_template_manifest(manifest_path=manifest_path)

        self.assertEqual(manifest.fallback_boxes.body_title.left, int(1.5 * EMU_PER_CM))
        self.assertEqual(manifest.selectors.theme_title.min_top, int(2 * EMU_PER_CM))
        self.assertEqual(manifest.render_layouts["general_business"]["origin_left"], int(3 * EMU_PER_CM))
        self.assertEqual(manifest.render_layouts["general_business"]["gap_x"], int(0.5 * EMU_PER_CM))
