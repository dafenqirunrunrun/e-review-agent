# V2.3 Sparse Representation Diagnostic

```json
{
  "gate": {
    "decision": "SPARSE_REPRESENTATION_RESCUE_CANDIDATE_FOUND",
    "status": "PASS"
  },
  "primaryRootCause": "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED",
  "representations": {
    "R0_CONTENT_ONLY": {
      "averageMaxWeight": 0.8567469,
      "averageNonZeroDimensions": 20,
      "averageWeightSum": 11.18547235,
      "caseCount": 153,
      "encodeP50Ms": 4.713,
      "encodeP95Ms": 4.713,
      "invalidWeightCount": 0,
      "medianNonZeroDimensions": 21.0,
      "p95NonZeroDimensions": 23.0,
      "rawSparseNonEmptyCount": 153,
      "rawSparseNonEmptyRate": 1.0,
      "tokenCountMedian": 24.0,
      "tokenCountP95": 24.0,
      "tokenizerErrorCount": 0,
      "truncationRate": 0.0
    },
    "R1_SECTION_CONTENT": {
      "averageMaxWeight": 0.77782724,
      "averageNonZeroDimensions": 28.673,
      "averageWeightSum": 13.21039059,
      "caseCount": 153,
      "encodeP50Ms": 5.022,
      "encodeP95Ms": 5.022,
      "invalidWeightCount": 0,
      "medianNonZeroDimensions": 30.0,
      "p95NonZeroDimensions": 32.0,
      "rawSparseNonEmptyCount": 153,
      "rawSparseNonEmptyRate": 1.0,
      "tokenCountMedian": 31.0,
      "tokenCountP95": 31.0,
      "tokenizerErrorCount": 0,
      "truncationRate": 0.0
    },
    "R2_TITLE_SECTION_CONTENT": {
      "averageMaxWeight": 0.72691674,
      "averageNonZeroDimensions": 30.641,
      "averageWeightSum": 12.84016001,
      "caseCount": 153,
      "encodeP50Ms": 5.11,
      "encodeP95Ms": 5.11,
      "invalidWeightCount": 0,
      "medianNonZeroDimensions": 32.0,
      "p95NonZeroDimensions": 34.0,
      "rawSparseNonEmptyCount": 153,
      "rawSparseNonEmptyRate": 1.0,
      "tokenCountMedian": 37.0,
      "tokenCountP95": 37.0,
      "tokenizerErrorCount": 0,
      "truncationRate": 0.0
    },
    "R3_SAFE_SCOPE_TITLE_SECTION_CONTENT": {
      "averageMaxWeight": 0.71311243,
      "averageNonZeroDimensions": 40.673,
      "averageWeightSum": 15.9703062,
      "caseCount": 153,
      "encodeP50Ms": 6.096,
      "encodeP95Ms": 6.096,
      "invalidWeightCount": 0,
      "medianNonZeroDimensions": 42.0,
      "p95NonZeroDimensions": 43.0,
      "rawSparseNonEmptyCount": 153,
      "rawSparseNonEmptyRate": 1.0,
      "tokenCountMedian": 40.0,
      "tokenCountP95": 40.0,
      "tokenizerErrorCount": 0,
      "truncationRate": 0.0
    },
    "R4_PARENT_SUMMARY_CONTENT": {
      "averageMaxWeight": 0.75541737,
      "averageNonZeroDimensions": 31.418,
      "averageWeightSum": 13.22754158,
      "caseCount": 153,
      "encodeP50Ms": 4.813,
      "encodeP95Ms": 4.813,
      "invalidWeightCount": 0,
      "medianNonZeroDimensions": 33.0,
      "p95NonZeroDimensions": 35.0,
      "rawSparseNonEmptyCount": 153,
      "rawSparseNonEmptyRate": 1.0,
      "tokenCountMedian": 31.0,
      "tokenCountP95": 31.0,
      "tokenizerErrorCount": 0,
      "truncationRate": 0.0
    }
  },
  "selectedRescueCandidate": "R0_CONTENT_ONLY"
}
```
