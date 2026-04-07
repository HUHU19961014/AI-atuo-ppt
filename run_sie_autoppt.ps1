param(
  [string]$Template,
  [string]$Html,
  [string]$OutputName = "Enterprise-AI-PPT",
  [string]$OutputDir,
  [int]$Chapters = 0,
  [int]$ActiveStart = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

if (-not $Template) { $Template = Join-Path $ProjectRoot "assets\templates\sie_template.pptx" }
if (-not $Html) { $Html = Join-Path $ProjectRoot "samples\input\uat_plan_sample.html" }
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot "output" }

if (-not (Test-Path $Template)) { throw "Template not found: $Template" }
if (-not (Test-Path $Html)) { throw "HTML not found: $Html" }

$scriptPath = Join-Path $ProjectRoot "main.py"
if (-not (Test-Path $scriptPath)) { throw "Generator script not found: $scriptPath" }

$versionFile = Join-Path $ProjectRoot "assets\templates\sie_template.version.txt"
if (Test-Path $versionFile) {
  $rawText = Get-Content $versionFile -Raw
  $m = [regex]::Match($rawText, "sha256=([0-9a-fA-F]{64})")
  $expected = ""
  if ($m.Success) { $expected = $m.Groups[1].Value.ToLower() }
  $actual = (Get-FileHash -Algorithm SHA256 -Path $Template).Hash.ToLower()
  if ([string]::IsNullOrWhiteSpace($expected)) {
    Write-Host "[WARN] Template fingerprint is empty. Run tools/template_utils/update_template_version.ps1"
  } elseif ($expected -ne $actual) {
    Write-Host "[WARN] Template fingerprint mismatch!"
    Write-Host "expected: $expected"
    Write-Host "actual:   $actual"
    Write-Host "Run tools/template_utils/update_template_version.ps1 and then tools/legacy_html_regression_check.ps1"
  } else {
    Write-Host "[OK] Template fingerprint matched."
  }
} else {
  Write-Host "[WARN] Version file not found: $versionFile"
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$cliArgs = @(
  $scriptPath,
  "--template", "$Template",
  "--html", "$Html",
  "--output-name", "$OutputName",
  "--output-dir", "$OutputDir",
  "--active-start", "$ActiveStart"
)

if ($Chapters -gt 0) {
  $cliArgs += @("--chapters", "$Chapters")
}

python @cliArgs

