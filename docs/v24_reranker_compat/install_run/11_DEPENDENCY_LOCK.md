# Dependency Lock

## Lock File

`ai-service/requirements-canonical-v24.lock.txt`

## Canonical Compatibility Matrix

- `torch==2.5.1+cu121`
- `transformers==4.51.3`
- `tokenizers==0.21.1`
- `huggingface-hub==0.30.2`
- `FlagEmbedding==1.3.5`
- `sentence-transformers==3.0.1`
- `accelerate==1.14.0`
- `peft==0.19.1`
- `safetensors==0.7.0`

`ai-service/requirements-rag.txt` now pins `transformers==4.51.3` instead of the previous loose `transformers>=4.51`.

No torch, CUDA, FlagEmbedding, or sentence-transformers package version was changed in repository dependency files.
