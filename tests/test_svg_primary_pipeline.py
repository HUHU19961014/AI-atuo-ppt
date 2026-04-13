import unittest
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from tools.sie_autoppt.v2.schema import OutlineDocument
from tools.sie_autoppt.v2.services import make_v2_ppt


@contextmanager
def _workspace_tmpdir():
    root = Path(__file__).resolve().parents[1] / ".tmp_test_workspace"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tmp_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class SvgPrimaryPipelineTests(unittest.TestCase):
    def test_make_routes_through_svg_pipeline(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain key issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present the roadmap."},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "关键结论",
                    "intent": "conclusion",
                    "blocks": [{"kind": "statement", "text": "先打通主链，再扩展到运营闭环。"}],
                }
            ],
        }

        with _workspace_tmpdir() as temp_dir:
            output_dir = Path(temp_dir)
            ppt_path = output_dir / "final.pptx"

            with (
                patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})),
                patch("tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline),
                patch("tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload),
                patch("tools.sie_autoppt.v2.services._write_svg_project") as write_svg_project,
                patch("tools.sie_autoppt.v2.services._run_svg_pipeline") as run_svg_pipeline,
            ):
                artifacts = make_v2_ppt(topic="AI strategy", output_dir=output_dir, ppt_output=ppt_path)

            expected_project = output_dir / "svg_projects" / "Enterprise-AI-PPT-V2_ppt169"
            write_svg_project.assert_called_once()
            run_svg_pipeline.assert_called_once_with(project_path=expected_project, final_ppt_output=ppt_path)
            self.assertEqual(artifacts.svg_project_path, expected_project)
            self.assertEqual(artifacts.svg_final_dir, expected_project / "svg_final")
            self.assertIn("svg_stage=final", artifacts.log_path.read_text(encoding="utf-8"))
