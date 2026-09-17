# V2.3 Unseen Retrieval Qualification Dataset

Dataset version: `v23-retrieval-qualification-v1`

Dataset hash: `d3835de362f936a3f5000395b57c447d1518e63a879e50a08e5198b920761c2d`

This dataset is a new synthetic, project-owned, unseen retrieval qualification benchmark for Phase 9.2 and later retrieval optimization work. It is separated from the previously consumed v2.2 reranker and retrieval diagnostic cases.

## Counts

| Split | Answerable | No-answer |
|---|---:|---:|
| Calibration | 100 | 25 |
| Evaluation | 100 | 25 |
| Challenge | 40 | 10 |

Total cases: `300`

Answerable cases: `240`

No-answer cases: `60`

## Governance

- Full query text is not persisted in committed artifacts.
- Full chunk text is not persisted in committed artifacts.
- Case family and document family do not cross split.
- Answerable labels point to valid eligible chunks at the fixed evaluation time.
- No-answer cases use unsupported synthetic query families and are marked with corpus audit hashes.

## Leakage Audit

```json
{
  "caseFamilyCrossSplitCount": 0,
  "documentFamilyCrossSplitCount": 0,
  "oldDiagnosticCaseOverlap": 0,
  "oldQueryHashOverlap": 0,
  "queryExactHashDuplicates": 37,
  "status": "PASS",
  "templateCrossSplitCount": 30
}
```

## Label Audit

```json
{
  "checkedAnswerableCases": 240,
  "failureCount": 0,
  "failures": [],
  "status": "PASS"
}
```
