# v2.2 Model Asset Provenance

## Required Assets

| Role | Model | Provider | License | Storage |
| --- | --- | --- | --- | --- |
| Embedding | `BAAI/bge-m3` | `FlagEmbedding` | Recorded from model card / local provenance | Outside Git |
| Reranker | `BAAI/bge-reranker-v2-m3` | `FlagEmbedding.FlagReranker` | `Apache-2.0` | Outside Git |
| LLM | `Qwen/Qwen3-1.7B` | `Transformers AutoModelForCausalLM` | `Apache-2.0` | Outside Git |

## Repository-Safe Evidence

The repository may only store sanitized summaries:

- model id
- provider
- revision hash
- asset fingerprint
- file count and total bytes
- license id
- architecture
- status token

The repository must not store:

- model weights
- tokenizer files
- real absolute model paths
- Hugging Face tokens
- cache directories
- wheelhouse files

## Tooling Added

| File | Purpose |
| --- | --- |
| `scripts/models/download_v22_real_models.py` | Downloads or verifies official reranker and LLM assets outside Git. |
| `scripts/models/verify_v22_real_model_assets.py` | Verifies an external v2.2 asset manifest and writes a sanitized repository summary. |
| `schemas/real-model-chain/v22-real-model-assets.schema.json` | Defines the manifest contract for real v2.2 model assets. |
| `config/examples/v22-real-model-assets.example.json` | Shows the expected manifest structure without real paths. |

## Current Provenance Status

| Asset | Status |
| --- | --- |
| BGE-M3 embedding | Existing external model directory re-fingerprinted and included in the external manifest. |
| Reranker | External v2.2 asset prepared with official revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. |
| Qwen3-1.7B | External v2.2 asset prepared with official revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`. |

## Current Blocking Reason

The Python Hugging Face API remained unstable in this environment, but the OS
HTTPS path returned the official model metadata and revisions. The real model
files and the true absolute asset manifest remain outside Git.
