# Public Critical Zero Plan

This Phase 4A plan targets only public CRITICAL dependency findings. It does not claim full dependency modernization or production readiness.

## Baseline

Source evidence:

- PR: `#28`
- Security run: `29673352460`
- Source commit: `c74fbafb0ec5adea9a32fcdb2d9e48185bf4e445`
- Trivy version: `0.72.0`
- Scan reports: 5

Baseline counts:

- CRITICAL findings: 35
- CRITICAL exceptions: 35
- HIGH findings: 196
- HIGH exceptions: 196
- Unexceptioned CRITICAL: 0
- Unexceptioned HIGH: 0

## Remediation Groups

| Group | Baseline CRITICAL count | Phase 4A action |
|---|---:|---|
| Runtime OS packages | 4 | Refresh Nginx Alpine runtime images from `nginx:1.27-alpine` to a fixed Alpine 3.22 tag. |
| Jackson | 12 | Align Jackson modules through Spring Boot dependency properties. |
| Shiro | 8 | Upgrade Shiro 1.x packages through dependency management. |
| Tomcat | 5 | Override embedded Tomcat to the fixed 9.0.x line. |
| PageHelper | 1 | Upgrade PageHelper starter and core dependency. |
| commons-collections | 1 | Pin the transitive legacy dependency to `3.2.2`. |
| Spring Framework / Boot | 4 | Verify after targeted dependency hardening; if still present, handle as a separate compatibility risk instead of hiding findings. |

## Order

1. Refresh public Nginx runtime images.
2. Harden Java dependency families with controlled dependency management.
3. Remove CRITICAL exceptions after the scan no longer reports CRITICAL findings.
4. Run the Critical-Zero gate against real Trivy JSON.
5. Keep HIGH exceptions visible and tracked under issue #29.

## Boundaries

- `PUBLIC_RELEASE_SECURITY_BLOCKED` remains active while HIGH exceptions remain.
- `PRODUCTION_READY_NOT_CLAIMED` remains active.
- No tag or Release is created.
- This phase does not introduce new business features, model runtime, RAG runtime or UI changes.
- Complete HIGH remediation is deferred to Phase 4B.
