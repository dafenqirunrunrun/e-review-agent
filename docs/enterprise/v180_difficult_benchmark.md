# v1.8.0 Difficult RAG Benchmark

Status: `V180_DIFFICULT_BENCHMARK_PASS`

This benchmark is project-owned synthetic data for enterprise RAG readiness. It is not a closed holdout, not external data, and not real user text.

## Scope

- Corpus chunks: 192
- Active chunks: 144
- Queries: 52
- Tenants: 4
- Topics: 13

## Difficulty Controls

- Paraphrased Chinese user queries against English/internal policy chunks.
- Same-topic distractor chunks.
- Cross-tenant forbidden chunks.
- Superseded inactive policy versions.
- Negative-control queries that should not retrieve risk policy evidence.
- Prompt-injection review scenario included as a retrieval topic, not as executable instruction.

## Leakage Checks

- Duplicate chunk IDs: 0
- Duplicate query IDs: 0
- Cross-tenant gold count: 0
- Missing or inactive gold count: 0
- Forbidden/gold overlap count: 0
- Query/gold lexical overlap mean: 0.001488
- Query/gold lexical overlap max: 0.017857

## Files

- Corpus: `data/private_research/enterprise_rag_v180/difficult_corpus.jsonl`
- Queries: `data/private_research/enterprise_rag_v180/difficult_queries.jsonl`
- Audit: `data/private_research/audit/v180_difficult_benchmark_audit.json`
