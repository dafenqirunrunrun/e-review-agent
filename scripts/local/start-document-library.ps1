param([switch]$StartFrontend)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$runtime = Join-Path $root '.runtime\document-library'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
if (Get-NetTCPConnection -LocalPort 8083 -State Listen -ErrorAction SilentlyContinue) {
    throw '8083 is in use. Stop the current admin service before starting this service pair.'
}
$python = Join-Path $root 'ai-service\.venv\Scripts\python.exe'
$jar = Join-Path $root 'litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar'
if (!(Test-Path $python) -or !(Test-Path $jar)) { throw 'Build the admin jar and create ai-service/.venv first.' }
# Shared only through the child process environment; never persisted or printed.
$previousToken = $env:DOCUMENT_WORKER_TOKEN
try {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $env:DOCUMENT_WORKER_TOKEN = [Convert]::ToBase64String($bytes)
    $admin = Start-Process java -ArgumentList @('-jar', "`"$jar`"", '--server.port=8083', '--server.address=127.0.0.1', '--spring.servlet.multipart.max-file-size=20MB', '--spring.servlet.multipart.max-request-size=21MB') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'admin.out.log') -RedirectStandardError (Join-Path $runtime 'admin.err.log')
    $worker = Start-Process $python -ArgumentList @('-u', 'scripts/document_job_worker.py') -WorkingDirectory (Join-Path $root 'ai-service') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'worker.out.log') -RedirectStandardError (Join-Path $runtime 'worker.err.log')
    $indexWorker = Start-Process $python -ArgumentList @('-u', 'scripts/document_index_worker.py') -WorkingDirectory (Join-Path $root 'ai-service') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'index-worker.out.log') -RedirectStandardError (Join-Path $runtime 'index-worker.err.log')
    @{ adminPid = $admin.Id; workerPid = $worker.Id; indexWorkerPid = $indexWorker.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'processes.json') -Encoding UTF8
    Write-Host "Started admin PID=$($admin.Id), document worker PID=$($worker.Id), index worker PID=$($indexWorker.Id)."
} finally { $env:DOCUMENT_WORKER_TOKEN = $previousToken }
if ($StartFrontend -and !(Get-NetTCPConnection -LocalPort 9527 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell.exe -ArgumentList @('-NoProfile', '-Command', 'npm run dev') -WorkingDirectory (Join-Path $root 'litemall-admin') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'frontend.out.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log') | Out-Null
}
Write-Host 'File library: http://127.0.0.1:9527/#/ai-workbench/knowledge-quality?tab=files'
