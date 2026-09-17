# Agent-RAG Phase 3A.3.1 Offline Dependency Closure

## Scope

Phase 3A.3.1 closes the dependency acquisition process for the official BGE-M3
provider path. It does not add Agent, RAG, reranker, model, database, or
business features.

Repository boundary:

```text
D:\EReviewAgent\litemall
```

Offline asset boundary:

```text
D:\EReviewAgent\offline-assets\phase3a3-py310-win_amd64
```

The offline asset directory is outside Git and must not be committed.

## Baseline

| Item | Result |
| --- | --- |
| Base environment | `torchtest` |
| Validation environment | `torchtest-phase3a3` |
| Python | `3.10.0` |
| Torch | `2.5.1+cu121` |
| Transformers | `5.3.0` |
| Base `pip check` | PASS |
| Clone `pip check` | PASS |
| Original environment modified | no |
| Clone created | yes |

The cloned environment keeps the same Torch and Transformers versions as the
base environment.

## Optional Provider Requirements

Optional top-level dependencies are isolated in:

```text
ai-service/requirements/requirements-phase3a3-provider.txt
```

Direct requirements:

```text
FlagEmbedding==1.3.5
sentence-transformers==3.0.1
```

These dependencies are intentionally not added to the default runtime
requirements.

## Current Dependency Audit

The cloned environment was audited with:

```text
ai-service/scripts/dependencies/audit_phase3a3_provider_dependencies.py
```

Current result:

```text
status=BLOCKED
missing=FlagEmbedding==1.3.5,sentence-transformers==3.0.1
versionMismatches=[]
networkUsed=false
environmentModified=false
```

Transfer files generated outside Git:

```text
transfer/phase3a3-top-level.txt
transfer/phase3a3-missing-round1.txt
```

Both currently contain:

```text
FlagEmbedding==1.3.5
sentence-transformers==3.0.1
```

## Wheelhouse Verification

The wheelhouse was verified with:

```text
ai-service/scripts/dependencies/verify_phase3a3_wheelhouse.py
```

Current result:

```text
status=BLOCKED
wheelCount=0
missingRequired=FlagEmbedding==1.3.5 wheel,sentence-transformers==3.0.1 wheel
torchWheelPresent=false
cudaWheelPresent=false
```

The expected top-level source hashes are:

```text
FlagEmbedding-1.3.5.tar.gz
a0714cb8dd03f38e74b84530684c47ad8e0442ab1f4cbb7b0bcd4017dafb9f9c

sentence_transformers-3.0.1-py3-none-any.whl
01050cc4053c49b9f5b78f6980b5a72db3fd3a0abb9169b1792ac83875505ee6
```

## Offline Acquisition Procedure

On a separate Windows x86_64 CPython 3.10 machine with working TLS:

```powershell
$BuilderRoot = "D:\phase3a3-wheelhouse-builder"
New-Item -ItemType Directory -Force "$BuilderRoot\sources" | Out-Null
New-Item -ItemType Directory -Force "$BuilderRoot\wheelhouse" | Out-Null
New-Item -ItemType Directory -Force "$BuilderRoot\manifests" | Out-Null
New-Item -ItemType Directory -Force "$BuilderRoot\requirements" | Out-Null

py -3.10 -m venv "$BuilderRoot\.venv"
$BuilderPython = "$BuilderRoot\.venv\Scripts\python.exe"

& $BuilderPython -m pip install --upgrade pip setuptools wheel packaging
& $BuilderPython -m pip check

& $BuilderPython -m pip download `
  --no-deps `
  --dest "$BuilderRoot\sources" `
  "FlagEmbedding==1.3.5" `
  "sentence-transformers==3.0.1"
```

Verify the downloaded top-level source hashes before building or installing.
If the hash differs, stop and do not install.

Build the FlagEmbedding wheel:

```powershell
& $BuilderPython -m pip wheel `
  --no-deps `
  --no-build-isolation `
  --wheel-dir "$BuilderRoot\wheelhouse" `
  "$BuilderRoot\sources\FlagEmbedding-1.3.5.tar.gz"

Copy-Item `
  "$BuilderRoot\sources\sentence_transformers-3.0.1-py3-none-any.whl" `
  "$BuilderRoot\wheelhouse\"
```

