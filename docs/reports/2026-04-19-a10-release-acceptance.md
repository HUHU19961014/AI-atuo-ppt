# A10 + Release Closure Acceptance (2026-04-19)

## Scope

- A10 static-quality closure:
  - mypy core debt files (`template_manifest.py`, `inputs/html_parser.py`, `planning/layout_policy.py`)
  - ruff key paths (`batch/`, `cli*`)
  - incremental ruff gate for `v2/` (baseline + regression block)
- Release acceptance verification:
  - `scripts/quality_gate.ps1`
  - full `pytest tests -q`

## Acceptance Evidence

### 1. Mypy (A10 core files)

Command:

```powershell
python -m mypy tools/sie_autoppt/template_manifest.py tools/sie_autoppt/inputs/html_parser.py tools/sie_autoppt/planning/layout_policy.py
```

Result: `Success: no issues found in 3 source files`.

### 2. Ruff (key paths)

Command:

```powershell
python -m ruff check tools/sie_autoppt/batch tools/sie_autoppt/cli.py tools/sie_autoppt/cli_parser.py tools/sie_autoppt/cli_sie.py tools/sie_autoppt/cli_v2_commands.py
```

Result: `All checks passed!`.

### 3. Ruff incremental gate (v2)

- Baseline file: `tests/fixtures/quality/ruff_v2_baseline.json`
- Gate report: `output/reports/ruff_v2_incremental_report.json`
- Current status:
  - baseline issues: `74`
  - current issues: `74`
  - regressions: `[]` (none)

### 4. Quality gate

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/quality_gate.ps1
```

Result: `quality gate passed` (10/10 steps passed, legacy boundary guard skipped because script missing).

### 5. Full regression

Command:

```powershell
pytest tests -q
```

Result: `529 passed, 4 skipped, 9 subtests passed`.

## Gate Changes Landed

- `scripts/quality_gate.ps1`
  - added full-rule ruff check for `batch/` + `cli*`
  - added `v2` incremental ruff baseline gate
  - added A10 core-file mypy check
  - normalized step numbering to `1/10 .. 10/10`
- `docs/TESTING.md` and `docs/RELEASE_PROCESS.md`
  - synchronized with the new A10 gates and commands

## Residual Debt (Explicitly Deferred)

- `tools/sie_autoppt/v2` still contains baseline ruff debt (`74` issues) tracked by incremental gate.
- Policy now is "no regression on v2 debt"; stock burn-down remains a separate batch task.
