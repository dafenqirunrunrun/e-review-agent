# E-Review Agent v2.0 Local Troubleshooting

## Doctor Fails

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-doctor.ps1
```

Fix blocked checks first. Warnings for real LLM and model reranker are expected unless optional model assets are configured.

## Port Already Used

Use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-status.ps1
```

The start script will not kill unrelated processes. Use `-KeepExisting` only when the existing process is the intended service.

## Migration Pending

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-migrate.ps1 -Status
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-migrate.ps1 -Apply
```

## Secret Scan Fails

Run:

```powershell
D:\anaconda\envs\torchtest\python.exe scripts\security\scan_repository_secrets.py
```

Review the JSON output under `artifacts\agent-rag\v2.0-rc\repository-secret-scan.json`. Do not hide real secrets with broad allowlists.

## Diagnostics

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\support\e-review-diagnostics.ps1
```

The diagnostics zip is designed to include summaries and redacted status only.

