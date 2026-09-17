param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$NodeVersion = "playwright@1.45.3"
)

$ErrorActionPreference = "Stop"
$nodeWork = Join-Path $env:TEMP "e-review-ppt-playwright"
if (-not (Test-Path $nodeWork)) {
  New-Item -ItemType Directory -Force $nodeWork | Out-Null
}

Push-Location $nodeWork
try {
  if (-not (Test-Path (Join-Path $nodeWork "package.json"))) {
    npm init -y | Out-Null
  }
  if (-not (Test-Path (Join-Path $nodeWork "node_modules\playwright"))) {
    npm install $NodeVersion --no-audit --no-fund
  }
} finally {
  Pop-Location
}

$env:NODE_PATH = Join-Path $nodeWork "node_modules"
node (Join-Path $PSScriptRoot "capture_product_screenshots.js") --root $Root
