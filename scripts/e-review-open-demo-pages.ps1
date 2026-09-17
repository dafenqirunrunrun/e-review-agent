param(
  [string]$UserFrontendUrl = "http://localhost:6255",
  [string]$AdminFrontendUrl = "http://localhost:9527"
)

$ErrorActionPreference = "Stop"

foreach ($url in @($UserFrontendUrl, $AdminFrontendUrl)) {
  try {
    $status = (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 15).StatusCode
    if ($status -ne 200) {
      throw "HTTP $status"
    }
    Start-Process $url
  } catch {
    throw "failed to open demo page $url : $($_.Exception.Message)"
  }
}

Write-Host "OPEN_DEMO_PAGES_READY"
