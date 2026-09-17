param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

$terms = @(
  "pending",
  "approved",
  "rejected",
  "enabled",
  "disabled",
  "fallback",
  "guardrail",
  "memory",
  "tool registry",
  "agentops",
  "approval",
  "risk_level",
  "false_positive",
  "suggestion_bad",
  "transferred_after_sales",
  "closed_without_action",
  "undefined",
  "null",
  "NaN"
)

$allowedFiles = @(
  "litemall-admin\src\utils\aiDisplayMap.js",
  "litemall-admin\src\api\aiEnterprise.js",
  "litemall-admin\src\api\aiDemoReview.js",
  "litemall-admin\src\locales\en.js",
  "docs\36_api_reference.md",
  "docs\66_zh_product_terminology_guide.md"
)

$uiFiles = @()
foreach ($dir in @("litemall-admin\src", "litemall-vue\src")) {
  $path = Join-Path $Root $dir
  if (Test-Path $path) {
    $uiFiles += Get-ChildItem $path -Recurse -File -Include "*.vue", "*.js"
  }
}

$docFiles = @(
  "docs\44_defense_assets_plan.md",
  "docs\46_ppt_outline_final_defense.md",
  "docs\47_defense_qna.md",
  "docs\60_enterprise_agent_gap_analysis.md",
  "docs\61_tool_registry_and_permission_design.md",
  "docs\62_agent_memory_design.md",
  "docs\63_guardrails_design.md",
  "docs\64_agentops_design.md",
  "docs\65_v11_enterprise_agent_platform_report.md",
  "docs\67_zh_localized_ppt_update_notes.md",
  "docs\68_v12_agent_protocol_and_rag_quality_plan.md",
  "docs\69_v12_rag_quality_report.md",
  "docs\70_tool_manifest_protocol_design.md",
  "docs\71_tool_schema_contract_test_report.md",
  "docs\72_agentops_trend_report.md",
  "docs\73_v12_final_report.md",
  "docs\74_v12_manual_ui_check_report.md",
  "docs\ppt_output\E-Review-Agent-v104-slide_notes.md"
) | ForEach-Object {
  $path = Join-Path $Root $_
  if (Test-Path $path) { Get-Item $path }
}

function Get-RelativePath($file) {
  return $file.FullName.Substring($Root.Length + 1)
}

function Is-AllowedFile($relative) {
  return $allowedFiles -contains $relative
}

function Has-TermInText($text) {
  if ($text -match 'app\.menu\.|promotion_ad\.|\.enabled_|^\s*[-_a-zA-Z0-9.]+\s*$') {
    return $false
  }
  if ($text -match 'AgentOps') {
    return $false
  }
  return $text -match '(?i)\b(pending|approved|rejected|enabled|disabled|fallback|guardrail|memory|tool registry|agentops|approval|risk_level|false_positive|suggestion_bad|transferred_after_sales|closed_without_action|undefined|null|NaN)\b'
}

function Is-LikelyVisibleUiLine($line) {
  $withoutExpressions = $line -replace '\{\{[^}]*\}\}', ''
  $visibleTextMatches = [regex]::Matches($withoutExpressions, '>\s*([^<]+?)\s*<')
  foreach ($match in $visibleTextMatches) {
    if (Has-TermInText $match.Groups[1].Value) {
      return $true
    }
  }

  $attributeMatches = [regex]::Matches($line, "(?i)(label|placeholder|title|empty-text|description|message|content)=[""']([^""']+)[""']")
  foreach ($match in $attributeMatches) {
    if (Has-TermInText $match.Groups[2].Value) {
      return $true
    }
  }

  $objectTextMatches = [regex]::Matches($line, "(?i)(label|hint|description|message|title)\s*:\s*[""']([^""']+)[""']")
  foreach ($match in $objectTextMatches) {
    if (Has-TermInText $match.Groups[2].Value) {
      return $true
    }
  }

  return $false
}

function Is-LikelyVisibleDocLine($line) {
  if ($line -match '^\s*[-*]\s*`' -or $line -match '`/.+`' -or $line -match '^\s*\|.*`') {
    return $false
  }
  if ($line -match '[A-Z0-9_]+_PASS') {
    return $false
  }
  return $line -match '(pending|approved|rejected|enabled|disabled|fallback|guardrail|memory|tool registry|agentops|approval|risk_level|false_positive|suggestion_bad|transferred_after_sales|closed_without_action|undefined|null|NaN)'
}

$violations = @()

foreach ($file in $uiFiles) {
  $relative = Get-RelativePath $file
  if (Is-AllowedFile $relative) {
    continue
  }
  $lines = [System.IO.File]::ReadAllLines($file.FullName)
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if (Is-LikelyVisibleUiLine $line) {
      $violations += [ordered]@{
        file = $relative
        line = $i + 1
        type = "visible_ui_english_or_internal_value"
        sample = if ($line.Length -gt 180) { $line.Substring(0, 180) } else { $line }
      }
    }
  }
}

foreach ($file in $docFiles) {
  $relative = Get-RelativePath $file
  if (Is-AllowedFile $relative) {
    continue
  }
  $lines = [System.IO.File]::ReadAllLines($file.FullName)
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if (Is-LikelyVisibleDocLine $line) {
      $violations += [ordered]@{
        file = $relative
        line = $i + 1
        type = "doc_visible_english_or_internal_value"
        sample = if ($line.Length -gt 180) { $line.Substring(0, 180) } else { $line }
      }
    }
  }
}

if ($violations.Count -gt 0) {
  [ordered]@{
    result = "FAIL"
    violations = $violations
  } | ConvertTo-Json -Depth 8
  exit 1
}

[ordered]@{
  result = "ZH_UI_TEXT_CHECK_PASS"
  scannedUiFiles = $uiFiles.Count
  scannedDocFiles = $docFiles.Count
} | ConvertTo-Json -Depth 4
