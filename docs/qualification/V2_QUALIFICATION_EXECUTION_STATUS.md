# v2.1 Qualification Execution Status

## Current State

- Starting RC: `ffd05f2611cf2c7996a681fa0343778da73f7e50`
- Current branch: `experiment/v2.1-model-quality-scale`
- Current module: v2.1 reproducibility remediation
- Public repository changes: none
- Push: none
- Tag: none
- Release: none

## Completed

- Independent qualification worktree created at `D:\EReviewAgent\litemall-quality-scale`.
- Qualification branch created from locked RC commit `ffd05f26`.
- RC baseline source archive generated outside the repository.
- RC baseline archive SHA-256 recorded in `docs/qualification/V2_RC_BASELINE_LOCK.md`.
- Offline-only model asset audit script added.
- Offline model asset audit executed and recorded in
  `artifacts/qualification/model-assets-summary.json`.
- Real reranker qualification recorded as blocked by missing local asset.
- Real local LLM qualification recorded as blocked by missing local asset.
- Synthetic knowledge scale generator and qualification runner added.
- 1K, 10K, and 100K synthetic scale qualification executed.
- Multi-process index consistency runner added and executed with two workers.
- Local capacity runner added and executed with a real 30-minute soak.
- Supply-chain runner added and executed.
- Integrated v2.1 qualification gate added.
- Integrated v2.1 qualification gate executed.
- Candidate decision recorded as `RETAIN_FFD05F26_RC_BASELINE`.
- Default FAISS persistence test decoupled from untracked `index.faiss` by
  using a controlled `tmp_path` fixture.
- Provider selection split into a default contract gate and a real runtime gate
  boundary.
- External qualification asset manifest schema, example, verifier, and
  documentation added.
- Asset verifier executed without local manifest and correctly reported asset
  blockers instead of default test failures.

## Blocked Or Not Yet Verified

- Real reranker runtime and quality: blocked by missing `RAG_RERANKER_MODEL_PATH`.
- Real local LLM runtime and quality: blocked by missing `AGENT_LLM_MODEL_PATH`.
- 1K/10K/100K knowledge scale: pass on deterministic synthetic local index.
- 1M knowledge scale: not executed; `MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED`.
- Multi-process index consistency: pass for local two-worker generation switch,
  checksum rejection, and rollback.
- Local capacity and 30-minute soak: observed locally with synthetic workload.
- SBOM and build provenance: generated.
- Vulnerability audit: blocked by unavailable authoritative vulnerability
  database.
- License inventory: generated, but unknown metadata requires review.
- Integrated gate: expected to preserve v2.0 RC because model and supply-chain
  blockers remain.
- Existing v2.0 RC gate in this experimental worktree: failed because
  migration status reported `Checksum mismatch for migration 20260720.01`; RC
  baseline worktree `D:\EReviewAgent\litemall-rc-verify` was not modified.
- Reproducibility remediation still needs clean verification worktree evidence
  after final commit.
- Migration `20260720.01` checksum root cause diagnosed as raw-byte
  CRLF/LF sensitivity; RC and v2.1 SQL Git blobs are identical.
- Migration manifest upgraded to `sha256-canonical-lf-v1` with explicit
  approved legacy raw-byte checksums.
- Migration status now reports `E_REVIEW_DATABASE_MIGRATION_STATUS_PASS`.
- Migration immutability gate reports `E_REVIEW_MIGRATION_IMMUTABILITY_PASS`
  and `E_REVIEW_MIGRATION_CROSS_PLATFORM_CHECKSUM_PASS`.
- License policy, license audit script, third-party notice, vulnerability scan
  bundle exporter, and vulnerability scan result importer added.
- License audit executed and conservatively reports `LICENSE_REVIEW_REQUIRED`.
- Vulnerability scan bundle exported outside the repository. No authoritative
  scan results have been imported, so the status remains
  `VULNERABILITY_DATABASE_UNAVAILABLE`.

## Tests And Evidence

