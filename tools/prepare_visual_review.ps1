param(
  [string]$Template,
  [string]$ReferenceBody,
  [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $Template) { $Template = Join-Path $ProjectRoot "assets\templates\sie_template.pptx" }
if (-not $ReferenceBody) { $ReferenceBody = Join-Path $ProjectRoot "input\reference_body_style.pptx" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $ProjectRoot "projects\visual_review" }

$scriptPath = Join-Path $ProjectRoot "tools\sie_autoppt_cli.py"
if (-not (Test-Path $Template)) { throw "Template not found: $Template" }
if (-not (Test-Path $scriptPath)) { throw "Generator script not found: $scriptPath" }

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reviewDir = Join-Path $OutputRoot "visual_review_$timestamp"
New-Item -ItemType Directory -Path $reviewDir -Force | Out-Null

$cases = @(
  @{
    Name = "uat_plan_sample"
    Label = "General business deck"
    Html = Join-Path $ProjectRoot "input\uat_plan_sample.html"
    Focus = @(
      "Check cover, directory, body, and ending slide order.",
      "Check active directory highlight changes by chapter.",
      "Check body title and subtitle placement."
    )
  },
  @{
    Name = "default_erp_blueprint"
    Label = "ERP architecture, process, and governance"
    Html = Join-Path $ProjectRoot "input\default_erp_blueprint.html"
    Focus = @(
      "Check solution_architecture, process_flow, and org_governance layouts.",
      "Check shapes, color blocks, and text for overlap.",
      "Check governance footer text remains readable."
    )
  },
  @{
    Name = "ai_pythonpptx_strategy"
    Label = "Reference-style import deck"
    Html = Join-Path $ProjectRoot "input\ai_pythonpptx_strategy.html"
    Focus = @(
      "Check comparison_upgrade, capability_ring, and five_phase_path style import.",
      "Check imported shapes, icons, and decorative assets are preserved.",
      "Check imported pages use the current sample content."
    )
  },
  @{
    Name = "vendor_launch_sample"
    Label = "Long-text and process deck"
    Html = Join-Path $ProjectRoot "input\vendor_launch_sample.html"
    Focus = @(
      "Check long text for visible overflow or truncation.",
      "Check process step boxes are evenly distributed.",
      "Check shortened directory labels remain readable."
    )
  }
)

$summaryLines = New-Object System.Collections.Generic.List[string]
$summaryLines.Add("# Visual Review Batch")
$summaryLines.Add("")
$summaryLines.Add("Generated at: $timestamp")
$summaryLines.Add("Output dir: $reviewDir")
$summaryLines.Add("")
$summaryLines.Add("Global checklist:")
$summaryLines.Add("- Cover, directory, body, and ending slides are in the right order.")
$summaryLines.Add("- Active directory highlight is correct.")
$summaryLines.Add("- Template visual assets are preserved.")
$summaryLines.Add("- No obvious text overflow, overlap, or misalignment.")
$summaryLines.Add("- Both _QA.txt and _QA.json exist.")
$summaryLines.Add("")

foreach ($case in $cases) {
  if (-not (Test-Path $case.Html)) {
    throw "HTML not found: $($case.Html)"
  }

  Write-Host ("-- Generating visual review case: {0}" -f $case.Name)
  $lines = @(
    python $scriptPath `
      --template "$Template" `
      --html "$($case.Html)" `
      --reference-body "$ReferenceBody" `
      --output-name "VisualReview_$($case.Name)" `
      --output-dir "$reviewDir" `
      --chapters 3 `
      --active-start 0
  ) 2>&1

  if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate visual review case: $($case.Name)"
  }

  $cleanLines = @($lines | Where-Object { $_ -and $_.Trim() -ne "" })
  if ($cleanLines.Count -lt 2) {
    throw "Unexpected CLI output for case: $($case.Name)"
  }

  $reportPath = $cleanLines[0].Trim()
  $pptxPath = $cleanLines[1].Trim()
  $jsonPath = [System.IO.Path]::ChangeExtension($reportPath, ".json")

  $summaryLines.Add("## $($case.Name)")
  $summaryLines.Add("")
  $summaryLines.Add("Label: $($case.Label)")
  $summaryLines.Add("")
  $summaryLines.Add("PPT: $pptxPath")
  $summaryLines.Add("QA.txt: $reportPath")
  $summaryLines.Add("QA.json: $jsonPath")
  $summaryLines.Add("Focus checks:")
  foreach ($item in $case.Focus) {
    $summaryLines.Add("- $item")
  }
  $summaryLines.Add("")
}

$summaryPath = Join-Path $reviewDir "VISUAL_REVIEW_CHECKLIST.md"
$summaryLines | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host ""
Write-Host "Visual review batch ready:"
Write-Host $reviewDir
Write-Host $summaryPath
