import json
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

from tools.sie_autoppt.v2.ppt_engine import generate_ppt
from tools.sie_autoppt.v2.schema import validate_deck_payload


class V2RenderTests(unittest.TestCase):
    def test_generate_ppt_renders_sample_deck(self):
        sample_path = Path("samples/sample_deck_v2.json")
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        validated = validate_deck_payload(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            ppt_path = Path(temp_dir) / "sample_v2.pptx"
            log_path = Path(temp_dir) / "sample_v2.log.txt"
            result = generate_ppt(validated, output_path=ppt_path, log_path=log_path)

            self.assertTrue(result.output_path.exists())
            self.assertTrue(log_path.exists())

            prs = Presentation(str(result.output_path))
            self.assertEqual(len(prs.slides), len(validated.deck.slides))
            all_text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))
            self.assertIn("项目背景", all_text)
            self.assertIn("重构前后对比", all_text)
