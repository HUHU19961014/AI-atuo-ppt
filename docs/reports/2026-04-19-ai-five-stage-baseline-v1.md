# AI Five-Stage Baseline v1 (2026-04-19)

## Scope

- Covers A08 baseline metrics and A09 rollout readiness signals.
- Baseline fixture set: `tests/fixtures/batch/ai_five_stage_baseline/cases.json` (10 cases).
- Metric source: `output/runs/*/final/run_summary.json` plus `dead_letter.json` for failed runs.

## Baseline Reference

Reference snapshot:

- `tests/fixtures/batch/ai_five_stage_baseline/baseline_metrics.json`

Core baseline numbers:

- success_rate: `0.90`
- avg_retry_attempts: `1.50`
- avg_total_tokens: `1400`
- avg_total_latency_ms: `2100`
- degraded_ratio: `0.15`

## Current Comparison Workflow

Run:

```powershell
python -m tools.sie_autoppt.batch.report_metrics `
  --runs-root .\output\runs `
  --fixtures-dir .\tests\fixtures\batch\ai_five_stage_baseline `
  --baseline-report .\tests\fixtures\batch\ai_five_stage_baseline\baseline_metrics.json `
  --report-out .\output\reports\ai_five_stage_metrics.json `
  --markdown-out .\output\reports\ai_five_stage_metrics.md
```

The generated markdown includes baseline deltas for release review.
