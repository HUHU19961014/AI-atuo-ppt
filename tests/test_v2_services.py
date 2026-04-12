import unittest
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import tools.sie_autoppt.v2.services as services_module
from tools.sie_autoppt.v2.schema import OutlineDocument, validate_deck_payload
from tools.sie_autoppt.v2.services import (
    DeckGenerationRequest,
    OutlineGenerationRequest,
    build_deck_prompts,
    build_outline_prompts,
    ensure_generation_context,
    generate_semantic_deck_with_ai,
    make_v2_ppt,
    resolve_slide_bounds,
)

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

class V2ServiceTests(unittest.TestCase):
    def test_run_command_passes_timeout(self):
        completed = type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("tools.sie_autoppt.v2.services.subprocess.run", return_value=completed) as run_mock:
            services_module._run_command(["echo", "ok"], step_name="unit-test")

        self.assertIn("timeout", run_mock.call_args.kwargs)

    def test_resolve_slide_bounds_supports_exact_and_range(self):
        self.assertEqual(
            resolve_slide_bounds(OutlineGenerationRequest(topic="AI", exact_slides=8)),
            (8, 8),
        )
        self.assertEqual(
            resolve_slide_bounds(OutlineGenerationRequest(topic="AI", min_slides=6, max_slides=9)),
            (6, 9),
        )

    def test_prompt_builders_include_core_constraints(self):
        context = {"industry": "制造", "audience_priorities": ["ROI"], "decision_focus": "预算决策"}
        strategy = {"core_tension": "投入与回报", "recommended_narrative_arc": "先判断再展开"}
        outline_request = OutlineGenerationRequest(
            topic="AI strategy",
            min_slides=6,
            max_slides=8,
            structured_context=context,
            strategic_analysis=strategy,
        )
        developer_prompt, user_prompt = build_outline_prompts(outline_request)
        self.assertIn("Return 6-8 pages.", developer_prompt)
        self.assertIn("AI strategy", user_prompt)
        self.assertIn('"industry": "制造"', user_prompt)
        self.assertIn('"core_tension": "投入与回报"', user_prompt)

        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain key issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present the roadmap."},
                ]
            }
        )
        deck_request = DeckGenerationRequest(
            topic="AI strategy",
            outline=outline,
            structured_context=context,
            strategic_analysis=strategy,
        )
        developer_prompt, user_prompt = build_deck_prompts(deck_request)
        self.assertIn("section_break", developer_prompt)
        self.assertIn("intent", developer_prompt)
        self.assertIn("blocks", developer_prompt)
        self.assertIn("timeline", developer_prompt)
        self.assertIn("cards", developer_prompt)
        self.assertIn("stats", developer_prompt)
        self.assertIn("matrix", developer_prompt)
        self.assertIn("anti_argument", developer_prompt)
        self.assertIn("data_sources", developer_prompt)
        self.assertIn('"page_no": 1', user_prompt)
        self.assertIn('"industry": "制造"', user_prompt)
        self.assertIn('"recommended_narrative_arc": "先判断再展开"', user_prompt)

    def test_make_v2_ppt_writes_rewritten_deck_artifacts(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain key issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present the roadmap."},
                ]
            }
        )
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test Deck", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [
                    {
                        "slide_id": "s1",
                        "layout": "title_content",
                        "title": "这是一个明显过长并且需要压缩表达的业务分析标题",
                        "content": [
                            "第一条内容明显过长，需要压缩到更适合页面承载的长度，并保留核心信息。",
                            "第二条内容也非常长，需要继续压缩表达，避免页面密度过高。",
                            "第三条需要保留。",
                            "第四条需要保留。",
                            "第五条需要保留。",
                            "第六条需要保留。",
                            "第七条用于测试自动合并。",
                        ],
                    }
                ],
            }
        )
        semantic_payload = {
            "meta": {"title": "Test Deck", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "这是一个明显过长并且需要压缩表达的业务分析标题",
                    "intent": "analysis",
                    "anti_argument": "前期投入和组织协同成本不可忽视。",
                    "data_sources": [
                        {"claim": "投资回收期", "source": "内部试点测算", "confidence": "medium"},
                    ],
                    "blocks": [
                        {
                            "kind": "bullets",
                            "items": [
                                "第一条内容明显过长，需要压缩到更适合页面承载的长度，并保留核心信息。",
                                "第二条内容也非常长，需要继续压缩表达，避免页面密度过高。",
                                "第三条需要保留。",
                                "第四条需要保留。",
                                "第五条需要保留。",
                                "第六条需要保留。",
                                "第七条用于测试自动合并。",
                            ],
                        }
                    ],
                }
            ],
        }

        context = {"industry": "制造", "decision_focus": "预算决策"}
        strategy = {"core_tension": "投入与回报", "recommended_narrative_arc": "先判断再展开"}

        with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=(context, strategy)), patch(
            "tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline
        ), patch(
            "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload
        ), patch(
            "tools.sie_autoppt.v2.services._run_svg_pipeline"
        ):
            with _workspace_tmpdir() as temp_dir:
                artifacts = make_v2_ppt(
                    topic="AI strategy",
                    output_dir=Path(temp_dir),
                    outline_output=Path(temp_dir) / "generated_outline.json",
                    semantic_output=Path(temp_dir) / "generated_semantic_deck.json",
                    deck_output=Path(temp_dir) / "generated_deck.json",
                    log_output=Path(temp_dir) / "log.txt",
                    ppt_output=Path(temp_dir) / "Enterprise-AI-PPT_Presentation.pptx",
                )

                self.assertTrue(artifacts.semantic_path.exists())
                self.assertTrue(artifacts.deck_path.exists())
                self.assertTrue(artifacts.rewrite_log_path.exists())
                self.assertTrue(artifacts.warnings_path.exists())
                payload = artifacts.deck.model_dump(mode="json")
                self.assertGreaterEqual(len(payload["slides"]), 2)
                self.assertTrue(all(slide["layout"] == "title_content" for slide in payload["slides"]))
                self.assertTrue(all(1 <= len(slide["content"]) <= 6 for slide in payload["slides"]))
                self.assertEqual(payload["slides"][0]["anti_argument"], "前期投入和组织协同成本不可忽视。")
                self.assertEqual(payload["slides"][0]["data_sources"][0]["source"], "内部试点测算")

    def test_make_v2_ppt_reuses_generated_context_across_outline_and_deck(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Plan", "goal": "Present the roadmap."},
                    {"page_no": 3, "title": "Decision", "goal": "Ask for a decision."},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "结论",
                    "intent": "conclusion",
                    "blocks": [{"kind": "statement", "text": "先打通主链，再扩展到运营闭环。"}],
                }
            ],
        }
        context = {"industry": "制造", "decision_focus": "预算决策"}
        strategy = {"core_tension": "投入与回报", "recommended_narrative_arc": "先判断再展开"}

        with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=(context, strategy)), patch(
            "tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline
        ) as generate_outline, patch(
            "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload
        ) as generate_semantic, patch(
            "tools.sie_autoppt.v2.services._run_svg_pipeline"
        ):
            with _workspace_tmpdir() as temp_dir:
                make_v2_ppt(topic="AI strategy", output_dir=Path(temp_dir))

        outline_request = generate_outline.call_args.args[0]
        deck_request = generate_semantic.call_args.args[0]
        self.assertEqual(outline_request.structured_context, context)
        self.assertEqual(outline_request.strategic_analysis, strategy)
        self.assertEqual(deck_request.structured_context, context)
        self.assertEqual(deck_request.strategic_analysis, strategy)

    def test_generate_semantic_deck_with_ai_validates_before_returning(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain issues."},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "结论",
                    "intent": "conclusion",
                    "blocks": [{"kind": "statement", "text": "先打通主链，再扩展到运营闭环。"}],
                }
            ],
        }

        fake_client = type(
            "FakeClient",
            (),
            {"create_structured_json": lambda self, **_: semantic_payload},
        )()

        context = {"industry": "制造", "decision_focus": "预算决策"}
        strategy = {"core_tension": "投入与回报", "recommended_narrative_arc": "先判断再展开"}

        with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=(context, strategy)), patch(
            "tools.sie_autoppt.v2.services.load_openai_responses_config"
        ), patch(
            "tools.sie_autoppt.v2.services.OpenAIResponsesClient", return_value=fake_client
        ):
            result = generate_semantic_deck_with_ai(
                DeckGenerationRequest(topic="AI strategy", outline=outline),
                model="test-model",
            )

        self.assertEqual(result["slides"][0]["intent"], "conclusion")

    def test_quick_mode_skips_context_and_strategy_generation(self):
        with patch("tools.sie_autoppt.v2.services.extract_structured_context") as extract_context, patch(
            "tools.sie_autoppt.v2.services.generate_strategy_with_ai"
        ) as generate_strategy:
            context, strategy = ensure_generation_context(
                topic="AI strategy",
                brief="",
                audience="管理层",
                language="zh-CN",
                generation_mode="quick",
                structured_context=None,
                strategic_analysis=None,
                model="test-model",
            )

        self.assertEqual(context, {})
        self.assertEqual(strategy, {})
        extract_context.assert_not_called()
        generate_strategy.assert_not_called()



