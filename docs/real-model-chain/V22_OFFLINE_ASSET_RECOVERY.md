# v2.2 Offline Asset Recovery

## Purpose

This document records the safe recovery path for v2.2 runtime dependencies and
official model assets. It does not claim production readiness and does not
store wheels, model weights, certificates, tokens, proxy credentials or real
asset manifests in Git.

## Target Environment

| Item | Value |
| --- | --- |
| Conda env | `agent-rag-v22-real-models` |
| Python | CPython 3.10.0, Windows x64 |
| Torch | `2.5.1+cu121` |
| CUDA | `12.1` |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| pip check | PASS |

Raw target environment diagnostics are stored outside Git under:

```text
<repo-external>/offline/v2.2/target-environment
```

## TLS Diagnosis

| Layer | PyPI | Hugging Face |
| --- | --- | --- |
| PowerShell / OS HTTPS | HTTP 200 | HTTP 200 |
| Python requests with inherited environment | Proxy/TLS EOF observed earlier | Proxy/TLS EOF observed earlier |
| Python requests with direct session | PyPI HTTP 200 | Hugging Face connection reset observed |
| pip with default inherited proxy behavior | TLS/SSL EOF |
| pip with `NO_PROXY=*` in current session | PyPI index available |

No unsafe mitigation was used:

- no `--trusted-host`
- no `verify=False`
- no `PYTHONHTTPSVERIFY=0`
- no global certificate verification disablement

## Runtime Dependency Recovery

The v2.2 environment was upgraded in-place from the isolated clone only, not the
previous verified baseline environment. Torch was not upgraded.

Pinned runtime packages:

```text
transformers==4.51.3
tokenizers==0.21.1
huggingface-hub==0.30.2
safetensors==0.5.3
```

Verification after install:

```text
pip check: PASS
transformers: 4.51.3
tokenizers: 0.21.1
huggingface-hub: 0.30.2
safetensors: 0.5.3
torch: 2.5.1+cu121
CUDA: available
```

## Offline Bundle Workflow

The repository now provides these bundle tools:

| File | Purpose |
| --- | --- |
| `config/requirements/v22-real-model-runtime.txt` | Fixed runtime package versions. |
| `scripts/offline/prepare_v22_online_bundle.ps1` | Build wheelhouse and official model bundle on a trusted online Windows machine. |
| `scripts/offline/verify_v22_offline_bundle.py` | Verify bundle schema, hashes, wheel compatibility and model provenance after transfer. |
| `scripts/offline/import_v22_offline_bundle.ps1` | Import verified model assets into the external v2.2 model root. |
| `schemas/offline/v22-offline-bundle.schema.json` | Repository-safe bundle manifest contract. |

Actual wheels, model files and true absolute asset manifests remain outside Git.

## Model Asset Status

| Asset | Status |
| --- | --- |
| BGE-M3 | Existing external asset re-verified and included in the external manifest. |
| bge-reranker-v2-m3 | External asset prepared with official revision and local file fingerprint. |
| Qwen3-1.7B | External asset prepared with official revision and local file fingerprint. |

Resolved official revisions obtained through the OS HTTPS path:

```text
BAAI/bge-reranker-v2-m3: 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e
Qwen/Qwen3-1.7B: 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e
```

## Runtime Smoke Results

| Gate | Result |
| --- | --- |
| Python environment | `E_REVIEW_V22_PYTHON_ENVIRONMENT_PASS` |
| Model assets | `E_REVIEW_V22_REAL_MODEL_ASSETS_PASS` |
| BGE-M3 real dense regression | 8 passed |
| Real reranker smoke | `AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS` |
| Real Qwen3 smoke | `AGENT_RAG_V22_REAL_LLM_RUNTIME_PASS` |

## Remaining Work

These runtime smokes are necessary but not sufficient to close the full v2.2
model quality blockers. The following are still required:

- real reranker benchmark
- real LLM 250-case quality set
- Java to Python to database real model E2E
- 1800-second real model chain soak
- final real model chain gate
