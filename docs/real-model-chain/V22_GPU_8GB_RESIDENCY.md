# v2.2 8GB GPU Residency Manager

## Scope

This document records the first formal shared GPU residency implementation for
the v2.2 real model chain. It is designed for a single 8GB-class CUDA device and
does not claim high-concurrency production readiness.

## Mode

The residency manager is controlled by:

```text
AGENT_MODEL_RESIDENCY_MODE=exclusive-model-slot
```

When enabled, BGE-M3 embedding, bge-reranker-v2-m3 and Qwen3-1.7B share the
same global GPU execution gate and model residency slot.

## Runtime Participants

| Model family | Runtime hook |
| --- | --- |
| BGE-M3 embedding | `embedding:bge-m3` |
| bge-reranker-v2-m3 | `reranker:bge-reranker-v2-m3` |
| Qwen3-1.7B LLM | `llm:qwen3-1.7b` |

The manager records:

```text
resident_model
active_requests
queue_depth
model_load_count
model_eviction_count
model_switch_count
oom_count
cuda_allocated_mb
cuda_reserved_mb
cuda_free_mb
cuda_peak_mb
```

## Eviction

When a new model family enters the exclusive slot and no active request is
running, the previous model family's registered unload callback is invoked.
Unload callbacks release Python object references, move model tensors to CPU
when possible, run garbage collection and clear CUDA cache.

This is stronger than calling `torch.cuda.empty_cache()` alone because model
object references are also cleared by each provider.

## Observability

Internal readiness and metrics endpoints expose:

```text
gpu
residency
```

The 1800-second soak can use these fields to verify:

```text
queue_depth = 0
active_requests = 0
model_switch_count >= expected switches
unexpected OOM = 0
```

## Current Verification

Targeted unit coverage verifies:

```text
model switching
evictor callback execution
active request release
load / eviction / switch counters
```

Real chained 1800-second stability has not run yet, so the following remains
open:

```text
AGENT_RAG_V22_GPU_8GB_STABILITY pending
```
