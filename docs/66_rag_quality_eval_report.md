# Historical RAG Quality Evaluation Report

> Version note: this is a historical v1.1-era RAG quality report kept for traceability.
> It used a 20-query local evaluation set. The current v1.2 quality baseline is
> `docs/69_v12_rag_quality_report.md`, which uses 40 golden RAG queries and is the
> authoritative report for v1.2 and v1.2.1 verification.

| metric | value |
| --- | ---: |
| query_count | 20 |
| retrieval_hit_rate | 100.00 |
| top1_match_score_avg | 0.80 |
| top3_non_empty_rate | 95.00 |
| evidence_coverage_rate | 100.00 |
| operation_result_coverage | 90.00 |
| retrieval_latency_ms_avg | 0.01 |
| query_without_result_count | 1 |

## Query Results

| query_id | non_empty | top1_match | top1_score | latency_ms |
| --- | --- | --- | ---: | ---: |
| RAG001 | True | True | 0.73 | 0.02 |
| RAG002 | True | True | 0.73 | 0.01 |
| RAG003 | True | True | 0.91 | 0.01 |
| RAG004 | True | True | 0.91 | 0.01 |
| RAG005 | True | True | 0.91 | 0.01 |
| RAG006 | True | True | 0.91 | 0.01 |
| RAG007 | True | False | 0.73 | 0.01 |
| RAG008 | True | False | 0.73 | 0.01 |
| RAG009 | True | True | 0.91 | 0.01 |
| RAG010 | True | True | 0.91 | 0.01 |
| RAG011 | True | True | 0.91 | 0.01 |
| RAG012 | True | True | 0.91 | 0.01 |
| RAG013 | True | True | 0.91 | 0.01 |
| RAG014 | True | True | 0.91 | 0.01 |
| RAG015 | True | False | 0.73 | 0.01 |
| RAG016 | True | True | 0.73 | 0.01 |
| RAG017 | True | True | 0.91 | 0.01 |
| RAG018 | False | True | 0.00 | 0.01 |
| RAG019 | True | True | 0.73 | 0.01 |
| RAG020 | True | True | 0.91 | 0.01 |

RAG_QUALITY_CHECK_PASS
