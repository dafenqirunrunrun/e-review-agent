# v1.6.1 Multimodal Agent Integration Report

## Current Progress

Completed integration work:

1. VLM provider package structure under `ai-service/app/vlm/`.
2. VLM API endpoints:
   - `GET /api/v1/vlm/status`
   - `POST /api/v1/vlm/schema/validate`
   - `POST /api/v1/vlm/text-image/consistency`
   - `POST /api/v1/vlm/smoke-test`
3. Structured visual schema validation through `VisualEvidenceResult`.
4. Text-image consistency helper that routes uncertain or conflicting evidence
   to human review.
5. Dedicated VLM provider smoke gate:
   - script: `scripts/e-review-vlm-provider-smoke.ps1`
   - result: `data/multimodal/eval/vlm_provider_smoke_results.json`
   - current marker: `VLM_PROVIDER_SMOKE_BLOCKED`
6. Independent VLM visual-evidence evaluation gate:
   - script: `scripts/e-review-vlm-visual-eval.ps1`
   - result: `data/multimodal/eval/vlm_visual_eval_results.json`
   - current marker: `MULTIMODAL_VLM_EVAL_BLOCKED`
7. Four-mode multimodal ablation gate:
   - script: `scripts/e-review-multimodal-ablation-eval.ps1`
   - result: `data/multimodal/eval/multimodal_ablation_results.json`
   - current marker: `MULTIMODAL_ABLATION_EVAL_BLOCKED`
8. Tool Registry exposure in the admin Agent platform:
   - `ImageEvidenceExtractTool`
   - `TextImageConsistencyTool`
   - `VisualEvidenceQualityTool`
   - `PrivacyVisualRiskTool`

## Not Completed

The following items remain blocked and must not be claimed as complete:

1. Real Qwen3-VL or Qwen2.5-VL image inference.
2. Privacy-filtered real image loading pipeline.
3. Real execution and persistence of the visual tools in Agent Tool Log.
4. Joint injection of text evidence, visual evidence, and Hybrid RAG evidence
   into the final governance model on real multimodal samples.
5. Four-group real multimodal ablation with real VLM output.

## Blocking Reasons

Current blockers:

- repo-external VLM model weights are not present;
- isolated real multimodal external test set is not present;
- original real images must remain outside Git;
- visual metrics must not be fabricated from filenames, paths, or manual labels.

Therefore the project currently reports blocked markers rather than pass markers:

- `VLM_PROVIDER_SMOKE_BLOCKED`
- `MULTIMODAL_VLM_EVAL_BLOCKED`
- `MULTIMODAL_ABLATION_EVAL_BLOCKED`

## Agent Boundary

The VLM is a visual-evidence extraction tool only. It must not:

1. decide refunds;
2. decide compensation;
3. ban users or merchants;
4. convert historical cases into facts about the current image;
5. write uncertain visual findings as confirmed facts.

If visual analysis fails or is uncertain, the Agent route must prefer human
review.

## Evidence Flow

The intended multimodal Agent flow is:

1. read current review text;
2. retrieve Hybrid RAG historical cases;
3. extract visual evidence from current images through VLM;
4. evaluate text-image consistency;
5. keep text, visual, and retrieved-case evidence separated;
6. ask the final governance model to produce a structured decision;
7. route unsafe, unsupported, conflicting, or uncertain cases to human review.

## Current Release Status

The final gate still reports `V161_FINAL_GATE_BLOCKED`. The multimodal Agent
integration is suitable as a prepared integration scaffold and audit artifact,
but it is not a completed real-world multimodal evaluation release.
