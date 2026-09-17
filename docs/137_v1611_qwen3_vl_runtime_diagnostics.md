# v1.6.1.1 Qwen3-VL Runtime Diagnostics

## Conclusion

`QWEN3_VL_RUNTIME_DIAGNOSTICS_BLOCKED`

This run attempted to unblock local Qwen3-VL inference. It did not produce
`VLM_MODEL_READY`, `VLM_DIRECT_INFERENCE_PASS`, `VLM_PROVIDER_SMOKE_PASS`, or
`VLM_OBSERVABILITY_PASS`.

## Verified Environment

- Python environment: torchtest
- torch: `2.5.1+cu121`
- CUDA version: `12.1`
- CUDA available: `true`
- GPU: `NVIDIA GeForce RTX 4060 Laptop GPU`
- BF16 supported: `true`
- transformers: `5.3.0`
- Qwen3-VL class import: `QWEN3_VL_IMPORT_OK`
- FastAPI available: `true`
- pytest available: `true`
- accelerate available: `false`

## Dependency Blocker

`accelerate` was not installed. Attempts against both PyPI and the Tsinghua
PyPI mirror failed with the same TLS/SSL EOF error:

`TLS/SSL connection has been closed (EOF) (_ssl.c:997)`

No torch, flash-attn, or bitsandbytes installation was attempted.

## Model Download Blocker

- Model id: `Qwen/Qwen3-VL-2B-Instruct`
- Source: official Hugging Face repository
- Local directory: `<external_model_root>/Qwen3-VL-2B-Instruct`
- Directory is outside Git: `true`
- File count: `0`
- Config present: `false`
- Processor/tokenizer present: `false`
- Weight file present: `false`
- Download marker: `VLM_MODEL_DOWNLOAD_BLOCKED_NETWORK`
- Error type: `ConnectError`
- Error message: `TLS/SSL connection has been closed (EOF) (_ssl.c:997)`

## Direct Inference

`qwen3_vl_direct_smoke.py` was executed and stopped correctly before inference:

`VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY`

No fallback result was counted as real VLM inference.

## Smoke And Observability

- Smoke marker: `VLM_PROVIDER_SMOKE_BLOCKED`
- Smoke images: `12`
- real_vlm_inference_count: `0`
- vlm_success_rate: `0.0`
- fallback_rate: `1.0`
- oom_count: `0`
- Observability marker: `VLM_OBSERVABILITY_BLOCKED`

## Next Retry

1. Restore a working HTTPS route for PyPI and official Hugging Face, or use an
   official ModelScope source.
2. Install only `accelerate`; do not reinstall torch.
3. Download `Qwen/Qwen3-VL-2B-Instruct` into the repository-external model
   directory.
4. Rerun `qwen3_vl_direct_smoke.py`.
5. Rerun `e-review-local-vlm-smoke.ps1` with the torchtest Python.

The final v1.6.1 gate remains blocked because real external text and real
multimodal evaluation data are still unavailable.
