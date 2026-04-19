# Testing

This document is aligned with the current CLI and batch architecture.

## 1. Local Quality Gate (CI-aligned)

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

Current gate order:

1. Targeted `ruff --select F`
2. Full-rule `ruff` for `batch/` + `cli*` key paths
3. `ruff` incremental baseline gate for `v2/` (`tools.sie_autoppt.quality.ruff_incremental`)
4. Targeted `mypy` + A10 core-file `mypy`
5. Release subset tests
6. Coverage gate for CLI entry surfaces
7. A08 baseline metrics gate (`tools.sie_autoppt.batch.report_metrics`)

## 2. Core Regression Entrypoints

### Full local suite

```powershell
python -m pytest tests -q
```

### Internal batch subset

```powershell
python -m pytest tests/test_batch_contracts.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_batch_metrics.py tests/test_batch_rollout.py tests/test_doc_drift.py -q
```

### A08 baseline metrics replay report

```powershell
python -m tools.sie_autoppt.batch.report_metrics `
  --runs-root .\output\runs `
  --run-id-prefix-filter ai-five-stage- `
  --fixtures-dir .\tests\fixtures\batch\ai_five_stage_baseline `
  --baseline-report .\tests\fixtures\batch\ai_five_stage_baseline\baseline_metrics.json `
  --report-out .\output\reports\ai_five_stage_metrics.json `
  --markdown-out .\output\reports\ai_five_stage_metrics.md
```

### A10 ruff incremental gate (v2 baseline)

```powershell
python -m tools.sie_autoppt.quality.ruff_incremental `
  --paths tools/sie_autoppt/v2 `
  --baseline tests/fixtures/quality/ruff_v2_baseline.json `
  --report-out output/reports/ruff_v2_incremental_report.json
```

### V2 compatibility subset

```powershell
python -m pytest tests/test_v2_services.py tests/test_v2_cli.py tests/test_quality_gate.py -q
```

## 3. Internal Batch Real Bridge Smoke (Optional)

Use this only when a real external `pptmaster` repo is available.

Prerequisites:

1. `--pptmaster-root` (or `SIE_PPTMASTER_ROOT`) points to a valid root.
2. The root contains:
   - `skills/ppt-master/scripts/total_md_split.py`
   - `skills/ppt-master/scripts/finalize_svg.py`
   - `skills/ppt-master/scripts/svg_to_pptx.py`

Example run (AI preprocess path):

```powershell
python .\main.py batch-make --topic "AI strategy" --brief "Executive deck" --pptmaster-root D:\path\to\ppt-master --run-id smoke-run --output-dir .\output
```

Example run (external bundle path):

```powershell
python .\main.py batch-make --content-bundle-json .\output\runs\sample\preprocess\content_bundle.json --pptmaster-root D:\path\to\ppt-master --run-id smoke-bundle --output-dir .\output
```

Pass criteria:

- `output/runs/<run_id>/final/final.pptx` exists.
- `output/runs/<run_id>/final/run_summary.json` exists with `final_state=SUCCEEDED`.

Failure diagnostics (acceptable if explicit):

- `output/runs/<run_id>/dead_letter.json` exists.
- `dead_letter.json` includes `stage`, `failure_code`, and `retry_attempts`.
- `logs/spans.jsonl`, `logs/usage.jsonl`, `logs/errors.jsonl` exist.

## 4. Troubleshooting Hints

- `Missing required pptmaster script`: check bridge root and required script paths.
- `unsupported slide intent`: validate `semantic_payload.slides[].intent`.
- `export hash mismatch`: compare `bridge/export_manifest.json` with exported PPTX hash.
- Input guard rejection: check suffix/size limits and URL/text validation rules.
