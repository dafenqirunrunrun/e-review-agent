# v2.1 Software Supply Chain Qualification

## Scope

This module generates lightweight local SBOM, dependency license inventory, and
build provenance artifacts for the v2.1 qualification branch.

## Runner

Added:

```text
ai-service/scripts/qualification/run_supply_chain_qualification.py
```

## Generated Artifacts

SBOM files:

```text
artifacts/sbom/java.cdx.json
artifacts/sbom/python.cdx.json
artifacts/sbom/admin.cdx.json
artifacts/sbom/customer.cdx.json
```

Qualification artifacts:

```text
artifacts/qualification/dependency-license-inventory.json
artifacts/qualification/build-provenance.json
artifacts/qualification/supply-chain-summary.json
```

## Result

Generated:

```text
E_REVIEW_V21_SBOM_PASS
E_REVIEW_V21_BUILD_PROVENANCE_PASS
```

Boundaries retained:

```text
VULNERABILITY_DATABASE_UNAVAILABLE
LICENSE_REVIEW_REQUIRED
```

## License Inventory

The automated license inventory found unknown license metadata for 180 component
entries. This does not mean the dependencies are non-compliant; it means the
current local scanner cannot prove compatibility. Human license review is
required before using the qualification branch as a publishable or production
release basis.

## Vulnerability Audit

No authoritative vulnerability database was queried by the offline script, so
the campaign does not claim zero vulnerabilities. The correct status is:

```text
VULNERABILITY_DATABASE_UNAVAILABLE
```

## Boundary

SBOM generation is not the same as a clean security audit. The v2.1 branch keeps
the release boundary until vulnerability and license review are completed with
authoritative tooling.
