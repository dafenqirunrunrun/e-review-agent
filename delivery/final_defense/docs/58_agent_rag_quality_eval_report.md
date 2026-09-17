# Agentic RAG Quality Evaluation Report

This report evaluates the local E-Review Agent workflow against a golden review set. It is intended for graduation defense, product demonstration, and follow-up optimization. It does not claim production-grade model performance.

## Summary

| Metric | Value |
| --- | ---: |
| golden_sample_count | 30 |
| sentiment_accuracy | 86.67 |
| risk_type_hit_rate | 96.67 |
| risk_level_accuracy | 90.0 |
| conflict_detection_accuracy | 93.33 |
| dominant_modality_accuracy | 100.0 |
| review_required_hit_rate | 90.0 |
| suggestion_action_hit_rate | 83.33 |
| case_retrieval_non_empty_rate | 100.0 |
| fallback_rate | 0.0 |
| average_latency_ms | 3.03 |
| empty_case_retrieval_rate | 0.0 |
| evidence_coverage_rate | 100.0 |

## Case Results

| review_id | sentiment | risk_type | risk_level | conflict | modality | suggestion | retrieval_non_empty | evidence | latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| G001 | True | True | False | False | True | True | True | True | 3 |
| G002 | True | True | True | True | True | True | True | True | 3 |
| G003 | True | True | True | True | True | True | True | True | 3 |
| G004 | True | True | True | True | True | True | True | True | 3 |
| G005 | True | True | True | True | True | True | True | True | 4 |
| G006 | True | True | True | True | True | True | True | True | 3 |
| G007 | True | True | True | True | True | True | True | True | 3 |
| G008 | True | True | True | True | True | True | True | True | 3 |
| G009 | True | True | True | True | True | True | True | True | 3 |
| G010 | True | True | True | True | True | True | True | True | 3 |
| G011 | True | True | True | True | True | True | True | True | 3 |
| G012 | True | True | True | True | True | True | True | True | 3 |
| G013 | True | True | True | True | True | True | True | True | 3 |
| G014 | True | True | True | True | True | True | True | True | 3 |
| G015 | True | True | True | True | True | True | True | True | 3 |
| G016 | True | True | True | True | True | True | True | True | 3 |
| G017 | True | True | True | True | True | True | True | True | 3 |
| G018 | False | True | True | True | True | False | True | True | 3 |
| G019 | True | True | True | True | True | True | True | True | 3 |
| G020 | True | True | True | True | True | True | True | True | 3 |
| G021 | False | True | True | True | True | False | True | True | 3 |
| G022 | True | True | True | True | True | True | True | True | 3 |
| G023 | True | True | True | True | True | True | True | True | 3 |
| G024 | False | False | False | True | True | False | True | True | 3 |
| G025 | True | True | False | True | True | False | True | True | 3 |
| G026 | True | True | True | False | True | True | True | True | 3 |
| G027 | True | True | True | True | True | True | True | True | 3 |
| G028 | True | True | True | True | True | True | True | True | 3 |
| G029 | False | True | True | True | True | False | True | True | 3 |
| G030 | True | True | True | True | True | True | True | True | 3 |

## Notes

- The current demo uses local rules and local case memory by default.
- Qdrant and external model calls are not required for this evaluation.
- Metrics below 70% are treated as improvement warnings instead of release blockers.
- Human operators remain responsible for final risk handling decisions.
