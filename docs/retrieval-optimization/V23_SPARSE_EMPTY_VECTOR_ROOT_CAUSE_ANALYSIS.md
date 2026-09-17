# V2.3 Sparse Empty Vector Root Cause Analysis

```json
{
  "inputProfileSummary": {
    "eligibleChunkCount": 153,
    "emptyVectorChunkCount": 153,
    "nonEmptyControlChunkCount": 0,
    "profilesHash": "278d076da2ddb909c84bde3dc6bf4842907fcc54abbe5ea6be350aa6a9d11ee5"
  },
  "rootCause": {
    "decision": "BGE_M3_SPARSE_SIGNAL_INADEQUATE_FOR_CURRENT_CORPUS",
    "eligibleChunkCount": 153,
    "emptySetReproductionStatus": "NOT_STABLE",
    "emptyVectorChunkCount": 153,
    "implementationDefect": false,
    "inputDefect": false,
    "modelId": "BAAI/bge-m3",
    "modelRevision": "external-existing",
    "modelSignalDefect": true,
    "originalEmptyVectorChunkCount": 97,
    "primaryCauseCounts": {
      "MODEL_RAW_SPARSE_EMPTY": 153
    },
    "representationDefect": false,
    "representationDiagnosticStatus": "REPRESENTATION_DIAGNOSTIC_NO_EFFECT",
    "reproducedEmptyVectorChunkCount": 153,
    "rootCauseConfidence": "HIGH",
    "schemaVersion": "agent-rag-v23-sparse-empty-vector-root-cause-v1",
    "singleVsBatchStatus": "PASS",
    "wrapperVsOfficialStatus": "WRAPPER_PARITY_PASS"
  }
}
```
