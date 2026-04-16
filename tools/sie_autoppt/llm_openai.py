import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import threading
import time
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib import error, request
from urllib.parse import urlparse
from functools import lru_cache

from .config import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_REASONING_EFFORT,
    DEFAULT_AI_TEXT_VERBOSITY,
    DEFAULT_AI_TIMEOUT_SEC,
    infer_llm_api_style,
)
from .exceptions import OpenAIConfigurationError, OpenAIHTTPStatusError, OpenAIResponsesError

LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class AnthropicVisionConfig:
    api_key: str
    base_url: str
    model: str
    timeout_sec: float


@dataclass(frozen=True)
class LLMUsageStats:
    input_tokens: int
    output_tokens: int
    total_tokens: int


def extract_usage_stats(payload: dict[str, Any]) -> dict[str, int]:
    usage_payload = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage_payload, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _to_int(value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    input_tokens = _to_int(usage_payload.get("input_tokens", usage_payload.get("prompt_tokens", 0)))
    output_tokens = _to_int(usage_payload.get("output_tokens", usage_payload.get("completion_tokens", 0)))
    total_tokens = _to_int(usage_payload.get("total_tokens", input_tokens + output_tokens))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}


def _estimate_cost_usd_from_usage(usage: dict[str, int]) -> float:
    try:
        input_price = float(os.environ.get("SIE_AUTOPPT_LLM_PRICE_INPUT_PER_1K", "0") or "0")
        output_price = float(os.environ.get("SIE_AUTOPPT_LLM_PRICE_OUTPUT_PER_1K", "0") or "0")
    except ValueError:
        return 0.0
    if input_price <= 0 and output_price <= 0:
        return 0.0
    return (
        (usage.get("input_tokens", 0) / 1000.0) * max(0.0, input_price)
        + (usage.get("output_tokens", 0) / 1000.0) * max(0.0, output_price)
    )


def _allows_empty_api_key(base_url: str) -> bool:
    """Only localhost endpoints are allowed without an API key (Ollama, LM Studio, etc.)."""
    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _local_probe_paths(base_url: str) -> tuple[str, ...]:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return (trimmed + "/models",)
    return (trimmed + "/models", trimmed + "/v1/models")


def _probe_local_openai_compat(url: str, timeout_sec: float = 0.35) -> bool:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            return 200 <= int(resp.status) < 500
    except error.HTTPError as exc:
        return 200 <= int(exc.code) < 500
    except Exception as exc:
        LOGGER.debug("local OpenAI-compatible probe failed for %s: %s", url, exc)
        return False


@lru_cache(maxsize=1)
def _discover_local_base_url() -> str:
    if os.environ.get("SIE_AUTOPPT_DISABLE_LOCAL_AI_DISCOVERY", "").strip().lower() in {"1", "true", "yes"}:
        return ""

    candidates = (
        "http://127.0.0.1:11434/v1",
        "http://127.0.0.1:3000/v1",
        "http://127.0.0.1:8000/v1",
        "http://127.0.0.1:8080/v1",
        "http://127.0.0.1:1234/v1",
        "http://localhost:11434/v1",
        "http://localhost:3000/v1",
    )
    for base_url in candidates:
        for probe_url in _local_probe_paths(base_url):
            if _probe_local_openai_compat(probe_url):
                return base_url.rstrip("/")
    LOGGER.debug(
        "No local OpenAI-compatible endpoint found (probed %s). "
        "Set OPENAI_BASE_URL to configure a specific endpoint, or set "
        "SIE_AUTOPPT_DISABLE_LOCAL_AI_DISCOVERY=1 to skip probing.",
        ", ".join(candidates),
    )
    return ""


