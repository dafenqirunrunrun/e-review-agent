# Public Backup And Restore

The public Docker runtime uses a MySQL container and a named Docker volume. Backup and restore are verified in CI with a probe table.

## PowerShell

```powershell
$env:PUBLIC_COMPOSE_PROJECT="ereview-public-local"
.\scripts\operations\backup_public_mysql.ps1
.\scripts\operations\restore_public_mysql.ps1
```

## Bash

```bash
export PUBLIC_COMPOSE_PROJECT=ereview-public-local
bash scripts/operations/backup_public_mysql.sh
bash scripts/operations/restore_public_mysql.sh
```

## CI Evidence

`scripts/ci/public_backup_restore_smoke.py` creates a probe row, dumps it, deletes it, restores the dump and verifies the marker returns.
