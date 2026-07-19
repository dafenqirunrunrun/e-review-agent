# Public Runtime Limitations

The public runtime is intended for clean-room reproducibility, CI verification and portfolio review.

## Not Production Ready

This repository does not claim production readiness.

Current gate:

- `PUBLIC_DOCKER_RUNTIME_PENDING` until remote runtime CI passes.
- `PRODUCTION_READY_NOT_CLAIMED`

## Not Included

- Private model weights
- Private datasets
- FAISS indexes
- Checkpoints
- Adapter weights
- Enterprise RAG runtime verification
- Private local Qwen/VLM runtime verification
- Real payment
- Real logistics
- Real refund
- Full database backup and disaster recovery verification
- Application version rollback verification
- Kubernetes deployment
- Production monitoring platform

## Public AI Runtime

The public Docker runtime uses deterministic rule analysis:

- `runtimeMode=public-rule`
- `engineType=rule`
- `modelLoaded=false`

This proves the business workflow can run from public source code. It does not prove private model quality or Enterprise RAG readiness.