Download any missing dependencies from `phase3a3-missing-round1.txt` with
`--no-deps`, excluding Torch, CUDA, FAISS, and model assets.

Copy only `wheelhouse` and `manifests` back to:

```text
D:\EReviewAgent\offline-assets\phase3a3-py310-win_amd64
```

## Target Installation Procedure

Only after wheelhouse verification passes:

```powershell
$Phase3Python = "D:\anaconda\envs\torchtest-phase3a3\python.exe"
$OfflineRoot = "D:\EReviewAgent\offline-assets\phase3a3-py310-win_amd64"

& $Phase3Python -m pip install `
  --no-index `
  --find-links "$OfflineRoot\wheelhouse" `
  -r "D:\EReviewAgent\litemall\ai-service\requirements\requirements-phase3a3-provider.txt"

& $Phase3Python -m pip check
& $Phase3Python ai-service/scripts/dependencies/audit_phase3a3_provider_dependencies.py `
  --output "$OfflineRoot\reports\provider-dependencies-final.json"
```

Do not install these packages into the original `torchtest` environment during
this phase.

## Official Provider Smoke

After dependencies and local BGE-M3 assets are present, run:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:RAG_DENSE_PROVIDER = "bge-m3"
$env:RAG_BGE_M3_PROVIDER_IMPL = "flagembedding"
$env:RAG_BGE_M3_DEVICE = "cuda"
$env:RAG_BGE_M3_USE_FP16 = "true"
$env:RAG_BGE_M3_BATCH_SIZE = "1"
$env:RAG_BGE_M3_MAX_LENGTH = "512"
$env:RAG_BGE_M3_NORMALIZE = "true"

& $Phase3Python ai-service/scripts/diagnostics/run_phase3a3_official_provider_smoke.py
```

PASS requires real `BGEM3FlagModel.encode(...).dense_vecs` execution and a
1024-dimensional vector. Mock, hash, filename-derived, or fallback embeddings
do not satisfy this gate.

## Current Gate

```text
AGENT_RAG_PHASE3A3_WHEELHOUSE_INTEGRITY=BLOCKED
AGENT_RAG_PHASE3A3_OFFLINE_DEPENDENCY=BLOCKED
AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER=BLOCKED
AGENT_RAG_PHASE3A3=BLOCKED
```

Phase 3B remains blocked.

## Phase 3A.3.2 Offline Installation Update

Phase 3A.3.2 completed the offline wheelhouse installation and runtime
verification in isolated validation environments. The original `torchtest`
environment was not modified.

The first validation clone preserved:

```text
torch=2.5.1+cu121
cudaAvailable=true
faiss=1.8.0
transformers=5.3.0
```

That environment proved the dependency and API incompatibility: `pip check`
reported `sentence-transformers 3.0.1` requires `transformers<5.0.0`, and
`FlagEmbedding` import failed because Transformers 5.3.0 no longer exposes the
API expected by FlagEmbedding 1.3.5.

A second isolated compatibility clone was therefore created for validation:

```text
torchtest-phase3a3-tf4
```

It installed only audited Python wheels from the offline wheelhouse using
`--no-index`; no Torch, CUDA, FAISS, model, or index files were added to the
wheelhouse or Git.

Final validated runtime:

| Item | Result |
| --- | --- |
| Python | `3.10.0` |
| Torch | `2.5.1+cu121` |
| CUDA available | `true` |
| FAISS | `1.8.0` |
| Transformers | `4.44.2` |
| FlagEmbedding | `1.3.5` |
| sentence-transformers | `3.0.1` |
| pip check | PASS |
| dependency audit | PASS |

Wheelhouse summary:

```text
wheelCount=19
torchWheelPresent=false
cudaWheelPresent=false
faissWheelPresent=false
sha256Verification=PASS
```

Current gate:

```text
AGENT_RAG_PHASE3A3_WHEELHOUSE_INTEGRITY=PASS
AGENT_RAG_PHASE3A3_OFFLINE_DEPENDENCY=PASS
AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER=PASS
AGENT_RAG_PHASE3A3=PASS
```

Phase 3B remains out of scope for this phase; no reranker work was started.
