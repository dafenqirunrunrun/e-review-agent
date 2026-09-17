param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$requiredScreenshots = @(
  "01_h5_home.png",
  "02_h5_demo_product_detail.png",
  "03_h5_order_submit.png",
  "04_h5_demo_payment.png",
  "05_h5_demo_shipping.png",
  "06_h5_confirm_receipt.png",
  "07_h5_review_submit_success.png",
  "08_admin_login_or_dashboard.png",
  "09_admin_ai_dashboard.png",
  "10_admin_comment_list_real_review.png",
  "11_admin_patrol_center.png",
  "12_admin_risk_center.png",
  "13_admin_operation_center.png",
  "14_admin_agent_trace_list.png",
  "15_admin_agent_trace_state_snapshot.png",
  "16_admin_agent_trace_role_timeline.png",
  "17_admin_agent_trace_replay_compare.png",
  "18_admin_agent_eval_quality_health.png",
  "19_admin_case_knowledge_retrieval.png",
  "20_admin_diagnostics_failure_groups.png",
  "21_admin_config_framework_status.png",
  "22_final_acceptance_pass.png"
)

$requiredDiagrams = @(
  "architecture_overview.png",
  "customer_agent_loop.png",
  "agentic_rag_workflow.png",
  "agent_trace_replay.png",
  "database_er_core.png",
  "test_acceptance_matrix.png",
  "benchmark_matrix.png"
)

$requiredOutput = @(
  "E-Review-Agent-v104-Product-Intro.pptx",
  "E-Review-Agent-v104-Product-Intro.pdf",
  "E-Review-Agent-v104-slide_notes.md",
  "E-Review-Agent-v104_screenshot_index.md",
  "E-Review-Agent-v104_asset_manifest.md"
)

foreach ($name in $requiredScreenshots) {
  $path = Join-Path $Root "docs\ppt_assets\screenshots\$name"
  if (-not (Test-Path $path)) { throw "Missing screenshot: $name" }
  if ((Get-Item $path).Length -lt 1024) { throw "Screenshot too small: $name" }
}

foreach ($name in $requiredDiagrams) {
  $path = Join-Path $Root "docs\ppt_assets\diagrams\$name"
  if (-not (Test-Path $path)) { throw "Missing diagram: $name" }
  if ((Get-Item $path).Length -lt 1024) { throw "Diagram too small: $name" }
}

foreach ($name in $requiredOutput) {
  $path = Join-Path $Root "docs\ppt_output\$name"
  if (-not (Test-Path $path)) { throw "Missing output: $name" }
  if ((Get-Item $path).Length -lt 1024) { throw "Output too small: $name" }
}

$scanFiles = Get-ChildItem (Join-Path $Root "docs\ppt_output") -File -Include *.md -Recurse
$badTerms = @("http://", "https://", "C:\", "D:\", ([char]0xFFFD), ([char]0x951F))
foreach ($file in $scanFiles) {
  $text = Get-Content $file.FullName -Raw -Encoding UTF8
  foreach ($term in $badTerms) {
    if ($text.Contains($term)) {
      throw "Output markdown contains forbidden text or mojibake: $($file.Name)"
    }
  }
}

Write-Host "PPT_ASSET_CHECK_PASS screenshots=$($requiredScreenshots.Count) diagrams=$($requiredDiagrams.Count) outputs=$($requiredOutput.Count)"
Write-Host "PPT_OUTPUT_CHECK_PASS"
