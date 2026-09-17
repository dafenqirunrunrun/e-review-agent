param(
  [string]$Python = "python",
  [string]$Source = "D:\EReviewAgent\data-private\banglishrev\reviews v1.json"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
Push-Location $repoRoot
try {
  & $Python .\ai-service\scripts\ingest_public_review_dataset.py --source $Source
  & $Python .\ai-service\scripts\anonymize_real_reviews.py
  & $Python .\ai-service\scripts\build_realworld_split.py
  exit 0
} finally {
  Pop-Location
}
