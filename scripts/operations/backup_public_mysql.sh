#!/usr/bin/env bash
set -euo pipefail

compose_project="${PUBLIC_COMPOSE_PROJECT:-${1:-}}"
output="${2:-artifacts/operations/v1.9.0-phase3/public-mysql-backup.sql}"

if [ -z "$compose_project" ]; then
  echo "PUBLIC_COMPOSE_PROJECT or first argument is required." >&2
  exit 1
fi

mkdir -p "$(dirname "$output")"
docker compose -p "$compose_project" -f compose.public.yml exec -T mysql \
  mysqldump -uroot -pchange_me_for_local_only litemall > "$output"
echo "PUBLIC_MYSQL_BACKUP_CREATED $output"
