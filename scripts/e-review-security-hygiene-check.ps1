param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }

$files = @()
$files += Get-Item -LiteralPath (Join-Path $projectRoot "README.md") -ErrorAction SilentlyContinue
$files += Get-ChildItem -Path (Join-Path $projectRoot "docs") -Include *.md -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "scripts") -Include *.ps1 -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "ai-service") -Include *.py -Recurse -File | Where-Object { $_.FullName -notmatch '\\(__pycache__|\.pytest_cache)\\' }
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-admin\src") -Include *.vue,*.js -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-vue\src") -Include *.vue,*.js -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-admin-api\src\main\java") -Include *.java -Recurse -File
$files += Get-ChildItem -Path (Join-Path $projectRoot "litemall-wx-api\src\main\java") -Include *.java -Recurse -File

$claimedIntegrated = -join @([char]0x5df2, [char]0x63a5, [char]0x5165)
$accessExternalMcp = -join @([char]0x63a5, [char]0x5165, [char]0x5916, [char]0x90e8, " MCP ", [char]0x670d, [char]0x52a1)
$externalMcp = -join @([char]0x5916, [char]0x90e8, " MCP")
$realPayment = -join @([char]0x771f, [char]0x5b9e, [char]0x652f, [char]0x4ed8)
$productionSaas = -join @([char]0x751f, [char]0x4ea7, [char]0x7ea7, " SaaS")
$fileUriText = "file" + "://"
$knownPasswordPattern = "cfcs" + "20000731|litemall" + "123456"
$negationPattern = -join @(
  [char]0x4e0d, [char]0x63a5, "|",
  [char]0x672a, [char]0x63a5, "|",
  [char]0x4e0d, [char]0x58f0, [char]0x660e, "|",
  [char]0x4e0d, [char]0x8868, [char]0x793a, "|",
  [char]0x4e0d, [char]0x4ee3, [char]0x8868, "|",
  [char]0x6ca1, [char]0x6709, "|",
  [char]0x4e0d, [char]0x662f, "|",
  [char]0x4e0d, [char]0x8981, [char]0x6c42, "|",
  [char]0x4e0d, [char]0x5f3a, [char]0x5236
)

$rules = @(
  @{ name = "known_local_db_password"; regex = $knownPasswordPattern },
  @{ name = "openai_secret_literal"; regex = "OPENAI_API_KEY\s*=\s*sk-|sk-[A-Za-z0-9]{20,}" },
  @{ name = "private_user_path"; regex = "C:\\\\Users\\\\" },
  @{ name = "file_uri"; regex = [regex]::Escape($fileUriText) },
  @{ name = "false_qdrant_claim"; regex = [regex]::Escape($claimedIntegrated) + ".{0,12}Qdrant" },
  @{ name = "false_mcp_claim"; regex = [regex]::Escape($claimedIntegrated) + ".{0,12}" + [regex]::Escape($externalMcp) + "|" + [regex]::Escape($accessExternalMcp) },
  @{ name = "false_real_payment_claim"; regex = [regex]::Escape($claimedIntegrated) + ".{0,12}" + [regex]::Escape($realPayment) },
  @{ name = "production_saas_claim"; regex = [regex]::Escape($productionSaas) }
)

function Is-Allowlisted {
  param([string]$RelativePath, [string]$Line, [string]$Issue)
  if ($RelativePath -like "scripts\e-review-security-hygiene-check.ps1") { return $true }
  if ($RelativePath -like "scripts\e-review-error-message-check.ps1" -and $Issue -in @("file_uri", "private_user_path")) { return $true }
  if ($RelativePath -like "scripts\e-review-doc-link-check.ps1" -and $Issue -in @("file_uri")) { return $true }
  if ($RelativePath -like "scripts\e-review-encoding-check.ps1" -and $Issue -in @("private_user_path", "file_uri", "openai_secret_literal")) { return $true }
  if ($RelativePath -like "docs\82_security_hygiene_report.md" -and $Issue -eq "production_saas_claim") { return $true }
  if ($RelativePath -like "docs\ppt_scripts\*" -and $Line -match 'badTerms|C:\\|D:\\|https?://') { return $true }
  if ($Line -match $negationPattern -or $Line -match 'not integrated|does not|not required|No real') { return $true }
  return $false
}

$hits = @()
foreach ($file in $files) {
  if ($null -eq $file) { continue }
  $relative = $file.FullName.Replace($projectRoot + "\", "")
  $lines = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -ErrorAction Stop
  for ($i = 0; $i -lt $lines.Count; $i++) {
    foreach ($rule in $rules) {
      if ($lines[$i] -match $rule.regex) {
        if (-not (Is-Allowlisted -RelativePath $relative -Line $lines[$i] -Issue $rule.name)) {
          $hits += [ordered]@{
            file = $relative
            line = $i + 1
            issue = $rule.name
          }
        }
      }
    }
  }
}

if ($hits.Count -gt 0) {
  $hits | ConvertTo-Json -Depth 4 | Write-Host
  throw "security hygiene check failed"
}

[ordered]@{
  scannedFiles = $files.Count
  result = "SECURITY_HYGIENE_CHECK_PASS"
} | ConvertTo-Json -Depth 4
