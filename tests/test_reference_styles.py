import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from tools.sie_autoppt.config import INPUT_DIR
from tools.sie_autoppt.models import BodyPageSpec
from tools.sie_autoppt.reference_styles import build_reference_import_plan, locate_reference_slide_no
from tools.sie_autoppt.slide_ops import set_slide_metadata_names


class ReferenceStyleTests(unittest.TestCase):
    def test_default_reference_body_contains_slide_metadata_names(self):
        reference_body_path = INPUT_DIR / "reference_body_style.pptx"
        expected_names = {
            5: "comparison_upgrade_reference",
            6: "pain_cards_reference",
            16: "capability_ring_reference",
            20: "five_phase_path_reference",
        }

        with zipfile.ZipFile(reference_body_path) as package:
            for slide_no, expected_name in expected_names.items():
                root = ElementTree.fromstring(package.read(f"ppt/slides/slide{slide_no}.xml"))
                c_sld = root.find("{http://schemas.openxmlformats.org/presentationml/2006/main}cSld")
                self.assertIsNotNone(c_sld)
                self.assertEqual(c_sld.attrib.get("name"), expected_name)

    def test_locate_reference_slide_no_prefers_slide_metadata_name(self):
        reference_body_path = INPUT_DIR / "reference_body_style.pptx"

        with tempfile.TemporaryDirectory() as temp_dir:
            copy_path = Path(temp_dir) / "reference_body_named.pptx"
            shutil.copy2(reference_body_path, copy_path)
            self.assertTrue(
                set_slide_metadata_names(
                    copy_path,
                    {
                        4: "comparison_upgrade_reference",
                        5: "comparison_upgrade_reference_old",
                    },
                )
            )

            self.assertEqual(locate_reference_slide_no("comparison_upgrade", copy_path), 4)

    def test_locate_reference_slide_no_prefers_text_markers(self):
        reference_body_path = INPUT_DIR / "reference_body_style.pptx"

        self.assertEqual(locate_reference_slide_no("comparison_upgrade", reference_body_path), 5)
        self.assertEqual(locate_reference_slide_no("capability_ring", reference_body_path), 16)
        self.assertEqual(locate_reference_slide_no("five_phase_path", reference_body_path), 20)

    def test_build_reference_import_plan_uses_resolved_slide_numbers(self):
        reference_body_path = INPUT_DIR / "reference_body_style.pptx"
        body_pages = [
            BodyPageSpec(
                page_key="p1",
                title="A",
                subtitle="",
                bullets=[],
                pattern_id="comparison_upgrade",
                reference_style_id="comparison_upgrade",
            ),
            BodyPageSpec(
                page_key="p2",
                title="B",
                subtitle="",
                bullets=[],
                pattern_id="capability_ring",
                reference_style_id="capability_ring",
            ),
            BodyPageSpec(
                page_key="p3",
                title="C",
                subtitle="",
                bullets=[],
                pattern_id="five_phase_path",
                reference_style_id="five_phase_path",
            ),
        ]

        self.assertEqual(
            build_reference_import_plan(body_pages, reference_body_path=reference_body_path),
            [(4, 5), (6, 16), (8, 20)],
        )
