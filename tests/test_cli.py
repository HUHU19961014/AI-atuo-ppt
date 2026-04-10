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
                }
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
                patch("tools.sie_autoppt.cli.generate_ppt_artifacts_from_deck_spec", return_value=fake_render_result) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            deck_spec_path = Path(temp_dir) / "Enterprise-AI-PPT.deck_spec.json"
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
                    }
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
                patch("tools.sie_autoppt.cli.generate_ppt_artifacts_from_deck_spec", return_value=fake_render_result) as render_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            structure_mock.assert_called_once()
            request = structure_mock.call_args.args[0]
            self.assertEqual(request.topic, "赛意系统文件上传清单")
            self.assertEqual(request.brief, "按责任人与时限整理上传要求")

            deck_spec_path = Path(temp_dir) / "Enterprise-AI-PPT.deck_spec.json"
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
