# Troubleshooting

## `AI healthcheck blocked`

Common causes:

- Missing or invalid `OPENAI_API_KEY` when your endpoint requires key auth.
- Wrong `OPENAI_BASE_URL`.
- Corporate network or proxy blocking outbound requests.

Checks:

1. Confirm environment variables are set (`.env.example` as baseline).
2. Run `enterprise-ai-ppt ai-check --topic "healthcheck"`.
3. If using local gateway, verify `/v1/models` is reachable first.

## `AI planning failed` / `AI strategy selection failed`

Common causes:

- Model not available on current endpoint.
- Upstream timeout or quota limit.
- Responses schema mismatch from upstream model.

Actions:

1. Switch to a known stable model via `--llm-model`.
2. Increase timeout with `SIE_AUTOPPT_LLM_TIMEOUT_SEC`.
3. Re-run command with same input and inspect stderr details.

## Long AI calls appear "stuck" with no progress

Cause:

- Upstream LLM call is still running, but default output is silent until response returns.

Actions:

1. Enable heartbeat progress logs:
   - `SIE_AUTOPPT_STREAM_PROGRESS=1`
   - Optional: `SIE_AUTOPPT_STREAM_PROGRESS_INTERVAL_SEC=3`
2. Re-run the same command and watch stdout for elapsed-time heartbeat lines.
3. If calls still hang beyond expected timeout, verify endpoint/network and `SIE_AUTOPPT_LLM_TIMEOUT_SEC`.

## `invalid sie-render input: no supported pattern ids available`

Cause:

- Pattern registry resolved to empty list.

Actions:

1. Verify pattern definitions are available under project assets/skills.
2. Ensure runtime can read project files from current working directory.

## `visual-draft failed`

Common causes:

- Invalid `--deck-spec-json` payload.
- Browser executable path invalid.
- Screenshot subprocess timeout.

Actions:

1. Validate deck spec JSON format.
2. Pass explicit `--browser` path to a local Edge/Chrome executable.
3. Reduce scope using `--page-index` for a single-page draft.

## Pytest cache permission warnings on Windows

Symptom:

- Warnings about `.pytest_cache` permission denied.

Action:

- This does not block test correctness; if needed, clean and recreate workspace temp/cache directories with appropriate permissions.
