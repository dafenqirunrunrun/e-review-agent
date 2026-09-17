# V2.3 Phase 9.0 Baseline Lock

This lock freezes the v2.2 retrieval and reranker diagnostic boundary before Phase 9.0-9.1 analysis.

| Item | Value |
|---|---|
| sourceCommit | `e7378b5e` |
| knowledgeSnapshotHash | `6a47565e19594a6c527df10e34c63af004a6080f80f1817d697d28e828746a94` |
| indexManifestHash | `90afa384d48974e333966edbe67b0a66fe7d0b1dd1e851ec71dbeb690748bc0c` |
| configurationHash | `b10def5fad62d13ace86fef1a208473d58bae940d647eb7e3484e21027a52b9f` |
| answerableCaseCount | `164` |
| retrievalEligibleCount | `74` |
| retrievalMissedCount | `90` |
| candidateCoverage | `0.4512195` |
| consumedRerankerDiagnosticCount | `74` |
| futureQualificationUseAllowed | `false` |

Frozen source artifact hashes:

- `v22-answerable-ranking-gate.json`: `851ddee98e3d447ef88940124afcc4f2c80ee37611b8e91d3eac56fc7125b8ac`
- `v22-answerability-canonical-candidate-pool-manifest.json`: `fcbc77942c0b867976a5727474d7dd068c32733128ee0d1ec511a1f05a0595f8`
- `v22-reranker-root-cause-decision.json`: `38a904d90a697513482a52bbb7dacb9a34b8174dcfd85104e89f94d3c6919059`
- `v22-reranker-case-level-error-analysis.json`: `b9b7dd4d6b96451458bc63176e0ff39864946c7a8fe2a6190c3ce881c8dc586a`

Boundary:

- The 74 retrieval-eligible cases remain consumed reranker diagnostics.
- The 90 retrieval-missed cases may be analyzed in Phase 9.1, then must become consumed retrieval diagnostics.
- Phase 9.0-9.1 does not tune retrieval runtime, BM25, dense retrieval, RRF, chunking, query expansion, sparse retrieval, or multi-vector retrieval.
