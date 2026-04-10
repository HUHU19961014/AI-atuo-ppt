import json
import mimetypes
import os
import time
from base64 import b64encode
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from .config import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_REASONING_EFFORT,
    DEFAULT_AI_TEXT_VERBOSITY,
    DEFAULT_AI_TIMEOUT_SEC,
    infer_llm_api_style,
)
from .exceptions import OpenAIConfigurationError, OpenAIHTTPStatusError, OpenAIResponsesError


@dataclass(frozen=True)
class OpenAIResponsesConfig:
    api_key: str
    base_url: str
    model: str
    timeout_sec: float
    reasoning_effort: str
    text_verbosity: str
    api_style: str
    organization: str | None = None
    project: str | None = None


def _allows_empty_api_key(base_url: str) -> bool:
    if os.environ.get("SIE_AUTOPPT_ALLOW_EMPTY_API_KEY", "").strip().lower() in {"1", "true", "yes"}:
        return True

    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def load_openai_responses_config(model: str | None = None) -> OpenAIResponsesConfig:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key and not _allows_empty_api_key(os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")):
        raise OpenAIConfigurationError("OPENAI_API_KEY is required for AI planning.")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not base_url:
        raise OpenAIConfigurationError("OPENAI_BASE_URL must not be empty.")
    api_style = infer_llm_api_style(base_url, configured_style=os.environ.get("SIE_AUTOPPT_LLM_API_STYLE"))

    return OpenAIResponsesConfig(
        api_key=api_key,
        base_url=base_url,
        model=(model or DEFAULT_AI_MODEL).strip(),
        timeout_sec=DEFAULT_AI_TIMEOUT_SEC,
        reasoning_effort=DEFAULT_AI_REASONING_EFFORT,
        text_verbosity=DEFAULT_AI_TEXT_VERBOSITY,
        api_style=api_style,
        organization=os.environ.get("OPENAI_ORG_ID", "").strip() or None,
        project=os.environ.get("OPENAI_PROJECT_ID", "").strip() or None,
    )


def extract_text_from_responses_payload(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                text = content["text"].strip()
                if text:
                    return text

    raise OpenAIResponsesError("Responses API did not return any text output.")


def extract_json_object_from_responses_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = extract_text_from_responses_payload(payload)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponsesError(f"Responses API returned non-JSON text: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenAIResponsesError("Responses API returned JSON, but the top-level value is not an object.")
    return data


def extract_text_from_chat_completions_payload(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not isinstance(choices, list):
        raise OpenAIResponsesError("Chat Completions API did not return a valid choices array.")

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message", {})
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)

    raise OpenAIResponsesError("Chat Completions API did not return any text content.")


def extract_json_object_from_chat_completions_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = extract_text_from_chat_completions_payload(payload)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponsesError(f"Chat Completions API returned non-JSON text: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenAIResponsesError("Chat Completions API returned JSON, but the top-level value is not an object.")
    return data


def format_openai_http_error(status_code: int, detail: str) -> str:
    message = detail.strip()
    error_code = ""
    error_type = ""

    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        error_payload = payload.get("error", {})
        if isinstance(error_payload, dict):
            error_code = str(error_payload.get("code") or "").strip()
            error_type = str(error_payload.get("type") or "").strip()
            api_message = str(error_payload.get("message") or "").strip()
            if api_message:
                message = api_message

    if error_code == "insufficient_quota":
        return (
            f"Responses API quota exceeded (HTTP {status_code}): {message} "
            "Check platform billing, credit balance, and project quota for this API key."
        )
    if error_code:
        return f"Responses API {error_code} (HTTP {status_code}): {message}"
    if error_type:
        return f"Responses API {error_type} (HTTP {status_code}): {message}"
    return f"Responses API HTTP {status_code}: {message}"


class OpenAIResponsesClient:
    def __init__(self, config: OpenAIResponsesConfig):
        self._config = config

    def create_structured_json(
        self,
        developer_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return self.create_structured_json_with_user_items(
            developer_prompt=developer_prompt,
            user_items=[{"type": "text", "text": user_prompt}],
            schema_name=schema_name,
            schema=schema,
        )

    def create_structured_json_with_user_items(
        self,
        developer_prompt: str,
        user_items: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if self._config.api_style == "chat_completions":
            return self._create_chat_completions_json(
                developer_prompt=developer_prompt,
                user_items=user_items,
            )
        try:
            return self._create_responses_json(
                developer_prompt=developer_prompt,
                user_items=user_items,
                schema_name=schema_name,
                schema=schema,
            )
        except OpenAIHTTPStatusError as exc:
            if self._config.api_style == "auto" and self._should_fallback_to_chat_completions(exc):
                return self._create_chat_completions_json(
                    developer_prompt=developer_prompt,
                    user_items=user_items,
                )
            raise

    def _create_responses_json(
        self,
        developer_prompt: str,
        user_items: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": self._config.model,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": developer_prompt}],
                },
                {
                    "role": "user",
                    "content": self._build_responses_user_content(user_items),
                },
            ],
            "text": {
                "verbosity": self._config.text_verbosity,
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            "reasoning": {"effort": self._config.reasoning_effort},
        }
        response_payload = self._post_json("/responses", payload)
        return extract_json_object_from_responses_payload(response_payload)

    def _should_fallback_to_chat_completions(self, exc: OpenAIHTTPStatusError) -> bool:
        if exc.status_code not in {400, 404, 405, 415, 422, 501}:
            return False
        detail = exc.detail.lower()
        route = exc.route.lower()
        indicators = (
            route,
            "unsupported",
            "not found",
            "does not exist",
            "unknown request url",
            "unrecognized request url",
            "invalid endpoint",
            "responses api",
        )
        return any(indicator in detail for indicator in indicators)

    def _create_chat_completions_json(
        self,
        developer_prompt: str,
        user_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": developer_prompt},
                {"role": "user", "content": self._build_chat_user_content(user_items) + [{"type": "text", "text": "\n\nReturn only one valid JSON object."}]},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        response_payload = self._post_json("/chat/completions", payload)
        return extract_json_object_from_chat_completions_payload(response_payload)

    def _build_responses_user_content(self, user_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        for item in user_items:
            item_type = str(item.get("type", "")).strip().lower()
            if item_type == "text":
                content.append({"type": "input_text", "text": str(item.get("text", ""))})
            elif item_type in {"image_path", "image"}:
                content.append({"type": "input_image", "image_url": _image_path_to_data_url(Path(str(item.get("path", ""))))})
            else:
                raise OpenAIResponsesError(f"Unsupported user item type: {item_type}")
        return content

    def _build_chat_user_content(self, user_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        for item in user_items:
            item_type = str(item.get("type", "")).strip().lower()
            if item_type == "text":
                content.append({"type": "text", "text": str(item.get("text", ""))})
            elif item_type in {"image_path", "image"}:
                content.append({"type": "image_url", "image_url": {"url": _image_path_to_data_url(Path(str(item.get("path", ""))))}})
            else:
                raise OpenAIResponsesError(f"Unsupported user item type: {item_type}")
        return content

    def _post_json(self, route: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw_body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self._config.base_url}{route}",
            data=raw_body,
            method="POST",
            headers=self._build_headers(),
        )

        max_retries = 3

        for attempt in range(max_retries):
            try:
                with request.urlopen(req, timeout=self._config.timeout_sec) as resp:
                    response_body = resp.read().decode("utf-8")

                try:
                    data = json.loads(response_body)
                except json.JSONDecodeError as exc:
                    raise OpenAIResponsesError(f"Responses API returned invalid JSON: {exc}") from exc
                if not isinstance(data, dict):
                    raise OpenAIResponsesError("Responses API returned a non-object JSON payload.")
                return data

            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < max_retries - 1:
                    time.sleep(self._retry_delay_seconds(attempt=attempt, retry_after_header=exc.headers.get("Retry-After")))
                    continue
                raise OpenAIHTTPStatusError(exc.code, detail, route) from exc
            except error.URLError as exc:
                if attempt < max_retries - 1:
                    time.sleep(self._retry_delay_seconds(attempt=attempt))
                    continue
                raise OpenAIResponsesError(f"Responses API request failed: {exc.reason}") from exc

        raise OpenAIResponsesError(f"Responses API request failed after {max_retries} retries")

    def _retry_delay_seconds(self, *, attempt: int, retry_after_header: str | None = None) -> float:
        if retry_after_header:
            try:
                retry_after = float(retry_after_header.strip())
            except ValueError:
                retry_after = 0.0
            if retry_after > 0:
                return retry_after
        return min(4.0, 0.5 * (2**attempt))

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        if self._config.organization:
            headers["OpenAI-Organization"] = self._config.organization
        if self._config.project:
            headers["OpenAI-Project"] = self._config.project
        return headers


def _image_path_to_data_url(path: Path) -> str:
    if not path.exists():
        raise OpenAIResponsesError(f"Image file does not exist: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/png"
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
