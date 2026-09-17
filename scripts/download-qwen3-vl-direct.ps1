param(
    [string]$ModelDir = "D:\EReviewAgent\models\Qwen3-VL-2B-Instruct",
    [string]$Revision = "main",
    [int]$MaxRetries = 5,
    [int]$ProgressIntervalSeconds = 10,
    [switch]$SmallFilesOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Net.Http

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$StatusDir = Join-Path $Root "data\multimodal\audit"
New-Item -ItemType Directory -Force -Path $StatusDir | Out-Null
$StatusPath = Join-Path $StatusDir "qwen3_vl_direct_download_status.json"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

$RepoId = "Qwen/Qwen3-VL-2B-Instruct"
$BaseUrl = "https://huggingface.co/$RepoId/resolve/$Revision/"
$Files = @(
    "config.json",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt",
    "chat_template.json",
    "generation_config.json",
    "video_preprocessor_config.json",
    "model.safetensors"
)
if ($SmallFilesOnly) {
    $Files = $Files | Where-Object { $_ -ne "model.safetensors" }
}

function Write-DownloadStatus {
    param(
        [string]$Status,
        [string]$ErrorCategory = "",
        [string]$ErrorSummary = "",
        [int]$RetryCount = 0
    )
    $completed = @()
    $partial = @()
    $bytes = 0
    foreach ($name in $Files) {
        $path = Join-Path $ModelDir $name
        $part = "$path.part"
        if (Test-Path $path) {
            $item = Get-Item $path
            $completed += @{ filename = $name; bytes = $item.Length }
            $bytes += $item.Length
        }
        if (Test-Path $part) {
            $item = Get-Item $part
            $partial += @{ filename = $name; bytes = $item.Length }
            $bytes += $item.Length
        }
    }
    $payload = @{
        marker = if ($Status -eq "PASS") { "QWEN3_VL_DIRECT_DOWNLOAD_PASS" } elseif ($Status -eq "PARTIAL") { "QWEN3_VL_DIRECT_DOWNLOAD_PARTIAL" } else { "QWEN3_VL_DIRECT_DOWNLOAD_BLOCKED" }
        repo_id = $RepoId
        requested_revision = $Revision
        resolved_revision = $null
        download_method = "PowerShell System.Net.Http.HttpClient ResponseHeadersRead with Range resume"
        model_dir = $ModelDir
        files_expected = $Files
        files_completed = $completed
        files_partial = $partial
        bytes_downloaded = $bytes
        retry_count = $RetryCount
        started_at = $script:StartedAt
        completed_at = (Get-Date).ToString("o")
        status = $Status
        error_category = $ErrorCategory
        error_summary = $ErrorSummary
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -Path $StatusPath -Encoding UTF8
}

function Get-FreeBytes {
    param([string]$Path)
    $root = [System.IO.Path]::GetPathRoot((Resolve-Path $Path).Path)
    return (Get-PSDrive -Name $root.Substring(0, 1)).Free
}

function New-HttpClient {
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $true
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(30)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd("EReviewAgent-Qwen3VL-DirectDownloader/1.0")
    return $client
}

function Download-OneFile {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Filename
    )
    $target = Join-Path $ModelDir $Filename
    $part = "$target.part"
    if ((Test-Path $target) -and $Filename -eq "model.safetensors" -and ((Get-Item $target).Length -lt 1GB)) {
        if (Test-Path $part) {
            throw "BOTH_TARGET_AND_PART_EXIST_FOR_$Filename"
        }
        Move-Item -LiteralPath $target -Destination $part
        Write-Host "DOWNLOAD_RESUME_INCOMPLETE_TARGET filename=$Filename bytes=$((Get-Item $part).Length)"
    }
    if ((Test-Path $target) -and ((Get-Item $target).Length -gt 0)) {
        Write-Host "DOWNLOAD_SKIP_COMPLETED filename=$Filename bytes=$((Get-Item $target).Length)"
        return 0
    }
    $url = "$BaseUrl$Filename"
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt += 1
        $existing = if (Test-Path $part) { (Get-Item $part).Length } else { 0 }
        $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, $url)
        if ($existing -gt 0) {
            $request.Headers.Range = New-Object System.Net.Http.Headers.RangeHeaderValue($existing, $null)
        }
        try {
            $response = $Client.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) {
                throw "HTTP_STATUS_$([int]$response.StatusCode)"
            }
            $contentLength = $response.Content.Headers.ContentLength
            $expectedTotal = if ($contentLength -ne $null) { $existing + [int64]$contentLength } else { $null }
            $free = Get-FreeBytes -Path $ModelDir
            if ($expectedTotal -ne $null -and $free -lt ([int64]$contentLength + 1024MB)) {
                throw "INSUFFICIENT_DISK_SPACE free=$free required=$([int64]$contentLength + 1024MB)"
            }
            $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
            $fileStream = [System.IO.File]::Open($part, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
            try {
                $buffer = New-Object byte[] (1024 * 1024)
                $lastProgress = Get-Date
                while ($true) {
                    $read = $stream.Read($buffer, 0, $buffer.Length)
                    if ($read -le 0) { break }
                    $fileStream.Write($buffer, 0, $read)
                    $now = Get-Date
                    if (($now - $lastProgress).TotalSeconds -ge $ProgressIntervalSeconds) {
                        $current = (Get-Item $part).Length
                        Write-Host "QWEN3_VL_DOWNLOAD_PROGRESS filename=$Filename bytes=$current expected=$expectedTotal"
                        Write-DownloadStatus -Status "PARTIAL" -RetryCount $attempt
                        $lastProgress = $now
                    }
                }
            }
            finally {
                $fileStream.Dispose()
                $stream.Dispose()
                $response.Dispose()
            }
            if ((Test-Path $part) -and ((Get-Item $part).Length -gt 0)) {
                $actualLength = (Get-Item $part).Length
                if ($expectedTotal -ne $null -and $actualLength -lt $expectedTotal) {
                    throw "INCOMPLETE_DOWNLOAD filename=$Filename actual=$actualLength expected=$expectedTotal"
                }
                if (Test-Path $target) {
                    Remove-Item -LiteralPath $target -Force
                }
                Move-Item -LiteralPath $part -Destination $target
                Write-Host "QWEN3_VL_DOWNLOAD_FILE_PASS filename=$Filename bytes=$((Get-Item $target).Length)"
                return $attempt
            }
            throw "EMPTY_DOWNLOAD_$Filename"
        }
        catch {
            $message = $_.Exception.Message
            Write-Host "QWEN3_VL_DOWNLOAD_RETRY filename=$Filename attempt=$attempt error=$message"
            Write-DownloadStatus -Status "PARTIAL" -ErrorCategory "download_retry" -ErrorSummary $message -RetryCount $attempt
            if ($attempt -ge $MaxRetries) {
                throw
            }
            Start-Sleep -Seconds ([Math]::Min(120, [Math]::Pow(2, $attempt)))
        }
    }
}

$script:StartedAt = (Get-Date).ToString("o")
$client = New-HttpClient
$totalRetries = 0
try {
    foreach ($file in $Files) {
        $totalRetries += Download-OneFile -Client $client -Filename $file
    }
    Write-DownloadStatus -Status "PASS" -RetryCount $totalRetries
    "QWEN3_VL_DIRECT_DOWNLOAD_PASS"
    exit 0
}
catch {
    Write-DownloadStatus -Status "PARTIAL" -ErrorCategory $_.Exception.GetType().Name -ErrorSummary $_.Exception.Message -RetryCount $totalRetries
    "QWEN3_VL_DIRECT_DOWNLOAD_PARTIAL"
    exit 1
}
finally {
    $client.Dispose()
}
