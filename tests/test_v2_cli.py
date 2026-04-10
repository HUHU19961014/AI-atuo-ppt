import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

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
                cli.main()

        deck_arg = render_mock.call_args.args[0]
        self.assertEqual(deck_arg.slides[0].layout, "title_only")
