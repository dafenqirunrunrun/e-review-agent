# Public Container Security

Public container security is checked with Trivy in GitHub Actions.

## Scans

- Filesystem scan for the repository using offline dependency resolution to avoid external repository rate limits.
- Image scan for backend, AI service, admin frontend and customer frontend images.
- SBOM generation in SPDX JSON format.
- Secret scanning remains covered by the separate gitleaks workflow.

## Gate

The gate fails when CRITICAL or HIGH vulnerabilities are found unless an explicit documented exception exists.

The current public baseline has no pre-approved exception.
