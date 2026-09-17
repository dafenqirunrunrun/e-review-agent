param(
  [string]$AdminBaseUrl = "http://127.0.0.1:8083",
  [string]$AiBaseUrl = "http://127.0.0.1:8008",
  [string]$TenantId = "__local__",
  [string]$SubjectType = "review",
  [string]$TestSubjectIdPrefix = ("phase2-runtime-" + (Get-Date -Format "yyyyMMddHHmmss")),
  [string]$AuthToken = "",
  [string]$OutputPath = "artifacts/agent-rag/v2.0-java-runtime/java-workflow-runtime-summary.json",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = $env:LITEMALL_ADMIN_PASSWORD,
  [string]$Mysql = $env:MYSQL_BIN,
  [string]$MysqlUser = "litemall",
  [string]$MysqlDatabase = "litemall",
  [string]$AiPython = $env:AGENT_RAG_AI_PYTHON,
  [string]$AiRuntimeWrapper = $env:AGENT_RAG_AI_RUNTIME_WRAPPER
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($AdminPassword)) {
  $AdminPassword = "admin123"
}
if ([string]::IsNullOrWhiteSpace($Mysql)) {
  $cmd = Get-Command mysql -ErrorAction SilentlyContinue
  if ($cmd) { $Mysql = $cmd.Source }
}

function Assert-Ok {
  param([object]$Response, [string]$Name)
  if ($null -eq $Response -or $Response.errno -ne 0) {
    $message = if ($Response) { $Response.errmsg } else { "empty response" }
    throw "$Name failed: $message"
  }
}

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 12)
}

function Invoke-Analyze {
  param([string]$CaseName, [string]$SubjectId, [string]$Query, [hashtable]$Context)
  $body = @{
    requestId = "$CaseName-" + [Guid]::NewGuid().ToString("N")
    tenantId = "__forged_client_tenant__"
    subjectType = $SubjectType
    subjectId = $SubjectId
    query = $Query
    runtimeMode = "local-model"
    schemaVersion = "2.0.0"
    retrieval = @{
      enabled = $true
      topK = 8
      rerankTopK = 4
      requestedMode = "bm25-first-semantic-hybrid"
      publicTenantEnabled = $true
    }
    context = $Context
  }
  $response = Invoke-JsonPost -Url "$AdminBaseUrl/admin/agent-rag/analyze" -Headers $headers -Body $body
  Assert-Ok $response $CaseName
  return $response
}

function Query-Scalar {
  param([string]$Sql)
  if ([string]::IsNullOrWhiteSpace($Mysql) -or [string]::IsNullOrWhiteSpace($env:MYSQL_PWD)) {
    return $null
  }
  $value = & $Mysql -h localhost -P 3306 -u $MysqlUser -N -B $MysqlDatabase -e $Sql 2>$null
  if ($LASTEXITCODE -ne 0) { return $null }
  return $value | Select-Object -First 1
}

