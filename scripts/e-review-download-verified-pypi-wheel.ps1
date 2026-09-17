param(
    [Parameter(Mandatory = $true)]
    [string]$Package,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [string]$PythonExecutable,

    [Parameter(Mandatory = $true)]
    [string]$Wheelhouse,

    [string]$PreferredPlatform = "win_amd64",

    [int]$MaxRetries = 8
)

$ErrorActionPreference = "Stop"

function Write-JsonResult($result) {
    $result | ConvertTo-Json -Depth 10
}

function Get-CompatibleTags {
    param([string]$Python)
    $code = @"
from packaging.tags import sys_tags
for tag in sys_tags():
    print(str(tag))
"@
    $tags = & $Python -c $code
    if ($LASTEXITCODE -ne 0) {
        throw "failed to read Python compatible tags"
    }
    return @($tags)
}

function Test-RequiresPython {
    param(
        [string]$Python,
        [AllowNull()][string]$RequiresPython
    )
    if ([string]::IsNullOrWhiteSpace($RequiresPython)) {
        return $true
    }
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($RequiresPython))
    $code = @"
import base64
import sys
from packaging.specifiers import SpecifierSet
from packaging.version import Version
spec = base64.b64decode('$encoded').decode()
version = Version(chr(46).join(map(str, sys.version_info[:3])))
print(str(version in SpecifierSet(spec)).lower())
"@
    $ok = & $Python -c $code
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    return ($ok -eq "true")
}

function Test-WheelTag {
    param(
        [string]$Filename,
        [string[]]$CompatibleTags,
        [string]$Platform
    )
    if (-not $Filename.EndsWith(".whl")) {
        return $false
    }
    $stem = $Filename.Substring(0, $Filename.Length - 4)
    $parts = $stem.Split("-")
    if ($parts.Count -lt 5) {
        return $false
    }
    $pyTags = $parts[$parts.Count - 3].Split(".")
    $abiTags = $parts[$parts.Count - 2].Split(".")
    $platformTags = $parts[$parts.Count - 1].Split(".")
    if (($platformTags -notcontains $Platform) -and ($platformTags -notcontains "any")) {
        return $false
    }
    foreach ($py in $pyTags) {
        foreach ($abi in $abiTags) {
            foreach ($plat in $platformTags) {
                if ($CompatibleTags -contains "$py-$abi-$plat") {
                    return $true
                }
            }
        }
    }
    return $false
}

function Invoke-OfficialDownload {
    param(
        [string]$Url,
        [string]$Target,
        [int]$Retries
    )
    $methods = @()
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $curlOutput = & curl.exe --silent --show-error --fail --location --retry $Retries --retry-all-errors --retry-delay 5 --connect-timeout 30 --max-time 1800 --output $Target $Url 2>&1
    $curlExitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference
    $methods += @{ method = "curl.exe"; exit_code = $curlExitCode; output = (($curlOutput | Out-String).Trim()) }
    if ($curlExitCode -eq 0 -and (Test-Path -LiteralPath $Target)) {
        return @{ success = $true; method = "curl.exe"; attempts = $methods }
    }

    Remove-Item -LiteralPath $Target -ErrorAction SilentlyContinue
    try {
        Start-BitsTransfer -Source $Url -Destination $Target -ErrorAction Stop
        $methods += @{ method = "Start-BitsTransfer"; exit_code = 0; output = "" }
        if (Test-Path -LiteralPath $Target) {
            return @{ success = $true; method = "Start-BitsTransfer"; attempts = $methods }
        }
    }
    catch {
        $methods += @{ method = "Start-BitsTransfer"; exit_code = 1; output = $_.Exception.GetType().Name }
    }

    Remove-Item -LiteralPath $Target -ErrorAction SilentlyContinue
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Target -UseBasicParsing -TimeoutSec 1800 -ErrorAction Stop
        $methods += @{ method = "Invoke-WebRequest"; exit_code = 0; output = "" }
        if (Test-Path -LiteralPath $Target) {
            return @{ success = $true; method = "Invoke-WebRequest"; attempts = $methods }
        }
    }
    catch {
        $methods += @{ method = "Invoke-WebRequest"; exit_code = 1; output = $_.Exception.GetType().Name }
    }

    return @{ success = $false; method = $null; attempts = $methods }
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Force -Path $Wheelhouse | Out-Null

$jsonUrl = "https://pypi.org/pypi/$Package/$Version/json"
$metadata = Invoke-WebRequest -Uri $jsonUrl -UseBasicParsing -TimeoutSec 120 | ConvertFrom-Json
$tags = Get-CompatibleTags -Python $PythonExecutable
$files = @($metadata.urls)
$candidates = @()
foreach ($file in $files) {
    if ($file.packagetype -ne "bdist_wheel") { continue }
    if ($file.yanked -eq $true) { continue }
    if (-not ($file.url -match "^https://files\.pythonhosted\.org/")) { continue }
    if (-not (Test-RequiresPython -Python $PythonExecutable -RequiresPython $file.requires_python)) { continue }
    if (-not (Test-WheelTag -Filename $file.filename -CompatibleTags $tags -Platform $PreferredPlatform)) { continue }
    $candidates += $file
}

if ($candidates.Count -eq 0) {
    Write-JsonResult @{
        status = "NO_COMPATIBLE_OFFICIAL_WHEEL"
        package = $Package
        version = $Version
        preferred_platform = $PreferredPlatform
        json_domain = "pypi.org"
    }
    exit 2
}

$selected = $candidates | Sort-Object filename | Select-Object -First 1
$target = Join-Path $Wheelhouse $selected.filename
$download = Invoke-OfficialDownload -Url $selected.url -Target $target -Retries $MaxRetries
if (-not $download.success) {
    Write-JsonResult @{
        status = "OFFICIAL_WHEEL_DOWNLOAD_BLOCKED"
        package = $Package
        version = $Version
        filename = $selected.filename
        official_domain = "files.pythonhosted.org"
        download_attempts = $download.attempts
    }
    exit 3
}

$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
$expected = ([string]$selected.digests.sha256).ToLowerInvariant()
if ($actual -ne $expected) {
    Remove-Item -LiteralPath $target -ErrorAction SilentlyContinue
    Write-JsonResult @{
        status = "WHEEL_SHA256_MISMATCH_BLOCKED"
        package = $Package
        version = $Version
        filename = $selected.filename
        expected_sha256 = $expected
        actual_sha256 = $actual
    }
    exit 4
}

Write-JsonResult @{
    status = "WHEEL_SHA256_VERIFIED"
    package = $Package
    version = $Version
    filename = $selected.filename
    sha256 = $actual
    json_domain = "pypi.org"
    official_domain = "files.pythonhosted.org"
    download_method = $download.method
    requires_python = $selected.requires_python
    requires_dist = $selected.requires_dist
    yanked = $selected.yanked
    wheelhouse_label = "<runtime-wheelhouse>"
}
