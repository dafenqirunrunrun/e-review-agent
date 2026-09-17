# V2.3 BGE-M3 Sparse Index Qualification

Index integrity and repeatability passed, but the Phase 9.4B Index Gate is blocked by the frozen empty-vector threshold.

```text
E_REVIEW_V23_BGE_M3_SPARSE_INDEX_BLOCKED
emptyVectorChunkRate = 0.63398693
allowedEmptyVectorChunkRate = 0.001
```

```json
{
  "build": {
    "averageNonZeroDimensions": 2.785714,
    "buildDurationMs": 19808.186,
    "contentHashMismatchCount": 0,
    "documentsPerSecond": 7.724079,
    "duplicateChunkCount": 0,
    "eligibleChunkCount": 153,
    "emptyVectorChunkCount": 97,
    "emptyVectorChunkRate": 0.63398693,
    "encodedChunkCount": 153,
    "firstEncodeDurationMs": 66.685,
    "indexFingerprint": "b90d071e4dd314831b95a4e933e2b2eee743be2cf1806b1e3e63fa1a9965cc72",
    "indexSizeBytes": 77341,
    "indexedChunkCount": 56,
    "invalidWeightChunkCount": 0,
    "manifestHash": "06da5bd2f1ff1ebc1d0a1e1204c4b172101578ea8da7a42c10d67b985f5ae6f5",
    "medianNonZeroDimensions": 3.0,
    "modelLoadDurationMs": 2031.203,
    "p95NonZeroDimensions": 6.0,
    "peakCpuMemoryBytes": 0,
    "peakCudaMemoryBytes": 1163904512,
    "schemaVersion": "agent-rag-v23-bge-m3-sparse-index-build-v1",
    "sensitivePolicy": {
      "externalIndexPathPersistedInRepo": false,
      "storesFullChunks": false,
      "storesFullQueries": false,
      "storesTokenWeightMapInRepoArtifacts": false
    },
    "status": "COMPLETE",
    "steadyStateEncodeP50Ms": 57.533,
    "steadyStateEncodeP95Ms": 63.138,
    "steadyStateEncodeP99Ms": 63.138,
    "totalNonZeroDimensions": 156,
    "warmupDurationMs": 2727.661
  },
  "integrity": {
    "allContentHashesConsistent": true,
    "allEligibleChunksEncoded": true,
    "allIndexedChunksFromSameSnapshot": true,
    "allSparseVectorsValid": true,
    "disabledIndexedCount": 0,
    "expiredIndexedCount": 0,
    "inactiveIndexedCount": 0,
    "schemaVersion": "agent-rag-v23-bge-m3-sparse-index-integrity-v1",
    "status": "PASS",
    "tenantViolationCount": 0,
    "tombstonedIndexedCount": 0
  },
  "manifest": {
    "buildDurationMs": 19808.186,
    "canonicalIndexHash": "b90d071e4dd314831b95a4e933e2b2eee743be2cf1806b1e3e63fa1a9965cc72",
    "contentHashMismatchCount": 0,
    "datasetHash": "d638d44c69e1e678c2f990fd193af23d2ac18962b6e2be5eaf1ffd19e4575e47",
    "datasetVersion": "v23-retrieval-qualification-v2",
    "duplicateChunkCount": 0,
    "eligibleChunkCount": 153,
    "emptyVectorChunkCount": 97,
    "emptyVectorChunkIdsHash": "10746d669c5c066454b2ae1ce67dcf7c14fdf709d504c63972f13116175ef6db",
    "encodedChunkCount": 153,
    "environmentFingerprint": "9820236f02e050fa189890df8dcf3a6055c7a6690d91d54f1afbddd1c8df0167",
    "evaluationTimeUtc": "2026-07-23T00:00:00Z",
    "indexFingerprint": "b90d071e4dd314831b95a4e933e2b2eee743be2cf1806b1e3e63fa1a9965cc72",
    "indexFormatVersion": "agent-rag-v23-bge-m3-sparse-index-v1",
    "indexGeneration": 1,
    "indexSizeBytes": 77341,
    "indexVersion": "v23-bge-m3-sparse-index",
    "indexedChunkCount": 56,
    "invalidWeightChunkCount": 0,
    "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
    "manifestHash": "06da5bd2f1ff1ebc1d0a1e1204c4b172101578ea8da7a42c10d67b985f5ae6f5",
    "metadataHash": "82e889ff7b07e743ae1902c73ccfcc38f10b69a33f86a20fb70794b9e2821cd3",
    "minimumSparseWeight": 0.0,
    "modelFingerprint": "a36441812a43bc60e2464af3cc3ffc4d466fc2dc9a52d921264b0109c39094a2",
    "modelId": "BAAI/bge-m3",
    "modelRevision": "external-existing",
    "postingHash": "735b637356a61eada087f33d28c13a37e95c9075ba93a5fd988300e046f7e5c0",
    "retrievalContentVersion": "content-only",
    "schemaVersion": "agent-rag-v23-bge-m3-sparse-index-manifest-v1",
    "scoreType": "BGE_M3_LEARNED_SPARSE_DOT_PRODUCT",
    "vectorHash": "58d1904692fe9c8ace3178ab117d68a5564e870bc87c1eb357f69425c5669902"
  },
  "repeatability": {
    "canonicalIndexHash": "b90d071e4dd314831b95a4e933e2b2eee743be2cf1806b1e3e63fa1a9965cc72",
    "canonicalIndexHashStable": true,
    "fullVectorHash": "58d1904692fe9c8ace3178ab117d68a5564e870bc87c1eb357f69425c5669902",
    "metadataHashStable": true,
    "postingHashStable": true,
    "resultRankingHashStable": true,
    "schemaVersion": "agent-rag-v23-bge-m3-sparse-index-repeatability-v1",
    "status": "PASS",
    "subsetVectorHash": "af1a501ae0064edfd0e45e9368ae16f1244cd81a3c4823a8453f2058c8204fec"
  }
}
```
