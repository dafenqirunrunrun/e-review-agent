# v1.6.1 VLM Provider Smoke Report

## Conclusion

`VLM_PROVIDER_SMOKE_BLOCKED`

- Provider marker: `MULTIMODAL_VLM_EVAL_BLOCKED`
- Model available: `False`
- Schema valid: `True`
- Provider: `local_qwen3_vl_transformers`
- Model name: `Qwen3-VL-2B-Instruct`
- Model directory kind: `repo_external_configured_path`
- Device: `cuda`
- dtype: `auto`
- 4-bit: `False`
- Memory strategy: `serial_lazy_load`

## Endpoints

- Status: `/api/v1/vlm/status`
- Smoke test: `/api/v1/vlm/smoke-test`

## Blocking Reasons

- VLM_MODEL_NOT_AVAILABLE
- provider smoke endpoint returned MULTIMODAL_VLM_EVAL_BLOCKED

## Evidence Boundary

This smoke check validates the VLM provider wiring, status endpoint, smoke-test
endpoint, and schema path. It does not claim real VLM inference success while
the local VLM weights and real image smoke samples are unavailable.
