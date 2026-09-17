# v2.1 Qualification RC Baseline Lock

## Baseline

- Repository: internal E-Review Agent repository
- RC source branch: `experiment/v2.0-agent-rag-governed-runtime`
- RC commit: `ffd05f2611cf2c7996a681fa0343778da73f7e50`
- RC short commit: `ffd05f26`
- RC verification worktree: `D:\EReviewAgent\litemall-rc-verify`
- Qualification branch: `experiment/v2.1-model-quality-scale`
- Qualification worktree: `D:\EReviewAgent\litemall-quality-scale`

## Locked RC Evidence

The v2.0 release candidate remains locked at `ffd05f26`. This campaign must not
rewrite the RC baseline, amend prior commits, overwrite RC evidence, push, tag,
or publish a release.

Previously verified RC evidence:

- `AGENT_RAG_V2_RELEASE_CANDIDATE_PASS`
- Java default tests: pass
- Java package build: pass
- Python tests: pass
- Admin production build: pass with existing warnings only
- Customer production build: pass with existing warnings only
- Migration: pass
- Backup/restore verification: pass
- Demo seed/run/cleanup: pass
- Safe diagnostics: pass
- Secret scan: pass
- Detached verification worktree clean at `ffd05f26`

## Baseline Source Archive

The baseline source archive was generated outside the Git repository and must
not be committed.

- Archive name: `e-review-agent-ffd05f26-source.zip`
- Archive location class: external qualification artifact directory
- SHA-256: `2AB531DA4B5558B750AF9F75E4DA305EDF7A8D8A9C1FAA067FA5E065B4FC6FDB`

## Boundaries Retained

- `MODEL_RERANKER_NOT_VERIFIED`
- `REAL_LLM_QUALITY_NOT_VERIFIED`
- `MODEL_FINE_TUNING_NOT_VERIFIED`
- `MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED`
- `MULTI_PROCESS_INDEX_CONSISTENCY_NOT_VERIFIED`
- `DISTRIBUTED_VECTOR_DATABASE_NOT_VERIFIED`
- `HIGH_AVAILABILITY_NOT_VERIFIED`
- `PRODUCTION_CONCURRENCY_NOT_VERIFIED`
- `ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED`
- `NO_PUBLIC_REPO_CHANGES`
- `NO_PUSH`
- `NO_TAG`
- `NO_RELEASE`

## Relationship To v2.1 Qualification

`ffd05f26` remains the stable local RC. The
`experiment/v2.1-model-quality-scale` branch is an isolated qualification branch
used to evaluate real model assets, scale, process consistency, local capacity,
and supply-chain evidence. A failure in this branch does not invalidate the
locked v2.0 RC baseline.
