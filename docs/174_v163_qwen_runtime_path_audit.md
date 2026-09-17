# V1.6.3 Qwen Runtime Path Audit

Status: `QWEN_RUNTIME_PATH_AUDIT_COMPLETE`

The existing provider uses a class-level runtime cache, so repeated samples in one Python process should not reload the model. However, it does not expose explicit unload, GPU lock counters, or per-stage latency fields. The v1.6.3 runtime budget smoke therefore uses a dedicated `QwenTextRuntimeSession` for auditable single-session execution.

Key findings:
- Model directory ready: `True`
- Existing provider cache: `True`
- Existing provider explicit unload: `False`
- Text path loads Qwen3-VL: `False`

## Runtime Budget Smoke

Status: `QWEN_TEXT_RUNTIME_BUDGET_PASS`

- real_model_inference_count: `4`
- model_load_count: `1`
- tokenizer_load_count: `1`
- generate_call_count: `4`
- gpu_lock_acquire_count: `1`
- schema_valid_rate: `1.0`
- avg_generate_ms: `5309.62`
- p95_generate_ms: `5167.83`
- avg_active_request_ms: `5317.79`
- p95_active_request_ms: `5169.68`
- gpu_peak_memory_mb: `4006.0`
- unload_success: `True`
