param(
  [string]$ComposeProject = $env:PUBLIC_COMPOSE_PROJECT,
  [string]$Input = "artifacts/operations/v1.9.0-phase3/public-mysql-backup.sql"
)

if (-not $ComposeProject) {
  throw "PUBLIC_COMPOSE_PROJECT or -ComposeProject is required."
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$source = Join-Path $root $Input
if (-not (Test-Path $source)) {
  throw "Backup file not found: $source"
}

Get-Content -Raw -Encoding UTF8 $source | docker compose -p $ComposeProject -f (Join-Path $root "compose.public.yml") exec -T mysql `
  sh -c "mysql -uroot -pchange_me_for_local_only litemall"

Write-Host "PUBLIC_MYSQL_RESTORE_COMPLETED $source"
