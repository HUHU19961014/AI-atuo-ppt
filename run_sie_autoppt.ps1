param(
  [string]$Topic = "企业 AI 战略汇报"
)

$ErrorActionPreference = "Stop"

throw @"
run_sie_autoppt.ps1 has been retired.

Use one of these paths instead:
- Primary V2 workflow: python .\main.py make --topic "$Topic" --theme sie_consulting_fixed
- No-AI local smoke: python .\main.py demo
- SVG->PPTX bridge: python .\main.py svg-export --svg-project-path <project_path> --svg-stage final
"@

