# v1.6.1.1 Direct VLM Download and Single GPU Gate Report

## Scope

This report covers the PowerShell/.NET acquisition path for Qwen3-VL, local `accelerate` wheel installation, model file verification, and the single-GPU gate used before direct inference.

No release tag was created. No SSL verification bypass, `--trusted-host`, `verify=False`, `flash-attn`, `bitsandbytes`, torch reinstall, or third-party model repack was used.

## Accelerate Wheel

- Method: PyPI JSON metadata plus PowerShell `Invoke-WebRequest`, then local `pip install --no-index --no-deps`.
- Version: `1.14.0`
- Wheel: `accelerate-1.14.0-py3-none-any.whl`
- SHA256 verified: yes
- Install marker: `ACCELERATE_LOCAL_WHEEL_INSTALL_PASS`
- `pip check`: reports an existing `pytest`/`tomli` issue, not an accelerate dependency issue.

Structured evidence: `data/multimodal/audit/accelerate_wheel_install_status.json`.

## Qwen3-VL Direct Download

- Repo: `Qwen/Qwen3-VL-2B-Instruct`
- Method: PowerShell `System.Net.Http.HttpClient` with `ResponseHeadersRead`, streamed writes, `.part` files, Range resume, retry, and atomic rename.
- Target directory: `<model-dir>`
- Git location: outside repository
- Completed files: 10
- Total model directory size: about 4069 MB
- `model.safetensors`: `4,255,140,312` bytes
- `.part` files remaining: none
- Download marker: `QWEN3_VL_DIRECT_DOWNLOAD_PASS`

An earlier short `model.safetensors` was detected by the verifier and the downloader was fixed so incomplete files are not marked complete.

Structured evidence: `data/multimodal/audit/qwen3_vl_direct_download_status.json`.

## Model Verification

Verification script:

```powershell
$env:E_REVIEW_VLM_MODEL_DIR="<model-dir>"
<torchtest-python> .\ai-service\scripts\verify_qwen3_vl_model_files.py
```

Checks passed:

- Required files exist and are non-empty
- No `.part` files
- `config.json`, `tokenizer.json`, and `tokenizer_config.json` parse
- `AutoConfig` loads with `model_type=qwen3_vl`
- `AutoProcessor` loads
- `Qwen3VLForConditionalGeneration` imports
- `safetensors` header is readable

Marker: `VLM_MODEL_READY`.

## Single GPU Gate

Implemented files:

- `ai-service/app/runtime/gpu_gate.py`
- `ai-service/scripts/wait_for_gpu_idle.py`
- `scripts/e-review-wait-for-gpu.ps1`
- `ai-service/tests/test_gpu_gate.py`

Default gate:

- Minimum free memory: `6000 MB`
- Busy utilization: `>20%`
- Idle utilization: `<=10%`
- Stable checks: `3`
- Default wait: infinite unless a timeout is explicitly supplied
- Lock path: `.runtime/gpu-gate/e-review-gpu.lock`

The gate does not terminate other processes. It only reports `GPU_BUSY_WAITING` and waits or times out.

Runtime smoke with a 5-second timeout detected the GPU as busy and returned `GPU_WAIT_TIMEOUT_BLOCKED`. No process was killed.

## Direct Inference Status

Direct smoke now uses the GPU gate before model loading. With a 60-second explicit timeout, the gate did not pass:

- Free memory remained around `5637-5652 MB`
- Minimum required free memory was `6000 MB`
- External GPU process entries were reported by `nvidia-smi`
- Model loading did not start
- `generate` did not execute
- Fallback was not used

Marker: `VLM_DIRECT_INFERENCE_BLOCKED_GPU_WAIT_TIMEOUT`.

## Remaining Blockers

- `VLM_DIRECT_INFERENCE_PASS`: blocked by current GPU gate state
- `VLM_UNLOAD_RELOAD_PASS`: not attempted because direct inference did not pass
- `VLM_PROVIDER_SMOKE_PASS`: not attempted because direct inference did not pass
- `VLM_OBSERVABILITY_PASS`: not attempted because provider smoke did not pass
- External real-world data gates remain blocked by design
