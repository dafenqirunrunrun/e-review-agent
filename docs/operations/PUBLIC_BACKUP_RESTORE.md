# Public Backup And Restore

The public Docker runtime uses a MySQL container and a named Docker volume. CI verifies a single logical probe-table dump and restore. This is not a full database disaster-recovery test.

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

The success token is `PUBLIC_MYSQL_LOGICAL_PROBE_RESTORE_PASS`.

## Verified Scope

- Scope: `single-probe-table`.
- Clean volume restore: not verified.
- Business tables verified: not verified.
- Disaster recovery verified: not verified.

## Not Verified

- Full MySQL database backup.
- MySQL volume deletion and clean-volume restore.
- Review/comment table restore.
- AI analysis table restore.
- Risk task table restore.
- Operation state restore.
- Production RPO or RTO.
