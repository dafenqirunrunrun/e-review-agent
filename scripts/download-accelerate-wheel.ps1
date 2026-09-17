param(
    [string]$Python = "D:\anaconda\envs\torchtest\python.exe",
    [string]$Wheelhouse = ".runtime\wheelhouse"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$StatusDir = Join-Path $Root "data\multimodal\audit"
New-Item -ItemType Directory -Force -Path $StatusDir | Out-Null
$StatusPath = Join-Path $StatusDir "accelerate_wheel_install_status.json"
$WheelhousePath = Join-Path $Root $Wheelhouse
New-Item -ItemType Directory -Force -Path $WheelhousePath | Out-Null

function Write-Status {
    param([hashtable]$Payload)
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -Path $StatusPath -Encoding UTF8
}

function Invoke-ProcessCapture {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $escaped = @()
    foreach ($arg in $Arguments) {
        $escaped += '"' + ($arg -replace '"', '\"') + '"'
    }
    $psi.Arguments = ($escaped -join " ")
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    return @{
        ExitCode = $process.ExitCode
        Output = (($stdout + "`n" + $stderr).Trim())
    }
}

try {
    $pypi = Invoke-RestMethod -Uri "https://pypi.org/pypi/accelerate/json" -TimeoutSec 60
    $version = $pypi.info.version
    $files = @($pypi.releases.$version | Where-Object {
        $_.yanked -eq $false -and
        $_.packagetype -eq "bdist_wheel" -and
        $_.filename -like "accelerate-*-py3-none-any.whl"
    })
    if ($files.Count -lt 1) {
        throw "NO_ACCELERATE_PY3_WHEEL_FOUND_FOR_VERSION_$version"
    }
    $file = $files | Select-Object -First 1
    $wheelPath = Join-Path $WheelhousePath $file.filename
    Invoke-WebRequest -Uri $file.url -OutFile $wheelPath -UseBasicParsing -TimeoutSec 300
    $actualHash = (Get-FileHash $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $expectedHash = [string]$file.digests.sha256
    if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
        throw "SHA256_MISMATCH expected=$expectedHash actual=$actualHash"
    }
    $install = Invoke-ProcessCapture -FilePath $Python -Arguments @("-m", "pip", "install", "--no-index", "--no-deps", $wheelPath)
    if ($install.ExitCode -ne 0) {
        throw "PIP_LOCAL_INSTALL_FAILED $($install.Output)"
    }
    $versionResult = Invoke-ProcessCapture -FilePath $Python -Arguments @("-c", "import accelerate; print(accelerate.__version__)")
    if ($versionResult.ExitCode -ne 0) {
        throw "ACCELERATE_IMPORT_FAILED $($versionResult.Output)"
    }
    $pipCheck = Invoke-ProcessCapture -FilePath $Python -Arguments @("-m", "pip", "check")
    $payload = @{
        marker = "ACCELERATE_LOCAL_WHEEL_INSTALL_PASS"
        package_version = $version
        filename = $file.filename
        url = $file.url
        size = $file.size
        sha256_digest = $expectedHash
        sha256_verified = $true
        wheel_path = $wheelPath
        python = $Python
        install_output = $install.Output
        accelerate_version = $versionResult.Output
        pip_check_exit_code = $pipCheck.ExitCode
        pip_check_output = $pipCheck.Output
    }
    Write-Status $payload
    $payload | ConvertTo-Json -Depth 8
    "ACCELERATE_LOCAL_WHEEL_INSTALL_PASS"
    exit 0
}
catch {
    $payload = @{
        marker = "ACCELERATE_LOCAL_WHEEL_INSTALL_BLOCKED"
        python = $Python
        wheelhouse = $WheelhousePath
        error_type = $_.Exception.GetType().Name
        error_message = $_.Exception.Message
    }
    Write-Status $payload
    $payload | ConvertTo-Json -Depth 8
    "ACCELERATE_LOCAL_WHEEL_INSTALL_BLOCKED"
    exit 1
}
