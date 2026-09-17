# V2.2 Phase 8.7 Correctness Baseline Lock

```json
{
  "schemaVersion": "agent-rag-v22-phase87-correctness-baseline-lock-v1",
  "sourceCommit": "a13825ce",
  "eligibilityVersion": "agent-rag-v22-canonical-evidence-eligibility-v1",
  "expirationSemantics": "effectiveFrom <= evaluationTimeUtc AND (expiresAt is null OR evaluationTimeUtc < expiresAt)",
  "variableKSemantics": "maximumFinalK is an upper bound; accepted evidence may be fewer than maximumFinalK",
  "noBackfillSemantics": "low-score and ineligible evidence are never appended to fill maximumFinalK",
  "rerankerModelId": "BAAI/bge-reranker-v2-m3",
  "rerankerRevision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
  "rerankerFingerprint": "cf87d1dfe5081feb734ff8635b7781f3f77c4bab3939ffba3a6d16a653611e82",
  "benchmarkHash": "222802bed4ac363db5dbdfba5b362584ff05e2788f606781bfa2cfbb7e39a0b6",
  "knowledgeSnapshotHash": "6a47565e19594a6c527df10e34c63af004a6080f80f1817d697d28e828746a94",
  "oldCandidatePoolHash": "988815fd359b70b4d08ccc589b29299bf6fcf5419b1a92a97c2c9cc327810d09",
  "correctnessGateEvidenceHash": "3315e07be31ca879deb04cb1bf7ca2d85f30c903f2c64991d6860e7ce0221ee7",
  "answerabilityBlockedEvidenceHash": "c49ee8a5de2e5b5addbdd99e6af6f31bafc896bc8239a47decc9da9d3153b454",
  "answerabilityGateHash": "b8564653873e23ff7897e33bee4f459349588f2f809a7858018dcf016779d369",
  "pythonDefaultRegression": "500 passed, 16 skipped",
  "boundary": "CALIBRATION_DATA_INSUFFICIENT remains unresolved before Phase 8.7 ranking gate"
}
```
