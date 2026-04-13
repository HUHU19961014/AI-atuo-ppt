# Compatibility Matrix

## Runtime

| Item | Supported | Notes |
|---|---|---|
| Python | 3.11+ | Project requirement from `pyproject.toml` |
| OS | Windows / Linux / macOS | Primary development environment is Windows |
| PowerPoint rendering | Yes | Through `python-pptx` plus SVG-primary pipeline |

## LLM Endpoints

| Provider style | Supported | Notes |
|---|---|---|
| OpenAI Responses API | Yes | Default when endpoint is OpenAI-compatible |
| OpenAI Chat Completions | Yes | Fallback by API style detection/config |
| Local OpenAI-compatible gateway | Yes | Use `OPENAI_BASE_URL` |
| Claude vision review | Yes | Requires `ANTHROPIC_API_KEY` |
| Plugin model adapter | Yes | Configure `SIE_AUTOPPT_PLUGIN_MODULES` + `SIE_AUTOPPT_MODEL_ADAPTER` |

## Workflow Paths

| Path | Status | Notes |
|---|---|---|
| V2 semantic pipeline (`make`, `v2-*`) | Recommended | Main production path |
| `review` / `iterate` visual loop | Recommended | Supports patch generation loop |
| `v2-patch` incremental edit | Recommended | Local patch apply for existing deck JSON |
| `sie-render` | Compatibility | Retained for actual SIE template delivery |
| legacy modules | Compatibility only | Not recommended as default entry |

## Language Policy

| Input language flag | Resolved policy |
|---|---|
| `zh`, `zh-cn` | `zh-CN` |
| `en`, `en-us` | `en-US` |
