# v1.6.1 Unblock Prerequisites Check

## Conclusion

`V161_UNBLOCK_PREREQUISITES_BLOCKED`

This report only checks whether the local environment has the prerequisites needed to continue real external text evaluation, real multimodal evaluation, VLM inference, and SFT readiness auditing. It must not be interpreted as a real evaluation PASS.

## Checks

| Check | Status | Evidence | Required action |
| --- | --- | --- | --- |
| real_text_source_file | `BLOCKED` | <repo-external>/data-private/banglishrev/reviews v1.json | Provide official BanglishRev JSON outside Git. |
| local_vlm_model | `BLOCKED` | <repo-external>/models/Qwen3-VL-2B-Instruct, <repo-external>/models/Qwen2.5-VL-3B-Instruct | Place complete Qwen3-VL/Qwen2.5-VL config, processor/tokenizer, and weights outside Git. |
| existing_text_models | `READY` | <repo-external>/models/bge-m3, <repo-external>/models/rag-reranker, <repo-external>/models/Qwen3-1.7B | Keep model weights outside Git. |
| torch_cuda_environment | `READY` | {"torch_available": true, "cuda_available": true, "device_count": 1, "python": "<local-conda>/envs/torchtest/python.exe", "return_code": 0} | Use torchtest Python for BGE/reranker/VLM checks. |
| private_data_not_tracked | `READY` | tracked_matches=0 | Remove private data/model paths from Git if any are tracked. |
| model_weights_not_tracked | `READY` | tracked_matches=0 | Remove model weights/index binaries from Git if any are tracked. |

## Blockers

- real_text_source_file: Provide official BanglishRev JSON outside Git.
- local_vlm_model: Place complete Qwen3-VL/Qwen2.5-VL config, processor/tokenizer, and weights outside Git.

## Next Steps

1. Place the compliant real review JSON outside Git, for example `<repo-external>/data-private/banglishrev/reviews v1.json`.
2. Place local VLM weights outside Git, for example `<repo-external>/models/Qwen3-VL-2B-Instruct`, or configure an equivalent repo-external model path.
3. If your local paths differ from the defaults, pass `-RealJson`, `-VlmCandidates`, `-TextModelDirs`, and `-TorchPython` to `scripts/e-review-v161-unblock-prerequisites.ps1`, or set `V161_REAL_TEXT_SOURCE`, `V161_VLM_MODEL_DIRS`, `V161_TEXT_MODEL_DIRS`, and `V161_TORCH_PYTHON`.
4. Rerun `scripts/e-review-realworld-ingest.ps1`, `scripts/e-review-vlm-visual-eval.ps1`, `scripts/e-review-multimodal-ablation-eval.ps1`, `scripts/e-review-multimodal-route-calibration.ps1`, and `scripts/e-review-v161-final-gate.ps1`.
5. Consider a release tag only after the final gate reports `V161_FINAL_GATE_PASS`.
