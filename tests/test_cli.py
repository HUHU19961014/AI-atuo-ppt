import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from tools.sie_autoppt import cli
from tools.sie_autoppt.llm_openai import OpenAIConfigurationError, OpenAIResponsesConfig
from tools.sie_autoppt.models import BodyPageSpec, DeckSpec


class CliTests(unittest.TestCase):
    def test_ai_check_prints_summary(self):
        deck = DeckSpec(
            cover_title="AI AutoPPT 健康检查",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="测试页",
                    subtitle="",
                    bullets=["要点一", "要点二"],
                    pattern_id="general_business",
                )
            ],
        )
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-check", "--topic", "健康检查"]),
            patch(
                "tools.sie_autoppt.services.load_openai_responses_config",
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
            patch("tools.sie_autoppt.services.plan_deck_spec_with_ai", return_value=deck),
            redirect_stdout(stdout),
        ):
            cli.main()

        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["api_style"], "responses")
        self.assertEqual(payload["page_count"], 1)
        self.assertEqual(payload["first_page_title"], "测试页")

    def test_ai_plan_rejects_mixing_exact_and_range(self):
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-plan", "--topic", "测试", "--chapters", "4", "--min-slides", "3"]),
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
                "tools.sie_autoppt.services.load_openai_responses_config",
                side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
            ),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("AI healthcheck blocked", stderr.getvalue())

    def test_ai_check_external_planner_reports_external_backend(self):
        deck = DeckSpec(
            cover_title="外部规划器",
            body_pages=[
                BodyPageSpec(
                    page_key="p1",
                    title="测试页",
                    subtitle="",
                    bullets=["要点一", "要点二"],
                    pattern_id="general_business",
                )
            ],
        )
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["sie-autoppt", "ai-check", "--planner-command", "echo test"]),
            patch("tools.sie_autoppt.services.plan_deck_spec_with_ai", return_value=deck),
            redirect_stdout(stdout),
        ):
            cli.main()

        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["api_style"], "external_command")
        self.assertEqual(payload["model"], "external-command")

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
