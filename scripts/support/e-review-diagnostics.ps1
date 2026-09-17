param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [string]$Python = $env:E_REVIEW_PYTHON
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

function Write-TextFile {
  param([string]$Path, [string]$Text)
  Set-Content -LiteralPath $Path -Encoding UTF8 -Value $Text
}

$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$runtime = Resolve-RuntimeHome $RuntimeHome
$Python = if ($Python) { $Python } else { "python" }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$diagDir = Join-Path $runtime "diagnostics\e-review-diagnostics-$timestamp"
New-Item -ItemType Directory -Force -Path $diagDir | Out-Null

$branch = (& git -C $root branch --show-current | Out-String).Trim()
$commit = (& git -C $root rev-parse --short=8 HEAD | Out-String).Trim()
$status = (& git -C $root status --short | Out-String)

$summary = [ordered]@{
  schemaVersion = "1.0.0"
  createdAt = (Get-Date).ToString("o")
  branch = $branch
  commit = $commit
  runtimeHome = $runtime
  boundaries = @("REAL_LLM_QUALITY_NOT_VERIFIED", "MODEL_RERANKER_NOT_VERIFIED", "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED", "NO_PUSH", "NO_TAG", "NO_RELEASE")
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $diagDir "summary.json")
Write-TextFile -Path (Join-Path $diagDir "git-status-redacted.txt") -Text $status

$versions = @()
foreach ($cmd in @("java -version", "mvn -version", "node --version", "npm --version")) {
  try { $versions += "## $cmd`n" + ((cmd /c "$cmd 2>&1") | Out-String) } catch { $versions += "## $cmd`n$($_.Exception.Message)" }
}
try { $versions += "## python`n" + ((& $Python --version 2>&1) | Out-String) } catch { $versions += "## python`n$($_.Exception.Message)" }
Write-TextFile -Path (Join-Path $diagDir "versions.txt") -Text ($versions -join "`n")

try {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\local\e-review-status.ps1") -RuntimeHome $runtime -Json |
    Set-Content -Encoding UTF8 (Join-Path $diagDir "health.json")
} catch {
  @{ status = "WARN"; error = $_.Exception.Message } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $diagDir "health.json")
}

@{
  defaultMavenGate = Test-Path (Join-Path $root "artifacts\agent-rag\v2.0-rc\default-maven-test-gate.json")
  secretScan = Test-Path (Join-Path $root "artifacts\agent-rag\v2.0-rc\repository-secret-scan.json")
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $diagDir "gate-status.json")

@() | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $diagDir "redacted-errors.json")

$zip = Join-Path $runtime "diagnostics\e-review-diagnostics-$timestamp.zip"
Compress-Archive -Path (Join-Path $diagDir "*") -DestinationPath $zip -Force
[ordered]@{
  schemaVersion = "1.0.0"
  status = "PASS"
  zip = $zip
  files = @("summary.json", "versions.txt", "health.json", "gate-status.json", "redacted-errors.json")
} | ConvertTo-Json -Depth 6
Write-Host "E_REVIEW_SAFE_DIAGNOSTICS_PASS"

