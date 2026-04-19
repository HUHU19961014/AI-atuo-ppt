# On-Call Runbook

## Incident Levels

- P1: Production generation blocked for all users.
- P2: Core command degraded (`make`, `review`, `iterate`).
- P3: Non-critical path issue (docs/UI/tooling).

## First 10 Minutes

1. Confirm affected command and full stderr.
2. Capture inputs:
   - topic/brief
   - command line
   - environment (`OPENAI_BASE_URL`, model vars)
3. Reproduce with smallest input.

## Quick Diagnostics

1. API/config health:
   - `python .\main.py ai-check --topic "oncall-check" --progress`
2. CLI baseline:
   - `python .\main.py --help`
3. Regression subset:
   - `python -m pytest tests/test_cli.py tests/test_clarify_web.py -q`
4. Five-stage rollout status:
   - `echo $env:SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED`
   - `echo $env:SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT`
   - Check `output/runs/<run_id>/final/ai_five_stage_rollback.json` when fallback occurred.

## Standard Mitigations

- Provider failure: switch model or base URL.
- Content validation hard-fail: run `v2-patch` for blocker fixes and rerender.
- Plugin regression: clear plugin env vars (`SIE_AUTOPPT_PLUGIN_MODULES`, `SIE_AUTOPPT_MODEL_ADAPTER`) and retry default path.
- Rollout fallback: set `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=0` to force legacy batch path.

## Escalation

- P1 unresolved after 30 minutes: escalate to maintainer and initiate rollback to last stable tag.
- Record all mitigation attempts and outputs in incident notes.

## A09 Rollout Playbook

1. Legacy default:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=0`
2. 10% canary window:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=1`
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT=10`
3. 50% canary window:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT=50`
4. Full rollout:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT=100`
5. One-command rollback:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=0`

Gate thresholds (A08):

- success_rate >= 0.85
- avg_retry_attempts <= 2.5
- degraded_ratio <= 0.35
- avg_total_latency_ms <= 3000

## Postmortem Template

1. Impact window and affected commands.
2. Root cause.
3. Immediate fix.
4. Long-term prevention (tests, guardrails, docs).
