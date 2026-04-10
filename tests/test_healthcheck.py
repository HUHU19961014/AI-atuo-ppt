import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt.healthcheck import run_ai_healthcheck
from tools.sie_autoppt.llm_openai import OpenAIConfigurationError, OpenAIResponsesConfig
from tools.sie_autoppt.v2.schema import OutlineDocument, validate_deck_payload


class HealthcheckTests(unittest.TestCase):
    def test_run_ai_healthcheck_uses_v2_generation_chain(self):
        outline = OutlineDocument.model_validate(
            {"pages": [{"page_no": 1, "title": "Context", "goal": "Set context."}]}
        )
        deck = validate_deck_payload(
            {
                "meta": {"title": "Healthcheck Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Lead with the decision"}],
            }
        )

        with (
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
        ):
            summary = run_ai_healthcheck(topic="Healthcheck")

        payload = json.loads(summary.to_json())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["cover_title"], "Healthcheck Deck")
        self.assertEqual(payload["first_page_title"], "Lead with the decision")
        self.assertEqual(payload["page_count"], 1)

    def test_run_ai_healthcheck_maps_configuration_error(self):
        with patch(
            "tools.sie_autoppt.healthcheck.load_openai_responses_config",
            side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning."),
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is required"):
                run_ai_healthcheck(topic="Healthcheck")

    def test_run_ai_healthcheck_with_render_reads_render_summary(self):
        deck = validate_deck_payload(
            {
                "meta": {"title": "Healthcheck Deck", "theme": "business_red", "language": "zh-CN", "author": "AI", "version": "2.0"},
                "slides": [{"slide_id": "s1", "layout": "title_only", "title": "Lead with the decision"}],
            }
        ).deck

        with patch(
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
        ):
            with unittest.mock.patch("tools.sie_autoppt.healthcheck.make_v2_ppt") as make_mock:
                with unittest.mock.patch("pathlib.Path.exists", return_value=True):
                    with unittest.mock.patch(
                        "pathlib.Path.read_text",
                        return_value=json.dumps(
                            {
                                "summary": {"warning_count": 1, "high_count": 0, "error_count": 0},
                                "review_required": True,
                                "auto_score": 88,
                                "auto_level": "合格",
                            },
                            ensure_ascii=False,
                        ),
                    ):
                        make_mock.return_value = type(
                            "FakeArtifacts",
                            (),
                            {
                                "deck": deck,
                                "pptx_path": Path("ai_check.pptx"),
                                "warnings_path": Path("warnings.json"),
                            },
                        )()
                        summary = run_ai_healthcheck(topic="Healthcheck", with_render=True)

        payload = json.loads(summary.to_json())
        self.assertTrue(payload["render_checked"])
        self.assertEqual(payload["pptx_path"], "ai_check.pptx")
        self.assertEqual(payload["warning_count"], 1)
        self.assertTrue(payload["review_required"])
        self.assertEqual(payload["auto_score"], 88)
