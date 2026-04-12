import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt import cli
from tools.sie_autoppt.llm_openai import OpenAIConfigurationError, OpenAIResponsesConfig
from tools.sie_autoppt.models import DeckRenderTrace, PageRenderTrace
from tools.sie_autoppt.v2.schema import OutlineDocument, validate_deck_payload


class CliTests(unittest.TestCase):
    def test_help_emphasizes_primary_commands_without_listing_legacy_choices(self):
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "--help"]),
            redirect_stdout(stdout),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("Primary commands: make, review, iterate", help_text)
        self.assertIn("onepage --topic ...", help_text)
        self.assertIn("sie-render --topic ... or --structure-json ...", help_text)
        self.assertIn("use sie-render for actual SIE template delivery", help_text)
        self.assertNotIn("{make,plan,render", help_text)

    def test_unknown_command_returns_curated_error_message(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "unknown-cmd"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("unknown command 'unknown-cmd'", stderr.getvalue())
        self.assertIn("primary commands (make, review, iterate)", stderr.getvalue())

    def test_ai_check_prints_summary(self):
        outline = OutlineDocument.model_validate(
            {"pages": [{"page_no": 1, "title": "Context", "goal": "Set context."}]}
        )
        deck = validate_deck_payload(
            {
                "meta": {"title": "AI AutoPPT Healthcheck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Test Page"}],
            }
        )
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-check", "--topic", "Healthcheck"]),
            patch(
                "tools.sie_autoppt.healthcheck.load_openai_responses_config",
                return_value=OpenAIResponsesConfig(
                    api_key="test-key",
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini",
                    timeout_sec=30,
                    reasoning_effort="low",
                    text_verbosity="low",
                    api_style="responses",
                ),
            ),
            patch("tools.sie_autoppt.healthcheck.generate_outline_with_ai", return_value=outline),
            patch("tools.sie_autoppt.healthcheck.generate_deck_with_ai", return_value=deck),
            redirect_stdout(stdout),
        ):
            cli.main()

        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["api_style"], "responses")
        self.assertEqual(payload["page_count"], 1)
        self.assertEqual(payload["first_page_title"], "Test Page")

    def test_make_rejects_mixing_exact_and_range(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "make", "--topic", "Test", "--chapters", "4", "--min-slides", "3"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--chapters cannot be combined", stderr.getvalue())

    def test_ai_check_reports_missing_api_key(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-check"]),
            patch(
                "tools.sie_autoppt.healthcheck.load_openai_responses_config",
                side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
            ),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("AI healthcheck blocked", stderr.getvalue())

    def test_ai_check_with_render_passes_flag_and_output_dir(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "ai-check", "--topic", "Healthcheck", "--with-render", "--output-dir", temp_dir]),
                patch(
                    "tools.sie_autoppt.cli.run_ai_healthcheck",
                    return_value=type("FakeSummary", (), {"to_json": lambda self: json.dumps({"status": "ok", "render_checked": True})})(),
                ) as healthcheck_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        self.assertTrue(json.loads(stdout.getvalue().strip())["render_checked"])
        self.assertTrue(healthcheck_mock.call_args.kwargs["with_render"])
        self.assertEqual(healthcheck_mock.call_args.kwargs["output_dir"], Path(temp_dir))

    def test_clarify_outputs_session_json_and_persists_state_file(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}\\clarifier_state.json"
            with (
                patch("sys.argv", ["sie-autoppt", "clarify", "--topic", "帮我做PPT", "--clarifier-state-file", state_path]),
                redirect_stdout(stdout),
            ):
                cli.main()

            payload = json.loads(stdout.getvalue().strip())
            self.assertEqual(payload["status"], "needs_clarification")
            self.assertTrue(payload["session"]["pending_dimensions"])

    def test_clarify_web_starts_local_server_with_host_and_port(self):
        with (
            patch("sys.argv", ["sie-autoppt", "clarify-web", "--host", "127.0.0.1", "--port", "9001"]),
            patch("tools.sie_autoppt.cli.serve_clarifier_web") as mocked_serve,
        ):
            cli.main()

        mocked_serve.assert_called_once_with(host="127.0.0.1", port=9001)

    def test_demo_renders_bundled_sample_without_ai(self):
        stdout = io.StringIO()
        demo_deck = validate_deck_payload(
            {
                "meta": {"title": "Demo", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Demo"}],
            }
        ).deck
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "demo", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.load_deck_document", return_value=demo_deck) as load_mock,
                patch(
                    "tools.sie_autoppt.cli.generate_v2_ppt",
                    return_value=type(
                        "FakeRenderArtifacts",
                        (),
                        {
                            "rewrite_log_path": Path(temp_dir) / "demo" / "rewrite_log.json",
                            "warnings_path": Path(temp_dir) / "demo" / "warnings.json",
                            "output_path": Path(temp_dir) / "demo" / "demo.pptx",
                        },
                    )(),
                ) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            load_mock.assert_called_once_with(cli.DEMO_SAMPLE_DECK)
            called = render_mock.call_args.kwargs
            self.assertEqual(called["output_path"].parent, Path(temp_dir) / "demo")
            self.assertEqual(called["log_path"].parent, Path(temp_dir) / "demo")
            self.assertTrue(called["output_path"].name.startswith("Enterprise-AI-PPT_demo_"))
            self.assertTrue(called["output_path"].name.endswith(".pptx"))
            self.assertTrue(called["log_path"].name.startswith("Enterprise-AI-PPT_demo_"))
            self.assertTrue(called["log_path"].name.endswith(".log.txt"))
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(cli.DEMO_SAMPLE_DECK))
            self.assertTrue(lines[1].endswith("rewrite_log.json"))
            self.assertTrue(lines[2].endswith("warnings.json"))
            self.assertIn("Enterprise-AI-PPT_demo_", lines[3])
            self.assertTrue(lines[3].endswith(".log.txt"))
            self.assertTrue(lines[4].endswith("demo.pptx"))

    def test_sie_render_builds_deck_spec_from_structure_json(self):
        stdout = io.StringIO()
        structure_payload = {
            "core_message": "对欧出口供应链合规追溯",
            "structure_type": "analysis",
            "sections": [
                {
                    "title": "监管要求",
                    "key_message": "法规和行业标准共同抬升追溯门槛。",
                    "arguments": [
                        {"point": "建立供应链地图", "evidence": "覆盖关键供应商与节点"},
                        {"point": "保留审计证据", "evidence": "支持抽查与举证"},
                    ],
                },
                {
                    "title": "实施路径",
                    "key_message": "分阶段完成主数据、流程与审计闭环。",
                    "arguments": [
                        {"point": "先试点后推广", "evidence": "降低切换风险"},
                        {"point": "统一审计口径", "evidence": "提升外审通过率"},
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            structure_path = Path(temp_dir) / "structure.json"
            structure_path.write_text(json.dumps(structure_payload, ensure_ascii=False), encoding="utf-8-sig")
            fake_ppt_path = Path(temp_dir) / "template-output.pptx"
            fake_render_result = type(
                "FakeRenderArtifacts",
                (),
                {
                    "output_path": fake_ppt_path,
                    "render_trace": DeckRenderTrace(
                        input_kind="deck_spec_json",
                        body_render_mode="preallocated_pool",
                        reference_import_applied=False,
                        page_traces=[
                            PageRenderTrace(
                                page_key="struct_page_01",
                                title="监管要求",
                                requested_pattern_id="general_business",
                                actual_pattern_id="general_business",
                            )
                        ],
                    ),
                },
            )()
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "sie-render",
                        "--structure-json",
                        str(structure_path),
                        "--output-dir",
                        temp_dir,
                    ],
                ),
                patch(
                    "tools.sie_autoppt.cli.apply_ai_content_layout_to_deck_spec",
                    side_effect=lambda deck_spec, model=None: (
                        deck_spec,
                        [{"page_index": 1, "old_pattern_id": "general_business", "new_pattern_id": "general_business", "rationale": "mock"}],
                    ),
                ),
                patch("tools.sie_autoppt.cli.generate_ppt_artifacts_from_deck_spec", return_value=fake_render_result) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            deck_spec_path = Path(temp_dir) / "Enterprise-AI-PPT.deck_spec.ai.json"
            render_trace_path = Path(temp_dir) / "Enterprise-AI-PPT.render_trace.json"
            self.assertTrue(deck_spec_path.exists())
            self.assertTrue(render_trace_path.exists())
            deck_spec_payload = json.loads(deck_spec_path.read_text(encoding="utf-8"))
            self.assertEqual(deck_spec_payload["cover_title"], "对欧出口供应链合规追溯")
            render_mock.assert_called_once()
            self.assertEqual(render_mock.call_args.kwargs["deck_spec_path"], deck_spec_path)
            self.assertEqual(render_mock.call_args.kwargs["template_path"], cli.DEFAULT_TEMPLATE)
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(deck_spec_path))
            self.assertEqual(lines[1], str(render_trace_path))
            self.assertEqual(lines[2], str(fake_ppt_path))

    def test_sie_render_requires_exactly_one_input_contract(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_spec_path = Path(temp_dir) / "deck_spec.json"
            structure_path = Path(temp_dir) / "structure.json"
            deck_spec_path.write_text("{}", encoding="utf-8")
            structure_path.write_text("{}", encoding="utf-8")
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "sie-render",
                        "--structure-json",
                        str(structure_path),
                        "--deck-spec-json",
                        str(deck_spec_path),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn(
            "exactly one actual-template input is required when command is 'sie-render'",
            stderr.getvalue(),
        )
        self.assertIn("--topic", stderr.getvalue())

    def test_sie_render_rejects_single_page_deck_spec_and_guides_onepage(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_spec_path = Path(temp_dir) / "deck_spec.json"
            deck_spec_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "cover_title": "x",
                        "body_pages": [
                            {
                                "page_key": "p1",
                                "title": "t",
                                "subtitle": "",
                                "bullets": ["a"],
                                "pattern_id": "claim_breakdown",
                                "nav_title": "",
                                "reference_style_id": None,
                                "payload": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "sie-render",
                        "--deck-spec-json",
                        str(deck_spec_path),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    cli.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("must use the 'onepage' command", stderr.getvalue())

    def test_sie_render_can_generate_structure_with_ai_from_topic(self):
        stdout = io.StringIO()
        fake_structure = cli.StructureSpec.from_dict(
            {
                "core_message": "供应链文件上传要点",
                "structure_type": "analysis",
                "sections": [
                    {
                        "title": "执行分工",
                        "key_message": "按责任人和时限上传关键单据。",
                        "arguments": [
                            {"point": "明确负责人", "evidence": "减少遗漏"},
                            {"point": "锁定时限", "evidence": "避免逾期"},
                        ],
                    },
                    {
                        "title": "审核准备",
                        "key_message": "按节点准备证据和追溯链路。",
                        "arguments": [
                            {"point": "先整理主数据", "evidence": "减少返工"},
                            {"point": "统一资料模板", "evidence": "便于第三方核查"},
                        ],
                    },
                ],
            }
        )
        fake_structure_result = type("FakeStructureResult", (), {"structure": fake_structure})()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_ppt_path = Path(temp_dir) / "template-output.pptx"
            fake_render_result = type(
                "FakeRenderArtifacts",
                (),
                {
                    "output_path": fake_ppt_path,
                    "render_trace": DeckRenderTrace(
                        input_kind="deck_spec_json",
                        body_render_mode="preallocated_pool",
                        reference_import_applied=False,
                        page_traces=[
                            PageRenderTrace(
                                page_key="struct_page_01",
                                title="执行分工",
                                requested_pattern_id="general_business",
                                actual_pattern_id="general_business",
                            )
                        ],
                    ),
                },
            )()
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "sie-render",
                        "--topic",
                        "赛意系统文件上传清单",
                        "--brief",
                        "按责任人与时限整理上传要求",
                        "--output-dir",
                        temp_dir,
                    ],
                ),
                patch("tools.sie_autoppt.cli.generate_structure_with_ai", return_value=fake_structure_result) as structure_mock,
                patch(
                    "tools.sie_autoppt.cli.apply_ai_content_layout_to_deck_spec",
                    side_effect=lambda deck_spec, model=None: (
                        deck_spec,
                        [{"page_index": 1, "old_pattern_id": "general_business", "new_pattern_id": "general_business", "rationale": "mock"}],
                    ),
                ),
                patch("tools.sie_autoppt.cli.generate_ppt_artifacts_from_deck_spec", return_value=fake_render_result) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            structure_mock.assert_called_once()
            request = structure_mock.call_args.args[0]
            self.assertEqual(request.topic, "赛意系统文件上传清单")
            self.assertEqual(request.brief, "按责任人与时限整理上传要求")

            deck_spec_path = Path(temp_dir) / "Enterprise-AI-PPT.deck_spec.ai.json"
            render_trace_path = Path(temp_dir) / "Enterprise-AI-PPT.render_trace.json"
            self.assertTrue(deck_spec_path.exists())
            self.assertTrue(render_trace_path.exists())

            deck_spec_payload = json.loads(deck_spec_path.read_text(encoding="utf-8"))
            self.assertEqual(deck_spec_payload["cover_title"], "赛意系统文件上传清单")

            render_mock.assert_called_once()
            self.assertEqual(render_mock.call_args.kwargs["deck_spec_path"], deck_spec_path)
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(deck_spec_path))
            self.assertEqual(lines[1], str(render_trace_path))
            self.assertEqual(lines[2], str(fake_ppt_path))

    def test_onepage_can_generate_structure_with_ai_from_topic(self):
        stdout = io.StringIO()
        fake_structure = cli.StructureSpec.from_dict(
            {
                "core_message": "上传责任、时限与动作需要放在同一页看清",
                "structure_type": "analysis",
                "sections": [
                    {
                        "title": "责任分工",
                        "key_message": "按责任人与时限拆解执行动作。",
                        "arguments": [
                            {"point": "明确负责人", "evidence": "减少遗漏"},
                            {"point": "锁定时限", "evidence": "避免逾期"},
                        ],
                    },
                    {
                        "title": "执行节奏",
                        "key_message": "围绕 ERP 触发点组织动作。",
                        "arguments": [
                            {"point": "发货单", "evidence": "7-13 天"},
                            {"point": "送货单", "evidence": "生成后 1 天"},
                        ],
                    },
                    {
                        "title": "批次说明",
                        "key_message": "后续批次直接上传赛意系统。",
                        "arguments": [
                            {"point": "起始批次", "evidence": "2025-07-15"},
                            {"point": "系统要求", "evidence": "直接上传"},
                        ],
                    },
                ],
            }
        )
        fake_structure_result = type("FakeStructureResult", (), {"structure": fake_structure})()
        fake_review_path = Path("C:/tmp/fake.review.json")
        fake_score_path = Path("C:/tmp/fake.score.json")
        fake_ppt_path = Path("C:/tmp/fake.onepage.pptx")
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "onepage",
                        "--topic",
                        "赛意系统文件上传清单",
                        "--brief",
                        "按责任人与时限整理上传要求",
                        "--output-dir",
                        temp_dir,
                    ],
                ),
                patch("tools.sie_autoppt.cli.generate_structure_with_ai", return_value=fake_structure_result) as structure_mock,
                patch(
                    "tools.sie_autoppt.cli.build_onepage_slide",
                    return_value=(fake_ppt_path, fake_review_path, fake_score_path, object()),
                ) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            structure_mock.assert_called_once()
            request = structure_mock.call_args.args[0]
            self.assertEqual(request.topic, "赛意系统文件上传清单")
            self.assertEqual(request.brief, "按责任人与时限整理上传要求")
            self.assertEqual(request.sections, 3)

            render_mock.assert_called_once()
            brief_output_path = Path(temp_dir) / "Enterprise-AI-PPT.onepage_brief.json"
            self.assertTrue(brief_output_path.exists())
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(brief_output_path))
            self.assertEqual(lines[1], str(fake_review_path))
            self.assertEqual(lines[2], str(fake_score_path))
            self.assertEqual(lines[3], str(fake_ppt_path))

    @unittest.skip("onepage now requires AI; fallback mode removed")
    def test_onepage_falls_back_when_ai_key_is_missing(self):
        stdout = io.StringIO()
        fake_review_path = Path("C:/tmp/fallback.review.json")
        fake_score_path = Path("C:/tmp/fallback.score.json")
        fake_ppt_path = Path("C:/tmp/fallback.onepage.pptx")
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "onepage",
                        "--topic",
                        "供应链周报",
                        "--brief",
                        "按状态、风险和动作组织一页汇报",
                        "--output-dir",
                        temp_dir,
                    ],
                ),
                patch(
                    "tools.sie_autoppt.cli.generate_structure_with_ai",
                    side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
                ),
                patch(
                    "tools.sie_autoppt.cli.build_onepage_slide",
                    return_value=(fake_ppt_path, fake_review_path, fake_score_path, object()),
                ),
                redirect_stdout(stdout),
            ):
                cli.main()

            brief_output_path = Path(temp_dir) / "Enterprise-AI-PPT.onepage_brief.json"
            payload = json.loads(brief_output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "供应链周报")
            self.assertEqual(payload["layout_strategy"], "auto")
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(brief_output_path))
            self.assertEqual(lines[3], str(fake_ppt_path))

    def test_onepage_requires_ai_and_fails_when_ai_key_is_missing(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "onepage",
                        "--topic",
                        "供应链周报",
                        "--brief",
                        "按状态、风险和动作组织一页汇报",
                        "--output-dir",
                        temp_dir,
                    ],
                ),
                patch(
                    "tools.sie_autoppt.cli.generate_structure_with_ai",
                    side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
                ),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    cli.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("AI is mandatory for 'onepage' content/layout planning", stderr.getvalue())

    def test_v2_plan_reuses_generation_context_between_outline_and_semantic_deck(self):
        stdout = io.StringIO()
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "背景", "goal": "说明背景。"},
                    {"page_no": 2, "title": "方案", "goal": "说明方案。"},
                    {"page_no": 3, "title": "行动", "goal": "说明行动。"},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "AI strategy", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [
                {"slide_id": "s1", "title": "结论", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "先判断再展开。"}]},
            ],
        }
        shared_context = {"industry": "制造", "decision_focus": "预算"}
        shared_strategy = {"core_tension": "投入与回报", "recommended_narrative_arc": "先判断再展开"}
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    ["sie-autoppt", "v2-plan", "--topic", "AI strategy", "--output-dir", temp_dir],
                ),
                patch(
                    "tools.sie_autoppt.cli.resolve_v2_clarified_context",
                    return_value=("AI strategy", "", "公司领导", None, 6, 8, "business_red"),
                ),
                patch(
                    "tools.sie_autoppt.cli.ensure_generation_context",
                    return_value=(shared_context, shared_strategy),
                ) as context_mock,
                patch("tools.sie_autoppt.cli.generate_outline_with_ai", return_value=outline) as outline_mock,
                patch("tools.sie_autoppt.cli.generate_semantic_deck_with_ai", return_value=semantic_payload) as semantic_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            context_mock.assert_called_once()
            outline_request = outline_mock.call_args.args[0]
            deck_request = semantic_mock.call_args.args[0]
            self.assertEqual(outline_request.structured_context, shared_context)
            self.assertEqual(outline_request.strategic_analysis, shared_strategy)
            self.assertEqual(deck_request.structured_context, shared_context)
            self.assertEqual(deck_request.strategic_analysis, shared_strategy)

    def test_removed_legacy_command_is_rejected(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "structure", "--topic", "做一个AI行业趋势汇报"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("unknown command 'structure'", stderr.getvalue())

    def test_topic_without_explicit_command_requires_clarification_before_v2_make(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "--topic", "做一份装备制造数字化方案", "--output-dir", temp_dir]),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    cli.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("Clarification required before 'v2-make'", stderr.getvalue())
        self.assertIn("semantic v2-make", stderr.getvalue())

    def test_v2_route_rejects_explicit_template_argument(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "--topic", "测试主题", "--template", "custom.pptx"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--template is no longer supported", stderr.getvalue())

    def test_option_was_explicit_supports_equals_syntax(self):
        self.assertTrue(cli.option_was_explicit(["--template=custom.pptx"], "--template"))
        self.assertTrue(cli.option_was_explicit(["--theme=business_red"], "--theme"))
        self.assertFalse(cli.option_was_explicit(["--topic", "test"], "--template"))

    def test_v2_option_compatibility_rejects_template_equals_syntax(self):
        parser = cli.argparse.ArgumentParser(add_help=False)
        with self.assertRaises(SystemExit) as ctx:
            cli.validate_v2_option_compatibility(
                ["--template=custom.pptx"],
                effective_command="v2-make",
                parser=parser,
            )

        self.assertEqual(ctx.exception.code, 2)

    def test_v2_option_compatibility_rejects_non_fixed_theme_equals_syntax(self):
        parser = cli.argparse.ArgumentParser(add_help=False)
        with self.assertRaises(SystemExit) as ctx:
            cli.validate_v2_option_compatibility(
                ["--theme=business_red"],
                effective_command="v2-make",
                parser=parser,
            )

        self.assertEqual(ctx.exception.code, 2)

    def test_explicit_make_with_topic_routes_to_v2_make(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "make", "--topic", "测试主题", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=("测试主题", "", "公司领导", None, 6, 8, "business_red")),
                patch(
                    "tools.sie_autoppt.cli.make_v2_ppt",
                    return_value=type(
                        "FakeArtifacts",
                        (),
                        {
                            "outline_path": Path(temp_dir) / "deck.outline.json",
                            "semantic_path": Path(temp_dir) / "deck.semantic.v2.json",
                            "deck_path": Path(temp_dir) / "deck.deck.v2.json",
                            "rewrite_log_path": Path(temp_dir) / "rewrite_log.json",
                            "warnings_path": Path(temp_dir) / "warnings.json",
                            "log_path": Path(temp_dir) / "deck.log.txt",
                            "pptx_path": Path(temp_dir) / "deck.pptx",
                        },
                    )(),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                cli.main()

        self.assertIn("'make' routes to semantic v2-make", stderr.getvalue())
        self.assertIn("deck.pptx", stdout.getvalue())

    def test_visual_draft_requires_deck_spec_json(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "visual-draft", "--output-dir", "C:/tmp"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--deck-spec-json is required when command is 'visual-draft'", stderr.getvalue())

    def test_visual_draft_prints_artifact_paths(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_artifacts = type(
                "VisualDraftArtifacts",
                (),
                {
                    "visual_spec_path": Path(temp_dir) / "why.visual_spec.json",
                    "preview_html_path": Path(temp_dir) / "why.preview.html",
                    "preview_png_path": Path(temp_dir) / "why.preview.png",
                    "visual_score_path": Path(temp_dir) / "why.visual_score.json",
                    "ai_review_path": Path(temp_dir) / "why.ai_visual_review.json",
                },
            )()
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "visual-draft",
                        "--deck-spec-json",
                        "C:/tmp/deck_spec.json",
                        "--output-dir",
                        temp_dir,
                        "--output-name",
                        "why",
                    ],
                ),
                patch("tools.sie_autoppt.cli.load_deck_spec", return_value=object()) as load_mock,
                patch("tools.sie_autoppt.cli.generate_visual_draft_artifacts", return_value=fake_artifacts) as run_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        load_mock.assert_called_once_with(Path("C:/tmp/deck_spec.json"))
        self.assertEqual(run_mock.call_args.kwargs["output_name"], "why")
        self.assertFalse(run_mock.call_args.kwargs["with_ai_review"])
        self.assertEqual(run_mock.call_args.kwargs["visual_rules_path"], "")
        lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].endswith(".visual_spec.json"))
        self.assertTrue(lines[4].endswith(".ai_visual_review.json"))

    def test_visual_draft_with_ai_flag_is_forwarded(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_artifacts = type(
                "VisualDraftArtifacts",
                (),
                {
                    "visual_spec_path": Path(temp_dir) / "why.visual_spec.json",
                    "preview_html_path": Path(temp_dir) / "why.preview.html",
                    "preview_png_path": Path(temp_dir) / "why.preview.png",
                    "visual_score_path": Path(temp_dir) / "why.visual_score.json",
                    "ai_review_path": Path(temp_dir) / "why.ai_visual_review.json",
                },
            )()
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "visual-draft",
                        "--deck-spec-json",
                        "C:/tmp/deck_spec.json",
                        "--output-dir",
                        temp_dir,
                        "--with-ai-review",
                    ],
                ),
                patch("tools.sie_autoppt.cli.load_deck_spec", return_value=object()),
                patch("tools.sie_autoppt.cli.generate_visual_draft_artifacts", return_value=fake_artifacts) as run_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        self.assertTrue(run_mock.call_args.kwargs["with_ai_review"])

    def test_visual_draft_with_rules_path_is_forwarded(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_artifacts = type(
                "VisualDraftArtifacts",
                (),
                {
                    "visual_spec_path": Path(temp_dir) / "why.visual_spec.json",
                    "preview_html_path": Path(temp_dir) / "why.preview.html",
                    "preview_png_path": Path(temp_dir) / "why.preview.png",
                    "visual_score_path": Path(temp_dir) / "why.visual_score.json",
                    "ai_review_path": Path(temp_dir) / "why.ai_visual_review.json",
                },
            )()
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "visual-draft",
                        "--deck-spec-json",
                        "C:/tmp/deck_spec.json",
                        "--output-dir",
                        temp_dir,
                        "--visual-rules-path",
                        "C:/tmp/visual_rules.toml",
                    ],
                ),
                patch("tools.sie_autoppt.cli.load_deck_spec", return_value=object()),
                patch("tools.sie_autoppt.cli.generate_visual_draft_artifacts", return_value=fake_artifacts) as run_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        self.assertEqual(run_mock.call_args.kwargs["visual_rules_path"], "C:/tmp/visual_rules.toml")

    def test_make_without_topic_or_outline_errors(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "make"]),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--topic or --outline-json is required when command is 'v2-make'", stderr.getvalue())
