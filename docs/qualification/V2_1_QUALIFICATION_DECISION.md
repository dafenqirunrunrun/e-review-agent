# v2.1 Qualification Decision

## Decision

```text
V2_1_QUALIFICATION_INFRASTRUCTURE_READY
```

## Rationale

The v2.1 qualification branch has now closed the reproducibility remediation
items for default Python tests, external asset contracts and migration
immutability. It is still not eligible to replace the locked v2.0 RC baseline.

Reasons:

- Real reranker asset is not configured:
  `AGENT_RAG_MODEL_RERANKER_BLOCKED`.
- Real local LLM asset is not configured:
  `AGENT_RAG_REAL_LLM_BLOCKED`.
- Real LLM quality remains:
  `REAL_LLM_QUALITY_NOT_VERIFIED`.
- Vulnerability audit could not query an authoritative vulnerability database:
  `VULNERABILITY_DATABASE_UNAVAILABLE`.
- License inventory contains unknown metadata and requires human review:
  `LICENSE_REVIEW_REQUIRED`.

## Positive Qualification Evidence

- RC baseline preserved.
- Default Python regression now passes without depending on untracked
  `index.faiss` or local model assets.
- Provider selection has a default contract gate and a separate real runtime
  asset boundary.
- External BGE-M3, dense index, reranker and LLM assets are governed by an
  explicit qualification asset manifest.
- Migration `20260720.01` checksum mismatch root cause was confirmed as
  raw-byte CRLF/LF sensitivity; RC and v2.1 SQL blobs match.
- Migration checksums now use `sha256-canonical-lf-v1` with explicit approved
  legacy raw-byte hashes.
- v2.0 RC compatibility gate passes in this v2.1 branch.
- 1K, 10K, and 100K deterministic synthetic knowledge scale passed.
- Two-worker local multi-process index generation switching, checksum rejection,
  and rollback passed.
- Local synthetic capacity matrix executed.
- 30-minute synthetic soak passed.
- SBOM artifacts generated.
- Build provenance generated.

## Boundary

The branch improves qualification infrastructure, but does not claim production
readiness and does not create a new RC. The stable local RC remains:

```text
ffd05f2611cf2c7996a681fa0343778da73f7e50
```

The following boundaries remain:

```text
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
VULNERABILITY_DATABASE_UNAVAILABLE
LICENSE_REVIEW_REQUIRED
MODEL_FINE_TUNING_NOT_VERIFIED
MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED
DISTRIBUTED_VECTOR_DATABASE_NOT_VERIFIED
HIGH_AVAILABILITY_NOT_VERIFIED
PRODUCTION_CONCURRENCY_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
NO_PUBLIC_REPO_CHANGES
NO_PUSH
NO_TAG
NO_RELEASE
```
