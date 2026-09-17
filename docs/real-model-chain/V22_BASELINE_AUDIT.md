# v2.2 Baseline Audit

## Scope

This audit starts the `v2.2 Real Model Chain Integration` branch from the
previous blocker-closure evidence commit.

## Frozen Baselines

| Baseline | Worktree | Required HEAD | Status |
| --- | --- | --- | --- |
| v2.0 stable RC | `D:/EReviewAgent/litemall` | `ffd05f2611cf2c7996a681fa0343778da73f7e50` | Preserved |
| v2.1 qualification infrastructure | `D:/EReviewAgent/litemall-quality-scale` | `2d160578c381cd701f90cbcf57b4a682959a2988` | Preserved |
| v2.1 blocker closure | `D:/EReviewAgent/litemall-v21-blocker-closure` | `efe7187621a3d1214e13824bf1c8c1288736f2ed` | Preserved |

## v2.2 Worktree

| Item | Value |
| --- | --- |
| Branch | `experiment/v2.2-real-model-chain` |
| Worktree | `D:/EReviewAgent/litemall-v22-real-model-chain` |
| Starting HEAD | `efe7187621a3d1214e13824bf1c8c1288736f2ed` |
| Public repo changes | No |
| Push / tag / release | No / no / no |

## Existing Reusable Components

| Area | Finding |
| --- | --- |
| BM25, dense retrieval, RRF | Already implemented in the Agent-RAG stack and must not be rewritten. |
| BGE-M3 embedding | Existing real embedding path exists from earlier phases; v2.2 keeps it as the embedding provider. |
| Reranker abstraction | `BaseReranker`, deterministic fallback, governed execution, and `LocalModelReranker` already exist. |
| FlagEmbedding hook | `LocalModelReranker` dynamically imports `FlagEmbedding.FlagReranker`. |
| Reranker fallback | Deterministic fallback exists and must remain available for controlled failure paths. |
| Local Qwen abstraction | `local_qwen3_transformers` provider and Agent-RAG LLM decider already exist. |
| Grounding and hard rules | The Agent-RAG contract already has citation-aware decisions and schema validation paths. |

## Gaps Before v2.2

| Gap | Current Status |
| --- | --- |
| Official reranker revision | Not yet resolved because Hugging Face TLS access is blocked in this run. |
| Reranker asset provenance | New tooling added; authoritative real manifest still pending. |
| Real reranker runtime | Not verified in this subphase. |
| Official Qwen3 revision | Not yet resolved because Hugging Face TLS access is blocked in this run. |
| Qwen3 runtime with required transformers version | Blocked until the isolated environment has `transformers>=4.51.0`. |
| Full Java to Python to DB real-model E2E | Not executed in this subphase. |
| 30-minute real-model soak | Not executed in this subphase. |

## Boundary

The following boundaries remain active until real assets, runtime, quality and
soak evidence all pass:

```text
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
NO_PUBLIC_REPO_CHANGES
NO_PUSH
NO_TAG
NO_RELEASE
```
