# Agent-RAG Phase 3A.2 Benchmark Design

## Purpose

Phase 3A.2 expands the evaluation fixture so dense retrieval is not judged only
on keyword-heavy queries.

The benchmark remains project-owned synthetic data. It is not customer data and
does not claim external production representativeness.

## Composition

| Challenge type | Count |
| --- | ---: |
| lexical | 54 |
| semantic | 54 |
| mixed | 36 |
| temporal | 10 |
| tenant-isolation | 10 |
| negative/no-answer | 10 |
| total | 174 |

Minimum requirements are satisfied:

- total cases >= 150
- semantic >= 40
- lexical >= 40
- mixed >= 30
- negative/no-answer >= 10
- tenant + temporal >= 20

## Split

The benchmark is split before final reporting:

- split seed: `302202`
- calibration cases: `52`
- evaluation cases: `122`
- calibration hash:
  `5b49e660cc2d2186abdbed642fcae70ba9e8e7c4cd56b1c7c1262887c4dd608b`
- evaluation hash:
  `16e55999a3305e0c9123ce73f3e940846e678ea45b6aaf93947acc29096e778c`

Fusion parameters are selected only on calibration cases. Final metrics are
reported on evaluation cases.

## Evaluation Results

Evaluation subset metrics:

| Subset | Mode | HitRate@5 | Recall@5 | MRR | nDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| Overall | BM25 | 0.2295 | 0.1295 | 0.2057 | 0.1444 |
| Overall | BGE-M3 | 0.1639 | 0.0410 | 0.0538 | 0.0333 |
| Overall | Hybrid | 0.2869 | 0.1443 | 0.2322 | 0.1588 |
| Lexical | BM25 | 0.3158 | 0.1632 | 0.2816 | 0.1891 |
| Lexical | BGE-M3 | 0.1579 | 0.0368 | 0.0342 | 0.0250 |
| Lexical | Hybrid | 0.3158 | 0.1632 | 0.2816 | 0.1891 |
| Semantic | BM25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Semantic | BGE-M3 | 0.1579 | 0.0421 | 0.0798 | 0.0428 |
| Semantic | Hybrid | 0.1579 | 0.0421 | 0.0798 | 0.0428 |
| Mixed | BM25 | 0.3600 | 0.2000 | 0.2960 | 0.2190 |
| Mixed | BGE-M3 | 0.1200 | 0.0320 | 0.0333 | 0.0237 |
| Mixed | Hybrid | 0.3600 | 0.2000 | 0.2960 | 0.2190 |
| Temporal | BM25 | 0.5714 | 0.4000 | 0.5714 | 0.4070 |
| Temporal | BGE-M3 | 0.4286 | 0.0857 | 0.1286 | 0.0681 |
| Temporal | Hybrid | 0.7143 | 0.4286 | 0.6000 | 0.4258 |
| No-answer | BM25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| No-answer | BGE-M3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| No-answer | Hybrid | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Interpretation

BM25 remains stronger on lexical and mixed queries. Dense retrieval has visible
signal on semantic queries where BM25 returns no relevant evidence. Hybrid also
improves temporal results in this controlled fixture.

This supports a conditional routing decision, not an unconditional dense or
hybrid default.
