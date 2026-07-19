#!/usr/bin/env bash
set -euo pipefail

compose_project="${PUBLIC_COMPOSE_PROJECT:-${1:-}}"
input="${2:-artifacts/operations/v1.9.0-phase3/public-mysql-backup.sql}"

if [ -z "$compose_project" ]; then
  echo "PUBLIC_COMPOSE_PROJECT or first argument is required." >&2
  exit 1
fi
if [ ! -f "$input" ]; then
  echo "Backup file not found: $input" >&2
  exit 1
fi

docker compose -p "$compose_project" -f compose.public.yml exec -T mysql \
  sh -c "mysql -uroot -pchange_me_for_local_only litemall" < "$input"
echo "PUBLIC_MYSQL_RESTORE_COMPLETED $input"
