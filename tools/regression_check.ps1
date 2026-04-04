param(
  [string]$TemplatePath,
  [string]$HtmlPath,
  [string]$InputDir,
  [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $TemplatePath) { $TemplatePath = Join-Path $ProjectRoot "assets\templates\sie_template.pptx" }
if (-not $InputDir) { $InputDir = Join-Path $ProjectRoot "input" }
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot "projects\generated" }

Write-Host "== SIE-autoppt Regression Check =="

function Assert-Path($path, $name) {
  if (-not (Test-Path $path)) {
    throw "$name not found: $path"
  }
  Write-Host "[OK] $name exists: $path"
}

function Assert-QA($reportPath, $caseName) {
  $qa = Get-Content $reportPath -Raw
  if ($qa -notmatch "check_ending_last: PASS") {
    throw "QA failed for ${caseName}: ending slide check did not pass."
  }
  if ($qa -notmatch "actual_directory_pages:\s+\[3, 5, 7\]") {
    throw "QA failed for ${caseName}: directory pages are not [3, 5, 7]."
  }
  $overflow = [regex]::Match($qa, "overflow_risk_boxes:\s+(\d+)")
  if (-not $overflow.Success) {
    throw "QA failed for ${caseName}: overflow_risk_boxes missing."
  }
  if ([int]$overflow.Groups[1].Value -gt 0) {
    throw "QA failed for ${caseName}: overflow_risk_boxes > 0."
  }
  if ($qa -notmatch "check_theme_title_font_40: PASS") {
    throw "QA failed for ${caseName}: theme title font is not fixed at 40pt."
  }
  if ($qa -notmatch "check_directory_title_font_24: PASS") {
    throw "QA failed for ${caseName}: directory title font is not fixed at 24pt."
  }
  if ($qa -notmatch "check_directory_assets_preserved: PASS") {
    throw "QA failed for ${caseName}: directory slide assets were not preserved."
  }
}

function Assert-ExpectedFailure($caseName) {
  if ($LASTEXITCODE -eq 0) {
    throw "Regression failed for ${caseName}: case was expected to fail but succeeded."
  }
}

function Assert-QAJson($reportPath, $caseName) {
  $script = @"
import json
from pathlib import Path

qa = json.loads(Path(r'''$reportPath''').read_text(encoding='utf-8'))
if not qa.get('schema_version'):
    raise SystemExit('schema_version missing')
if not qa.get('template_manifest_path'):
    raise SystemExit('template_manifest_path missing')
if not qa.get('template_name'):
    raise SystemExit('template_name missing')
checks = qa.get('checks', {})
if checks.get('theme_title_font') != 'PASS':
    raise SystemExit('theme title font check did not pass')
if checks.get('directory_title_font') != 'PASS':
    raise SystemExit('directory title font check did not pass')
print('ok')
"@
  $output = @($script | python -) 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "QA JSON failed for ${caseName}: $($output -join ' ')"
  }
}

Assert-Path $TemplatePath "Template"
Assert-Path $InputDir "Input directory"
Assert-Path (Join-Path $ProjectRoot "tools\sie_autoppt_cli.py") "CLI entry"

python --version | Out-Null
python -c "import pptx; print('python-pptx ok')" | Out-Null
Write-Host "[OK] Python and python-pptx available"

python -m py_compile (Join-Path $ProjectRoot "tools\sie_autoppt_cli.py")
python -m py_compile (Join-Path $ProjectRoot "tools\sie_autoppt\generator.py")
Write-Host "[OK] Python files compiled"

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$cases = @()
if ($HtmlPath) {
  Assert-Path $HtmlPath "HTML input"
  $cases = @(Get-Item $HtmlPath)
} else {
  $cases = @(Get-ChildItem -Path $InputDir -Filter *.html | Sort-Object Name)
  if ($cases.Count -eq 0) {
    throw "No HTML regression cases found under: $InputDir"
  }
}

foreach ($case in $cases) {
  $caseName = [System.IO.Path]::GetFileNameWithoutExtension($case.Name)
  $expectFailure = $case.Name -like "*.fail.html"
  Write-Host ("-- Running case: {0}" -f $caseName)
  if ($expectFailure) {
    try {
      & python (Join-Path $ProjectRoot "tools\sie_autoppt_cli.py") `
        --template "$TemplatePath" `
        --html "$($case.FullName)" `
        --output-name "SIE_Regression_$caseName" `
        --output-dir "$OutputDir" `
        --chapters 3 `
        --active-start 0 1>$null 2>$null
    } catch {
      if ($LASTEXITCODE -eq 0) {
        throw
      }
    }
    Assert-ExpectedFailure $caseName
    Write-Host ("[OK] Expected failure passed: {0}" -f $caseName)
    continue
  }

  $lines = @(
    python (Join-Path $ProjectRoot "tools\sie_autoppt_cli.py") `
      --template "$TemplatePath" `
      --html "$($case.FullName)" `
      --output-name "SIE_Regression_$caseName" `
      --output-dir "$OutputDir" `
      --chapters 3 `
      --active-start 0
  ) 2>&1

  if ($LASTEXITCODE -ne 0) {
    throw "Generation failed for case: $caseName"
  }

  $cleanLines = @($lines | Where-Object { $_ -and $_.Trim() -ne "" })
  if ($cleanLines.Count -lt 2) {
    throw "Unexpected CLI output for case: $caseName"
  }

  $reportPath = $cleanLines[0].Trim()
  $pptxPath = $cleanLines[1].Trim()
  $jsonReportPath = [System.IO.Path]::ChangeExtension($reportPath, ".json")
  Assert-Path $reportPath "QA report for $caseName"
  Assert-Path $jsonReportPath "QA JSON report for $caseName"
  Assert-Path $pptxPath "PPT output for $caseName"
  Assert-QA $reportPath $caseName
  Assert-QAJson $jsonReportPath $caseName
  Write-Host ("[OK] Case passed: {0}" -f $caseName)
}

Write-Host ("== Regression check passed ({0} case(s)) ==" -f $cases.Count)