def load_openai_responses_config(model: str | None = None) -> OpenAIResponsesConfig:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    configured_base_url = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
    if configured_base_url:
        base_url = configured_base_url
    elif api_key:
        base_url = "https://api.openai.com/v1"
    else:
        discovered = _discover_local_base_url()
        if discovered:
            base_url = discovered
        else:
            base_url = "https://api.openai.com/v1"
            LOGGER.warning(
                "No OPENAI_API_KEY, OPENAI_BASE_URL, or local LLM endpoint found. "
                "Falling back to %s which may be unreachable in some network environments. "
                "Set OPENAI_BASE_URL (e.g. https://dashscope.aliyuncs.com/compatible-mode/v1) "
                "and OPENAI_API_KEY to configure a reachable AI endpoint.",
                base_url,
            )

    if not api_key and not _allows_empty_api_key(base_url):
        raise OpenAIConfigurationError(
            f"OPENAI_API_KEY is required when connecting to {base_url}. "
            "Configure via:\n"
            "  - CLI: --api-key sk-xxx --base-url https://your-endpoint/v1\n"
            "  - Env: set OPENAI_API_KEY=sk-xxx and OPENAI_BASE_URL=https://your-endpoint/v1\n"
            "  - Local: start Ollama (port 11434) or other OpenAI-compatible local server."
        )

    if not base_url:
        raise OpenAIConfigurationError("OPENAI_BASE_URL must not be empty.")
    api_style = infer_llm_api_style(base_url, configured_style=os.environ.get("SIE_AUTOPPT_LLM_API_STYLE"))

    LOGGER.info(
        "LLM config: base_url=%s, model=%s, api_style=%s, api_key=%s",
        base_url,
        model or DEFAULT_AI_MODEL,
        api_style,
        f"{api_key[:8]}..." if len(api_key) > 8 else ("(empty)" if not api_key else "(local)"),
    )

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


def load_anthropic_vision_config(model: str | None = None) -> AnthropicVisionConfig:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").strip().rstrip("/")
    resolved_model = (model or os.environ.get("SIE_AUTOPPT_CLAUDE_MODEL", "claude-3-7-sonnet-latest")).strip()
    if not api_key:
        raise OpenAIConfigurationError(
            "ANTHROPIC_API_KEY is required for Claude vision review. "
            "Set ANTHROPIC_API_KEY or switch provider to OpenAI."
        )
    if not base_url:
        raise OpenAIConfigurationError("ANTHROPIC_BASE_URL must not be empty.")
    return AnthropicVisionConfig(
        api_key=api_key,
        base_url=base_url,
        model=resolved_model,
        timeout_sec=DEFAULT_AI_TIMEOUT_SEC,
    )


