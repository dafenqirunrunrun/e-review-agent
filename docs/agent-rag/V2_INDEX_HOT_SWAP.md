# V2 Index Hot Swap

FAISS active-index activation and active-index loading now share a local re-entrant lock.

Protected operations:

- `activate(index_version, provider_metadata, tenant_id)`
- `load_active(provider_metadata, tenant_id)`

Safety properties:

- A reader does not observe a partially written active pointer.
- Activation validates candidate compatibility before switching the active pointer.
- Previous active index is preserved in `PREVIOUS` before activation.
- Index load latency and hot-swap count are recorded in metrics.

Limitations:

- This is a local process lock, not a distributed coordination mechanism.
- It does not claim zero-downtime multi-node rollout.
