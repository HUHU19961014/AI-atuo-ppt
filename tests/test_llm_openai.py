import unittest
from io import BytesIO
from unittest.mock import patch
from urllib import error

from tools.sie_autoppt.llm_openai import (
    OpenAIResponsesClient,
    OpenAIResponsesConfig,
    OpenAIResponsesError,
    extract_json_object_from_chat_completions_payload,
    extract_text_from_chat_completions_payload,
    extract_json_object_from_responses_payload,
    extract_text_from_responses_payload,
    format_openai_http_error,
    load_openai_responses_config,
)


class OpenAIResponsesTests(unittest.TestCase):
    def test_extract_text_prefers_output_text(self):
        payload = {"output_text": '{"ok": true}'}

        self.assertEqual(extract_text_from_responses_payload(payload), '{"ok": true}')

    def test_extract_text_falls_back_to_output_message_content(self):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"cover_title":"AI","body_pages":[]}'},
                    ],
                }
            ]
        }

        self.assertEqual(
            extract_text_from_responses_payload(payload),
            '{"cover_title":"AI","body_pages":[]}',
        )

    def test_extract_json_object_rejects_non_object(self):
        with self.assertRaises(OpenAIResponsesError):
            extract_json_object_from_responses_payload({"output_text": '["not","an","object"]'})

    def test_extract_text_from_chat_completions_payload(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"cover_title":"AI","body_pages":[]}',
                    }
                }
            ]
        }

        self.assertEqual(
            extract_text_from_chat_completions_payload(payload),
            '{"cover_title":"AI","body_pages":[]}',
        )

    def test_extract_json_object_from_chat_completions_payload(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"cover_title":"AI","body_pages":[]}',
                    }
                }
            ]
        }

        self.assertEqual(
            extract_json_object_from_chat_completions_payload(payload),
            {"cover_title": "AI", "body_pages": []},
        )

    def test_format_openai_http_error_surfaces_quota_guidance(self):
        detail = """
        {
          "error": {
            "message": "You exceeded your current quota.",
            "type": "insufficient_quota",
            "code": "insufficient_quota"
          }
        }
        """

        message = format_openai_http_error(429, detail)

        self.assertIn("quota exceeded", message)
        self.assertIn("billing", message)
        self.assertIn("429", message)

    def test_load_openai_responses_config_auto_detects_siliconflow_chat_mode(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://api.siliconflow.cn/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="deepseek-ai/DeepSeek-V3")

        self.assertEqual(config.api_style, "chat_completions")
        self.assertEqual(config.base_url, "https://api.siliconflow.cn/v1")
        self.assertEqual(config.model, "deepseek-ai/DeepSeek-V3")

    def test_load_openai_responses_config_defaults_non_openai_hosts_to_chat_completions(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://proxy.example.com/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="custom-model")

        self.assertEqual(config.api_style, "chat_completions")

    def test_load_openai_responses_config_allows_empty_key_for_localhost(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "",
                "OPENAI_BASE_URL": "http://localhost:4000/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="local-model")

        self.assertEqual(config.api_style, "chat_completions")
        self.assertEqual(config.api_key, "")

    def test_chat_completions_mode_uses_openai_compatible_endpoint(self):
        client = OpenAIResponsesClient(
            OpenAIResponsesConfig(
                api_key="sk-test",
                base_url="https://api.siliconflow.cn/v1",
                model="deepseek-ai/DeepSeek-V3",
                timeout_sec=30,
                reasoning_effort="low",
                text_verbosity="low",
                api_style="chat_completions",
            )
        )

        with patch.object(
            client,
            "_post_json",
            return_value={"choices": [{"message": {"content": '{"cover_title":"AI","body_pages":[]}'}}]},
        ) as post_json:
            result = client.create_structured_json(
                developer_prompt="system prompt",
                user_prompt="user prompt",
                schema_name="ignored",
                schema={"type": "object"},
            )

        self.assertEqual(result, {"cover_title": "AI", "body_pages": []})
        called_route, called_payload = post_json.call_args.args
        self.assertEqual(called_route, "/chat/completions")
        self.assertEqual(called_payload["response_format"], {"type": "json_object"})

    def test_post_json_retries_with_backoff_for_retryable_http_errors(self):
        client = OpenAIResponsesClient(
            OpenAIResponsesConfig(
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                timeout_sec=30,
                reasoning_effort="low",
                text_verbosity="low",
                api_style="responses",
            )
        )

        http_error = error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0.25"},
            fp=BytesIO(b'{"error":{"message":"rate limited","code":"rate_limit"}}'),
        )

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"output_text":"{\\"ok\\":true}"}'

        with (
            patch("tools.sie_autoppt.llm_openai.request.urlopen", side_effect=[http_error, _Response()]),
            patch("tools.sie_autoppt.llm_openai.time.sleep") as sleep,
        ):
            payload = client._post_json("/responses", {"test": True})

        self.assertEqual(payload["output_text"], '{"ok":true}')
        sleep.assert_called_once_with(0.25)
