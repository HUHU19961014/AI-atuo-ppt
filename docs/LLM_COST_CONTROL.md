# LLM Cost Controls

The OpenAI client now supports usage tracking, budget guards, and cache.

## Environment Variables

- `SIE_AUTOPPT_LLM_USAGE_LOG_PATH`: JSONL usage log file path.
- `SIE_AUTOPPT_LLM_TOKEN_BUDGET`: hard token cap for current process.
- `SIE_AUTOPPT_LLM_COST_BUDGET_USD`: hard USD cap for current process.
- `SIE_AUTOPPT_LLM_PRICE_INPUT_PER_1K`: input token price for USD estimation.
- `SIE_AUTOPPT_LLM_PRICE_OUTPUT_PER_1K`: output token price for USD estimation.
- `SIE_AUTOPPT_LLM_CACHE_ENABLED`: `1/0`, enable local response cache.
- `SIE_AUTOPPT_LLM_CACHE_DIR`: cache directory path.

## Notes

- Budget checks apply per process runtime.
- Cache key includes `base_url`, `model`, `api_style`, route, and request payload.
- If pricing env vars are not set, estimated USD remains `0` while token accounting still works.
