param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "== SIE-autoppt Unit Tests =="
python -m unittest discover -s (Join-Path $ProjectRoot "tests") -v
