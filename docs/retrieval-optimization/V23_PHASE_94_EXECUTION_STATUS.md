# V2.3 Phase 9.4 Execution Status

Status: `BLOCKED_AT_SPARSE_ENVIRONMENT_GATE`

## What Worked

The offline Phase3A.3 wheelhouse was reused to install the locked `FlagEmbedding==1.3.5` and required non-core dependencies without installing or downgrading `torch`, `transformers`, `tokenizers`, `faiss`, or CUDA packages.

With a small compatibility shim for the removed `transformers.utils.import_utils.is_torch_fx_available` symbol, the local `BAAI/bge-m3` model executed real sparse encoding on CUDA:

```text
realSparseExecution = true
cudaUsed = true
fallbackUsed = false
finiteWeights = true
nonEmptyWeights = true
deterministicRepeat = true
scoreType = BGE_M3_LEARNED_SPARSE_DOT_PRODUCT
```

## What Blocked

The environment gate requires `pip check` to pass. It did not pass because the offline locked `sentence-transformers==3.0.1` metadata requires `transformers<5.0.0`, while the current validated project runtime uses `transformers==5.3.0`.

```text
pipCheckPass = false
blockingDependency = sentence-transformers 3.0.1 requires transformers<5.0.0,>=4.34.0
currentTransformers = 5.3.0
```

The project did not downgrade `transformers`, because that would change the already validated Qwen3 and Dense runtime baseline in the shared `torchtest` environment.

## Engineering Decision

Sparse index construction, sparse single-retriever evaluation, three-way calibration, evaluation, and challenge were not run. This preserves the Phase 9.4 rule that Environment, Runtime, and Index gates must pass before quality experiments proceed.

## Resume-Ready Note

Recovered a real BGE-M3 sparse runtime path from an offline verified wheelhouse and proved CUDA sparse lexical-weight execution, but identified a package metadata conflict between legacy FlagEmbedding-era dependencies and the project’s newer Transformers runtime. Blocked the three-way retrieval experiment rather than downgrading core LLM/RAG dependencies, demonstrating reproducibility and dependency-governance discipline.

## Boundaries

```text
STRUCTURED_RETRIEVAL_CONTENT_NOT_QUALIFIED
BGE_M3_SPARSE_ENVIRONMENT_BLOCKED
SPARSE_INDEX_NOT_RUN
THREE_WAY_RETRIEVAL_NOT_RUN
RUNTIME_INTEGRATED = false
NO_PUBLIC_REPO_CHANGES
NO_PUSH
NO_TAG
NO_RELEASE
```
