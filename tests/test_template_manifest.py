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
        self.assertEqual(manifest.style_guide.title_max_chars, 32)
        self.assertEqual(manifest.style_guide.preferred_item_counts, (3, 5, 9))
        self.assertEqual(manifest.style_guide.overflow_policy, "paginate")
        self.assertEqual(
            [variant["id"] for variant in manifest.pattern_variants["general_business"]],
            ["general_business_3", "general_business_5", "general_business_9"],
        )
        self.assertEqual(
            [variant["capacity"] for variant in manifest.pattern_variants["process_flow"]],
            [3, 5, 9],
        )
        self.assertEqual(len(manifest.slide_pools.directory), 20)
        self.assertEqual(manifest.slide_pools.directory[:3], (2, 4, 6))
        self.assertEqual(manifest.slide_pools.directory[-1], 40)
        self.assertEqual(manifest.slide_pools.body[:3], (3, 5, 7))
        self.assertEqual(manifest.slide_pools.body[-1], 41)
        self.assertEqual(manifest.slide_pools.ending, 42)
        self.assertIn("general_business", manifest.render_layouts)
        self.assertIn("general_business_3", manifest.render_layouts)
        self.assertIn("process_flow_9", manifest.render_layouts)
        self.assertIn("roadmap_timeline", manifest.render_layouts)
        self.assertIn("kpi_dashboard", manifest.render_layouts)
        self.assertIn("risk_matrix", manifest.render_layouts)
        self.assertIn("claim_breakdown", manifest.render_layouts)

    def test_template_path_resolves_to_adjacent_manifest(self):
        self.assertEqual(resolve_template_manifest_path(DEFAULT_TEMPLATE), DEFAULT_TEMPLATE_MANIFEST)

    def test_template_path_resolves_folder_manifest_for_variant_template(self):
        template_path = Path("assets/templates/business_gold/template.pptx")
        self.assertEqual(resolve_template_manifest_path(template_path), Path("assets/templates/business_gold/manifest.json"))

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
            validate_slide_pool_configuration(invalid_manifest, body_page_count=3, slide_count=43)

    def test_manifest_supports_cm_units_for_geometry(self):
        data = json.loads(DEFAULT_TEMPLATE_MANIFEST.read_text(encoding="utf-8"))
        data["fallback_boxes"]["body_title"]["left"] = "1.5cm"
        data["selectors"]["theme_title"]["min_top"] = "2cm"
        data["render_layouts"]["general_business"]["origin_left"] = "3cm"
        data["render_layouts"]["general_business"]["gap_x"] = "0.5cm"
        data["style_guide"]["body_max_chars"] = 140

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "temp.manifest.json"
            manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            manifest = load_template_manifest(manifest_path=manifest_path)

        self.assertEqual(manifest.fallback_boxes.body_title.left, int(1.5 * EMU_PER_CM))
        self.assertEqual(manifest.selectors.theme_title.min_top, int(2 * EMU_PER_CM))
        self.assertEqual(manifest.render_layouts["general_business"]["origin_left"], int(3 * EMU_PER_CM))
        self.assertEqual(manifest.render_layouts["general_business"]["gap_x"], int(0.5 * EMU_PER_CM))
        self.assertEqual(manifest.style_guide.body_max_chars, 140)

    def test_manifest_rejects_pattern_variant_without_render_layout(self):
        data = json.loads(DEFAULT_TEMPLATE_MANIFEST.read_text(encoding="utf-8"))
        data["pattern_variants"] = {
            "general_business": [
                {"id": "missing_general_business_variant", "capacity": 3},
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "temp.manifest.json"
            manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_template_manifest(manifest_path=manifest_path)

        self.assertIn("missing_general_business_variant", str(ctx.exception))
        self.assertIn("render_layouts.missing_general_business_variant", str(ctx.exception))

    def test_variant_template_manifest_loads_style_guide_markdown(self):
        manifest = load_template_manifest(template_path=Path("assets/templates/business_gold/template.pptx"))

        self.assertEqual(manifest.template_name, "business_gold")
        self.assertEqual(manifest.style_guide.theme_name, "Executive Gold")
        self.assertEqual(manifest.style_guide.accent_rgb, (168, 126, 33))
        self.assertIn("premium", manifest.style_guide.tone_keywords)
        self.assertIn("outcome first", manifest.style_guide.narrative_preferences)
        self.assertEqual(
            [variant["id"] for variant in manifest.pattern_variants["general_business"]],
            ["general_business_3", "general_business_5", "general_business_9"],
        )
