param(
  [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $OutputRoot) { $OutputRoot = Join-Path $ProjectRoot "projects\visual_review" }
$scriptPath = Join-Path $ProjectRoot "tools\prepare_visual_review.py"
if (-not (Test-Path $scriptPath)) { throw "Visual review batch script not found: $scriptPath" }

python $scriptPath --output-root "$OutputRoot"
if ($LASTEXITCODE -ne 0) {
  throw "Failed to prepare V2 visual review batch."
}
