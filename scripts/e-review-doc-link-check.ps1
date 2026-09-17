param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

$files = @()
$readme = Join-Path $Root "README.md"
if (Test-Path $readme) {
  $files += Get-Item $readme
}
$docsDir = Join-Path $Root "docs"
if (Test-Path $docsDir) {
  $files += Get-ChildItem $docsDir -Recurse -File -Filter "*.md"
}
$adminSrc = Join-Path $Root "litemall-admin\src"
if (Test-Path $adminSrc) {
  $files += Get-ChildItem $adminSrc -Recurse -File -Include "*.vue", "*.js"
}
$h5Src = Join-Path $Root "litemall-vue\src"
if (Test-Path $h5Src) {
  $files += Get-ChildItem $h5Src -Recurse -File -Include "*.vue", "*.js"
}

$violations = @()
$linePattern = '(https?://[^\s\)\]<>"]+|file://[^\s\)\]<>"]+|[A-Za-z]:[\\/][^\s\)\]<>"]+)'
foreach ($file in $files) {
  $lines = Get-Content -LiteralPath $file.FullName
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    foreach ($match in [regex]::Matches($line, $linePattern)) {
      $value = $match.Value.TrimEnd('.', ',', ';', '`')
      if ($value -match '^https?://(localhost|127\.0\.0\.1)(:\d+)?') {
        continue
      }
      if ($value -match '^https?://example\.com/') {
        continue
      }
      if ($value -match '^http://www\.w3\.org/') {
        continue
      }
      $violations += [ordered]@{
        file = $file.FullName.Substring($Root.Length + 1)
        line = $i + 1
        value = $value
      }
    }
  }
}

if ($violations.Count -gt 0) {
  [ordered]@{
    result = "FAIL"
    violations = $violations
  } | ConvertTo-Json -Depth 6
  exit 1
}

[ordered]@{
  scannedFiles = $files.Count
  result = "DOC_LINK_CHECK_PASS"
} | ConvertTo-Json -Depth 4
