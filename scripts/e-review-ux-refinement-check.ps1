param(
  [switch]$SkipFlowChecks
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir

function Assert-FileContains {
  param([string]$Path, [string]$Pattern, [string]$Name)
  $full = Join-Path $root $Path
  if (-not (Test-Path $full)) {
    throw "$Name missing: $Path"
  }
  $text = Get-Content -LiteralPath $full -Raw -Encoding UTF8
  if ($text -notmatch $Pattern) {
    throw "$Name missing pattern: $Pattern"
  }
}

function Assert-FileNotContains {
  param([string]$Path, [string]$Pattern, [string]$Name)
  $full = Join-Path $root $Path
  $text = Get-Content -LiteralPath $full -Raw -Encoding UTF8
  if ($text -match $Pattern) {
    throw "$Name contains forbidden pattern: $Pattern"
  }
}

function Assert-FileNotContainsAscii {
  param([string]$Path, [string]$Needle, [string]$Name)
  $full = Join-Path $root $Path
  $bytes = [System.IO.File]::ReadAllBytes($full)
  $text = [System.Text.Encoding]::ASCII.GetString($bytes)
  if ($text.Contains($Needle)) {
    throw "$Name contains forbidden ASCII text: $Needle"
  }
}

function Invoke-Gate {
  param([string]$ScriptName, [string]$Marker)
  $scriptPath = Join-Path $scriptDir $ScriptName
  $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
  $text = ($output | Out-String)
  if ($LASTEXITCODE -ne 0 -or $text -notmatch [regex]::Escape($Marker)) {
    Write-Host $text
    throw "$ScriptName did not report $Marker"
  }
}

$router = "litemall-admin/src/router/index.js"
$locale = "litemall-admin/src/locales/zh-Hans.js"

Assert-FileContains $router "path: 'home'" "AI home route"
Assert-FileContains $router "path: 'governance-flow'" "governance flow route"
Assert-FileContains $router "path: 'observability'" "observability route"
Assert-FileContains $router "path: 'knowledge-quality'" "knowledge quality route"
Assert-FileContains $router "path: 'platform-governance'" "platform governance route"
Assert-FileContains $router "redirect: '/ai-workbench/home'" "legacy dashboard redirect"
Assert-FileContains $router "governance-flow\?tab=patrol" "legacy patrol redirect"
Assert-FileContains $router "observability\?tab=trace" "legacy trace redirect"
Assert-FileContains $router "knowledge-quality\?tab=rag" "legacy rag redirect"
Assert-FileContains $router "platform-governance\?tab=tools" "legacy tool redirect"

Assert-FileContains $locale "ai_workbench_home" "Chinese home menu key"
Assert-FileContains $locale "ai_governance_flow" "Chinese governance menu key"
Assert-FileContains $locale "ai_observability" "Chinese observability menu key"
Assert-FileContains $locale "ai_knowledge_quality" "Chinese knowledge menu key"
Assert-FileContains $locale "ai_platform_governance" "Chinese platform menu key"

$newPages = @(
  "litemall-admin/src/views/ai-workbench-home/index.vue",
  "litemall-admin/src/views/ai-governance-flow/index.vue",
  "litemall-admin/src/views/ai-observability/index.vue",
  "litemall-admin/src/views/ai-knowledge-quality/index.vue",
  "litemall-admin/src/views/ai-platform-governance/index.vue"
)

foreach ($page in $newPages) {
  Assert-FileNotContains $page "undefined\s*</" ($page + " undefined visible text")
  Assert-FileNotContains $page "null\s*</" ($page + " null visible text")
  Assert-FileNotContainsAscii $page "NaN" ($page + " NaN visible text")
  Assert-FileNotContains $page "delivery-check|service-status|final-acceptance-center|startup-page|database-backup-page|delivery-package-page" $page
}

Assert-FileContains "litemall-admin/src/views/ai-workbench-home/index.vue" "startDemo" "home start demo action"
Assert-FileContains "litemall-admin/src/views/ai-workbench-home/index.vue" "runOnce" "home patrol action"
Assert-FileContains "litemall-admin/src/views/ai-workbench-home/index.vue" "governance-flow" "home governance link"
Assert-FileContains "litemall-admin/src/views/ai-workbench-home/index.vue" "observability" "home observability link"
Assert-FileContains "litemall-admin/src/views/ai-governance-flow/index.vue" "name=.reviews." "governance reviews tab"
Assert-FileContains "litemall-admin/src/views/ai-governance-flow/index.vue" "name=.patrol." "governance patrol tab"
Assert-FileContains "litemall-admin/src/views/ai-governance-flow/index.vue" "name=.risk." "governance risk tab"
Assert-FileContains "litemall-admin/src/views/ai-governance-flow/index.vue" "name=.operation." "governance operation tab"
Assert-FileContains "litemall-admin/src/views/ai-observability/index.vue" "name=.trace." "observability trace tab"
Assert-FileContains "litemall-admin/src/views/ai-observability/index.vue" "name=.replay." "observability replay tab"
Assert-FileContains "litemall-admin/src/views/ai-observability/index.vue" "name=.eval." "observability eval tab"
Assert-FileContains "litemall-admin/src/views/ai-observability/index.vue" "name=.agentops." "observability agentops tab"
Assert-FileContains "litemall-admin/src/views/ai-observability/index.vue" "name=.diagnostics." "observability diagnostics tab"
Assert-FileContains "litemall-admin/src/views/ai-knowledge-quality/index.vue" "name=.case." "knowledge case tab"
Assert-FileContains "litemall-admin/src/views/ai-knowledge-quality/index.vue" "name=.rag." "knowledge rag tab"
Assert-FileContains "litemall-admin/src/views/ai-knowledge-quality/index.vue" "name=.memory." "knowledge memory tab"
Assert-FileContains "litemall-admin/src/views/ai-platform-governance/index.vue" "name=.tools." "platform tools tab"
Assert-FileContains "litemall-admin/src/views/ai-platform-governance/index.vue" "name=.approval." "platform approval tab"
Assert-FileContains "litemall-admin/src/views/ai-platform-governance/index.vue" "name=.guardrails." "platform guardrails tab"
Assert-FileContains "litemall-admin/src/views/ai-platform-governance/index.vue" "name=.agents." "platform agents tab"
Assert-FileContains "litemall-admin/src/views/ai-platform-governance/index.vue" "name=.config." "platform config tab"

if (-not $SkipFlowChecks) {
  Invoke-Gate "e-review-full-ui-flow-check.ps1" "FULL_UI_FLOW_PASS"
  Invoke-Gate "e-review-final-acceptance.ps1" "FINAL_ACCEPTANCE_PASS"
}

[ordered]@{
  visibleMenus = 5
  legacyRoutesKept = $true
  h5DemoHints = $true
  result = "UX_REFINEMENT_CHECK_PASS"
} | ConvertTo-Json -Depth 6

Write-Host "UX_REFINEMENT_CHECK_PASS"
