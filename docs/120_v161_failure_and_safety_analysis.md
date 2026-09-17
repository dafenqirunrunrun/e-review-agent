# v1.6.1 Failure and Safety Analysis

## Confirmed Risks

1. The original v1.6 golden query set contains oracle-style metadata shortcuts. Expected risk type and level can participate in request metadata and inflate Hybrid RAG scoring.
2. Synthetic cases and queries are generated from fixed templates. The earlier 100% Hit@3/Hit@5 results cannot be treated as real-world generalization evidence.
3. Strict No-Oracle evaluation reduces Hybrid Neural performance to Hit@3=0.2125, Hit@5=0.3250, and MRR=0.1821, showing that performance drops once templates and answer fields are removed.
4. No compliant, anonymized, isolated real-world external text test set is currently available in the repo-external data path, so real-world text metrics cannot be marked PASS.
5. The local machine does not currently provide Qwen3-VL or Qwen2.5-VL weights in the configured repo-external model path, so real VLM inference cannot be marked PASS.
6. Human-review routing has not been calibrated on real dev or multimodal validation data. Historical shortcut summaries such as a single manual-review percentage are not sufficient.
7. SFT readiness remains NOT_READY. The project must not proceed to QLoRA-SFT, DPO, or VLM fine-tuning from the current data state.

## Applied Protections

- Added a leakage audit script and produced `RAG_LEAKAGE_AUDIT_COMPLETE`.
- Added a strict synthetic query set that separates input text from evaluation labels.
- Added strict No-Oracle retrieval evaluation to quantify the impact of template and metadata shortcuts.
- Added a real-data source manifest and explicit local-source BLOCKED status when the repo-external dataset is unavailable.
- Added a dedicated VLM Provider smoke gate that reports `VLM_PROVIDER_SMOKE_BLOCKED` when model weights are absent.
- Added a separate VLM visual-evidence evaluation gate that reports `MULTIMODAL_VLM_EVAL_BLOCKED` rather than reusing smoke status.
- Added structured visual schema validation and a visual evidence boundary report.
- Added SFT data-readiness audit outputting `SFT_DATA_NOT_READY` and `VLM_SFT_DATA_NOT_READY`.
- Added final gate and release guard scripts so a release tag is blocked unless all required real-world, VLM, routing, and SFT gates pass.

## Current Blocked Gates

- `REALWORLD_EXTERNAL_EVAL_PASS`: blocked by missing anonymized real external text test data.
- `REALWORLD_QWEN_EXTERNAL_EVAL_PASS`: blocked by missing 200-sample isolated real external text test data.
- `VLM_PROVIDER_SMOKE_PASS`: blocked by missing local repo-external VLM weights.
- `MULTIMODAL_VLM_EVAL_PASS`: blocked by missing local VLM weights and compliant real multimodal external test data.
- `MULTIMODAL_ABLATION_EVAL_PASS`: blocked by missing real multimodal external data and real VLM output.
- `REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_PASS`: blocked by missing real dev and multimodal validation data.
- `SFT_DATA_READY`: blocked by missing real external holdout evidence, double-annotation consistency, and final train/test separation checks.
- `VLM_SFT_DATA_READY`: blocked by missing compliant multimodal samples and image redistribution/privacy evidence.

## Safety Conclusion

The current v1.6.1 branch is suitable as an audit and multimodal-integration preparation branch. It is not a completed real-world multimodal evaluation release. Do not create the `v1.6.1-realworld-multimodal-evaluation` tag, and do not enter QLoRA-SFT or VLM fine-tuning until compliant real data, VLM weights, real external evaluation, routing calibration, and SFT readiness gates are all proven by scripts.
