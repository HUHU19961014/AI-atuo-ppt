import json
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, INPUT_DIR
from tools.sie_autoppt.deck_spec_io import write_deck_spec
from tools.sie_autoppt.generator import generate_ppt, generate_ppt_artifacts_from_deck_spec, generate_ppt_artifacts_from_html
from tools.sie_autoppt.qa import write_qa_report


class GenerationIntegrationTests(unittest.TestCase):
    def test_generate_ppt_and_qa_reports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "uat_plan_sample.html",
                reference_body_path=None,
                output_prefix="Unit_Test_Generation",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )
            out = artifacts.output_path
            pattern_ids = artifacts.deck_plan.pattern_ids
            chapter_lines = artifacts.deck_plan.chapter_lines

            self.assertTrue(out.exists())
            self.assertEqual(out.suffix, ".pptx")
            self.assertEqual(len(pattern_ids), 3)
            self.assertEqual(len(chapter_lines), 5)
            self.assertEqual(artifacts.render_trace.body_render_mode, "preallocated_pool")
            self.assertEqual(artifacts.render_trace.input_kind, "html")

            report = write_qa_report(
                out,
                len(pattern_ids),
                pattern_ids=pattern_ids,
                chapter_lines=chapter_lines,
                template_path=DEFAULT_TEMPLATE,
                render_trace=artifacts.render_trace,
            )
            json_report = report.with_suffix(".json")

            self.assertTrue(report.exists())
            self.assertTrue(json_report.exists())

            qa = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(qa["template_name"], "sie_template")
            self.assertEqual(qa["schema_version"], "1.2")
            self.assertEqual(qa["checks"]["ending_last"], "PASS")
            self.assertEqual(qa["checks"]["theme_title_font"], "PASS")
            self.assertEqual(qa["checks"]["directory_title_font"], "PASS")
            self.assertEqual(qa["checks"]["directory_assets_preserved"], "PASS")
            self.assertEqual(qa["render_trace"]["input_kind"], "html")
            self.assertEqual(qa["render_trace"]["body_render_mode"], "preallocated_pool")
            self.assertEqual(len(qa["render_trace"]["page_traces"]), 3)

    def test_generate_reference_style_deck_without_reference_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "ai_pythonpptx_strategy.html",
                reference_body_path=None,
                output_prefix="Unit_Test_Reference_Fallback",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )
            out = artifacts.output_path
            pattern_ids = artifacts.deck_plan.pattern_ids
            chapter_lines = artifacts.deck_plan.chapter_lines

            self.assertTrue(out.exists())
            self.assertEqual(pattern_ids, ["comparison_upgrade", "capability_ring", "five_phase_path"])
            self.assertFalse(artifacts.render_trace.reference_import_applied)

            report = write_qa_report(
                out,
                len(pattern_ids),
                pattern_ids=pattern_ids,
                chapter_lines=chapter_lines,
                template_path=DEFAULT_TEMPLATE,
                render_trace=artifacts.render_trace,
            )
            qa = json.loads(report.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(qa["checks"]["ending_last"], "PASS")
            self.assertEqual(qa["actual_directory_pages"], [3, 5, 7])
            self.assertEqual(qa["checks"]["directory_assets_preserved"], "PASS")
            self.assertEqual(qa["render_trace"]["reference_import_applied"], False)
            self.assertTrue(qa["render_trace"]["reference_import_reason"])
            self.assertEqual(
                [trace["render_route"] for trace in qa["render_trace"]["page_traces"]],
                [
                    "native_fallback:comparison_upgrade",
                    "native_fallback:capability_ring",
                    "native_fallback:five_phase_path",
                ],
            )

    def test_generate_reference_style_deck_with_native_reference_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "ai_pythonpptx_strategy.html",
                reference_body_path=INPUT_DIR / "reference_body_style.pptx",
                output_prefix="Unit_Test_Reference_Import",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )

            self.assertTrue(artifacts.output_path.exists())
            self.assertTrue(artifacts.render_trace.reference_import_applied)
            self.assertEqual(
                [trace.render_route for trace in artifacts.render_trace.page_traces],
                [
                    "reference_import:comparison_upgrade",
                    "reference_import:capability_ring",
                    "reference_import:five_phase_path",
                ],
            )

    def test_generate_ppt_from_deck_spec_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_spec_path = Path(temp_dir) / "planned_deck.json"
            _, pattern_ids, chapter_lines = generate_ppt(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "architecture_program_sample.html",
                reference_body_path=None,
                output_prefix="Compatibility_Run",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )
            self.assertEqual(len(pattern_ids), 3)
            self.assertEqual(len(chapter_lines), 5)

            planned_artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=INPUT_DIR / "architecture_program_sample.html",
                reference_body_path=None,
                output_prefix="Plan_Source",
                chapters=3,
                active_start=0,
                output_dir=Path(temp_dir),
            )
            write_deck_spec(planned_artifacts.deck_plan.deck, deck_spec_path)

            rendered_artifacts = generate_ppt_artifacts_from_deck_spec(
                template_path=DEFAULT_TEMPLATE,
                deck_spec_path=deck_spec_path,
                reference_body_path=None,
                output_prefix="Render_From_Json",
                active_start=0,
                output_dir=Path(temp_dir),
            )

            self.assertTrue(rendered_artifacts.output_path.exists())
            self.assertEqual(rendered_artifacts.render_trace.input_kind, "deck_spec_json")
            self.assertEqual(rendered_artifacts.deck_plan.pattern_ids, planned_artifacts.deck_plan.pattern_ids)
