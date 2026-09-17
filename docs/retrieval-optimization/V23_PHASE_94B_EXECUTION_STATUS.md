# V2.3 Phase 9.4B Execution Status

Status: `BLOCKED_AT_INDEX_GATE`

Phase 9.4B built a governed BGE-M3 sparse inverted index from the locked content-only knowledge snapshot, but the Index Gate blocked retrieval experiments because the empty sparse document vector rate exceeded the frozen threshold.

Index result:

```text
eligibleChunkCount = 153
encodedChunkCount = 153
indexedChunkCount = 56
emptyVectorChunkCount = 97
emptyVectorChunkRate = 0.63398693
invalidWeightChunkCount = 0
contentHashMismatchCount = 0
expiredIndexedCount = 0
inactiveIndexedCount = 0
disabledIndexedCount = 0
tenantViolationCount = 0
canonicalIndexHashStable = true
```
Resource result:

```text
buildDurationMs = 19808.186
documentsPerSecond = 7.724079
modelLoadDurationMs = 2031.203
steadyStateEncodeP50Ms = 57.533
steadyStateEncodeP95Ms = 63.138
peakCudaMemoryBytes = 1163904512
indexSizeBytes = 77341
```

Gate decision:

```text
E_REVIEW_V23_BGE_M3_SPARSE_INDEX_BLOCKED
PHASE_94C_THREE_WAY_FUSION_ALLOWED = false
```

Retrieval calibration was not run because Phase 9.4B requires the Index Gate to pass before any sparse retrieval experiment.

Resume-ready note:

```text
Problem: real BGE-M3 sparse runtime worked, but the content-only benchmark chunks are short and repetitive; BGE-M3 returned empty learned sparse vectors for 97 of 153 eligible chunks.
Technical action: built an external governed inverted index with eligibility-before-indexing, deterministic postings, vector validation, repeatability hashing and safe repository artifacts.
Result: index integrity and repeatability passed, but empty vector rate 0.63398693 exceeded the frozen 0.001 threshold, so sparse retrieval and three-way fusion were blocked.
Decision: do not enter Phase 9.4C until sparse vector coverage is improved by a separately governed representation/indexing change.
```
