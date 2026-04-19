import unittest
import shutil
import os
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
    build_outline_schema,
    build_outline_prompts,
    ensure_generation_context,
    generate_outline_with_ai,
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
    def test_outline_schema_requires_story_rationale_and_strategy_controls(self):
        schema = build_outline_schema(
            OutlineGenerationRequest(
                topic="AI strategy",
                min_slides=3,
                max_slides=3,
                chapter_count=3,
                audience_tier="executive",
                narrative_pacing="balanced",
            )
        )

        self.assertIn("story_rationale", schema["required"])
        self.assertIn("story_rationale", schema["properties"])
        self.assertIn("outline_strategy", schema["required"])
        self.assertIn("outline_strategy", schema["properties"])

    def test_generate_outline_with_ai_requires_story_rationale_field(self):
        payload_without_rationale = {
            "pages": [
                {"page_no": 1, "title": "Decision Context", "goal": "State what decision is needed now."},
                {"page_no": 2, "title": "Execution Path", "goal": "Describe the execution route and dependencies."},
                {"page_no": 3, "title": "Recommendation", "goal": "Summarize recommendation and owner commitment."},
            ],
            "outline_strategy": {
                "chapter_count": 3,
                "audience_tier": "executive",
                "narrative_pacing": "balanced",
            },
        }
        fake_client = type(
            "FakeClient",
            (),
            {"create_structured_json": lambda self, **_: payload_without_rationale},
        )()

        with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})), patch(
            "tools.sie_autoppt.v2.services._create_structured_client", return_value=fake_client
        ):
            with self.assertRaises(ValueError) as exc_info:
                generate_outline_with_ai(
                    OutlineGenerationRequest(topic="AI strategy", min_slides=3, max_slides=3),
                    model="test-model",
                    max_attempts=1,
                )

        self.assertIn("story_rationale", str(exc_info.exception))

    def test_generate_outline_with_ai_retries_on_generic_title_quality_issue(self):
        payloads = [
            {
                "pages": [
                    {"page_no": 1, "title": "Background", "goal": "Provide generic background for everyone."},
                    {"page_no": 2, "title": "Analysis", "goal": "Provide broad analysis without conclusion."},
                    {"page_no": 3, "title": "Future Outlook", "goal": "Describe future outlook with no decision."},
                ],
                "story_rationale": "Attempted to build from context.",
                "outline_strategy": {
                    "chapter_count": 3,
                    "audience_tier": "executive",
                    "narrative_pacing": "balanced",
                },
            },
            {
                "pages": [
                    {"page_no": 1, "title": "Decision Context", "goal": "Frame the decision and the current constraint."},
                    {"page_no": 2, "title": "Execution Tradeoffs", "goal": "Compare options and resource implications."},
                    {"page_no": 3, "title": "Recommended Path", "goal": "Close with recommendation, owner, and milestone."},
                ],
                "story_rationale": "Conclusion first, then tradeoffs, then owner-backed close.",
                "outline_strategy": {
                    "chapter_count": 3,
                    "audience_tier": "executive",
                    "narrative_pacing": "balanced",
                },
            },
        ]

        class SequenceClient:
            def __init__(self, responses):
                self.responses = list(responses)
                self.calls = 0

            def create_structured_json(self, **kwargs):
                self.calls += 1
                return self.responses[self.calls - 1]

        client = SequenceClient(payloads)

        with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})), patch(
            "tools.sie_autoppt.v2.services._create_structured_client", return_value=client
        ):
            outline = generate_outline_with_ai(
                OutlineGenerationRequest(topic="AI strategy", min_slides=3, max_slides=3),
                model="test-model",
                max_attempts=2,
            )

        self.assertEqual(client.calls, 2)
        self.assertEqual(outline.pages[-1].title, "Recommended Path")

    def test_make_v2_ppt_fails_fast_when_pptmaster_root_missing(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Plan", "goal": "Present the roadmap."},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "Focus on one chain first."}]}],
        }
        with patch.dict(os.environ, {}, clear=True), patch(
            "tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})
        ) as ensure_context, patch("tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline), patch(
            "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload
        ):
            with _workspace_tmpdir() as temp_dir, self.assertRaises(FileNotFoundError) as exc_info:
                make_v2_ppt(topic="AI strategy", output_dir=Path(temp_dir))

        self.assertIn("SIE_PPTMASTER_ROOT", str(exc_info.exception))
        ensure_context.assert_called_once()

    def test_make_v2_ppt_uses_explicit_pptmaster_root(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "结论", "goal": "先给结论。"},
                    {"page_no": 2, "title": "路径", "goal": "说明落地路径。"},
                ]
            }
        )
        semantic_payload = {
            "meta": {
                "title": "AI strategy",
                "theme": "sie_consulting_fixed",
                "language": "zh-CN",
                "author": "AI",
                "version": "2.0",
            },
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "先聚焦主链路",
                    "intent": "conclusion",
                    "blocks": [{"kind": "bullets", "items": ["先打通主链路"]}],
                    "data_sources": [{"claim": "效率提升", "source": "内部试点", "confidence": "medium"}],
                }
            ],
        }

        with _workspace_tmpdir() as temp_dir:
            temp_path = Path(temp_dir)
            fake_root = temp_path / "pptmaster_root"
            for relative in (
                "skills/ppt-master/scripts/total_md_split.py",
                "skills/ppt-master/scripts/finalize_svg.py",
                "skills/ppt-master/scripts/svg_to_pptx.py",
            ):
                script_path = fake_root / relative
                script_path.parent.mkdir(parents=True, exist_ok=True)
                script_path.write_text("print('ok')\n", encoding="utf-8")

            def _fake_run_command(command: list[str], *, step_name: str) -> None:
                if step_name == "svg export":
                    output_path = Path(command[command.index("-o") + 1])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(b"pptx")

            with patch(
                "tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})
            ), patch(
                "tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline
            ), patch(
                "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload
            ), patch("tools.sie_autoppt.v2.services._run_command", side_effect=_fake_run_command):
                artifacts = make_v2_ppt(
                    topic="AI strategy",
                    output_dir=temp_path,
                    pptmaster_root=fake_root,
                )
                self.assertTrue(artifacts.pptx_path.exists())

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
        validate_deck_payload(
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

    def test_make_v2_ppt_runs_end_to_end_pipeline_with_svg_stage(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "结论", "goal": "先给结论。"},
                    {"page_no": 2, "title": "路径", "goal": "说明落地路径。"},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {
                    "slide_id": "s1",
                    "title": "先聚焦主链路落地，再扩展到协同优化",
                    "intent": "conclusion",
                    "anti_argument": "短期投入会上升，但可以换来可复用能力。",
                    "blocks": [{"kind": "bullets", "items": ["优先打通主链路", "用试点沉淀标准", "季度复盘扩面"]}],
                    "data_sources": [{"claim": "效率提升", "source": "内部试点", "confidence": "medium"}],
                }
            ],
        }

        with _workspace_tmpdir() as temp_dir:
            temp_path = Path(temp_dir)
            fake_root = temp_path / "pptmaster_root"
            for relative in (
                "skills/ppt-master/scripts/total_md_split.py",
                "skills/ppt-master/scripts/finalize_svg.py",
                "skills/ppt-master/scripts/svg_to_pptx.py",
            ):
                script = fake_root / relative
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text("print('ok')\n", encoding="utf-8")

            def _fake_run_command(command: list[str], *, step_name: str) -> None:
                if step_name == "svg export":
                    output_path = Path(command[command.index("-o") + 1])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(b"pptx")

            with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})), patch(
                "tools.sie_autoppt.v2.services.generate_outline_with_ai", return_value=outline
            ), patch(
                "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai", return_value=semantic_payload
            ), patch(
                "tools.sie_autoppt.v2.services._run_command", side_effect=_fake_run_command
            ):
                artifacts = make_v2_ppt(topic="AI strategy", output_dir=temp_path, pptmaster_root=fake_root)

            self.assertTrue(artifacts.outline_path.exists())
            self.assertTrue(artifacts.semantic_path.exists())
            self.assertTrue(artifacts.deck_path.exists())
            self.assertTrue(artifacts.rewrite_log_path.exists())
            self.assertTrue(artifacts.warnings_path.exists())
            self.assertTrue(artifacts.pptx_path.exists())
            self.assertIsNotNone(artifacts.svg_project_path)
            self.assertTrue((artifacts.svg_project_path / "svg_output").exists())

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

    def test_outline_prompt_uses_normalized_english_policy(self):
        request = OutlineGenerationRequest(topic="AI strategy", language="en", min_slides=3, max_slides=3)
        developer_prompt, _ = build_outline_prompts(request)
        self.assertIn("Use en-US.", developer_prompt)
        self.assertIn("All user-facing text must be in English.", developer_prompt)

    def test_generate_semantic_deck_with_plugin_model_adapter(self):
        outline = OutlineDocument.model_validate(
            {"pages": [{"page_no": 1, "title": "Context", "goal": "Set context."}]}
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "sie_consulting_fixed", "language": "en-US", "author": "AI", "version": "2.0"},
            "slides": [{"slide_id": "s1", "title": "Decision", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "Decide now."}]}],
        }
        fake_client = type("FakeClient", (), {"create_structured_json": lambda self, **_: semantic_payload})()
        with patch.dict(os.environ, {"SIE_AUTOPPT_MODEL_ADAPTER": "plugin_adapter"}), patch(
            "tools.sie_autoppt.v2.services.resolve_model_adapter",
            return_value=lambda _model=None: fake_client,
        ), patch(
            "tools.sie_autoppt.v2.services.ensure_generation_context",
            return_value=({}, {}),
        ):
            result = generate_semantic_deck_with_ai(
                DeckGenerationRequest(topic="AI strategy", outline=outline, language="en"),
                model="test-model",
            )
        self.assertEqual(result["slides"][0]["title"], "Decision")



