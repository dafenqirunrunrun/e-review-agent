# V2.3 Candidate Fusion Calibration

Decision: `VALID_WEIGHTED_RRF_CONFIGURATION`

## Experiment Note

Problem: the frozen v2.3 baseline showed that BM25 and Dense could already find most relevant evidence in their deeper Top-100 pools, but the current RRF/post-fusion candidate budget dropped many deep-ranked hits before the deterministic reranker.

Optimization: kept `maximumFinalK=5` and `allowBackfill=false`, then searched only the calibration split over bounded `bm25RetrieveK`, `denseRetrieveK`, `rrfRankWindow`, `postFusionCandidateK`, and a small fixed set of RRF weights. Evaluation and challenge splits were not used for choosing the configuration.

Selected configuration: `bm25RetrieveK=20`, `denseRetrieveK=100`, `rrfRankWindow=100`, `postFusionCandidateK=20`, `bm25Weight=0.75`, `denseWeight=1.25`, `rrfRankConstant=60`.

Result: calibration `Coverage@20` improved from the corrected baseline `0.579167` to `0.700000` while preserving tenant/expiry/inactive filtering, duplicate deduplication, no-backfill, and final evidence cap constraints.

Resume-ready wording: identified candidate-budget truncation as the dominant Hybrid RAG recall bottleneck, separated raw union oracle from budgeted fusion metrics, and improved answerable evidence capture through bounded RRF window and weight calibration without increasing the LLM context evidence count.

```json
{
  "datasetHash": "d3835de362f936a3f5000395b57c447d1518e63a879e50a08e5198b920761c2d",
  "decision": "VALID_WEIGHTED_RRF_CONFIGURATION",
  "schemaVersion": "agent-rag-v23-candidate-fusion-calibration-decision-v1",
  "selected": {
    "averageCandidateCount": 20,
    "configuration": {
      "allowBackfill": false,
      "bm25RetrieveK": 20,
      "bm25Weight": 0.75,
      "denseRetrieveK": 100,
      "denseWeight": 1.25,
      "maximumFinalK": 5,
      "postFusionCandidateK": 20,
      "rrfRankConstant": 60,
      "rrfRankWindow": 100
    },
    "configurationHash": "ce88dd40b0ada235832348e4f4c1f6e3149692243aef7d07ed5df490af17b3b6",
    "configurationId": "cfg-ce88dd40b0ad",
    "deterministicRerankerMetrics": {
      "caseCount": 100,
      "coverageAt5": 0.3,
      "missCount": 70,
      "mrr": 0.116167,
      "ndcgAt5": 0.160634,
      "recallAt5": 0.3
    },
    "disabledCandidatesAccepted": 0,
    "duplicateCandidates": 0,
    "expiredCandidatesAccepted": 0,
    "inactiveCandidatesAccepted": 0,
    "latencyP50": 158.889,
    "latencyP95": 197.522,
    "latencyP99": 328.367,
    "lowScoreBackfillCount": 0,
    "maximumCandidateCount": 20,
    "oracleCaptureRateAt20": 0.707071,
    "oracleCaptureRateAt30": 0.707071,
    "oracleCaptureRateAtSelectedK": 0.707071,
    "rawUnionMetrics": {
      "caseCount": 100,
      "coverageAt10": 0.53,
      "coverageAt100": 0.99,
      "coverageAt20": 0.77,
      "coverageAt30": 0.87,
      "coverageAt5": 0.26,
      "coverageAt50": 0.92,
      "coverageAt75": 0.98,
      "missCount": 1,
      "mrr": 0.144118,
      "ndcgAt5": 0.105456,
      "recallAt10": 0.53,
      "recallAt100": 0.99,
      "recallAt20": 0.77,
      "recallAt30": 0.87,
      "recallAt5": 0.26,
      "recallAt50": 0.92,
      "recallAt75": 0.98
    },
    "rrfMetrics": {
      "caseCount": 100,
      "coverageAt10": 0.48,
      "coverageAt100": 0.7,
      "coverageAt20": 0.7,
      "coverageAt30": 0.7,
      "coverageAt5": 0.31,
      "coverageAt50": 0.7,
      "coverageAt75": 0.7,
      "missCount": 30,
      "mrr": 0.158176,
      "ndcgAt5": 0.166943,
      "recallAt10": 0.48,
      "recallAt100": 0.7,
      "recallAt20": 0.7,
      "recallAt30": 0.7,
      "recallAt5": 0.31,
      "recallAt50": 0.7,
      "recallAt75": 0.7
    },
    "tenantViolations": 0
  },
  "status": "PASS",
  "validConfigurationCount": 31
}
```
