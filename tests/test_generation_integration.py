import json
import sys
import tempfile
import unittest
from pathlib import Path

from tools.sie_autoppt.config import DEFAULT_TEMPLATE, INPUT_DIR
from tools.sie_autoppt.deck_spec_io import write_deck_spec
from tools.sie_autoppt.generator import generate_ppt, generate_ppt_artifacts_from_deck_spec, generate_ppt_artifacts_from_html
from tools.sie_autoppt.planning.ai_planner import AiPlanningRequest
from tools.sie_autoppt.qa import write_qa_report
from tools.sie_autoppt.services import render_from_ai_plan


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
            self.assertEqual(qa["schema_version"], "1.4")
            self.assertEqual(qa["checks"]["ending_last"], "PASS")
            self.assertEqual(qa["checks"]["theme_title_font"], "PASS")
            self.assertEqual(qa["checks"]["directory_title_font"], "PASS")
            self.assertEqual(qa["checks"]["directory_assets_preserved"], "PASS")
            self.assertEqual(qa["checks"]["template_pool_mode"], "PASS")
            self.assertEqual(qa["checks"]["reference_style_coverage"], "PASS")
            self.assertEqual(qa["checks"]["preflight"], "PASS")
            self.assertIn("content_density", qa["checks"])
            self.assertIn("title_uniqueness", qa["checks"])
            self.assertEqual(qa["render_trace"]["input_kind"], "html")
            self.assertEqual(qa["render_trace"]["body_render_mode"], "preallocated_pool")
            self.assertEqual(len(qa["render_trace"]["page_traces"]), 3)
            self.assertIn("fallback_render_pages", qa["metrics"])
            self.assertIn("low_confidence_pattern_pages", qa["metrics"])
            self.assertIn("preflight_note_count", qa["metrics"])
            self.assertEqual(qa["metrics"]["preflight_note_count"], 0)

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
            self.assertEqual(qa["checks"]["reference_style_coverage"], "WARN")
            self.assertEqual(qa["checks"]["preflight"], "WARN")
            self.assertEqual(qa["render_trace"]["reference_import_applied"], False)
            self.assertTrue(qa["render_trace"]["reference_import_reason"])
            self.assertEqual(qa["metrics"]["preflight_note_count"], 1)
            self.assertEqual(qa["render_trace"]["preflight_notes"], ["reference body slide library is unavailable"])
            self.assertGreaterEqual(qa["metrics"]["fallback_render_pages"], 1)
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
            self.assertEqual(artifacts.render_trace.preflight_notes, [])
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

    def test_generate_slide_tag_html_with_more_than_three_pages(self):
        html = """
        <div class="title">Supply Chain Compliance</div>
        <slide data-pattern="general_business"><h2>Overview</h2><p>Global pressure</p></slide>
        <slide data-pattern="process_flow"><h2>Roadmap</h2><ul><li>Assess</li><li>Design</li><li>Launch</li></ul></slide>
        <slide data-pattern="solution_architecture"><h2>Architecture</h2><p>Data layer</p><p>Application layer</p></slide>
        <slide data-pattern="org_governance"><h2>Governance</h2><p>Clarify ownership</p></slide>
        <slide><h2>Summary</h2><p>Close the loop</p></slide>
        <slide><h2>Next Step</h2><p>Start pilot</p></slide>
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "slides.html"
            html_path.write_text(html, encoding="utf-8")

            artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=html_path,
                reference_body_path=None,
                output_prefix="Slide_Tag_Six_Pages",
                chapters=None,
                active_start=0,
                output_dir=Path(temp_dir),
            )

            self.assertTrue(artifacts.output_path.exists())
            self.assertEqual(len(artifacts.deck_plan.pattern_ids), 6)
            self.assertEqual(artifacts.deck_plan.pattern_ids[:4], ["general_business", "process_flow", "solution_architecture", "org_governance"])
            self.assertEqual(artifacts.render_trace.body_render_mode, "preallocated_pool")

    def test_generate_slide_tag_html_with_continuation_pages(self):
        html = """
        <div class="title">Supply Chain Compliance</div>
        <slide data-pattern="process_flow">
          <h2>Roadmap</h2>
          <ul>
            <li>Assess current process dependencies across regions</li>
            <li>Design target operating flow with governance controls</li>
            <li>Align governance checkpoints with program milestones</li>
            <li>Prepare migration runbook for cutover readiness</li>
            <li>Execute pilot launch with cross-team command center</li>
            <li>Scale to remaining sites with controlled rollout waves</li>
            <li>Stabilize support model after go-live transition</li>
            <li>Capture KPI baseline for benefits tracking</li>
            <li>Expand controls to supplier collaboration touchpoints</li>
            <li>Close lessons learned and institutionalize playbook</li>
          </ul>
        </slide>
        <slide><h2>Summary</h2><p>Close the loop</p></slide>
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "slides_continuation.html"
            html_path.write_text(html, encoding="utf-8")

            artifacts = generate_ppt_artifacts_from_html(
                template_path=DEFAULT_TEMPLATE,
                html_path=html_path,
                reference_body_path=None,
                output_prefix="Slide_Tag_Continuation",
                chapters=None,
                active_start=0,
                output_dir=Path(temp_dir),
            )

            self.assertTrue(artifacts.output_path.exists())
            self.assertEqual(len(artifacts.deck_plan.deck.body_pages), 3)
            self.assertEqual(artifacts.deck_plan.deck.body_pages[1].page_key, "slide_1_cont_2")
            self.assertTrue(artifacts.deck_plan.deck.body_pages[1].is_continuation)
            self.assertEqual(artifacts.deck_plan.chapter_lines[:2], ["Roadmap", "Summary"])
            self.assertEqual(len(artifacts.render_trace.page_traces), 3)

    def test_render_from_ai_plan_uses_clarified_context_with_external_planner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_path = temp_path / "external_planner.py"
            script_path.write_text(
                "import json, sys\n"
                "payload = json.load(sys.stdin)\n"
                "user_prompt = payload.get('user_prompt', '')\n"
                "assert 'Q2业绩汇报' in user_prompt\n"
                "assert '公司领导' in user_prompt\n"
                "assert '商务专业' in user_prompt\n"
                "assert '增长数据' in user_prompt\n"
                "print(json.dumps({"
                "'cover_title': 'Q2业绩汇报', "
                "'body_pages': ["
                "{'title': '经营表现', 'subtitle': '关键指标回顾', 'bullets': ['收入增长', '利润改善'], 'pattern_id': 'general_business', 'nav_title': '表现'}"
                "]"
                "}, ensure_ascii=False))\n",
                encoding="utf-8",
            )

            result = render_from_ai_plan(
                template_path=DEFAULT_TEMPLATE,
                request=AiPlanningRequest(
                    topic="帮我做Q2业绩汇报，5页，给公司领导看，商务专业风格",
                    brief="重点讲增长数据、技术突破、下阶段计划",
                    chapters=1,
                ),
                reference_body_path=None,
                output_prefix="Clarifier_Render_Path",
                active_start=0,
                output_dir=temp_path,
                planner_command=f'{sys.executable} "{script_path}"',
            )

            self.assertTrue(result.output_path.exists())
            self.assertTrue(result.report_path.exists())
