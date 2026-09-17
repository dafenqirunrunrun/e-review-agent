param(
  [string]$SparsePython = $env:E_REVIEW_SPARSE_PYTHON,
  [string]$PrimaryPython = $env:E_REVIEW_PRIMARY_PYTHON,
  [string]$ModelManifest = $env:E_REVIEW_MODEL_MANIFEST,
  [string]$ExternalOutput = $env:E_REVIEW_OUTPUT_MANIFEST
)

if (-not $SparsePython) { throw "E_REVIEW_SPARSE_PYTHON is required" }
if (-not $PrimaryPython) { throw "E_REVIEW_PRIMARY_PYTHON is required" }
if (-not $ModelManifest) { throw "E_REVIEW_MODEL_MANIFEST is required" }

$script = Join-Path $PSScriptRoot "..\..\ai-service\scripts\qualification\run_v23_bge_m3_sparse_isolated_environment_audit.py"
& $SparsePython $script --primary-python $PrimaryPython --model-manifest $ModelManifest --external-output $ExternalOutput
exit $LASTEXITCODE
