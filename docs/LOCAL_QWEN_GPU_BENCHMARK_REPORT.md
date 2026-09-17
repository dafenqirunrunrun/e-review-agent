# Local Qwen GPU Benchmark Report

## Scope

Step 21.3A.1 measures the existing local Qwen3-1.7B model in an isolated CUDA environment. Runtime routing, Safety Gate, datasets, Frozen Gold, and production model loading are unchanged.

## GPU Environment

- GPU: `NVIDIA GeForce RTX 4060 Laptop GPU`; VRAM `8188 MiB` total / `6031 MiB` free at audit.
- Driver: `566.24`; driver CUDA capability `12.7`.
- PyTorch: `2.14.0+cu126`; CUDA runtime `12.6`.
- Actual model device / dtype: `cuda:0` / `bfloat16`.
- Peak allocated / reserved VRAM: `3407.38` / `3434.0` MiB.

## Five Case Probe

GPU P50 `4132.0 ms`, P95 `8794.6 ms`, P99 `9679.72 ms`.
CPU-to-GPU speedup: P50 `12.3824x`, P95 `11.9526x`.
Schema compliance `0.8000`; retries `1`.

## 20 Case Checkpoint

Gate: `FAIL`; coverage: `ambiguous, explicit, hard, hard-negative, implicit, multi-risk, noisy, normal`.

| Metric | Rule | Qwen GPU |
| --- | ---: | ---: |
| Exact Accuracy | 0.2353 | 0.2353 |
| Micro F1 | 0.3333 | 0.2800 |
| Material Safety Errors | 11 | 11 |

## Full Benchmark

Not run because the staged checkpoint did not authorize it.

## Integrity

- Prompt hash: `101D8FAA73E3245720D237AF98031EEDC9EAC054D3E3339C559864DC5EA2CE79` (identical to CPU probe).
- Generation config hash: `1E0D855823AA56074CD8A0473CCF338CEB00E74FBA26C7610051D9C23501D7B3` (identical to CPU probe).
- Frozen Gold not executed; SHA `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.
- External model/API calls: `0`.
- Runtime services before: `{"8008": {"available": true, "httpStatus": 200}, "8083": {"available": true, "httpStatus": 200}, "9527": {"available": true, "httpStatus": 200}}`.
- Runtime services after: `{"8008": {"available": true, "httpStatus": 200}, "8083": {"available": true, "httpStatus": 200}, "9527": {"available": true, "httpStatus": 200}}`.

## Gates

- `gpuEnvironmentGate` = `PASS`
- `gpuPytorchGate` = `PASS`
- `gpuModelLoadGate` = `PASS`
- `gpuLatencyGate` = `PASS`
- `gpuSchemaGate` = `PASS`
- `localQwen20CaseQualityGate` = `FAIL`
- `localQwen100CaseBenchmarkGate` = `NOT_RUN_CHECKPOINT_FAILED`
- `runtimeServicesGate` = `PASS`
- `step21_3a_1Gate` = `FAIL_LOCAL_QWEN_QUALITY`

## Recommendation

`QWEN_1_7B_CAPACITY_INSUFFICIENT`
