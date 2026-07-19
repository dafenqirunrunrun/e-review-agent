# Public Container Security

Public container security is checked with Trivy in GitHub Actions.

## Scans

- Filesystem scan for the repository using offline dependency resolution to avoid external repository rate limits.
- Image scan for backend, AI service, admin frontend and customer frontend images.
- The blocking baseline scan currently uses Trivy with unfixed vulnerabilities excluded. This is a release gate for fixed/remediable CRITICAL/HIGH findings, not a complete vulnerability audit.
- Informational scans without that boundary may expose additional unfixed upstream vulnerabilities and must be reviewed separately before any production claim.
- SBOM generation in SPDX JSON format.
- Secret scanning remains covered by the separate gitleaks workflow.

## Gate

The gate fails when unexceptioned CRITICAL or HIGH vulnerabilities are found.

The public baseline contains documented temporary CRITICAL/HIGH exceptions. The exception list makes legacy risk visible and auditable; it does not make the runtime secure or production-ready.

When CRITICAL/HIGH exceptions remain, the valid status tokens are:

- `PUBLIC_CONTAINER_RISK_BASELINE_AUDITED`
- `PUBLIC_CONTAINER_EXCEPTIONS_VALIDATED`
- `PUBLIC_RELEASE_SECURITY_BLOCKED`

`PUBLIC_CONTAINER_SECURITY_PASS` is only valid for a future baseline with no CRITICAL findings, no CRITICAL exceptions, no unexceptioned HIGH findings, no expired exceptions and no invalid exception records.
