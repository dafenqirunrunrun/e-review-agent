# E-Review Agent Final Defense Package

This directory is the curated delivery entry for the graduation defense version.

Recommended version:

- Branch: `release/v1.3-graduation-defense-readiness`
- Suggested tag: `v1.3-graduation-defense-readiness`
- Main demo path: H5 customer review to AI Agent governance loop

Directory layout:

| Directory | Purpose |
| --- | --- |
| `docs/` | Defense guides, thesis materials, test reports, deployment notes |
| `scripts/` | One-click startup, service checks, demo data reset, final validation scripts |
| `reports/` | Generated validation summaries and browser regression notes |
| `screenshots/` | Reserved for defense screenshots and recording frames |

Before recording or presenting, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-check-all.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-db-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-demo-mode-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-graduation-final-check.ps1
```

System boundary:

- No real payment integration.
- No real logistics integration.
- No real refund integration.
- No mandatory external model API key.
- No external vector database dependency.
- Demo payment and demo shipping are used only for graduation defense flow verification.
