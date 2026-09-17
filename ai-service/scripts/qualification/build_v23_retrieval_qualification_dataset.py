from __future__ import annotations

import json
from pathlib import Path

from v23_retrieval_common import (
    DOCS,
    OUT,
    REAL_MODEL_OUT,
    SOURCE_COMMIT,
    build_dataset_manifest,
    build_v23_cases,
    read_json,
    sha256_file,
    stable_hash,
    write_json,
    write_text,
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    cases = build_v23_cases()
    manifest = build_dataset_manifest(cases)
    leakage = manifest["leakageAudit"]
    write_json(OUT / "v23-retrieval-dataset-leakage-audit.json", leakage)
    write_json(OUT / "v23-retrieval-qualification-v1-manifest.json", manifest)
    write_json(OUT / "v23-current-retrieval-configuration.json", current_configuration(manifest))
    write_text(DOCS / "V23_PHASE_90_BASELINE_LOCK.md", render_baseline_lock(manifest))
    write_text(DOCS / "V23_RETRIEVAL_QUALIFICATION_DATASET.md", render_dataset_doc(manifest))
    print("E_REVIEW_V23_RETRIEVAL_DATASET_BUILT")
    print(manifest["datasetHash"])
    return 0


def current_configuration(manifest: dict) -> dict:
    candidate_manifest = read_json(REAL_MODEL_OUT / "v22-answerability-canonical-candidate-pool-manifest.json")
    reranker_manifest = read_json(REAL_MODEL_OUT / "v22-reranker-benchmark-manifest.json")
    return {
        "schemaVersion": "agent-rag-v23-current-retrieval-configuration-v1",
        "sourceCommit": SOURCE_COMMIT,
        "datasetVersion": manifest["datasetVersion"],
        "datasetHash": manifest["datasetHash"],
        "bm25": {
            "tokenizer": "project BM25Retriever default lexical tokenizer",
            "analyzer": "lowercase token matching from app.rag.sparse_retriever",
            "topK": [5, 10, 20, 50, 100],
            "minimumScore": "not tuned in Phase 9.0-9.1",
            "fieldBoosts": "not tuned in Phase 9.0-9.1",
        },
        "dense": {
            "model": "BAAI/bge-m3",
            "revision": "recorded in local qualification asset manifest when supplied; absolute paths are not persisted",
            "dimension": "read from runtime/index trace during baseline",
            "normalize": "current provider default",
            "similarity": "FAISS index metric from runtime",
            "topK": [5, 10, 20, 50, 100],
        },
        "rrf": {
            "rankConstant": 60,
            "rankWindow": 100,
            "bm25Weight": 1.0,
            "denseWeight": 0.5,
            "note": "configuration frozen for diagnosis; no Phase 9.0-9.1 tuning",
        },
        "eligibility": {
            "tenant": True,
            "active": True,
            "disabled": True,
            "effectiveFrom": True,
            "expiresAt": True,
            "duplicate": True,
            "tombstone": True,
            "version": "canonical evidence eligibility as of v2.2 baseline",
        },
        "candidatePool": {
            "maximumCandidates": 100,
            "deduplication": "chunkId",
            "sourceRouting": "tenant plus public scope",
            "sourceCandidatePoolHash": candidate_manifest.get("candidatePoolHash", ""),
        },
        "hashes": {
            "v22AnswerableRankingGate": sha256_file(REAL_MODEL_OUT / "v22-answerable-ranking-gate.json"),
            "v22CandidatePoolManifest": sha256_file(REAL_MODEL_OUT / "v22-answerability-canonical-candidate-pool-manifest.json"),
            "v22RerankerRootCauseDecision": sha256_file(REAL_MODEL_OUT / "v22-reranker-root-cause-decision.json"),
            "v22RerankerCaseLevelErrorAnalysis": sha256_file(REAL_MODEL_OUT / "v22-reranker-case-level-error-analysis.json"),
            "v22BenchmarkHash": reranker_manifest.get("benchmarkHash", ""),
        },
        "configurationHash": stable_hash({"dataset": manifest["datasetHash"], "candidatePool": candidate_manifest.get("candidatePoolHash", ""), "rrfK": 60}),
    }


def render_baseline_lock(manifest: dict) -> str:
    config = current_configuration(manifest)
    return f"""# V2.3 Phase 9.0 Baseline Lock

This lock freezes the v2.2 retrieval and reranker diagnostic boundary before Phase 9.0-9.1 analysis.

| Item | Value |
|---|---|
| sourceCommit | `{SOURCE_COMMIT}` |
| knowledgeSnapshotHash | `{manifest['knowledgeSnapshotHash']}` |
| indexManifestHash | `{manifest['indexManifestHash']}` |
| configurationHash | `{config['configurationHash']}` |
| answerableCaseCount | `164` |
| retrievalEligibleCount | `74` |
| retrievalMissedCount | `90` |
| candidateCoverage | `0.4512195` |
| consumedRerankerDiagnosticCount | `74` |
| futureQualificationUseAllowed | `false` |

Frozen source artifact hashes:

- `v22-answerable-ranking-gate.json`: `{config['hashes']['v22AnswerableRankingGate']}`
- `v22-answerability-canonical-candidate-pool-manifest.json`: `{config['hashes']['v22CandidatePoolManifest']}`
- `v22-reranker-root-cause-decision.json`: `{config['hashes']['v22RerankerRootCauseDecision']}`
- `v22-reranker-case-level-error-analysis.json`: `{config['hashes']['v22RerankerCaseLevelErrorAnalysis']}`

Boundary:

- The 74 retrieval-eligible cases remain consumed reranker diagnostics.
- The 90 retrieval-missed cases may be analyzed in Phase 9.1, then must become consumed retrieval diagnostics.
- Phase 9.0-9.1 does not tune retrieval runtime, BM25, dense retrieval, RRF, chunking, query expansion, sparse retrieval, or multi-vector retrieval.
"""


def render_dataset_doc(manifest: dict) -> str:
    return f"""# V2.3 Unseen Retrieval Qualification Dataset

Dataset version: `{manifest['datasetVersion']}`

Dataset hash: `{manifest['datasetHash']}`

This dataset is a new synthetic, project-owned, unseen retrieval qualification benchmark for Phase 9.2 and later retrieval optimization work. It is separated from the previously consumed v2.2 reranker and retrieval diagnostic cases.

## Counts

| Split | Answerable | No-answer |
|---|---:|---:|
| Calibration | {manifest['calibrationCounts'].get('answerable', 0)} | {manifest['calibrationCounts'].get('no_answer', 0)} |
| Evaluation | {manifest['evaluationCounts'].get('answerable', 0)} | {manifest['evaluationCounts'].get('no_answer', 0)} |
| Challenge | {manifest['challengeCounts'].get('answerable', 0)} | {manifest['challengeCounts'].get('no_answer', 0)} |

Total cases: `{manifest['totalCases']}`

Answerable cases: `{manifest['answerableCases']}`

No-answer cases: `{manifest['noAnswerCases']}`

## Governance

- Full query text is not persisted in committed artifacts.
- Full chunk text is not persisted in committed artifacts.
- Case family and document family do not cross split.
- Answerable labels point to valid eligible chunks at the fixed evaluation time.
- No-answer cases use unsupported synthetic query families and are marked with corpus audit hashes.

## Leakage Audit

```json
{json.dumps(manifest['leakageAudit'], ensure_ascii=False, indent=2, sort_keys=True)}
```

## Label Audit

```json
{json.dumps(manifest['labelAudit'], ensure_ascii=False, indent=2, sort_keys=True)}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