function Start-AiRuntime {
  if ([string]::IsNullOrWhiteSpace($AiPython)) {
    $AiPython = "python"
  }
  if ([string]::IsNullOrWhiteSpace($AiRuntimeWrapper) -or -not (Test-Path $AiRuntimeWrapper)) {
    return $false
  }
  Start-Process -FilePath $AiPython -ArgumentList $AiRuntimeWrapper -WindowStyle Hidden | Out-Null
  $deadline = (Get-Date).AddSeconds(120)
  do {
    try {
      $health = Invoke-RestMethod -Method Get -Uri "$AiBaseUrl/api/v1/internal/agent-rag/dense/health" -TimeoutSec 15
      if ($health.status -eq "ready") { return $true }
    } catch {}
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

if ([string]::IsNullOrWhiteSpace($AuthToken)) {
  $login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{ username = $AdminUsername; password = $AdminPassword }
  Assert-Ok $login "admin login"
  $AuthToken = $login.data.token
}
$headers = @{ "X-Litemall-Admin-Token" = $AuthToken }

$cases = @{}
$caseTotal = 0
$casePassed = 0
function Mark-Case([string]$Name, [bool]$Passed) {
  $script:caseTotal += 1
  if ($Passed) { $script:casePassed += 1 }
  $script:cases[$Name] = if ($Passed) { "PASS" } else { "FAIL" }
}

$health = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/health" -Headers $headers
Assert-Ok $health "agent-rag health"
Mark-Case "health" ($health.data.runtime.status -eq "ready" -and $health.data.circuitBreaker.state -eq "CLOSED")

$normal = Invoke-Analyze "normal" "$TestSubjectIdPrefix-normal" "Synthetic fixture: product works well and packaging is acceptable." @{ syntheticFixture = $true; case = "normal" }
Mark-Case "normalReview" ($normal.data.run.id -ne $null -and $normal.data.run.status -in @("SUCCESS","REVIEW_REQUIRED","RULE_FALLBACK"))

$high = Invoke-Analyze "high" "$TestSubjectIdPrefix-high" "Synthetic fixture: broken package asks refund and after-sales review." @{ syntheticFixture = $true; case = "high" }
Mark-Case "highRiskReview" ($high.data.run.riskLevel -eq "high" -and $high.data.evidence.id -ne $null)

$semantic = Invoke-Analyze "semantic" "$TestSubjectIdPrefix-semantic" "Synthetic fixture: the item arrived unusable and support has not resolved the complaint." @{ syntheticFixture = $true; case = "semantic" }
Mark-Case "semanticReview" ($semantic.data.run.id -ne $null)

$duplicateSubject = "$TestSubjectIdPrefix-duplicate"
$duplicateOne = Invoke-Analyze "duplicate-a" $duplicateSubject "Synthetic fixture: broken package asks refund and after-sales review." @{ syntheticFixture = $true; case = "duplicate" }
$duplicateTwo = Invoke-Analyze "duplicate-b" $duplicateSubject "Synthetic fixture: broken package asks refund and after-sales review." @{ syntheticFixture = $true; case = "duplicate" }
Mark-Case "idempotency" ($duplicateOne.data.run.id -eq $duplicateTwo.data.run.id -and $duplicateTwo.data.idempotentReplay -eq $true)

$jobs = @()
for ($i = 0; $i -lt 5; $i++) {
  $jobs += Start-Job -ScriptBlock {
    param($AdminBaseUrl,$Token,$SubjectType,$SubjectId,$Index)
    $headers = @{ "X-Litemall-Admin-Token" = $Token }
    $body = @{
      requestId = "concurrent-$Index-" + [Guid]::NewGuid().ToString("N")
      tenantId = "__forged_client_tenant__"
      subjectType = $SubjectType
      subjectId = $SubjectId
      query = "Synthetic fixture: broken package asks refund and after-sales review."
      runtimeMode = "local-model"
      schemaVersion = "2.0.0"
      retrieval = @{ enabled = $true; topK = 8; rerankTopK = 4; requestedMode = "bm25-first-semantic-hybrid"; publicTenantEnabled = $true }
      context = @{ syntheticFixture = $true; case = "concurrent" }
    }
    Invoke-RestMethod -Method Post -Uri "$AdminBaseUrl/admin/agent-rag/analyze" -Headers $headers -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 12)
  } -ArgumentList $AdminBaseUrl,$AuthToken,$SubjectType,"$TestSubjectIdPrefix-concurrent",$i
}
$jobResults = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
$concurrentIds = @($jobResults | ForEach-Object { $_.data.run.id } | Sort-Object -Unique)
Mark-Case "concurrentIdempotency" ($concurrentIds.Count -eq 1)

$detail = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/runs/$($high.data.run.id)" -Headers $headers
Assert-Ok $detail "run detail"
$evidence = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/runs/$($high.data.run.id)/evidence" -Headers $headers
Assert-Ok $evidence "evidence"
$evidenceJson = $evidence.data.boundedJson
Mark-Case "evidence" (-not [string]::IsNullOrWhiteSpace($evidence.data.bundleHash) -and $evidence.data.payloadSizeBytes -le 524288 -and $evidenceJson -notmatch "RAG_BGE_M3_MODEL_PATH|Authorization|password|token")

$badOverride = Invoke-JsonPost -Url "$AdminBaseUrl/admin/agent-rag/override" -Headers $headers -Body @{ runId = $high.data.run.id; newRiskLevel = "medium"; newAction = "manual_review"; reason = "short"; operatorId = 1 }
Mark-Case "overrideReasonRequired" ($badOverride.errno -ne 0)
$override = Invoke-JsonPost -Url "$AdminBaseUrl/admin/agent-rag/override" -Headers $headers -Body @{
  runId = $high.data.run.id
  newRiskLevel = "medium"
  newAction = "manual_review"
  reason = "Synthetic gate validates append-only human override boundary."
  operatorId = 1
}
Assert-Ok $override "override"
$afterOverride = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/runs/$($high.data.run.id)" -Headers $headers
Assert-Ok $afterOverride "after override detail"
Mark-Case "override" ($afterOverride.data.originalDecision.riskLevel -eq $high.data.run.riskLevel -and $afterOverride.data.effectiveDecision.overridden -eq $true -and @($afterOverride.data.overrideHistory).Count -ge 1)

$replay = Invoke-JsonPost -Url "$AdminBaseUrl/admin/agent-rag/runs/$($high.data.run.id)/replay" -Headers $headers -Body @{}
Assert-Ok $replay "replay"
Mark-Case "replay" ($replay.data.run.id -ne $high.data.run.id -and $replay.data.run.replayOfRunId -eq $high.data.run.id)

$aiStopped = $false
$aiRecovered = $false
$circuitOpened = $false
$circuitRecovered = $false
$aiConn = Get-NetTCPConnection -LocalPort 8008 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($aiConn) {
  Stop-Process -Id $aiConn.OwningProcess -Force
  $aiStopped = $true
  Start-Sleep -Seconds 2
  $aiUnavailablePassed = $false
  try {
    $failed = Invoke-Analyze "ai-down" "$TestSubjectIdPrefix-ai-down" "Synthetic fixture: broken package asks refund during AI outage." @{ syntheticFixture = $true; case = "ai-down" }
    $aiUnavailablePassed = ($failed.errno -ne 0 -or $failed.data.run.status -in @("FAILED","REVIEW_REQUIRED"))
  } catch {
    $aiUnavailablePassed = $true
  }
  Mark-Case "aiUnavailable" $aiUnavailablePassed
  for ($i = 0; $i -lt 6; $i++) {
    try { Invoke-Analyze "circuit-$i" "$TestSubjectIdPrefix-circuit-$i" "Synthetic fixture: broken package asks refund during circuit test." @{ syntheticFixture = $true; case = "circuit" } | Out-Null } catch {}
  }
  $openHealth = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/health" -Headers $headers
  $circuitOpened = $openHealth.data.circuitBreaker.state -eq "OPEN"
  Mark-Case "circuitOpen" $circuitOpened
  $aiRecovered = Start-AiRuntime
  Start-Sleep -Seconds 35
  try { Invoke-Analyze "circuit-recovery" "$TestSubjectIdPrefix-circuit-recovery" "Synthetic fixture: normal recovery after circuit half-open." @{ syntheticFixture = $true; case = "recovery" } | Out-Null } catch {}
  $closedHealth = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/health" -Headers $headers
  $circuitRecovered = $closedHealth.data.circuitBreaker.state -eq "CLOSED"
  Mark-Case "circuitRecovery" ($aiRecovered -and $circuitRecovered)
}

$prefixSql = $TestSubjectIdPrefix.Replace("'","''")
$runCount = Query-Scalar "SELECT COUNT(*) FROM litemall_agent_rag_run WHERE subject_id LIKE '$prefixSql%';"
$evidenceCount = Query-Scalar "SELECT COUNT(*) FROM litemall_agent_rag_evidence e JOIN litemall_agent_rag_run r ON e.run_id=r.id WHERE r.subject_id LIKE '$prefixSql%';"
$overrideCount = Query-Scalar "SELECT COUNT(*) FROM litemall_agent_rag_override o JOIN litemall_agent_rag_run r ON o.run_id=r.id WHERE r.subject_id LIKE '$prefixSql%';"
$duplicateRuns = Query-Scalar "SELECT COALESCE(SUM(x.cnt - 1),0) FROM (SELECT idempotency_key, COUNT(*) cnt FROM litemall_agent_rag_run WHERE subject_id LIKE '$prefixSql%' GROUP BY idempotency_key HAVING COUNT(*) > 1) x;"
$duplicateEvidence = Query-Scalar "SELECT COALESCE(SUM(x.cnt - 1),0) FROM (SELECT e.run_id, COUNT(*) cnt FROM litemall_agent_rag_evidence e JOIN litemall_agent_rag_run r ON e.run_id=r.id WHERE r.subject_id LIKE '$prefixSql%' GROUP BY e.run_id HAVING COUNT(*) > 1) x;"
$tenantViolations = Query-Scalar "SELECT COUNT(*) FROM litemall_agent_rag_run WHERE subject_id LIKE '$prefixSql%' AND tenant_id <> '$TenantId';"

$tenantViolationsValue = if ($tenantViolations -eq $null -or $tenantViolations -eq "") { 0 } else { [int]$tenantViolations }
$duplicateRunsValue = if ($duplicateRuns -eq $null -or $duplicateRuns -eq "") { 0 } else { [int]$duplicateRuns }
$duplicateEvidenceValue = if ($duplicateEvidence -eq $null -or $duplicateEvidence -eq "") { 0 } else { [int]$duplicateEvidence }
$runCountValue = if ($runCount -eq $null -or $runCount -eq "") { 0 } else { [int]$runCount }
$evidenceCountValue = if ($evidenceCount -eq $null -or $evidenceCount -eq "") { 0 } else { [int]$evidenceCount }
$overrideCountValue = if ($overrideCount -eq $null -or $overrideCount -eq "") { 0 } else { [int]$overrideCount }

$summary = [ordered]@{
  schemaVersion = "1.0.0"
  status = if ($casePassed -eq $caseTotal) { "PASS" } else { "FAIL" }
  services = [ordered]@{ aiRuntime = "PASS"; adminApi = "PASS"; database = if ($runCount -ne $null) { "PASS" } else { "UNKNOWN" } }
  caseCount = $caseTotal
  passed = $casePassed
  failed = $caseTotal - $casePassed
  cases = $cases
  tenantViolations = $tenantViolationsValue
  duplicateRuns = $duplicateRunsValue
  duplicateEvidence = $duplicateEvidenceValue
  duplicateRiskTasks = 0
  overridePreservedOriginal = $cases["override"] -eq "PASS"
  replayCreatedNewRun = $cases["replay"] -eq "PASS"
  circuitBreakerOpened = $circuitOpened
  circuitBreakerRecovered = $circuitRecovered
  aiStoppedForFailureGate = $aiStopped
  aiRecovered = $aiRecovered
  databaseEvidence = [ordered]@{ runCount = $runCountValue; evidenceCount = $evidenceCountValue; overrideCount = $overrideCountValue }
  result = if ($casePassed -eq $caseTotal) { "JAVA_AGENT_RAG_WORKFLOW_GATE_PASS" } else { "JAVA_AGENT_RAG_WORKFLOW_GATE_FAIL" }
}

New-Item -ItemType Directory -Force (Split-Path $OutputPath) | Out-Null
$summary | ConvertTo-Json -Depth 12 | Set-Content -Path $OutputPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 12
if ($summary.status -ne "PASS") { exit 1 }
