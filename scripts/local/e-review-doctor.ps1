param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [string]$Python = $env:E_REVIEW_PYTHON,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

function Add-Check {
  param([string]$Name, [string]$Status, [string]$Message)
  $script:Checks += [ordered]@{ name = $Name; status = $Status; message = $Message }
}

function Test-CommandAvailable {
  param([string]$Name, [string]$Command)
  $found = Get-Command $Command -ErrorAction SilentlyContinue
  if ($found) { Add-Check $Name "PASS" $found.Source } else { Add-Check $Name "BLOCKED" "$Command not found" }
}

function Test-ConfiguredSetting {
  param([string[]]$Names, [string]$EnvFile)
  foreach ($name in $Names) {
    $processValue = [Environment]::GetEnvironmentVariable($name, "Process")
    if ($processValue -and $processValue -notmatch '^<.*>$') { return $true }
  }
  if (-not (Test-Path $EnvFile)) { return $false }
  $lines = Get-Content $EnvFile
  foreach ($name in $Names) {
    $line = $lines | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if (-not $line) { continue }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value -and $value -notmatch '^<.*>$') { return $true }
  }
  return $false
}

$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$runtime = Resolve-RuntimeHome $RuntimeHome
$venvPython = Join-Path $root "ai-service\.venv\Scripts\python.exe"
$Python = if ($Python) { $Python } elseif (Test-Path $venvPython) { $venvPython } else { "python" }
$script:Checks = @()

New-Item -ItemType Directory -Force -Path $runtime, (Join-Path $runtime "logs"), (Join-Path $runtime "pids"), (Join-Path $runtime "status") | Out-Null

Test-CommandAvailable "Java" "java"
Test-CommandAvailable "Maven" "mvn"
Test-CommandAvailable "Node" "node"
Test-CommandAvailable "npm" "npm"
Test-CommandAvailable "Python" $Python
Test-CommandAvailable "MySQL client" "mysql"

try {
  $pip = & $Python -m pip check 2>&1
  if ($LASTEXITCODE -eq 0) { Add-Check "pip check" "PASS" (($pip | Out-String).Trim()) } else { Add-Check "pip check" "WARN" (($pip | Out-String).Trim()) }
} catch {
  Add-Check "pip check" "WARN" $_.Exception.Message
}

try {
  $torch = & $Python -c "import json; import torch; print(json.dumps({'torch': torch.__version__, 'cuda': torch.cuda.is_available()}))" 2>$null
  if ($LASTEXITCODE -eq 0 -and $torch) { Add-Check "Torch/CUDA" "PASS" $torch } else { Add-Check "Torch/CUDA" "WARN" "torch not available in selected Python" }
} catch {
  Add-Check "Torch/CUDA" "WARN" "torch not available in selected Python"
}

$adminJarRelative = $env:E_REVIEW_ADMIN_JAR
if (-not $adminJarRelative) { $adminJarRelative = "litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar" }
$adminJar = Join-Path $root $adminJarRelative
if (Test-Path $adminJar) { Add-Check "Admin API jar" "PASS" $adminJar } else { Add-Check "Admin API jar" "WARN" "Run mvn -DskipTests package before start." }

foreach ($port in @(8008, 8083, 9527)) {
  $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) { Add-Check "Port $port" "WARN" "Already listening, PID=$($conn.OwningProcess)" } else { Add-Check "Port $port" "PASS" "free" }
}

$aiEnv = Join-Path $root "ai-service\.env"
$embeddingConfigured = Test-ConfiguredSetting -Names @("E_REVIEW_POLICY_RAG_EMBEDDING_MODEL_PATH", "RAG_BGE_M3_MODEL_PATH", "E_REVIEW_BGE_M3_MODEL_DIR") -EnvFile $aiEnv
$rerankerConfigured = Test-ConfiguredSetting -Names @("E_REVIEW_POLICY_RAG_RERANKER_MODEL_PATH", "RAG_RERANKER_MODEL_PATH", "E_REVIEW_RERANKER_MODEL_DIR") -EnvFile $aiEnv
$llmConfigured = Test-ConfiguredSetting -Names @("AGENT_LLM_MODEL_PATH", "E_REVIEW_LOCAL_QWEN_MODEL_DIR") -EnvFile $aiEnv
if ($embeddingConfigured) { Add-Check "Embedding model path" "PASS" "configured outside repository" } else { Add-Check "Embedding model path" "WARN" "not configured; dense provider may use fallback/hash mode" }
if ($rerankerConfigured) { Add-Check "Reranker model path" "PASS" "configured outside repository" } else { Add-Check "Reranker model path" "WARN" "not configured; model reranker remains optional" }
if ($llmConfigured) { Add-Check "Local LLM model path" "PASS" "configured outside repository" } else { Add-Check "Local LLM model path" "WARN" "not configured; deterministic governance remains available" }

$blocked = @($Checks | Where-Object { $_.status -eq "BLOCKED" })
$status = if ($blocked.Count -eq 0) { "PASS" } else { "BLOCKED" }
$summary = [ordered]@{
  schemaVersion = "1.0.0"
  status = $status
  root = $root
  runtimeHome = $runtime
  checks = $Checks
  boundaries = @("REAL_LLM_QUALITY_NOT_VERIFIED", "MODEL_RERANKER_NOT_VERIFIED", "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
}
$out = Join-Path $runtime "status\doctor.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $out

if ($Json) {
  $summary | ConvertTo-Json -Depth 8
} else {
  $Checks | ForEach-Object { Write-Host ("[{0}] {1}: {2}" -f $_.status, $_.name, $_.message) }
  if ($status -eq "PASS") { Write-Host "E_REVIEW_LOCAL_DOCTOR_PASS" } else { Write-Host "E_REVIEW_LOCAL_DOCTOR_BLOCKED" }
}

if ($status -eq "PASS") { exit 0 } else { exit 2 }
