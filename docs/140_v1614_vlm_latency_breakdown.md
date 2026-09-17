# v1.6.1.4 VLM Latency Breakdown

## Conclusion

`VLM_PROVIDER_LATENCY_TARGET_NOT_MET`

Correctness passed: 12/12 real Qwen3-VL inference, schema valid rate 1.0,
fallback rate 0, OOM count 0. Runtime session reuse reduced per-image
provider latency to roughly 2.25 seconds, but total wall clock remained above
the 300 second target because the single GPU waited about 453 seconds for WDDM
GPU utilization to become idle.

## Root Cause

The old provider smoke path acquired the GPU lock, loaded `AutoProcessor`,
loaded Qwen3-VL, generated, and unloaded once per image. The new session path
holds one GPU lock, loads the processor/model once, then runs 12 serial real
`generate` calls.

## Key Metrics

| Metric | Value |
| --- | ---: |
| total_samples | 12 |
| real_vlm_inference_count | 12 |
| schema_valid_rate | 1.0 |
| fallback_rate | 0.0 |
| model_load_count | 1 |
| processor_load_count | 1 |
| generate_call_count | 12 |
| unload_count | 1 |
| gpu_lock_acquire_count | 1 |
| avg_generate_ms | 2216.29 |
| p95_generate_ms | 2573.45 |
| avg_end_to_end_ms | 2246.56 |
| p95_end_to_end_ms | 2589.69 |
| total_wall_clock_ms | 496805.52 |
| gpu_peak_memory_mb | 4142.0 |
| repair_used_rate | 1.0 |
| second_generate_count | 0 |

## Timing Boundary

`generate_ms` includes only `model.generate`. Model load, processor load, GPU
wait, image decode/resize, processor encode, transfer, decode, schema repair,
and provider mapping are recorded separately. GPU wait is not counted in
`avg_generate_ms` or `avg_end_to_end_ms`; it is included in total wall clock.
