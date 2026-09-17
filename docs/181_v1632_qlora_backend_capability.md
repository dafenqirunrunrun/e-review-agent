# V1.6.3.2 QLoRA Backend Capability

Status: `PRIVATE_SYNTHETIC_QLORA_BACKEND_BLOCKED`

- backend_name: `bitsandbytes`
- backend_version: `None`
- four_bit_config_created: `False`
- four_bit_model_load_attempted: `False`
- four_bit_model_load_success: `False`
- quantized_module_count: `0`
- trainable_adapter_only: `False`
- cpu_offload_used: `False`

Reason: `bitsandbytes` is not installed in the isolated `ereview_sft` environment, and the official PyPI dependency dry-run failed with TLS/SSL EOF before metadata resolution. The run did not fall back to plain LoRA or BF16 training.