def infer_visual_review_provider(model: str | None, provider: str | None = None) -> str:
    explicit = str(provider or "").strip().lower()
    if explicit in {"openai", "claude"}:
        return explicit
    if explicit and explicit != "auto":
        raise ValueError("vision provider must be one of: auto, openai, claude")
    normalized_model = str(model or "").strip().lower()
    if normalized_model.startswith("claude"):
        return "claude"
    return "openai"


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
    _usage_lock = Lock()
    _session_input_tokens = 0
    _session_output_tokens = 0
    _session_total_tokens = 0
    _session_total_cost_usd = 0.0

    def __init__(self, config: OpenAIResponsesConfig):
        self._config = config

    @classmethod
    def reset_usage_counters(cls) -> None:
        with cls._usage_lock:
            cls._session_input_tokens = 0
            cls._session_output_tokens = 0
            cls._session_total_tokens = 0
            cls._session_total_cost_usd = 0.0

    @classmethod
    def usage_counters(cls) -> dict[str, float]:
        with cls._usage_lock:
            return {
                "input_tokens": float(cls._session_input_tokens),
                "output_tokens": float(cls._session_output_tokens),
                "total_tokens": float(cls._session_total_tokens),
                "total_cost_usd": float(cls._session_total_cost_usd),
            }

    def _token_budget_limit(self) -> int:
        raw = os.environ.get("SIE_AUTOPPT_LLM_TOKEN_BUDGET", "").strip()
        if not raw:
            return 0
        try:
            return max(0, int(raw))
        except ValueError:
            return 0

    def _cost_budget_limit(self) -> float:
        raw = os.environ.get("SIE_AUTOPPT_LLM_COST_BUDGET_USD", "").strip()
        if not raw:
            return 0.0
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0

    def _usage_log_path(self) -> Path | None:
        raw = os.environ.get("SIE_AUTOPPT_LLM_USAGE_LOG_PATH", "").strip()
        if not raw:
            return None
        return Path(raw)

    def _cache_enabled(self) -> bool:
        return os.environ.get("SIE_AUTOPPT_LLM_CACHE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

    def _cache_dir(self) -> Path:
        raw = os.environ.get("SIE_AUTOPPT_LLM_CACHE_DIR", ".tmp_llm_cache").strip() or ".tmp_llm_cache"
        return Path(raw)

    def _cache_key(self, route: str, payload: dict[str, Any]) -> str:
        raw = json.dumps(
            {
                "base_url": self._config.base_url,
                "model": self._config.model,
                "api_style": self._config.api_style,
                "route": route,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_path(self, route: str, payload: dict[str, Any]) -> Path:
        return self._cache_dir() / f"{self._cache_key(route, payload)}.json"

    def _try_load_cached_response(self, route: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._cache_enabled():
            return None
        cache_path = self._cache_path(route, payload)
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if isinstance(data, dict):
            return data
        return None

    def _save_cached_response(self, route: str, payload: dict[str, Any], response_payload: dict[str, Any]) -> None:
        if not self._cache_enabled():
            return
        cache_dir = self._cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(route, payload)
        cache_path.write_text(json.dumps(response_payload, ensure_ascii=False), encoding="utf-8")

    def _append_usage_log(self, *, route: str, usage: dict[str, int], cost_usd: float) -> None:
        log_path = self._usage_log_path()
        if log_path is None:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": int(time.time()),
            "route": route,
            "model": self._config.model,
            "base_url": self._config.base_url,
            "usage": usage,
            "estimated_cost_usd": cost_usd,
            "session_totals": self.usage_counters(),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _enforce_budget_pre_request(self) -> None:
        token_budget = self._token_budget_limit()
        cost_budget = self._cost_budget_limit()
        with self._usage_lock:
            if token_budget and self._session_total_tokens >= token_budget:
                raise OpenAIResponsesError(
                    f"LLM token budget exceeded: {self._session_total_tokens}/{token_budget} tokens used in this process."
                )
            if cost_budget and self._session_total_cost_usd >= cost_budget:
                raise OpenAIResponsesError(
                    f"LLM cost budget exceeded: ${self._session_total_cost_usd:.6f}/${cost_budget:.6f} used in this process."
                )

    def _record_usage(self, *, route: str, payload: dict[str, Any]) -> None:
        usage = extract_usage_stats(payload)
        cost_usd = _estimate_cost_usd_from_usage(usage)
        with self._usage_lock:
            self._session_input_tokens += usage["input_tokens"]
            self._session_output_tokens += usage["output_tokens"]
            self._session_total_tokens += usage["total_tokens"]
            self._session_total_cost_usd += cost_usd
            token_budget = self._token_budget_limit()
            cost_budget = self._cost_budget_limit()
            over_token_budget = bool(token_budget and self._session_total_tokens > token_budget)
            over_cost_budget = bool(cost_budget and self._session_total_cost_usd > cost_budget)
        self._append_usage_log(route=route, usage=usage, cost_usd=cost_usd)
        if over_token_budget:
            raise OpenAIResponsesError(
                f"LLM token budget exceeded after this call: {self._session_total_tokens}/{token_budget}."
            )
        if over_cost_budget:
            raise OpenAIResponsesError(
                f"LLM cost budget exceeded after this call: ${self._session_total_cost_usd:.6f}/${cost_budget:.6f}."
            )

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

    async def acreate_structured_json(
        self,
        developer_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.create_structured_json,
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
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

    async def acreate_structured_json_with_user_items(
        self,
        developer_prompt: str,
        user_items: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.create_structured_json_with_user_items,
            developer_prompt=developer_prompt,
            user_items=user_items,
            schema_name=schema_name,
            schema=schema,
        )

    async def acreate_structured_json_batch(
        self,
        requests: list[dict[str, Any]],
        *,
        concurrency: int = 4,
    ) -> list[dict[str, Any]]:
        if not requests:
            return []
        bounded = max(1, int(concurrency))
        semaphore = asyncio.Semaphore(bounded)
        results: list[dict[str, Any] | None] = [None] * len(requests)

        async def _run(index: int, request_item: dict[str, Any]) -> None:
            async with semaphore:
                results[index] = await self.acreate_structured_json_with_user_items(
                    developer_prompt=str(request_item["developer_prompt"]),
                    user_items=list(request_item["user_items"]),
                    schema_name=str(request_item["schema_name"]),
                    schema=dict(request_item["schema"]),
                )

        await asyncio.gather(*(_run(index, item) for index, item in enumerate(requests)))
        return [item for item in results if item is not None]

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
        cached = self._try_load_cached_response(route, payload)
        if cached is not None:
            self._record_usage(route=route, payload=cached)
            return cached

        self._enforce_budget_pre_request()
        raw_body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self._config.base_url}{route}",
            data=raw_body,
            method="POST",
            headers=self._build_headers(),
        )

        max_retries = 3

        for attempt in range(max_retries):
            heartbeat_stop = threading.Event()
            heartbeat_thread = self._start_progress_heartbeat(route=route, stop_event=heartbeat_stop)
            try:
                with request.urlopen(req, timeout=self._config.timeout_sec) as resp:
                    response_body = resp.read().decode("utf-8")

                try:
                    data = json.loads(response_body)
                except json.JSONDecodeError as exc:
                    raise OpenAIResponsesError(f"Responses API returned invalid JSON: {exc}") from exc
                if not isinstance(data, dict):
                    raise OpenAIResponsesError("Responses API returned a non-object JSON payload.")
                self._save_cached_response(route, payload, data)
                self._record_usage(route=route, payload=data)
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
                raise OpenAIResponsesError(
                    f"Responses API request failed: {exc.reason}. "
                    f"Target: {self._config.base_url}{route}. "
                    "Please set OPENAI_BASE_URL and OPENAI_API_KEY, "
                    "or start a local LLM service (e.g. Ollama). "
                    "See TROUBLESHOOTING.md for details."
                ) from exc
            finally:
                heartbeat_stop.set()
                if heartbeat_thread is not None:
                    heartbeat_thread.join(timeout=0.2)

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

    def _start_progress_heartbeat(self, *, route: str, stop_event: threading.Event) -> threading.Thread | None:
        enabled = os.environ.get("SIE_AUTOPPT_STREAM_PROGRESS", "").strip().lower() in {"1", "true", "yes"}
        if not enabled:
            return None
        interval_raw = os.environ.get("SIE_AUTOPPT_STREAM_PROGRESS_INTERVAL_SEC", "").strip()
        try:
            interval = float(interval_raw) if interval_raw else 3.0
        except ValueError:
            interval = 3.0
        interval = min(10.0, max(1.0, interval))

        started = time.time()

        def _worker() -> None:
            while not stop_event.wait(interval):
                elapsed = time.time() - started
                print(
                    f"progress: waiting for AI response {route} ({elapsed:.1f}s elapsed)",
                    flush=True,
                )

        thread = threading.Thread(target=_worker, name="sie-autoppt-llm-heartbeat", daemon=True)
        thread.start()
        return thread


def _image_path_to_data_url(path: Path) -> str:
    if not path.exists():
        raise OpenAIResponsesError(f"Image file does not exist: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/png"
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
