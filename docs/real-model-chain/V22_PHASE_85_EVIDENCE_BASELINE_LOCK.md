# V2.2 Phase 8.5 Evidence Baseline Lock

{
  "baselineCommit": "1dfa8359",
  "benchmarkHash": "222802bed4ac363db5dbdfba5b362584ff05e2788f606781bfa2cfbb7e39a0b6",
  "calibrationHash": "5b49e660cc2d2186abdbed642fcae70ba9e8e7c4cd56b1c7c1262887c4dd608b",
  "createdAtUtc": "2026-07-22T14:57:55Z",
  "evaluationHash": "16e55999a3305e0c9123ce73f3e940846e678ea45b6aaf93947acc29096e778c",
  "evidenceHashes": {
    "adminLintGateSha256": "7eb4c847ededb9a0f0ead148170e11e61887c0472fc27b4e83a266fd0ab8ed7b",
    "llmGateSha256": "92945111d3c6d12c54145e9b95ad24961e9ed8458041fd0a19473b7b6ad96d2d",
    "markerGateSha256": "35aaad661aa95ec17971f39f47a086d8cee0d6b9feda570499d2db1850d4a5a3",
    "oldE2eSha256": "77d431fed64b854cbb75c6380d40b1e8ad392aec69e83eef51d3882b994ae81e",
    "oldSoakSha256": "8dcd45f444f11ae0f4c0cc2743a84e7f7dd4ef9344df3ff3647d80dd64746b4e",
    "rerankerBenchmarkSha256": "cb7d7f5cf3ec783bffd9d33dcbe4625ecbb0ef8f1dc5908fc875ec3a82625529"
  },
  "knowledgeHash": "6a47565e19594a6c527df10e34c63af004a6080f80f1817d697d28e828746a94",
  "notes": [
    "The old soak proves stability of the always-return-top-k runtime only.",
    "If a formal evidence rejection policy is integrated into runtime, E2E and 1800-second soak must be rerun.",
    "Local asset paths are intentionally omitted."
  ],
  "rerankerFingerprint": "cf87d1dfe5081feb734ff8635b7781f3f77c4bab3939ffba3a6d16a653611e82",
  "rerankerModelId": "BAAI/bge-reranker-v2-m3",
  "rerankerRevision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
  "schemaVersion": "agent-rag-v22-phase85-evidence-baseline-lock-v1"
}
