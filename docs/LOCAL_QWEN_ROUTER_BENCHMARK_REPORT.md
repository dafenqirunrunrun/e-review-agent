# Local Qwen Router Benchmark Report

## Scope

Step 21.3A-Lite compares the immutable Step 21.2.3 Rule Router baseline with the existing local Qwen generation model. It does not modify runtime routing, execute Frozen Gold, use RAG, or call an external model provider.

## Local Model

- Provider: `local_qwen3_transformers`
- Model: `Qwen/Qwen3-1.7B` (1.7B)
- Device / dtype: `cpu` / `bfloat16`
- Context length: `40960`
- External API cost: `0`; local compute, latency, and hardware cost are not zero.

## Availability

Gate: `PASS`. Schema valid: `True`. Latency: `59306 ms`.

## Five Case Latency Probe

P50 `51164.0 ms`, P95 `105118.0 ms`, P99 `115062.8 ms`. Status: `LOCAL_QWEN_HIGH_LATENCY`.

## Benchmark Execution

Completed cases: `5`. Full 100-case benchmark completed: `False`. Stop reason: `LOCAL_QWEN_HIGH_LATENCY`.

## Rule vs Local Qwen

| Metric | Rule | Local Qwen |
| --- | ---: | ---: |
| Exact Accuracy | 0.2526 | N/A |
| Micro F1 | 0.3516 | N/A |
| Macro F1 | 0.3675 | N/A |
| Multi-risk Exact | 0.0000 | N/A |
| Multi-risk F1 | 0.2923 | N/A |
| Boundary Accuracy | 0.1091 | N/A |
| Boundary F1 | 0.2981 | N/A |
| Abstention Accuracy | 0.0000 | N/A |
| Material Safety Errors | 50 | N/A |
| Schema Compliance | 1.0000 | 0.8000 |
| P50 ms | 0.0203 | 51164.0 |
| P95 ms | 0.03708 | 105118.0 |

Probe-only Qwen quality values are intentionally not promoted into the official comparison when the CPU latency guard stops the 100-case run.

## Reliability

Self-reported confidence finding: `SELF_REPORTED_CONFIDENCE_NOT_RELIABLE`. Fast-path candidate gate: `FAIL`.

## Safety

Official safety benchmark: `False`. Probe material safety errors: `1`. High-risk auto-pass candidates: `1`.

## Cost and External Models

`LOCAL_INFERENCE_API_COST = 0`. This excludes local compute, latency, and hardware cost. `EXTERNAL_MODEL_COMPARISON = NOT_RUN_NO_PROVIDER_CONFIGURED`.

## Gates

- `benchmarkHarnessGate` = `PASS`
- `localQwenAvailabilityGate` = `PASS`
- `localQwenQualityGate` = `FAIL`
- `localQwenReliabilityGate` = `FAIL`
- `ruleVsQwenComparisonGate` = `FAIL`
- `externalModelComparisonGate` = `NOT_RUN_NO_PROVIDER_CONFIGURED`
- `step21_3aLiteGate` = `FAIL`

## Frozen Gold

Frozen Gold was not executed. SHA remained `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.

## Limitations

- The local Python environment is CPU-only even though the host has a discrete GPU.
- The Demo Candidate dataset is not human gold.
- A five-case latency probe is not a quality benchmark.
- No external model comparison was run.

## Next Recommendation

`LOCAL_QWEN_NOT_SUITABLE_AS_ROUTER`
