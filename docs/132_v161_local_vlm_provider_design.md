# v1.6.1 Local VLM Provider Design

## Provider Boundary

- Provider name: `local_qwen3_vl_transformers`
- Preferred model: `Qwen/Qwen3-VL-2B-Instruct`
- Role: structured visual evidence extraction
- Non-role: final refund, compensation, ban, or governance decision

The VLM provider is a tool node. Qwen3-1.7B remains responsible for final text,
visual evidence, and Hybrid RAG synthesis.

## API Surface

- `GET /api/v1/vlm/status`
- `POST /api/v1/vlm/image/analyze`
- `POST /api/v1/vlm/text-image/consistency`
- `POST /api/v1/vlm/smoke-test`

## Structured Visual Evidence Schema

The required result contains:

- image availability and quality
- OCR text array
- visual findings with confidence in `[0, 1]`
- package damage, product damage, leakage, missing part, mismatch, and privacy flags
- text-image consistency
- visual risk level
- visual evidence list
- unsupported visual claims
- human review flag
- missing information list

Arrays must not be null. Unclear, blurred, unrelated, or unsupported evidence
must be represented as `uncertain` plus `need_human_review=true`.

## Memory Strategy

The RTX 4060 Laptop 8GB target uses serial lazy loading:

1. load VLM only for image requests
2. process batch size 1
3. cap image pixels
4. generate bounded output
5. record latency and GPU peak memory
6. unload model and processor references
7. call garbage collection and CUDA cache cleanup

Qwen3-1.7B, Qwen3-VL, BGE-M3, and the neural reranker must not be kept resident
at the same time by default.

## Current Implementation Status

The existing provider still blocks real analysis when the model is unavailable.
The new local smoke script records this honestly as
`VLM_PROVIDER_SMOKE_BLOCKED`. It must not be interpreted as a multimodal
evaluation pass.
