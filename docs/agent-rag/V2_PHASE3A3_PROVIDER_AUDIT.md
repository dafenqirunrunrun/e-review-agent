# Agent-RAG Phase 3A.3 Provider Audit

## Environment

| Item | Value |
| --- | --- |
| Python | `3.10.0` |
| Torch | `2.5.1+cu121` |
| CUDA available | `true` |
| CUDA version | `12.1` |
| GPU count | `1` |
| FAISS | `1.8.0` |
| Transformers | `5.3.0` |
| Accelerate | `1.14.0` |
| FlagEmbedding | not installed |
| Sentence Transformers | not installed |
| pip check | PASS |

The BGE-M3 model path is supplied by `RAG_BGE_M3_MODEL_PATH`. Documentation and
evidence do not record the full local path.

## Dependency Attempt

The online install attempt was intentionally minimal:

```text
python -m pip install --no-deps FlagEmbedding==1.3.5 sentence-transformers==3.0.1
```

Result:

```text
TLS/SSL EOF while accessing pypi.org
```

Conda install was also attempted:

```text
conda install -n torchtest -c conda-forge flagembedding sentence-transformers -y
```

Result:

```text
CondaSSLError while accessing conda-forge
```

No `--trusted-host`, `verify=False`, global SSL bypass, torch upgrade or
transformers upgrade was used.

## Current Providers

| Provider | Status | Implementation |
| --- | --- | --- |
| Hash | available | deterministic fixture |
| Legacy CLS | available | `AutoTokenizer + AutoModel.last_hidden_state[:,0]` |
| FlagEmbedding | blocked | `PROVIDER_DEPENDENCY_MISSING:FlagEmbedding` |
| Sentence Transformers | blocked | `PROVIDER_DEPENDENCY_MISSING:sentence-transformers` |

## Actual API Signatures

FlagEmbedding and Sentence Transformers signatures could not be inspected
because the packages are not installed. The provider implementations therefore
fail closed until the dependencies are present.

## Dependency Risk

Phase 3A.3 cannot honestly output
`AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER_PASS` until `FlagEmbedding` is installed and
`BGEM3FlagModel.encode(...).dense_vecs` is actually executed.

Offline wheelhouse remediation is required if TLS remains blocked.

## Phase 3A.3.1 Offline Dependency Closure

Phase 3A.3.1 created an isolated validation environment:

```text
torchtest-phase3a3
```

The original `torchtest` environment was not modified. Both environments keep:

```text
torch=2.5.1+cu121
transformers=5.3.0
pip check=PASS
```

The dependency audit script reports:

```text
status=BLOCKED
missing=FlagEmbedding==1.3.5,sentence-transformers==3.0.1
versionMismatches=[]
networkUsed=false
environmentModified=false
```

The wheelhouse verifier reports:

```text
status=BLOCKED
wheelCount=0
torchWheelPresent=false
cudaWheelPresent=false
missingRequired=FlagEmbedding==1.3.5 wheel,sentence-transformers==3.0.1 wheel
```

This keeps the official provider gate blocked. No PASS conclusion is claimed.

## Phase 3A.3.2 Runtime Audit Update

The blocked Phase 3A.3.1 state has been resolved for the official provider path
using an isolated Transformers 4.x validation clone. The original `torchtest`
environment remains unchanged.

Observed compatibility evidence:

- `torchtest-phase3a3` with Transformers 5.3.0: dependency audit PASS, but
  `pip check` reports `sentence-transformers 3.0.1` requires
  `transformers<5.0.0`.
- `FlagEmbedding` on Transformers 5.3.0 fails import because the expected
  Transformers API is no longer present.
- `torchtest-phase3a3-tf4` with Transformers 4.44.2 passes `pip check`,
  provider dependency audit, and real runtime smoke.

Runtime versions in the successful validation clone:

| Package | Version |
| --- | --- |
| Torch | `2.5.1+cu121` |
| CUDA | `12.1`, available |
| FAISS | `1.8.0` |
| Transformers | `4.44.2` |
| FlagEmbedding | `1.3.5` |
| sentence-transformers | `3.0.1` |

Official provider smoke:

```text
providerImpl=flagembedding
providerConformance=official-library
encodeMethod=BGEM3FlagModel.encode.dense_vecs
device=cuda
dtype=float16-effective
dimension=1024
norms~=1.0
status=PASS
```

Reference provider status:

```text
REFERENCE_PROVIDER_COMPATIBILITY_BLOCKED
```

The reference Sentence Transformers path imports successfully, but the local
BGE-M3 asset is not a Sentence Transformers model directory in this environment.
This does not block the selected official FlagEmbedding provider.
