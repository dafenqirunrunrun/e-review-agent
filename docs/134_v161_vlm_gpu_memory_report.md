# v1.6.1 Local VLM GPU Memory Report

## Environment

- Provider: `local_qwen3_vl_transformers`
- Model: `Qwen3-VL-2B-Instruct`
- Model directory: `<external_model_root>/Qwen3-VL-2B-Instruct`
- Device: `cuda`
- dtype: `auto`
- Max images: `4`
- Max pixels: `1048576`
- Lazy/unload strategy: serial lazy load, unload after request

## GPU Snapshot

```json
{
  "cuda_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
  "gpu_memory_total_mb": 8187.5,
  "gpu_memory_allocated_mb": 0.0,
  "gpu_memory_reserved_mb": 0.0
}
```

## Model Files

```json
{
  "exists": true,
  "file_count": 0,
  "total_size_mb": 0.0,
  "has_config": false,
  "has_processor_or_tokenizer": false,
  "has_weight_file": false
}
```

## Current Finding

The configured Qwen3-VL model directory is outside Git as required, but the
local weight files are not available in this environment yet. No real VLM load,
peak memory, inference latency, or unload memory recovery can be claimed.
