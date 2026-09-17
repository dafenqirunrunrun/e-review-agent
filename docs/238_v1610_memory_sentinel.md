# V1.6.10 Training Memory Sentinel

- warning_free_memory_mb: `300`
- sustained_low_free_memory_mb: `200`
- emergency_free_memory_mb: `128`
- A single low global free-memory sample now records `TRAINING_MEMORY_TRANSIENT_LOW_WARNING` and triggers cleanup/recheck.
- Training still stops for emergency low memory, sustained low memory with reserved growth, external compute, CUDA OOM, GPU lock loss, or post-cleanup phase retention.
