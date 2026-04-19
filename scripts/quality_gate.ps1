Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )
    Write-Host $Name
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name (exit code: $LASTEXITCODE)"
    }
}

Invoke-Step "[1/10] Ruff (CLI targeted F checks)" {
    python -m ruff check tools/sie_autoppt/cli.py tools/sie_autoppt/clarify_web.py tools/sie_autoppt/exceptions.py tools/sie_autoppt/cli_parser.py --select F
}

Invoke-Step "[2/10] Ruff (V2/planning/qa targeted F checks)" {
    python -m ruff check tools/sie_autoppt/v2 tools/sie_autoppt/planning tools/sie_autoppt/qa --select F
}

Invoke-Step "[3/10] Ruff (batch + CLI full rules)" {
    python -m ruff check tools/sie_autoppt/batch tools/sie_autoppt/cli.py tools/sie_autoppt/cli_parser.py tools/sie_autoppt/cli_sie.py tools/sie_autoppt/cli_v2_commands.py
}

Invoke-Step "[4/10] Ruff incremental baseline gate (v2)" {
    python -m tools.sie_autoppt.quality.ruff_incremental `
        --paths tools/sie_autoppt/v2 `
        --baseline tests/fixtures/quality/ruff_v2_baseline.json `
        --report-out output/reports/ruff_v2_incremental_report.json
}

Invoke-Step "[5/10] Ruff (targeted tests F checks)" {
    python -m ruff check tests/test_cli.py tests/test_clarify_web.py tests/test_v2_services.py tests/test_v2_quality_checks.py --select F
}

Invoke-Step "[6/10] Mypy (release target files)" {
    python -m mypy tools/sie_autoppt/llm_openai.py tools/sie_autoppt/cli_v2_commands.py tools/sie_autoppt/language_policy.py
}

Invoke-Step "[7/10] Mypy (A10 core files)" {
    python -m mypy tools/sie_autoppt/template_manifest.py tools/sie_autoppt/inputs/html_parser.py tools/sie_autoppt/planning/layout_policy.py
}

$legacyGuard = "tools/check_legacy_boundary.py"
if (Test-Path $legacyGuard) {
    Invoke-Step "[8/10] Legacy boundary guard" {
        python $legacyGuard
    }
}
else {
    Write-Warning "[8/10] Legacy boundary guard skipped: $legacyGuard not found"
}

$releaseTests = @(
    "tests/test_cli.py",
    "tests/test_v2_cli.py",
    "tests/test_clarify_web.py",
    "tests/test_clarifier.py",
    "tests/test_v2_services.py",
    "tests/test_v2_quality_checks.py",
    "tests/test_plugins.py",
    "tests/test_language_policy.py"
) | Where-Object { Test-Path $_ }

if ($releaseTests.Count -eq 0) {
    throw "No release subset tests were found."
}

Invoke-Step "[9/10] Release subset tests + coverage gate" {
    python -m pytest @releaseTests -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m coverage run --source=tools.sie_autoppt.cli,tools.sie_autoppt.cli_v2_commands -m pytest tests/test_cli.py tests/test_v2_cli.py tests/test_clarifier.py tests/test_clarify_web.py -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m coverage report -m --fail-under=80
}

Invoke-Step "[10/10] A08 baseline metrics gate" {
    python -m tools.sie_autoppt.batch.report_metrics `
        --runs-root output/runs `
        --run-id-prefix-filter ai-five-stage- `
        --fixtures-dir tests/fixtures/batch/ai_five_stage_baseline `
        --baseline-report tests/fixtures/batch/ai_five_stage_baseline/baseline_metrics.json `
        --report-out output/reports/ai_five_stage_metrics.json `
        --markdown-out output/reports/ai_five_stage_metrics.md `
        --min-fixtures 10 `
        --require-samples 0 `
        --min-success-rate 0.85 `
        --max-avg-retries 2.5 `
        --max-degraded-ratio 0.35 `
        --max-avg-latency-ms 3000
}

Write-Host "quality gate passed"
