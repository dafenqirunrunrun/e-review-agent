param(
  [string]$AuthorizationManifest,
  [string]$InputPath,
  [string]$IntendedUse = "internal_evaluation",
  [string]$SourceId = "unknown",
  [switch]$DryRun = $true,
  [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = "D:\anaconda\envs\torchtest\python.exe"

if ($ValidateOnly) {
  & $Python "$Root\ai-service\scripts\validate_authorization_manifest.py" --manifest $AuthorizationManifest --intended-use $IntendedUse --data-type text
  exit $LASTEXITCODE
}

$args = @(
  "$Root\ai-service\scripts\intake_authorized_dataset.py",
  "--authorization-manifest", $AuthorizationManifest,
  "--input-path", $InputPath,
  "--intended-use", $IntendedUse,
  "--source-id", $SourceId,
  "--data-type", "text"
)

if (-not $DryRun) {
  $args += "--write"
}

& $Python @args
& $Python "$Root\ai-service\scripts\redact_authorized_review_text.py"
& $Python "$Root\ai-service\scripts\audit_authorized_dataset_leakage.py"
& $Python "$Root\ai-service\scripts\audit_authorized_sft_readiness.py"
