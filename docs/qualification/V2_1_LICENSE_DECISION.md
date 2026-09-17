# v2.1 License Decision

## Status

```text
LICENSE_REVIEW_REQUIRED
```

## Evidence

The local license audit uses:

- `compliance/license-policy.yml`
- `scripts/compliance/audit_dependency_licenses.py`
- `artifacts/qualification/dependency-license-inventory.json`
- `artifacts/qualification/license-review-summary.json`

The audit remains conservative. Unknown package metadata is not treated as
safe, and this document is not a legal opinion.

## Candidate Requirement

v2.1 candidate eligibility requires:

- denied dependencies = 0
- unknown direct dependencies = 0
- unknown model licenses = 0
- required notices generated
- copyleft impact explicitly reviewed

Those conditions are not fully closed in this run.

## Decision

Keep `RETAIN_FFD05F26_RC_BASELINE`.
