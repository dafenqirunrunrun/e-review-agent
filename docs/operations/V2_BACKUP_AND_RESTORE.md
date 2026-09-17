# E-Review Agent v2.0 Backup and Restore

## Scope

The default backup captures Agent-RAG operational tables only. It does not export the full litemall business database unless explicitly requested.

Default tables:

- `litemall_agent_rag_schema_history`
- `litemall_agent_rag_run`
- `litemall_agent_rag_evidence`
- `litemall_agent_rag_override`
- `litemall_agent_rag_audit_chain`

## Backup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-backup.ps1
```

Expected token:

```text
E_REVIEW_BACKUP_PASS
```

The script writes:

- SQL dump.
- Manifest JSON.
- SHA-256 checksum.

The default output location is:

```text
%LOCALAPPDATA%\EReviewAgent\runtime\backups\
```

## Verify Restore Package

```powershell
$manifest = Get-ChildItem "$env:LOCALAPPDATA\EReviewAgent\runtime\backups" -Filter "agent-rag-backup-*.manifest.json" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

powershell -ExecutionPolicy Bypass -File scripts\database\e-review-restore.ps1 -ManifestFile $manifest.FullName -VerifyOnly
```

Expected token:

```text
E_REVIEW_RESTORE_VERIFY_PASS
```

## Restore

Restore is intentionally guarded:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-restore.ps1 -ManifestFile <manifest-json> -Restore -ConfirmRestore
```

Only restore into a disposable or explicitly approved database.

## Migration Bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-migrate.ps1 -Status
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-migrate.ps1 -Apply
```

Expected apply token:

```text
E_REVIEW_DATABASE_MIGRATION_PASS
```

The migration history table is:

```text
litemall_agent_rag_schema_history
```

