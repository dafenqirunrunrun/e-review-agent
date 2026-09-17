# V2.2 Phase 8.6 Correctness Baseline Lock

```json
{
  "schemaVersion": "agent-rag-v22-phase86-correctness-baseline-lock-v1",
  "sourceCommit": "b84aaf49",
  "rerankerModelId": "BAAI/bge-reranker-v2-m3",
  "rerankerRevision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
  "rerankerFingerprint": "cf87d1dfe5081feb734ff8635b7781f3f77c4bab3939ffba3a6d16a653611e82",
  "benchmarkHash": "222802bed4ac363db5dbdfba5b362584ff05e2788f606781bfa2cfbb7e39a0b6",
  "knowledgeHash": "6a47565e19594a6c527df10e34c63af004a6080f80f1817d697d28e828746a94",
  "calibrationHash": "5b49e660cc2d2186abdbed642fcae70ba9e8e7c4cd56b1c7c1262887c4dd608b",
  "evaluationHash": "16e55999a3305e0c9123ce73f3e940846e678ea45b6aaf93947acc29096e778c",
  "evaluationTimeUtc": "2026-07-22T00:00:00Z",
  "timezone": "UTC",
  "phase85FalseEvidenceTotal": 35,
  "phase85FalseEvidenceCases": 7,
  "phase85ExpiredEvidenceAccepted": 3,
  "phase85PassingPolicies": 0,
  "phase85EvidenceSha256": {
    "falseEvidenceAudit": "77841fc7defc0b38b8d4ef204403c23ad14c1e3918eaf1f2cb0b089712252e8d",
    "rejectionCalibrationDecision": "cb0a0c73b709dd3fe566fcd7146624c30d81fc2f6dd5a5d2366d7c8dfd4d4b69",
    "rejectionCalibrationReport": "f1ce04eadd76218ee7516df4c422ef682613acea778be20ec98d105b9d30d968"
  },
  "phase86CorrectnessGateSha256": "3315e07be31ca879deb04cb1bf7ca2d85f30c903f2c64991d6860e7ce0221ee7",
  "decision": "PHASE_85_EVIDENCE_LOCKED_FOR_FAILURE_DIAGNOSIS_ONLY"
}
```

The Phase 8.5 artifacts remain frozen as evidence of the old always-return-top-k pipeline failure. They are not treated as successful results for the Phase 8.6 pipeline.
