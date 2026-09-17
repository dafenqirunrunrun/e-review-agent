# v2.1 Migration Checksum Diagnosis

## Scope

This document records the diagnosis for migration `20260720.01`, which failed in the v2.1 qualification worktree with `Checksum mismatch for migration 20260720.01`.

## Files

- Manifest: `scripts/database/agent-rag-migrations.json`
- Runner: `scripts/database/e-review-migrate.ps1`
- SQL: `litemall-db/sql/litemall_agent_rag_workflow.sql`

## Root Cause

The RC commit and the v2.1 branch contain the same Git blob for migration `20260720.01`; the migration SQL was not semantically changed. The mismatch came from the previous runner using raw file bytes. On Windows, the checked-out SQL can use CRLF line endings, while the repository blob and the stored database checksum used LF-normalized bytes.

## Evidence

- `20260720.01` manifest Git blob in RC and v2.1: identical
- `20260720.01` SQL Git blob in RC and v2.1: identical
- Worktree raw SHA-256 with CRLF: `b612725cf81bf549132aeb2c5762e8c0c5069dc500230a61cfd265f52ee2c625`
- Canonical LF SHA-256: `a7a54f2a209cb73db1461fae9d7a4554dee904f3467456f203811100bdcc04fb`
- Local schema history checksum for `20260720.01`: `a7a54f2a209cb73db1461fae9d7a4554dee904f3467456f203811100bdcc04fb`

## Remediation

The migration manifest now declares `sha256-canonical-lf-v1` and stores a canonical checksum for each migration. The runner computes canonical LF checksums and accepts only explicitly approved legacy raw-byte checksums when the current canonical checksum still matches the manifest.

The remediation does not update historical database checksums and does not modify old SQL semantics.
