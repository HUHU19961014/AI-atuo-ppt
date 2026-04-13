import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.prompting import PromptRenderError, load_prompt, load_prompt_template, render_prompt_template


class PromptingTests(unittest.TestCase):
    def test_load_prompt_strips_metadata_and_exposes_version(self):
        prompt = load_prompt("prompts/system/v2_outline.md")

        self.assertEqual(prompt.version, "1.2.0")
        self.assertTrue(prompt.body.startswith("You are an enterprise PPT outline planner."))
        self.assertIn("slide_rule", prompt.placeholders)

    def test_render_prompt_template_rejects_missing_required_placeholder(self):
        with self.assertRaises(PromptRenderError):
            render_prompt_template(
                "prompts/system/v2_outline.md",
                language="zh-CN",
                feedback_block="",
            )

    def test_render_prompt_template_supports_metadata_free_templates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            prompt_path = Path(temp_dir) / "sample.md"
            prompt_path.write_text("Hello {name}", encoding="utf-8")
            relative_path = str(prompt_path.relative_to(Path.cwd())).replace("\\", "/")

            rendered = render_prompt_template(relative_path, name="World")
            template_body = load_prompt_template(relative_path)

        self.assertEqual(rendered, "Hello World")
        self.assertEqual(template_body, "Hello {name}")
