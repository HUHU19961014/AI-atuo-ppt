param(
  [string]$Topic = "企业 AI 投资决策汇报健康检查",
  [ValidateSet("quick", "deep")]
  [string]$GenerationMode = "quick",
  [switch]$WithRender
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $env:OPENAI_API_KEY) {
  throw "OPENAI_API_KEY is required for real AI smoke tests."
}

$env:SIE_AUTOPPT_RUN_REAL_AI_TESTS = "1"
$env:SIE_AUTOPPT_REAL_AI_TOPIC = $Topic
$env:SIE_AUTOPPT_REAL_AI_GENERATION_MODE = $GenerationMode

if ($WithRender) {
  $env:SIE_AUTOPPT_REAL_AI_WITH_RENDER = "1"
} else {
  Remove-Item Env:SIE_AUTOPPT_REAL_AI_WITH_RENDER -ErrorAction SilentlyContinue
}

Write-Host "== Enterprise-AI-PPT Real AI Smoke Test =="
Write-Host ("Topic: {0}" -f $Topic)
Write-Host ("Generation mode: {0}" -f $GenerationMode)
Write-Host ("With render: {0}" -f $WithRender.IsPresent)

python -m pytest "$ProjectRoot\tests\test_real_ai_smoke.py" -q
