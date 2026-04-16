import unittest
from io import BytesIO
import threading
from unittest.mock import AsyncMock, patch
from urllib import error

from tools.sie_autoppt.llm_openai import (
    OpenAIConfigurationError,
    OpenAIHTTPStatusError,
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

    def test_load_openai_responses_config_defaults_unknown_hosts_to_auto_mode(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://api.siliconflow.cn/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="deepseek-ai/DeepSeek-V3")

        self.assertEqual(config.api_style, "auto")
        self.assertEqual(config.base_url, "https://api.siliconflow.cn/v1")
        self.assertEqual(config.model, "deepseek-ai/DeepSeek-V3")

    def test_load_openai_responses_config_defaults_non_openai_hosts_to_auto(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://proxy.example.com/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="custom-model")

        self.assertEqual(config.api_style, "auto")

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

        self.assertEqual(config.api_style, "auto")
        self.assertEqual(config.api_key, "")

    def test_load_openai_responses_config_rejects_empty_key_for_remote_by_default(self):
        """Remote endpoints now require an API key by default (policy change)."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
            clear=False,
        ):
            with self.assertRaises(OpenAIConfigurationError) as ctx:
                load_openai_responses_config(model="gpt-4o-mini")

            self.assertIn("OPENAI_API_KEY is required", str(ctx.exception))

    def test_load_openai_responses_config_flag_does_not_override_remote_key_requirement(self):
        """SIE_AUTOPPT_ALLOW_EMPTY_KEY is no longer supported — AI is mandatory."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "SIE_AUTOPPT_ALLOW_EMPTY_KEY": "1",
            },
            clear=False,
        ):
            with self.assertRaises(OpenAIConfigurationError) as ctx:
                load_openai_responses_config(model="gpt-4o-mini")

            self.assertIn("OPENAI_API_KEY is required", str(ctx.exception))

    def test_load_openai_responses_config_cli_overrides_via_env(self):
        """Verify CLI --api-key / --base-url are applied by patching env vars."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-from-cli",
                "OPENAI_BASE_URL": "https://custom-endpoint.example.com/v1",
            },
            clear=False,
        ):
            config = load_openai_responses_config(model="custom-model")

        self.assertEqual(config.api_key, "sk-from-cli")
        self.assertEqual(config.base_url, "https://custom-endpoint.example.com/v1")
        self.assertEqual(config.model, "custom-model")

    def test_auto_mode_falls_back_to_chat_completions_when_responses_endpoint_is_unsupported(self):
        client = OpenAIResponsesClient(
            OpenAIResponsesConfig(
                api_key="sk-test",
                base_url="https://proxy.example.com/v1",
                model="custom-model",
                timeout_sec=30,
                reasoning_effort="low",
                text_verbosity="low",
                api_style="auto",
            )
        )

        with patch.object(
            client,
            "_post_json",
            side_effect=[
                OpenAIHTTPStatusError(404, '{"error":{"message":"Unknown request URL: POST /responses"}}', "/responses"),
                {"choices": [{"message": {"content": '{"cover_title":"AI","body_pages":[]}'}}]},
            ],
        ) as post_json:
            result = client.create_structured_json(
                developer_prompt="system prompt",
                user_prompt="user prompt",
                schema_name="ignored",
                schema={"type": "object"},
            )

        self.assertEqual(result, {"cover_title": "AI", "body_pages": []})
        first_route = post_json.call_args_list[0].args[0]
        second_route = post_json.call_args_list[1].args[0]
        self.assertEqual(first_route, "/responses")
        self.assertEqual(second_route, "/chat/completions")

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

    def test_start_progress_heartbeat_disabled_by_default(self):
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
        with patch.dict("os.environ", {}, clear=False):
            thread = client._start_progress_heartbeat(route="/responses", stop_event=threading.Event())
        self.assertIsNone(thread)

    def test_start_progress_heartbeat_enabled(self):
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
        stop_event = threading.Event()
        with patch.dict(
            "os.environ",
            {
                "SIE_AUTOPPT_STREAM_PROGRESS": "1",
                "SIE_AUTOPPT_STREAM_PROGRESS_INTERVAL_SEC": "1",
            },
            clear=False,
        ):
            thread = client._start_progress_heartbeat(route="/responses", stop_event=stop_event)
            self.assertIsNotNone(thread)
            self.assertTrue(thread.is_alive())
            stop_event.set()
            thread.join(timeout=0.3)


class OpenAIResponsesAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_acreate_structured_json_delegates_to_sync_implementation(self):
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
        with patch.object(client, "create_structured_json", return_value={"ok": True}) as create_json:
            result = await client.acreate_structured_json(
                developer_prompt="system",
                user_prompt="user",
                schema_name="schema",
                schema={"type": "object"},
            )
        self.assertEqual(result, {"ok": True})
        create_json.assert_called_once()

    async def test_acreate_structured_json_with_user_items_delegates_to_sync_implementation(self):
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
        with patch.object(client, "create_structured_json_with_user_items", return_value={"ok": True}) as create_json:
            result = await client.acreate_structured_json_with_user_items(
                developer_prompt="system",
                user_items=[{"type": "text", "text": "hello"}],
                schema_name="schema",
                schema={"type": "object"},
            )
        self.assertEqual(result, {"ok": True})
        create_json.assert_called_once()

    async def test_acreate_structured_json_batch_preserves_request_order(self):
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
        requests = [
            {
                "developer_prompt": "s1",
                "user_items": [{"type": "text", "text": "u1"}],
                "schema_name": "schema",
                "schema": {"type": "object"},
            },
            {
                "developer_prompt": "s2",
                "user_items": [{"type": "text", "text": "u2"}],
                "schema_name": "schema",
                "schema": {"type": "object"},
            },
        ]
        client.acreate_structured_json_with_user_items = AsyncMock(side_effect=[{"id": 1}, {"id": 2}])  # type: ignore[method-assign]
        result = await client.acreate_structured_json_batch(requests, concurrency=2)
        self.assertEqual(result, [{"id": 1}, {"id": 2}])
