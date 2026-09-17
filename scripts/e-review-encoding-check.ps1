param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

$targets = @(
  @{ Path = "README.md"; Include = @("*.md") },
  @{ Path = "docs"; Include = @("*.md", "*.jsonl") },
  @{ Path = "litemall-admin\src"; Include = @("*.vue", "*.js") },
  @{ Path = "litemall-vue\src"; Include = @("*.vue", "*.js") },
  @{ Path = "ai-service"; Include = @("*.py", "*.json") },
  @{ Path = "scripts"; Include = @("*.ps1") }
)

$files = @()
foreach ($target in $targets) {
  $path = Join-Path $Root $target.Path
  if (-not (Test-Path $path)) {
    continue
  }
  if ((Get-Item $path).PSIsContainer) {
    $files += Get-ChildItem $path -Recurse -File -Include $target.Include
  } else {
    $files += Get-Item $path
  }
}

$bomFiles = @()
$violations = @()
$mojibakeMarkers = @(
  [string][char]0x6D93,
  [string][char]0x7E50,
  [string][char]0x935F,
  [string][char]0x93C4,
  [string][char]0x6D94,
  [string][char]0x9411,
  [string][char]0x5A06,
  [string][char]0xFFFD,
  [string][char]0x95B8,
  [string][char]0x95C1,
  [string][char]0x95BA,
  [string][char]0x95BB,
  [string][char]0x6FDE,
  [string][char]0x9227,
  [string][char]0x93AE,
  [string][char]0x93B7,
  [string][char]0x9420,
  [string][char]0x940E
)
$privatePathPattern = 'C:\\Users\\|file://'
$secretPattern = '(?i)(OPENAI_API_KEY\s*=\s*sk-|sk-[A-Za-z0-9]{20,})'

foreach ($file in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $bomFiles += $file.FullName.Substring($Root.Length + 1)
  }

  $text = [System.Text.Encoding]::UTF8.GetString($bytes)
  $lines = $text -split "`r?`n"
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    $hit = $null
    if (($mojibakeMarkers | Where-Object { $line.Contains($_) }).Count -gt 0) {
      $hit = "possible_mojibake"
    } elseif (($file.Name -notin @("e-review-doc-link-check.ps1", "e-review-encoding-check.ps1")) -and $line -match $privatePathPattern) {
      $hit = "private_or_file_path"
    } elseif ($line -match $secretPattern) {
      $hit = "secret_like_text"
    }

    if ($hit) {
      $violations += [ordered]@{
        file = $file.FullName.Substring($Root.Length + 1)
        line = $i + 1
        type = $hit
        sample = if ($line.Length -gt 160) { $line.Substring(0, 160) } else { $line }
      }
    }
  }
}

if ($bomFiles.Count -gt 0 -or $violations.Count -gt 0) {
  [ordered]@{
    result = "FAIL"
    scannedFiles = $files.Count
    BOM_REMAINING = $bomFiles.Count
    bomFiles = $bomFiles
    violations = $violations
  } | ConvertTo-Json -Depth 8
  exit 1
}

[ordered]@{
  scannedFiles = $files.Count
  BOM_REMAINING = 0
  result = "ENCODING_CHECK_PASS"
} | ConvertTo-Json -Depth 4
