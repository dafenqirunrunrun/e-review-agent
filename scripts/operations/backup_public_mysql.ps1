param(
  [string]$ComposeProject = $env:PUBLIC_COMPOSE_PROJECT,
  [string]$Output = "artifacts/operations/v1.9.0-phase3/public-mysql-backup.sql"
)

if (-not $ComposeProject) {
  throw "PUBLIC_COMPOSE_PROJECT or -ComposeProject is required."
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$target = Join-Path $root $Output
New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null

docker compose -p $ComposeProject -f (Join-Path $root "compose.public.yml") exec -T mysql `
  mysqldump -uroot -pchange_me_for_local_only litemall | Set-Content -Encoding UTF8 $target

Write-Host "PUBLIC_MYSQL_BACKUP_CREATED $target"
