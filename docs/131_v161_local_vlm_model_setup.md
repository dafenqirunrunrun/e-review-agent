# v1.6.1 Local VLM Model Setup

## Status

`VLM_MODEL_READY` is not claimed in the current workspace.

The preferred model is `Qwen/Qwen3-VL-2B-Instruct`. Metadata checks confirmed
that the preferred Hugging Face repository exists and is not gated, but the
local model directory does not yet contain the required weight files.

## Required Local Path

- Model id: `Qwen/Qwen3-VL-2B-Instruct`
- Local directory: `<external_model_root>/Qwen3-VL-2B-Instruct`
- Repository boundary: outside the Git working tree
- Git policy: model weights and Hugging Face cache must not be committed

## Required Environment Variables

```powershell
$env:E_REVIEW_VLM_PROVIDER="local_qwen3_vl_transformers"
$env:E_REVIEW_VLM_MODEL_DIR="<external_model_root>\Qwen3-VL-2B-Instruct"
$env:E_REVIEW_VLM_DEVICE="cuda"
$env:E_REVIEW_VLM_DTYPE="auto"
$env:E_REVIEW_VLM_MAX_NEW_TOKENS="384"
$env:E_REVIEW_VLM_MAX_IMAGES="4"
$env:E_REVIEW_VLM_MAX_PIXELS="1048576"
$env:E_REVIEW_VLM_MIN_PIXELS="65536"
$env:E_REVIEW_VLM_TIMEOUT_SECONDS="180"
$env:E_REVIEW_VLM_ENABLE_THINKING="false"
$env:E_REVIEW_VLM_LAZY_LOAD="true"
$env:E_REVIEW_VLM_UNLOAD_AFTER_REQUEST="true"
```

## Current Readiness Check

- Preferred model directory exists: yes, but empty
- Config file present: no
- Processor/tokenizer file present: no
- Weight file present: no
- Real Transformers VLM inference executed: no
- Quantization used: no
- BF16/FP16 verified: BF16 supported by the torchtest CUDA environment
- Release tag allowed: no

## Latest Runtime Diagnostics

- Runtime diagnostics marker: `QWEN3_VL_RUNTIME_DIAGNOSTICS_BLOCKED`
- Qwen3-VL class import: `QWEN3_VL_IMPORT_OK`
- CUDA environment: `torch 2.5.1+cu121`, RTX 4060 Laptop GPU, BF16 supported
- Missing dependency: `accelerate`
- Dependency installation blocker: TLS/SSL EOF while accessing PyPI and the Tsinghua PyPI mirror
- Model download blocker: `VLM_MODEL_DOWNLOAD_BLOCKED_NETWORK`
- Direct inference marker: `VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY`

## Next Manual Step

Restore a working HTTPS route or use an official ModelScope source. Then install
only `accelerate`, download the official model snapshot into the external model
directory, and rerun:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-local-vlm-smoke.ps1
```

If the preferred model cannot be obtained, do not silently substitute another
model. Record `PREFERRED_VLM_MODEL_NOT_AVAILABLE` and only then evaluate
`Qwen/Qwen2.5-VL-3B-Instruct` as an explicit fallback.
