param(
    [string]$Stage,
    [int]$MinFreeMemoryMB = 6000,
    [int]$CheckIntervalSeconds = 20,
    [int]$StableChecks = 3,
    [int]$TimeoutSeconds = 0,
    [string]$Python = "D:\anaconda\envs\torchtest\python.exe",
    [string]$GpuGateMode = "auto",
    [int]$MaxWddmTotalUtilization = 60,
    [int]$MaxFreeMemoryDropMB = 256,
    [string]$RequireZeroNumericComputeProcesses = "true",
    [string]$AllowWddmGraphicsActivity = "true"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& $Python ".\ai-service\scripts\wait_for_gpu_idle.py" `
    --stage $Stage `
    --min-free-memory-mb $MinFreeMemoryMB `
    --check-interval-seconds $CheckIntervalSeconds `
    --stable-checks $StableChecks `
    --timeout-seconds $TimeoutSeconds `
    --gpu-gate-mode $GpuGateMode `
    --max-wddm-total-utilization $MaxWddmTotalUtilization `
    --max-free-memory-drop-mb $MaxFreeMemoryDropMB `
    --require-zero-numeric-compute-processes $RequireZeroNumericComputeProcesses `
    --allow-wddm-graphics-activity $AllowWddmGraphicsActivity
exit $LASTEXITCODE