- Model asset audit: executed with offline-only semantics.
- Reranker asset result: `RERANKER_ASSET_BLOCKED`, blocker `ENV_PATH_NOT_SET`.
- LLM asset result: `LLM_ASSET_BLOCKED`, blocker `ENV_PATH_NOT_SET`.
- Python compile check for `audit_local_model_assets.py`: pass.
- Real reranker marker test: `1 skipped, 498 deselected`.
- Real LLM marker test: `0 selected, 499 deselected`; pytest returned non-zero
  because no `real_llm` marker tests are selected in this worktree.
- Scale qualification: `AGENT_RAG_SCALE_1K_PASS`,
  `AGENT_RAG_SCALE_10K_PASS`, `AGENT_RAG_SCALE_100K_PASS`.
- Multi-process index consistency:
  `AGENT_RAG_MULTI_PROCESS_INDEX_CONSISTENCY_PASS`.
- Local capacity: `LOCAL_QUALIFICATION_CAPACITY_OBSERVED` and
  `E_REVIEW_V21_30_MINUTE_SOAK_PASS`.
- Supply chain: `E_REVIEW_V21_SBOM_PASS`,
  `E_REVIEW_V21_BUILD_PROVENANCE_PASS`,
  `VULNERABILITY_DATABASE_UNAVAILABLE`, `LICENSE_REVIEW_REQUIRED`.
- Integrated decision: `RETAIN_FFD05F26_RC_BASELINE`.
- Integrated v2.1 gate: `E_REVIEW_V21_QUALIFICATION_CAMPAIGN_BLOCKED`.
- Python full regression: `485 passed, 12 skipped, 2 failed`. Failures were
  missing local FAISS index material in the new worktree and a provider
  selection gate blocked by unavailable BGE-M3 model assets.
- Targeted reproducibility tests after remediation commit 1:
  `9 passed` for `test_v180_real_retrieval_eval.py`,
  `test_v200_agent_rag_enterprise_maturity.py`, and
  `test_v21_qualification_asset_contract.py`.
- Provider contract gate:
  `AGENT_RAG_PROVIDER_SELECTION_CONTRACT_PASS`,
  `AGENT_RAG_RETRIEVAL_DEFAULT_PASS`, and
  `AGENT_RAG_ENTERPRISE_TARGET_MODE_PASS`.
- Qualification asset verifier without a manifest:
  `QUALIFICATION_BGE_ASSET_BLOCKED`,
  `QUALIFICATION_DENSE_INDEX_ASSET_BLOCKED`,
  `QUALIFICATION_RERANKER_ASSET_BLOCKED`, and
  `QUALIFICATION_LLM_ASSET_BLOCKED`.
- License audit: `LICENSE_REVIEW_REQUIRED`.
- Vulnerability export: `E_REVIEW_VULNERABILITY_SCAN_BUNDLE_EXPORTED`.
- Vulnerability import without scan results:
  `VULNERABILITY_DATABASE_UNAVAILABLE`.
- Python default full regression after remediation:
  `488 passed, 12 skipped, 0 failed`.
- Java `mvn test -DskipTests=false`: pass.
- Java `mvn -DskipTests package`: pass.
- Admin `npm run build:prod`: pass with existing warnings.
- Customer `npm run build:prod`: pass with existing warnings.
- v2.0 RC compatibility gate:
  `AGENT_RAG_V2_RELEASE_CANDIDATE_PASS`, with existing model and production
  boundaries still reported.
- v2.1 reproducibility gate:
  `E_REVIEW_V21_QUALIFICATION_INFRASTRUCTURE_PASS`.
- Java `mvn test -DskipTests=false`: pass.
- Java `mvn -DskipTests package`: pass.
- Admin `npm run build:prod`: pass with existing warnings.
- Customer `npm run build:prod`: pass with existing warnings.
- Existing v2.0 RC gate in this worktree: fail on migration checksum mismatch;
  this was recorded as an experimental-worktree environment issue.
- `git diff --check`: pass with line-ending warnings only.

## Exact Next Action

Commit the final remediation gate evidence, then create a clean verification
worktree from the final HEAD and rerun the lightweight verification gate there.
Do not push, tag, or create a release.
