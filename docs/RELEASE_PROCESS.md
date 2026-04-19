# Release Process

## Scope

This process covers versioned release preparation, quality validation, tagging, and rollback readiness.

## Pre-Release Checklist

1. Confirm `CHANGELOG.md` has an `[Unreleased]` summary for included changes.
2. Run local quality gates:
   - `python -m ruff check tools/sie_autoppt/cli.py tools/sie_autoppt/clarify_web.py tools/sie_autoppt/exceptions.py tools/sie_autoppt/cli_parser.py --select F`
   - `python -m ruff check tools/sie_autoppt/batch tools/sie_autoppt/cli.py tools/sie_autoppt/cli_parser.py tools/sie_autoppt/cli_sie.py tools/sie_autoppt/cli_v2_commands.py`
   - `python -m tools.sie_autoppt.quality.ruff_incremental --paths tools/sie_autoppt/v2 --baseline tests/fixtures/quality/ruff_v2_baseline.json --report-out output/reports/ruff_v2_incremental_report.json`
   - `python -m mypy tools/sie_autoppt/template_manifest.py tools/sie_autoppt/inputs/html_parser.py tools/sie_autoppt/planning/layout_policy.py`
   - `python -m pytest tests/test_cli.py tests/test_clarify_web.py tests/test_clarifier.py -q`
   - `python -m tools.sie_autoppt.batch.report_metrics --runs-root .\output\runs --run-id-prefix-filter ai-five-stage- --fixtures-dir .\tests\fixtures\batch\ai_five_stage_baseline --baseline-report .\tests\fixtures\batch\ai_five_stage_baseline\baseline_metrics.json --report-out .\output\reports\ai_five_stage_metrics.json --markdown-out .\output\reports\ai_five_stage_metrics.md --require-samples 0 --min-success-rate 0.85 --max-avg-retries 2.5 --max-degraded-ratio 0.35 --max-avg-latency-ms 3000`
3. Validate critical generation path:
   - `python .\main.py make --topic "Release smoke test" --min-slides 3 --max-slides 4 --progress`
4. Confirm docs were updated when behavior changed:
   - `docs/CLI_REFERENCE.md`
   - `docs/TROUBLESHOOTING.md`
   - `docs/COMPATIBILITY_MATRIX.md`
   - `docs/ONCALL_RUNBOOK.md`

## A09 Rollout Checklist

1. Default keep legacy path:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=0`
2. Start canary:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=1`
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT=10`
3. Expand canary to 50% when metrics stay within thresholds for two days.
4. Full rollout:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT=100`
5. Emergency rollback:
   - `SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED=0`

## Versioning

1. Bump version in `pyproject.toml`.
2. Add release section to `CHANGELOG.md` with date.
3. Commit as: `chore(release): vX.Y.Z`.

## Release Validation

1. Trigger GitHub workflow `release-readiness.yml`.
2. Ensure all checks pass.
3. Tag:
   - `git tag vX.Y.Z`
   - `git push origin vX.Y.Z`

## Rollback

1. Identify last stable tag.
2. Re-deploy last stable package/artifact.
3. Open incident summary and append root cause + corrective actions to runbook.
