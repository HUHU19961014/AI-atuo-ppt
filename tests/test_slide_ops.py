import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, INPUT_DIR
from tools.sie_autoppt.slide_ops import import_slides_from_presentation


def _slide_xml_text(package: zipfile.ZipFile, slide_no: int) -> str:
    root = ElementTree.fromstring(package.read(f"ppt/slides/slide{slide_no}.xml"))
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    texts = [node.text for node in root.findall(".//a:t", namespace) if node.text]
    return " ".join(texts)


class SlideOpsTests(unittest.TestCase):
    def test_import_slides_from_presentation_replaces_body_slides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "target.pptx"
            shutil.copy2(DEFAULT_TEMPLATE, target_path)

            ok = import_slides_from_presentation(
                target_path,
                INPUT_DIR / "reference_body_style.pptx",
                [(4, 5), (6, 16), (8, 20)],
            )

            self.assertTrue(ok)

            with zipfile.ZipFile(target_path) as package:
                self.assertIn("价值：业务效能跃升", _slide_xml_text(package, 4))
                self.assertIn("赛意追溯产品亮点", _slide_xml_text(package, 6))
                self.assertIn("追溯管理", _slide_xml_text(package, 8))
                self.assertIn("外部追溯推进路径", _slide_xml_text(package, 8))
                content_types_root = ElementTree.fromstring(package.read("[Content_Types].xml"))
                svg_defaults = [
                    child
                    for child in content_types_root
                    if child.tag.endswith("Default") and child.attrib.get("Extension") == "svg"
                ]
                self.assertTrue(svg_defaults)
