# v2.2 Execution Status

## Current State

| Item | Value |
| --- | --- |
| Starting HEAD | `efe7187621a3d1214e13824bf1c8c1288736f2ed` |
| Current subphase | Formal runtime integration |
| Development worktree | `D:/EReviewAgent/litemall-v22-real-model-chain` |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU, 8GB class |
| Python environment | `agent-rag-v22-real-models` |
| Push / tag / release | No / no / no |

## Completed

- Created the isolated v2.2 worktree and branch.
- Captured lightweight hardware evidence in `artifacts/real-model-chain/hardware-summary.json`.
- Created an isolated Conda environment from the prior verified environment.
- Added v2.2 model asset schema, example manifest, provisioning script and manifest verifier.
- Added a Python environment readiness gate.
- Diagnosed TLS/proxy behavior and selected a safe recovery path without disabling TLS verification.
- Recovered pinned runtime dependencies in the isolated environment without upgrading Torch.
- Resolved official model revisions through the OS HTTPS path.
- Generated an external real asset manifest outside Git.
- Passed Python environment and model asset gates.
- Passed real BGE-M3 dense regression.
- Passed real FlagEmbedding reranker CUDA smoke.
- Passed real Qwen3 CUDA generate smoke.
- Integrated the reranker formal runtime path with the external v2.2 asset manifest.
- Added formal `real_reranker_runtime` marker coverage through `AgentRagRuntime`.
- Integrated the local Qwen3 formal runtime path with manifest-backed model ID, revision and fingerprint evidence.
- Added v2.2 prompt trust boundary, strict JSON schema parsing, citation validation and grounding checks.
- Added formal `real_llm_runtime` marker coverage through `AgentRagRuntime`.
- Added the shared 8GB GPU model residency manager and wired BGE-M3, reranker and Qwen3 into a single exclusive model slot when enabled.
- Wired the main `AgentRagRuntime` retrieval path to Phase3A dense/hybrid retrieval when configured, with dense evidence fields persisted in Python results.
- Exposed real-model evidence through Java DTOs for dense retrieval, reranking and local Qwen3 LLM runtime fields.
- Persisted lightweight requested/effective provider, retrieval mode, index version, fallback and human-review evidence into Agent-RAG run records.
- Added Admin detail/runtime visibility for sanitized real-model evidence and GPU residency metadata without exposing model paths, prompts or raw outputs.
- Added the Java-to-Python-to-database v2.2 real-model-chain E2E runner.
- Added the v2.2 real-model-chain soak runner with 1800-second duration enforcement and 30-second runtime sampling.
- Added v2.2 reranker, LLM and full-chain readiness gates that read real summaries and remain `BLOCKED` until E2E, quality and soak evidence exists.
- Fixed legacy `taxonomy` knowledge source rows by mapping them to the canonical `public-regulation` source type before Agent-RAG contract validation.
- Added grounded citation repair for local Qwen3 decisions: invalid citation IDs are removed, and the decision is still rejected unless the remaining citations or summary text are grounded in retrieved evidence.
- Passed the Java-to-Python-to-database v2.2 real model chain E2E runner on 2026-07-22 with 24/24 real BGE-M3, BGE reranker and Qwen3 executions. The run used admin-api on `18083` because local `8083` startup encountered a port conflict.

## Blocked

| Blocker | Evidence |
| --- | --- |
| Real reranker quality | Runtime smoke passed; frozen benchmark and quality gate still pending. |
| Real LLM quality | Runtime smoke and formal runtime marker passed; 250-case quality, safety and grounding gates still pending. |
| Real E2E | PASS evidence exists in `artifacts/real-model-chain/v22-real-model-chain-e2e-summary.json`; 8083 remains a local port conflict, so this run used admin-api `18083`. |
| Soak | 1800-second real model chain soak still pending. |
| GPU stability | Residency manager added; real chained soak verification still pending. |
| Java E2E persistence proof | Java DTO and unit-level persistence mapping are covered; Java to Python to database real-model E2E passed once on 2026-07-22. |
| Reranker gate | Gate script exists and currently blocks until frozen benchmark, E2E and soak evidence pass. |
| LLM gate | Gate script exists and currently blocks until 250-case quality, E2E and soak evidence pass. |
| Full-chain gate | Gate script exists and currently blocks until all real-model, regression and clean verification evidence pass. |

## Tests

| Test | Result |
| --- | --- |
| v2.1 asset contract targeted test | `1 passed` |
| Isolated env `pip check` | PASS |
| Python environment gate | `E_REVIEW_V22_PYTHON_ENVIRONMENT_PASS` |
| Model asset gate | `E_REVIEW_V22_REAL_MODEL_ASSETS_PASS` |
| real_dense marker | `8 passed` |
| real reranker smoke | `AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS` |
| real_reranker_runtime marker | `1 passed` |
| reranker regression file | `10 passed` |
| real Qwen3 smoke | `AGENT_RAG_V22_REAL_LLM_RUNTIME_PASS` |
| LLM phase4 regression file | `6 passed, 1 skipped` |
| real_llm_runtime marker | `1 passed` |
| observability / residency regression file | `8 passed` |
| real_reranker_runtime with exclusive residency | `1 passed` |
| real_llm_runtime with exclusive residency | `1 passed` |
| AgentRAG dense wiring regression | `test_v200_agent_rag_phase3a.py`: `7 passed, 4 skipped` |
| real_dense split run | Phase3A `5 passed`; Phase3A1 `1 passed`; Phase3A2 `2 passed` when run sequentially |
| Java Agent-RAG evidence targeted tests | `16 passed` with `mvn -pl litemall-admin-api -am "-Dtest=AgentRagClientContractTest,AgentRagWorkflowPersistenceTest" -DfailIfNoTests=false test` |
| Admin build after evidence UI | `npm run build:prod` passed with existing profile export and asset-size warnings |
| v2.2 readiness gate dry run | Reranker / LLM / full-chain gates returned `BLOCKED` as expected because E2E, quality and soak summaries are not complete |
| Local Qwen3 citation repair and legacy taxonomy regression | `15 passed, 5 skipped` for targeted Phase3A/Phase4 files |
| Full AI service regression | `494 passed, 14 skipped` |
| v2.2 real model chain E2E | `AGENT_RAG_V22_REAL_MODEL_E2E_PASS`; 24/24 BGE, reranker and Qwen3 executions; zero tenant, permission, citation, PII, prompt-injection, duplicate or unhandled-error violations |

## GPU Memory

Observed peak CUDA memory:

- real reranker smoke: about 548 MB
- real Qwen3 smoke: about 3321 MB

## Exact Next Action

Run the frozen reranker benchmark, 250-case LLM quality evaluation and the
1800-second soak. Do not close
`REAL_LLM_QUALITY_NOT_VERIFIED` until the frozen 250-case quality set, Java E2E
and soak gates pass.
