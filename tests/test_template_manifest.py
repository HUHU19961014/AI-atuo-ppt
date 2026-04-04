import unittest

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, DEFAULT_TEMPLATE_MANIFEST
from tools.sie_autoppt.template_manifest import ShapeBounds, load_template_manifest, resolve_template_manifest_path


class _FakeShape:
    def __init__(self, top: int, width: int):
        self.top = top
        self.width = width


class TemplateManifestTests(unittest.TestCase):
    def test_default_manifest_loads(self):
        manifest = load_template_manifest()

        self.assertEqual(manifest.template_name, "sie_template")
        self.assertEqual(manifest.version, "1.0")
        self.assertEqual(manifest.slide_roles.theme, 1)
        self.assertEqual(manifest.slide_roles.directory, 2)
        self.assertEqual(manifest.fonts.theme_title_pt, 40.0)
        self.assertEqual(manifest.fonts.directory_title_pt, 24.0)

    def test_template_path_resolves_to_adjacent_manifest(self):
        self.assertEqual(resolve_template_manifest_path(DEFAULT_TEMPLATE), DEFAULT_TEMPLATE_MANIFEST)

    def test_shape_bounds_matches_expected_geometry(self):
        bounds = ShapeBounds(min_top=100, max_top=200, min_width=300)

        self.assertTrue(bounds.matches(_FakeShape(top=150, width=400)))
        self.assertFalse(bounds.matches(_FakeShape(top=90, width=400)))
        self.assertFalse(bounds.matches(_FakeShape(top=150, width=250)))
