# Agent-RAG Phase 3A.2 Dense Diagnosis

## Implementation Validation

Phase 3A.2 audits the real BGE-M3 dense path instead of assuming dense retrieval
is automatically better than BM25.

Evidence files:

- `artifacts/agent-rag/v2.0-phase3a2/embedding-health.json`
- `artifacts/agent-rag/v2.0-phase3a2/query-failure-analysis.json`
- `artifacts/agent-rag/v2.0-phase3a2/phase3a2-gate-result.json`

Provider metadata:

| Field | Value |
| --- | --- |
| Library | `transformers` |
| Library version | `5.3.0` |
| Encode method | `AutoTokenizer + AutoModel.last_hidden_state[:, 0]` |
| Pooling | `CLS` |
| Query instruction | empty |
| Document instruction | empty |
| Normalize | `true` |
| Dimension | `1024` |
| Device | `cuda` |
| Max length | `512` |

This confirms the current provider is deterministic and numerically valid, but
it uses a generic Transformers CLS pooling path rather than a BGE-M3-specific
embedding wrapper. That is a quality risk, not a FAISS correctness failure.

## Embedding Health

The embedding health gate passed:

- Vector count: `8`
- Dimension: `1024`
- NaN count: `0`
- Inf count: `0`
- Zero vector count: `0`
- Same-text repeat similarity: `1.0`
- Synonym similarity: `0.812301`
- Related similarity: `0.659112`
- Unrelated similarity: `0.417971`
- Pairwise cosine min/p50/p95/max: `0.380732 / 0.493804 / 0.812301 / 1.0`

Sanity rule result:

```text
AGENT_RAG_EMBEDDING_HEALTH_PASS
```

## FAISS Validation

FAISS `IndexFlatIP` was checked against numpy brute-force inner product on the
same query and same active vectors.

- Top-K IDs match: `true`
- Top-K scores match: `true`
- Metadata/vector position mapping: `true`
- Save/load consistency: `true`
- Vector count: `474`
- Dimension: `1024`

Gate:

```text
AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_PASS
```

## Query Processing

`QueryAnalyzer` keeps the original normalized query as the first rewritten query.
Phase 3A.2 did not find evidence that query expansion replaces the original
query for dense retrieval. However, the current real dense runtime searches only
the original query vector and does not yet evaluate expanded dense queries.

## Chunk Design

Chunk statistics:

- char p50/p95: `179 / 193`
- token p50/p95: `24 / 24`
- title-only chunks: `0`
- short chunks: `30`
- long chunks: `0`
- duplicate content count: `0`

Chunking is controlled and compact. The main risk is not length explosion, but
the synthetic fixture repeats topic keywords heavily, which favors BM25.

## Root Cause

The root cause is multi-factor:

1. Current BGE-M3 provider uses generic `AutoModel` CLS pooling, not a
   BGE-M3-specific encode API. The path is numerically stable, but quality is
   not fully validated.
2. The benchmark contains many short, topic-repeated synthetic chunks. Lexical
   overlap is structurally strong, so BM25 is favored.
3. Current hybrid runtime protects sparse top-5 before appending dense-only
   candidates. This explains why prior Phase 3A hybrid results exactly matched
   BM25 top-5.
4. Dense retrieval does show semantic-subset signal, but it is not enough to
   justify making hybrid-real the unconditional default.

Final conclusion:

```text
AGENT_RAG_DENSE_SEMANTIC_GAIN_ONLY
```

## Decision

Default retrieval should not be unconditional `hybrid-real`.

Recommended default:

```text
RAG_DEFAULT_RETRIEVAL_MODE=bm25-first-semantic-hybrid
```

BGE-M3 remains conditionally useful for semantic/implicit-intent queries and
experimental for broader production use.
