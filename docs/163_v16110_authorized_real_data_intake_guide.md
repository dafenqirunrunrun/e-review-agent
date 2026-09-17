# V1.6.1.10 Authorized Real Data Intake Guide

This guide defines the evidence required before any private or third-party real-world data can be promoted beyond an internal pilot.

## Required Authorization Fields

- `source_name`: dataset or enterprise data source name.
- `data_owner`: person or organization that controls the data rights.
- `authorization_basis`: contract, license, internal ownership, research approval, or equivalent basis.
- `authorization_document_reference`: internal reference to the approval document.
- `allowed_internal_evaluation`: whether private internal evaluation is allowed.
- `allowed_external_evaluation`: whether formal external evaluation is allowed.
- `allowed_model_training`: whether SFT, DPO, or other model training is allowed.
- `allowed_redistribution`: whether any sample, derivative, or artifact may be redistributed.
- `allowed_image_use`: whether review images may be used.
- `allowed_retention_period`: permitted retention period and deletion trigger.
- `privacy_responsibility`: owner for privacy review and deletion requests.
- `deletion_requirements`: required deletion, masking, or retention controls.
- `approved_by`: explicit approving person or authority.
- `approved_at`: approval timestamp.

## Gate Rules

Current Amazon and ASAP pilot data remain private internal pilot data only. Technical pilot success does not grant formal external-test, training, redistribution, or commercial rights.

Codex must not fill this template with invented approvals. The template only records future explicit authorization supplied by the user or an authorized data owner.

## Optional Intake Paths

### A. User-Owned Data

Use this path only when the user or enterprise owns the review data and explicitly confirms internal evaluation rights. Training rights must be marked separately. Privacy responsibility and deletion handling must be explicit.

### B. Enterprise Authorized Data

Use this path when an enterprise provides a documented authorization. Record the authorization document ID, permitted scope, retention period, whether images are allowed, and whether model training is allowed.

### C. Explicit-License Public Data

Use this path only when the dataset has a clear license. Record the license name, official license URL, and separate judgments for text use, image use, training, and redistribution.

Status: `AUTHORIZED_REAL_DATA_REQUIRED_FOR_FORMAL_EVALUATION`
