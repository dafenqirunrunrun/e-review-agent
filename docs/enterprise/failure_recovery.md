# Failure Recovery

```mermaid
sequenceDiagram
  participant API
  participant Factory
  participant Adapter
  participant Base
  API->>Factory: analyze request
  Factory->>Adapter: validate hash and metadata
  Adapter-->>Factory: failure or circuit open
  Factory->>Base: rollback to base
  Base-->>API: schema-valid conservative result
  API->>API: audit rollback reason
```

Rollback triggers include adapter hash mismatch, load failure, CUDA OOM, repeated schema failure, repeated fallback, latency circuit breaker, prohibited action, GPU lock loss, and external compute contention. After rollback, adapter is not automatically restored.
