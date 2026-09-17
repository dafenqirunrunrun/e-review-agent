# V2 GPU Concurrency

The local Runtime remains a single-node Windows demonstration environment. To avoid accidental concurrent CUDA overload, embedding calls use a local gate:

- Default concurrency: `1`
- Environment override: `AGENT_RAG_GPU_CONCURRENCY`
- Queue timeout override: `AGENT_RAG_GPU_QUEUE_TIMEOUT_MS`

Behavior:

- CPU embedding calls do not acquire the GPU gate.
- CUDA embedding calls acquire the gate before model encode.
- If the gate cannot be acquired before timeout, the call fails with `AGENT_RAG_GPU_QUEUE_TIMEOUT`.
- The slot is released in a `finally` path, including exception paths.

Validation:

- Unit tests verify queue timeout, slot release, and serialized concurrent work.
- Runtime metrics expose current `gpu_in_flight` and `gpu_queue_timeout_total`.

Limitations:

- This is not a distributed lock.
- It protects the local process only.
