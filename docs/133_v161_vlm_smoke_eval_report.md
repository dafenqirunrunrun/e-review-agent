# v1.6.1 Local VLM Smoke Evaluation Report

## Conclusion

`VLM_PROVIDER_SMOKE_BLOCKED`

This report covers only synthetic, non-private smoke images generated under
`.runtime/vlm-smoke/`. It is not a real e-commerce multimodal external
evaluation and must not be used as a release gate pass.

## Metrics

| Metric | Value |
| --- | ---: |
| total_samples | 12 |
| real_vlm_inference_count | 0 |
| vlm_success_rate | 0.0 |
| visual_schema_valid_rate | 0 |
| visual_field_complete_rate | 0 |
| fallback_rate | 1 |
| invalid_json_count | 0 |
| repair_used_rate | 0 |
| avg_latency_ms | 3.87 |
| p95_latency_ms | 5.01 |
| gpu_peak_memory_mb | 0.0 |
| oom_count | 0 |
| unload_success_rate | 0 |
| privacy_smoke_detection_rate | 0 |

## Blocking Reasons

- VLM_MODEL_WEIGHTS_NOT_AVAILABLE
- ACCELERATE_NOT_INSTALLED_FOR_TRANSFORMERS_DEVICE_MAP
- NO_REAL_TRANSFORMERS_VLM_INFERENCE_RECORDED

## Evidence Boundary

- Smoke images are synthetic drawings, not real user review images.
- The current provider must not emit `VLM_PROVIDER_SMOKE_PASS` unless real
  Transformers inference succeeds on the smoke set.
- The final v1.6.1 release gate remains blocked until compliant real text and
  multimodal external datasets are available and isolated.
