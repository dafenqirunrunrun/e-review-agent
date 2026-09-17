# v1.6.1 Full Regression Report

## Conclusion

- Regression result: `V161_REGRESSION_COMPLETE_WITH_BLOCKED_RELEASE_GATES`
- Final gate marker: `V161_FINAL_GATE_BLOCKED`
- Release allowed: `False`
- Skip builds: `True`

## Stage Results

| Stage | Status | Markers | Duration(s) |
| --- | --- | --- | --- |
| python-pytest | `PASS` | - | 18.59 |
| unblock-prerequisites | `PASS` | V161_UNBLOCK_PREREQUISITES_BLOCKED | 3.33 |
| external-test-isolation | `PASS` | EXTERNAL_TEST_ISOLATION_AUDIT_PASS | 0.54 |
| rag-leakage-audit | `PASS` | RAG_LEAKAGE_AUDIT_COMPLETE | 43.0 |
| realworld-ingest | `PASS` | PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED, REALWORLD_SPLIT_BLOCKED | 0.78 |
| rag-validity-external | `PASS` | REALWORLD_EXTERNAL_EVAL_BLOCKED | 82.5 |
| vlm-provider-smoke | `PASS` | VLM_PROVIDER_SMOKE_BLOCKED | 3.37 |
| local-vlm-smoke | `PASS` | VLM_PROVIDER_SMOKE_BLOCKED | 13.31 |
| vlm-observability | `PASS` | VLM_OBSERVABILITY_BLOCKED | 0.55 |
| vlm-visual-eval | `PASS` | MULTIMODAL_VLM_EVAL_BLOCKED | 0.52 |
| multimodal-ablation | `PASS` | MULTIMODAL_ABLATION_EVAL_BLOCKED | 0.55 |
| qwen-realworld-external | `PASS` | REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED | 0.55 |
| route-calibration | `PASS` | REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED | 1.87 |
| sft-readiness | `PASS` | SFT_DATA_NOT_READY, VLM_SFT_DATA_NOT_READY | 1.29 |
| security-hygiene | `PASS` | SECURITY_HYGIENE_CHECK_PASS | 3.02 |
| doc-link | `PASS` | DOC_LINK_CHECK_PASS | 1.08 |
| encoding | `PASS` | ENCODING_CHECK_PASS | 17.87 |
| error-message | `PASS` | ERROR_MESSAGE_CHECK_PASS | 2.15 |
| v161-final-gate | `PASS` | V161_FINAL_GATE_BLOCKED | 0.67 |
| final-status-summary | `PASS` | V161_FINAL_STATUS_SUMMARY_COMPLETE | 1.05 |

## Release Decision

This regression proves that the audit and evaluation scripts can run repeatably and collect the current evidence. Release eligibility is decided only by `scripts/e-review-v161-final-gate.ps1`. The current state must not receive the `v1.6.1-realworld-multimodal-evaluation` release tag unless the final gate reports `V161_FINAL_GATE_PASS`.
