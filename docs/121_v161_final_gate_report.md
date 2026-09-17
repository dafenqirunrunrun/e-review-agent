# v1.6.1 Final Gate Report

## Conclusion

`V161_FINAL_GATE_BLOCKED`

- Release allowed: `False`
- Recommended tag: `None`
- Git forbidden tracked files: `0`

## Gate Details

| Gate | Current | Required | Release gate | Evidence |
| --- | --- | --- | --- | --- |
| synthetic_leakage_audit | `RAG_LEAKAGE_AUDIT_COMPLETE` | `RAG_LEAKAGE_AUDIT_COMPLETE` | no | data/rag/audit/leakage_audit_summary.json |
| source_manifest | `SOURCE_MANIFEST_PRESENT` | `SOURCE_MANIFEST_PRESENT` | no | data/real_world/source_manifest/source_manifest.jsonl |
| realworld_external_eval | `REALWORLD_EXTERNAL_EVAL_BLOCKED` | `REALWORLD_EXTERNAL_EVAL_PASS` | yes | data/rag/audit/validity_external_eval_results.json |
| qwen_realworld_external_eval | `REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED` | `REALWORLD_QWEN_EXTERNAL_EVAL_PASS` | yes | data/rag/audit/qwen_realworld_external_eval_results.json |
| vlm_provider_smoke | `VLM_PROVIDER_SMOKE_BLOCKED` | `VLM_PROVIDER_SMOKE_PASS` | yes | data/multimodal/eval/vlm_provider_smoke_results.json |
| multimodal_vlm_eval | `MULTIMODAL_VLM_EVAL_BLOCKED` | `MULTIMODAL_VLM_EVAL_PASS` | yes | data/multimodal/eval/vlm_visual_eval_results.json |
| multimodal_ablation_eval | `MULTIMODAL_ABLATION_EVAL_BLOCKED` | `MULTIMODAL_ABLATION_EVAL_PASS` | yes | data/multimodal/eval/multimodal_ablation_results.json |
| route_calibration | `REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED` | `REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_PASS` | yes | data/multimodal/eval/route_calibration_results.json |
| text_sft_readiness | `SFT_DATA_NOT_READY` | `SFT_DATA_READY` | yes | data/multimodal/audit/sft_data_readiness.json |
| vlm_sft_readiness | `VLM_SFT_DATA_NOT_READY` | `VLM_SFT_DATA_READY` | yes | data/multimodal/audit/sft_data_readiness.json |
| forbidden_git_payload | `NO_FORBIDDEN_TRACKED_PAYLOAD` | `NO_FORBIDDEN_TRACKED_PAYLOAD` | yes | git ls-files |

## Release Blockers

- realworld_external_eval: current=REALWORLD_EXTERNAL_EVAL_BLOCKED, required=REALWORLD_EXTERNAL_EVAL_PASS
- qwen_realworld_external_eval: current=REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED, required=REALWORLD_QWEN_EXTERNAL_EVAL_PASS
- vlm_provider_smoke: current=VLM_PROVIDER_SMOKE_BLOCKED, required=VLM_PROVIDER_SMOKE_PASS
- multimodal_vlm_eval: current=MULTIMODAL_VLM_EVAL_BLOCKED, required=MULTIMODAL_VLM_EVAL_PASS
- multimodal_ablation_eval: current=MULTIMODAL_ABLATION_EVAL_BLOCKED, required=MULTIMODAL_ABLATION_EVAL_PASS
- route_calibration: current=REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED, required=REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_PASS
- text_sft_readiness: current=SFT_DATA_NOT_READY, required=SFT_DATA_READY
- vlm_sft_readiness: current=VLM_SFT_DATA_NOT_READY, required=VLM_SFT_DATA_READY

## Key Metrics

- exact duplicate count: `0`
- normalized duplicate count: `0`
- near duplicate count: `0`
- metadata shortcut count: `109`
- strict no-oracle Hit@5: `0.325`
- real external count: `0`
- qwen real external count: `0`
- VLM provider model available: `False`
- multimodal external count: `0`
- route unsafe auto pass rate: `0.0`
- route high risk review recall: `1.0`

## Release Decision

The current artifacts can be used as v1.6.1 audit and multimodal integration
preparation evidence, but they cannot be released as a completed real-world
external evaluation version. The release tag `v1.6.1-realworld-multimodal-evaluation`
is allowed only after all required release gates pass.
