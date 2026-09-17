# v1.6.1.1 Network TLS Diagnostics and Offline VLM Acquisition

## Scope

This report is limited to the two active blockers for the local Qwen3-VL path:

1. HTTPS/TLS download path for Python package/model acquisition.
2. Qwen3-VL model weights and real direct inference.

No release tag was created. No SSL verification bypass, `--trusted-host`, or `verify=False` workaround was used.

## Environment

- Project: `<project-root>`
- Python: `<torchtest-python>`
- Target model: `Qwen/Qwen3-VL-2B-Instruct`
- Target model directory: `<model-dir>`
- Model directory location: outside Git
- GPU baseline: NVIDIA GeForce RTX 4060 Laptop GPU, CUDA available
- Transformers baseline: Qwen3-VL model class import succeeds

## TLS Diagnostic Matrix

The machine has no configured proxy in the checked environment variables and WinHTTP reports direct access.

| Layer | Target | Result | Evidence |
| --- | --- | --- | --- |
| pip config | local config | PASS | No global/site/user pip config file was present. |
| WinHTTP proxy | OS proxy | PASS | Direct access, no proxy server. |
| curl | PyPI accelerate simple index | PASS | HTTP 200. |
| curl | Hugging Face config URL | FAIL | `curl` returned exit 6 DNS resolution failure for Hugging Face. |
| PowerShell `Invoke-WebRequest` | PyPI | PASS | HTTP 200 with `-UseBasicParsing`. |
| PowerShell `Invoke-WebRequest` | Hugging Face config URL | PASS | HTTP 200 with `-UseBasicParsing`. |
| Python `urllib` | PyPI | PASS | HTTP 200. |
| Python `urllib` | Hugging Face config URL | PASS | HTTP 200. |
| `huggingface_hub`/`httpx` | `snapshot_download` | FAIL | TLS/SSL EOF while connecting to official Hugging Face. |
| conda | conda-forge accelerate | FAIL | `CondaSSLError`, ASN1 not enough data. |

Classification:

- OS-level network failure: partial. PowerShell can reach both endpoints, but curl fails DNS resolution for Hugging Face.
- Python-level certificate failure: not confirmed by `urllib`; `urllib` reaches both endpoints successfully.
- pip configuration failure: not indicated; no pip config file was found.
- Hugging Face-only restriction: not a simple full block; config URL works via PowerShell/urllib, but `huggingface_hub` snapshot fails with TLS EOF.
- PyPI-only restriction: not indicated by curl/PowerShell/urllib; installer paths may still hit SSL/TLS failures.

Detailed raw evidence is stored in `data/multimodal/audit/network_tls_diagnostics.json`.

## Conda Accelerate Attempt

Command executed once:

```powershell
conda install -n torchtest -c conda-forge accelerate
```

Result: blocked.

Error summary:

```text
CondaSSLError: HTTPSConnectionPool(host=conda.anaconda.org, port=443): Max retries exceeded with url /conda-forge/win-64/current_repodata.json; SSLError [ASN1: NOT_ENOUGH_DATA] not enough data (_ssl.c:4035)
```

`accelerate` was unavailable during this TLS diagnostic pass. A later PowerShell wheelhouse install resolved this; see `docs/139_v1611_direct_vlm_download_gpu_gate_report.md`.

Structured result: `data/multimodal/audit/conda_accelerate_install_result.json`.

## Offline Accelerate Procedure

Use this only on a trusted networked Windows machine. Do not download or replace `torch`.

Download wheel:

```powershell
py -3.11 -m pip download --no-deps -d <wheelhouse> accelerate
```

Copy the wheelhouse to this machine, then install only the accelerate wheel:

```powershell
<torchtest-python> -m pip install --no-index --no-deps <accelerate-wheel>
<torchtest-python> -m pip check
<torchtest-python> -c "import accelerate; print(accelerate.__version__)"
```

Do not run any command that upgrades or reinstalls `torch`, `flash-attn`, or `bitsandbytes`.

## Offline Qwen3-VL Model Procedure

If `huggingface_hub.snapshot_download` continues to fail on this machine, download the official model on a trusted networked machine:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-VL-2B-Instruct",
    local_dir=r"<portable-dir>\Qwen3-VL-2B-Instruct",
    local_dir_use_symlinks=False,
    resume_download=True,
)
```

Copy the complete directory to:

```text
<model-dir>
```

Then verify it locally:

```powershell
$env:E_REVIEW_VLM_MODEL_DIR="<model-dir>"
<torchtest-python> .\ai-service\scripts\verify_qwen3_vl_model_files.py
```

The verification checks:

- `config.json`
- processor/tokenizer files
- `.safetensors` weights
- weight index files
- `AutoConfig`
- `AutoProcessor`
- `Qwen3VLForConditionalGeneration` class availability

Current result for this TLS diagnostic pass: blocked. A later PowerShell/.NET direct download completed the official model files; see `docs/139_v1611_direct_vlm_download_gpu_gate_report.md`.

## Direct Smoke Loading Policy

`ai-service/scripts/qwen3_vl_direct_smoke.py` now supports two real Transformers loading paths:

- When `accelerate` is available: load with `device_map="auto"`.
- When `accelerate` is unavailable: load without `device_map`, then call `model.to("cuda")`.

The second path is still real single-GPU Transformers inference, not a fallback model and not a rules-based JSON stub.

Direct smoke constraints:

- `local_files_only=True`
- `dtype=torch.bfloat16`
- batch size 1
- single image
- longest image edge capped at 512 pixels
- `max_new_tokens=64`
- `do_sample=False`

Current result for this TLS diagnostic pass was `VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY`. After direct download, model verification reaches `VLM_MODEL_READY`, while direct inference remains blocked by the GPU gate; see `docs/139_v1611_direct_vlm_download_gpu_gate_report.md`.

## Current Gate Status

- `VLM_MODEL_READY`: reached later via PowerShell/.NET direct download
- `VLM_DIRECT_INFERENCE_PASS`: still not reached; GPU gate timed out below the 6000 MB free-memory threshold
- `VLM_PROVIDER_SMOKE_PASS`: not reached
- `VLM_OBSERVABILITY_PASS`: not reached
- `V161_FINAL_GATE`: still blocked

Remaining blocker after the follow-up direct download: real direct inference is waiting on a clean single-GPU gate pass; external real-world data gates also remain blocked by design.
