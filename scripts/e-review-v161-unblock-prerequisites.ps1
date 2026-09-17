param(
  [string]$Python = "python",
  [string]$RealJson = "",
  [string]$VlmCandidates = "",
  [string]$TextModelDirs = "",
  [string]$TorchPython = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
  $argsList = @(".\ai-service\scripts\v161_unblock_prerequisites.py")
  if ($RealJson) {
    $argsList += @("--real-json", $RealJson)
  }
  if ($VlmCandidates) {
    $argsList += @("--vlm-candidates", $VlmCandidates)
  }
  if ($TextModelDirs) {
    $argsList += @("--text-model-dirs", $TextModelDirs)
  }
  if ($TorchPython) {
    $argsList += @("--torch-python", $TorchPython)
  }
  & $Python @argsList
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
