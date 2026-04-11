param(
  [string]$TemplatePath,
  [string]$HtmlPath,
  [string]$InputDir,
  [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $ProjectRoot "tools\regression_check.ps1"

Write-Host "== Enterprise-AI-PPT Legacy Compatibility Wrapper =="
Write-Host "[WARN] legacy_html_regression_check.ps1 validates compatibility only. It is not part of the default V2 release path."

if (-not (Test-Path $scriptPath)) {
  throw "Legacy regression wrapper target not found: $scriptPath"
}

powershell -ExecutionPolicy Bypass -File $scriptPath `
  -TemplatePath $TemplatePath `
  -HtmlPath $HtmlPath `
  -InputDir $InputDir `
  -OutputDir $OutputDir
