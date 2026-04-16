import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tools.sie_autoppt import cli
from tools.sie_autoppt.v2.schema import OutlineDocument, validate_deck_payload

RESOLVED_V2_CONTEXT = (
    "AI make",
    "Brief",
    "公司领导",
    None,
    6,
    10,
    "business_red",
)


class V2CliTests(unittest.TestCase):
    def test_v2_outline_writes_default_outline_path(self):
        stdout = io.StringIO()
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Plan", "goal": "Show plan."},
                    {"page_no": 3, "title": "Action", "goal": "Next steps."},
                ]
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-outline", "--topic", "AI outline", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.generate_outline_with_ai", return_value=outline),
                redirect_stdout(stdout),
            ):
                cli.main()

            self.assertIn(str(Path(temp_dir) / "generated_outline.json"), stdout.getvalue())

    def test_v2_plan_prints_outline_semantic_and_deck_paths(self):
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present plan."},
                    {"page_no": 4, "title": "Impact", "goal": "Quantify impact."},
                    {"page_no": 5, "title": "Roadmap", "goal": "Show roadmap."},
                    {"page_no": 6, "title": "Conclusion", "goal": "Close the deck."},
                ]
            }
        )
        validated = validate_deck_payload(
            {
                "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"layout": "title_only", "title": "Conclusion"}],
            }
        )
        semantic_payload = {
            "meta": {"title": "Test Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "Conclusion"}]}],
        }

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-plan", "--topic", "AI plan", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.ensure_generation_context", return_value=({}, None)),
                patch("tools.sie_autoppt.cli.generate_outline_with_ai", return_value=outline),
                patch("tools.sie_autoppt.cli.generate_semantic_deck_with_ai", return_value=semantic_payload),
                patch("tools.sie_autoppt.cli.compile_semantic_deck_payload", return_value=validated),
                redirect_stdout(stdout),
            ):
                cli.main()

            output = stdout.getvalue()
            self.assertIn("generated_outline.json", output)
            self.assertIn("generated_semantic_deck.json", output)
            self.assertIn("generated_deck.json", output)

    def test_v2_make_prints_seven_artifact_paths(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-make", "--topic", "AI make", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
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
            ):
                cli.main()

            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 7)
            self.assertTrue(lines[0].endswith(".outline.json"))
            self.assertTrue(lines[1].endswith(".semantic.v2.json"))
            self.assertTrue(lines[2].endswith(".deck.v2.json"))
            self.assertTrue(lines[3].endswith("rewrite_log.json"))
            self.assertTrue(lines[4].endswith("warnings.json"))
            self.assertTrue(lines[5].endswith(".log.txt"))
            self.assertTrue(lines[6].endswith(".pptx"))

    def test_v2_make_with_isolate_output_uses_run_subdirectory(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "v2-make",
                        "--topic",
                        "AI make",
                        "--output-dir",
                        temp_dir,
                        "--isolate-output",
                        "--run-id",
                        "run-001",
                    ],
                ),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch(
                    "tools.sie_autoppt.cli.make_v2_ppt",
                    return_value=type(
                        "FakeArtifacts",
                        (),
                        {
                            "outline_path": Path(temp_dir) / "runs" / "run-001" / "deck.outline.json",
                            "semantic_path": Path(temp_dir) / "runs" / "run-001" / "deck.semantic.v2.json",
                            "deck_path": Path(temp_dir) / "runs" / "run-001" / "deck.deck.v2.json",
                            "rewrite_log_path": Path(temp_dir) / "runs" / "run-001" / "rewrite_log.json",
                            "warnings_path": Path(temp_dir) / "runs" / "run-001" / "warnings.json",
                            "log_path": Path(temp_dir) / "runs" / "run-001" / "deck.log.txt",
                            "pptx_path": Path(temp_dir) / "runs" / "run-001" / "deck.pptx",
                        },
                    )(),
                ) as make_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        self.assertEqual(make_mock.call_args.kwargs["output_dir"], Path(temp_dir) / "runs" / "run-001")

    def test_v2_make_timeout_always_fails(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    ["sie-autoppt", "v2-make", "--topic", "AI make", "--output-dir", temp_dir],
                ),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.make_v2_ppt", side_effect=TimeoutError("timed out")),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as exc:
                    cli.main()
            self.assertEqual(exc.exception.code, 1)
            self.assertIn("timed out", stderr.getvalue())

    def test_v2_make_passes_generation_mode_to_services(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    ["sie-autoppt", "v2-make", "--topic", "AI make", "--output-dir", temp_dir, "--generation-mode", "quick"],
                ),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
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
                ) as make_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

        self.assertEqual(make_mock.call_args.kwargs["generation_mode"], "quick")

    def test_v2_compile_writes_compiled_deck_from_semantic_json(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_path = Path(temp_dir) / "generated_semantic_deck.json"
            semantic_path.write_text(
                json.dumps(
                    {
                        "meta": {
                            "title": "Test",
                            "theme": "business_red",
                            "language": "zh-CN",
                            "author": "AI",
                            "version": "2.0",
                        },
                        "slides": [
                            {
                                "slide_id": "s1",
                                "title": "Conclusion",
                                "intent": "conclusion",
                                "blocks": [{"kind": "statement", "text": "Lead with the core decision."}],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            compiled_path = Path(temp_dir) / "compiled.deck.json"
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "v2-compile",
                        "--deck-json",
                        str(semantic_path),
                        "--plan-output",
                        str(compiled_path),
                    ],
                ),
                redirect_stdout(stdout),
            ):
                cli.main()

            self.assertEqual(stdout.getvalue().strip(), str(compiled_path))
            payload = json.loads(compiled_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["slides"][0]["layout"], "title_only")
            self.assertEqual(payload["slides"][0]["title"], "Lead with the core decision.")

    def test_full_pipeline_uses_standardized_v2_output_names(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "--full-pipeline", "--topic", "AI make", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch(
                    "tools.sie_autoppt.cli.make_v2_ppt",
                    return_value=type(
                        "FakeArtifacts",
                        (),
                        {
                            "outline_path": Path(temp_dir) / "generated_outline.json",
                            "semantic_path": Path(temp_dir) / "generated_semantic_deck.json",
                            "deck_path": Path(temp_dir) / "generated_deck.json",
                            "rewrite_log_path": Path(temp_dir) / "rewrite_log.json",
                            "warnings_path": Path(temp_dir) / "warnings.json",
                            "log_path": Path(temp_dir) / "log.txt",
                            "pptx_path": Path(temp_dir) / "Enterprise-AI-PPT_Presentation.pptx",
                        },
                    )(),
                ) as make_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            called = make_mock.call_args.kwargs
            self.assertEqual(called["outline_output"], Path(temp_dir) / "generated_outline.json")
            self.assertEqual(called["semantic_output"], Path(temp_dir) / "generated_semantic_deck.json")
            self.assertEqual(called["deck_output"], Path(temp_dir) / "generated_deck.json")
            self.assertEqual(called["log_output"], Path(temp_dir) / "log.txt")
            self.assertEqual(called["ppt_output"], Path(temp_dir) / "Enterprise-AI-PPT_Presentation.pptx")

            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(lines[0], str(Path(temp_dir) / "generated_outline.json"))
            self.assertEqual(lines[1], str(Path(temp_dir) / "generated_semantic_deck.json"))
            self.assertEqual(lines[2], str(Path(temp_dir) / "generated_deck.json"))
            self.assertEqual(lines[3], str(Path(temp_dir) / "rewrite_log.json"))
            self.assertEqual(lines[4], str(Path(temp_dir) / "warnings.json"))
            self.assertEqual(lines[5], str(Path(temp_dir) / "log.txt"))
            self.assertEqual(lines[6], str(Path(temp_dir) / "Enterprise-AI-PPT_Presentation.pptx"))

    def test_v2_make_full_pipeline_e2e_writes_all_artifacts(self):
        stdout = io.StringIO()

        def fake_make_v2_ppt(**kwargs):
            outline_path = kwargs["outline_output"]
            semantic_path = kwargs["semantic_output"]
            deck_path = kwargs["deck_output"]
            log_path = kwargs["log_output"]
            pptx_path = kwargs["ppt_output"]
            rewrite_log_path = kwargs["output_dir"] / "rewrite_log.json"
            warnings_path = kwargs["output_dir"] / "warnings.json"

            outline_path.parent.mkdir(parents=True, exist_ok=True)
            outline_path.write_text('{"pages":[{"page_no":1,"title":"Intro","goal":"Set context."}]}', encoding="utf-8")
            semantic_path.write_text('{"meta":{"title":"Deck"},"slides":[]}', encoding="utf-8")
            deck_path.write_text('{"meta":{"title":"Deck"},"slides":[]}', encoding="utf-8")
            rewrite_log_path.write_text('{"rewrites":[]}', encoding="utf-8")
            warnings_path.write_text('{"warnings":[]}', encoding="utf-8")
            log_path.write_text("render ok", encoding="utf-8")
            pptx_path.write_bytes(b"pptx")

            return type(
                "FakeArtifacts",
                (),
                {
                    "outline_path": outline_path,
                    "semantic_path": semantic_path,
                    "deck_path": deck_path,
                    "rewrite_log_path": rewrite_log_path,
                    "warnings_path": warnings_path,
                    "log_path": log_path,
                    "pptx_path": pptx_path,
                },
            )()

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-make", "--topic", "AI make", "--full-pipeline", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.make_v2_ppt", side_effect=fake_make_v2_ppt),
                redirect_stdout(stdout),
            ):
                cli.main()

            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 7)
            for line in lines:
                self.assertTrue(Path(line).exists(), f"Expected artifact to exist: {line}")
            self.assertTrue(lines[0].endswith("generated_outline.json"))
            self.assertTrue(lines[1].endswith("generated_semantic_deck.json"))
            self.assertTrue(lines[2].endswith("generated_deck.json"))
            self.assertTrue(lines[6].endswith("Enterprise-AI-PPT_Presentation.pptx"))

    def test_v2_plan_with_outline_json_skips_context_generation(self):
        stdout = io.StringIO()
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Issues", "goal": "Explain issues."},
                    {"page_no": 3, "title": "Plan", "goal": "Present plan."},
                ]
            }
        )
        semantic_payload = {
            "meta": {"title": "Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
            "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "Lead with a decision."}]}],
        }
        validated = validate_deck_payload(
            {
                "meta": {"title": "Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Conclusion"}],
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            outline_path = Path(temp_dir) / "provided_outline.json"
            outline_path.write_text(outline.model_dump_json(indent=2), encoding="utf-8")
            with (
                patch("sys.argv", ["sie-autoppt", "v2-plan", "--outline-json", str(outline_path), "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.ensure_generation_context") as context_mock,
                patch("tools.sie_autoppt.cli.generate_semantic_deck_with_ai", return_value=semantic_payload),
                patch("tools.sie_autoppt.cli.compile_semantic_deck_payload", return_value=validated),
                redirect_stdout(stdout),
            ):
                cli.main()
            context_mock.assert_not_called()
            out_lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(out_lines), 2)
            self.assertIn("generated_semantic_deck.json", out_lines[0])
            self.assertIn("generated_deck.json", out_lines[1])

    def test_v2_plan_batch_writes_candidate_semantic_outputs(self):
        stdout = io.StringIO()
        outline = OutlineDocument.model_validate(
            {
                "pages": [
                    {"page_no": 1, "title": "Context", "goal": "Set context."},
                    {"page_no": 2, "title": "Plan", "goal": "Propose options."},
                ]
            }
        )
        semantic_payloads = [
            {
                "meta": {"title": "Deck A", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "title": "Conclusion A", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "A"}]}],
            },
            {
                "meta": {"title": "Deck B", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "title": "Conclusion B", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "B"}]}],
            },
        ]
        validated = validate_deck_payload(
            {
                "meta": {"title": "Deck A", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Conclusion A"}],
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    ["sie-autoppt", "v2-plan", "--topic", "AI plan", "--output-dir", temp_dir, "--batch-size", "2"],
                ),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.ensure_generation_context", return_value=({}, None)),
                patch("tools.sie_autoppt.cli.generate_outline_with_ai", return_value=outline),
                patch("tools.sie_autoppt.cli.generate_semantic_deck_with_ai") as single_generate_mock,
                patch(
                    "tools.sie_autoppt.cli.generate_semantic_decks_with_ai_batch",
                    new=AsyncMock(return_value=semantic_payloads),
                ) as batch_generate_mock,
                patch("tools.sie_autoppt.cli.compile_semantic_deck_payload", return_value=validated),
                redirect_stdout(stdout),
            ):
                cli.main()
            batch_generate_mock.assert_called_once()
            single_generate_mock.assert_not_called()
            out_lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(out_lines), 4)
            self.assertIn("generated_outline.json", out_lines[0])
            self.assertIn("generated_semantic_deck.json", out_lines[1])
            self.assertIn("generated_semantic_deck.candidate_2.json", out_lines[2])
            self.assertIn("generated_deck.json", out_lines[3])

    def test_v2_review_prints_five_artifact_paths(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-review", "--deck-json", "deck.json", "--review-output-dir", temp_dir]),
                patch(
                    "tools.sie_autoppt.cli.review_deck_once",
                    return_value=type(
                        "FakeReviewArtifacts",
                        (),
                        {
                            "review_path": Path(temp_dir) / "review_once.json",
                            "patch_path": Path(temp_dir) / "patches_review_once.json",
                            "deck_path": Path(temp_dir) / "review_once.deck.json",
                            "pptx_path": Path(temp_dir) / "review_once.pptx",
                            "preview_dir": Path(temp_dir) / "previews_review_once",
                        },
                    )(),
                ),
                redirect_stdout(stdout),
            ):
                cli.main()

            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[0].endswith("review_once.json"))
            self.assertTrue(lines[1].endswith("patches_review_once.json"))
            self.assertTrue(lines[2].endswith(".deck.json"))
            self.assertTrue(lines[3].endswith(".pptx"))

    def test_v2_iterate_prints_five_artifact_paths(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-iterate", "--deck-json", "deck.json", "--review-output-dir", temp_dir, "--max-rounds", "2"]),
                patch(
                    "tools.sie_autoppt.cli.iterate_visual_review",
                    return_value=type(
                        "FakeLoopArtifacts",
                        (),
                        {
                            "final_review_path": Path(temp_dir) / "review_round_2.json",
                            "final_patch_path": Path(temp_dir) / "patches_round_2.json",
                            "deck_path": Path(temp_dir) / "review_round_1_patched.deck.json",
                            "pptx_path": Path(temp_dir) / "review_round_2.pptx",
                            "preview_dir": Path(temp_dir) / "previews_round_2",
                        },
                    )(),
                ),
                redirect_stdout(stdout),
            ):
                cli.main()

            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[0].endswith("review_round_2.json"))
            self.assertTrue(lines[1].endswith("patches_round_2.json"))
            self.assertTrue(lines[3].endswith(".pptx"))

    def test_iterate_alias_routes_to_v2_iterate(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "iterate", "--deck-json", "deck.json", "--review-output-dir", temp_dir, "--max-rounds", "2"]),
                patch(
                    "tools.sie_autoppt.cli.iterate_visual_review",
                    return_value=type(
                        "FakeLoopArtifacts",
                        (),
                        {
                            "final_review_path": Path(temp_dir) / "review_round_2.json",
                            "final_patch_path": Path(temp_dir) / "patches_round_2.json",
                            "deck_path": Path(temp_dir) / "review_round_1_patched.deck.json",
                            "pptx_path": Path(temp_dir) / "review_round_2.pptx",
                            "preview_dir": Path(temp_dir) / "previews_round_2",
                        },
                    )(),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                cli.main()

            self.assertIn("'iterate' maps to 'v2-iterate'", stderr.getvalue())
            lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[0].endswith("review_round_2.json"))

    def test_v2_render_accepts_semantic_deck_json(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_path = Path(temp_dir) / "semantic.json"
            semantic_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [
                            {
                                "slide_id": "s1",
                                "title": "结论",
                                "intent": "conclusion",
                                "blocks": [{"kind": "statement", "text": "先打通主链路，再扩展到运营闭环。"}],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (
                patch("sys.argv", ["sie-autoppt", "v2-render", "--deck-json", str(semantic_path), "--output-dir", temp_dir]),
                patch.dict("os.environ", {"SIE_AUTOPPT_ENFORCE_AI_FOR_PPT": "1"}, clear=False),
                patch(
                    "tools.sie_autoppt.cli.review_deck_once",
                    return_value=type(
                        "FakeReviewArtifacts",
                        (),
                        {
                            "review_path": Path(temp_dir) / "review_once.json",
                            "patch_path": Path(temp_dir) / "patches_review_once.json",
                            "deck_path": Path(temp_dir) / "review_once.deck.json",
                            "pptx_path": Path(temp_dir) / "review_once.pptx",
                            "preview_dir": Path(temp_dir) / "previews_review_once",
                        },
                    )(),
                ),
                patch(
                    "tools.sie_autoppt.cli.generate_v2_ppt",
                    return_value=type(
                        "FakeRenderArtifacts",
                        (),
                        {
                            "rewrite_log_path": Path(temp_dir) / "rewrite_log.json",
                            "warnings_path": Path(temp_dir) / "warnings.json",
                            "output_path": Path(temp_dir) / "rendered.pptx",
                        },
                    )(),
                ) as render_mock,
                redirect_stdout(stdout),
            ):
                (Path(temp_dir) / "review_once.deck.json").write_text(
                    json.dumps(
                        {
                            "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                            "slides": [{"slide_id": "s1", "layout": "title_only", "title": "缁撹"}],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (Path(temp_dir) / "patches_review_once.json").write_text('{"patches":[]}', encoding="utf-8")
                cli.main()

        deck_arg = render_mock.call_args.args[0]
        self.assertEqual(deck_arg.slides[0].layout, "title_only")

    def test_v2_patch_writes_patched_deck(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            patch_path = Path(temp_dir) / "patch.json"
            output_path = Path(temp_dir) / "patched.deck.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"layout": "title_only", "title": "Before"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            patch_path.write_text(json.dumps({"ops": []}, ensure_ascii=False), encoding="utf-8")
            with (
                patch(
                    "sys.argv",
                    [
                        "sie-autoppt",
                        "v2-patch",
                        "--deck-json",
                        str(deck_path),
                        "--patch-json",
                        str(patch_path),
                        "--plan-output",
                        str(output_path),
                    ],
                ),
                patch("tools.sie_autoppt.cli.apply_patch_set", side_effect=lambda deck, _patch: deck) as patch_mock,
                redirect_stdout(stdout),
            ):
                cli.main()

            self.assertEqual(stdout.getvalue().strip(), str(output_path))
            self.assertEqual(patch_mock.call_count, 1)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["slides"][0]["title"], "Before")

    def test_v2_patch_rejects_non_object_patch_payload(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            patch_path = Path(temp_dir) / "patch.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"layout": "title_only", "title": "Before"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            patch_path.write_text(json.dumps([{"op": "replace"}], ensure_ascii=False), encoding="utf-8")
            with (
                patch("sys.argv", ["sie-autoppt", "v2-patch", "--deck-json", str(deck_path), "--patch-json", str(patch_path)]),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as exc:
                    cli.main()
            self.assertEqual(exc.exception.code, 2)
            self.assertIn("top-level JSON must be an object", stderr.getvalue())

    def test_v2_patch_surfaces_patch_validation_error(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            patch_path = Path(temp_dir) / "patch.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"layout": "title_only", "title": "Before"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            patch_path.write_text(json.dumps({"ops": []}, ensure_ascii=False), encoding="utf-8")
            with (
                patch("sys.argv", ["sie-autoppt", "v2-patch", "--deck-json", str(deck_path), "--patch-json", str(patch_path)]),
                patch("tools.sie_autoppt.cli.apply_patch_set", side_effect=ValueError("invalid op index")),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as exc:
                    cli.main()
            self.assertEqual(exc.exception.code, 2)
            self.assertIn("invalid op index", stderr.getvalue())

    def test_ai_check_prints_summary_json(self):
        stdout = io.StringIO()
        fake_summary = type("FakeSummary", (), {"to_json": lambda self: '{"ok": true}'})()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-check", "--topic", "health"]),
            patch("tools.sie_autoppt.cli.run_ai_healthcheck", return_value=fake_summary),
            redirect_stdout(stdout),
        ):
            cli.main()
        self.assertEqual(stdout.getvalue().strip(), '{"ok": true}')

    def test_v2_make_non_timeout_error_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("sys.argv", ["sie-autoppt", "v2-make", "--topic", "AI make", "--output-dir", temp_dir]),
                patch("tools.sie_autoppt.cli.resolve_v2_clarified_context", return_value=RESOLVED_V2_CONTEXT),
                patch("tools.sie_autoppt.cli.make_v2_ppt", side_effect=RuntimeError("service unavailable")),
            ):
                with self.assertRaises(RuntimeError):
                    cli.main()

    def test_v2_render_failure_surfaces_runtime_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_path = Path(temp_dir) / "semantic.json"
            semantic_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "xx"}]}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            reviewed_deck_path = Path(temp_dir) / "reviewed.deck.json"
            reviewed_deck_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Conclusion"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            patch_path = Path(temp_dir) / "patches.json"
            patch_path.write_text('{"patches":[]}', encoding="utf-8")
            with (
                patch("sys.argv", ["sie-autoppt", "v2-render", "--deck-json", str(semantic_path)]),
                patch(
                    "tools.sie_autoppt.cli.review_deck_once",
                    return_value=type(
                        "FakeReviewArtifacts",
                        (),
                        {
                            "review_path": Path(temp_dir) / "review.json",
                            "patch_path": patch_path,
                            "deck_path": reviewed_deck_path,
                            "pptx_path": Path(temp_dir) / "review.pptx",
                            "preview_dir": Path(temp_dir) / "previews",
                        },
                    )(),
                ),
                patch("tools.sie_autoppt.cli.generate_v2_ppt", side_effect=RuntimeError("render failed")),
            ):
                with self.assertRaises(RuntimeError):
                    cli.main()

    def test_v2_render_exits_when_ai_review_gate_fails(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_path = Path(temp_dir) / "semantic.json"
            semantic_path.write_text(
                json.dumps(
                    {
                        "meta": {"title": "Test", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                        "slides": [{"slide_id": "s1", "title": "Conclusion", "intent": "conclusion", "blocks": [{"kind": "statement", "text": "xx"}]}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (
                patch(
                    "sys.argv",
                    ["sie-autoppt", "v2-render", "--deck-json", str(semantic_path)],
                ),
                patch("tools.sie_autoppt.cli.review_deck_once", side_effect=RuntimeError("review failed")),
                redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as exc:
                    cli.main()
            self.assertEqual(exc.exception.code, 1)
            self.assertIn("AI review/patch gate failed", stderr.getvalue())

    def test_v2_review_failure_surfaces_runtime_error(self):
        with (
            patch("sys.argv", ["sie-autoppt", "v2-review", "--deck-json", "deck.json"]),
            patch("tools.sie_autoppt.cli.review_deck_once", side_effect=RuntimeError("review failed")),
        ):
            with self.assertRaises(RuntimeError):
                cli.main()

    def test_v2_iterate_failure_surfaces_runtime_error(self):
        with (
            patch("sys.argv", ["sie-autoppt", "v2-iterate", "--deck-json", "deck.json"]),
            patch("tools.sie_autoppt.cli.iterate_visual_review", side_effect=RuntimeError("iterate failed")),
        ):
            with self.assertRaises(RuntimeError):
                cli.main()
