param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }

$roughInternalError = [string]::Concat([char]0x7cfb, [char]0x7edf, [char]0x5185, [char]0x90e8, [char]0x9519, [char]0x8bef)
$garbledChinesePlaceholder = [string]([char]0x951f)
$fileUriText = "file" + "://"
$patterns = @(
  @{ name = "mojibake_replacement"; regex = [regex]::Escape([string]([char]0xfffd)) },
  @{ name = "mojibake_garbled"; regex = [regex]::Escape($garbledChinesePlaceholder) },
  @{ name = "rough_internal_error_text"; regex = [regex]::Escape($roughInternalError) },
  @{ name = "stacktrace_text"; regex = "(?i)stacktrace" },
  @{ name = "user_facing_exception_text"; regex = "Exception in user-facing text" },
  @{ name = "private_user_path"; regex = "C:\\\\Users\\\\" },
  @{ name = "file_uri"; regex = [regex]::Escape($fileUriText) }
)

$files = @()
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-admin\src") -Include *.vue,*.js -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-vue\src") -Include *.vue,*.js -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-admin-api\src\main\java") -Include *.java -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-wx-api\src\main\java") -Include *.java -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "ai-service") -Include *.py -Recurse -File | Where-Object { $_.FullName -notmatch '\\(__pycache__|\.pytest_cache)\\' }

$hits = @()
foreach ($file in $files) {
  $relative = $file.FullName.Replace($projectRoot + "\", "")
  $lines = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -ErrorAction Stop
  for ($i = 0; $i -lt $lines.Count; $i++) {
    foreach ($pattern in $patterns) {
      if ($lines[$i] -match $pattern.regex) {
        if ($pattern.name -eq "stacktrace_text" -and $relative -like "*.java" -and $lines[$i] -match "printStackTrace") {
          continue
        }
        $hits += [ordered]@{
          file = $relative
          line = $i + 1
          issue = $pattern.name
        }
      }
    }
  }
}

if ($hits.Count -gt 0) {
  $hits | ConvertTo-Json -Depth 4 | Write-Host
  throw "error message hygiene check failed"
}

[ordered]@{
  scannedFiles = $files.Count
  result = "ERROR_MESSAGE_CHECK_PASS"
} | ConvertTo-Json -Depth 4
