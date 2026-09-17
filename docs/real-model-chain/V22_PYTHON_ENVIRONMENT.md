# v2.2 Python Environment

## Environment

| Item | Value |
| --- | --- |
| Conda env | `agent-rag-v22-real-models` |
| Source env | `torchtest-phase3a3-tf4` |
| Python executable | External Conda environment |
| Torch | `2.5.1+cu121` |
| CUDA | `12.1` |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |

## Initial Import Check

| Package | Observed |
| --- | --- |
| torch | `2.5.1+cu121` |
| transformers | Initially `4.44.2`, upgraded to `4.51.3` in the isolated v2.2 env |
| accelerate | `1.14.0` |
| faiss | `1.8.0` |
| FlagEmbedding | Importable, version unknown |

## Required Upgrade

Qwen3 requires `transformers>=4.51.0`. The v2.2 target set is:

```text
transformers>=4.51.0,<5
accelerate>=1.0,<2
safetensors>=0.4,<1
huggingface-hub>=0.28,<2
FlagEmbedding>=1.3.5,<2
```

## Current Installation Result

The first online installation attempt failed because PyPI HTTPS/TLS access was
interrupted:

```text
TLS/SSL connection has been closed (EOF)
```

The subsequent diagnosis showed that the OS HTTPS path could access PyPI, while
Python/pip inherited proxy behavior produced TLS EOF. Setting `NO_PROXY=*` for
the current session allowed pip to access PyPI while preserving certificate
verification. No unsafe TLS bypass was used.

Final installed versions:

```text
transformers==4.51.3
tokenizers==0.21.1
huggingface-hub==0.30.2
safetensors==0.5.3
torch==2.5.1+cu121
```

## Gate

`scripts/readiness/run_v22_python_environment_gate.py` records a structured
PASS/BLOCKED result in:

```text
artifacts/real-model-chain/python-environment-gate.json
```

Current result:

```text
E_REVIEW_V22_PYTHON_ENVIRONMENT_PASS
```
