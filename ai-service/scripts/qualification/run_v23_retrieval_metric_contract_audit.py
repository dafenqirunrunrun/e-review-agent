from __future__ import annotations

import argparse
import os
from pathlib import Path

from v23_candidate_fusion_common import DOCS, OUT, FusionConfig, evaluate_config, file_sha256, load_dataset, prepare_runtime, read_json, write_json, write_text
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))
    cases, manifest = load_dataset()
    payload = benchmark_payload()
    provider, runtime = prepare_runtime(payload)
    try:
        corrected = evaluate_config([case for case in cases if case["label"] == "answerable"], runtime, FusionConfig(20, 20, 20, 100))
    finally:
        try:
            provider.close()
        except Exception:
            pass
    old = read_json(OUT / "v23-current-retrieval-baseline.json")
    audit = build_audit(old, corrected, manifest)
    write_json(OUT / "v23-retrieval-metric-contract-audit.json", audit)
    write_json(OUT / "v23-current-retrieval-baseline-corrected.json", corrected_baseline(old, corrected, manifest))
    write_text(DOCS / "V23_PHASE_92_INPUT_BASELINE_LOCK.md", render_lock(manifest, old))
    write_text(DOCS / "V23_RETRIEVAL_METRIC_CONTRACT.md", render_contract(audit, corrected))
    print("E_REVIEW_V23_RETRIEVAL_METRIC_CONTRACT_PASS" if audit["status"] == "PASS" else "E_REVIEW_V23_RETRIEVAL_METRIC_CONTRACT_BLOCKED")
    return 0 if audit["status"] == "PASS" else 1


def build_audit(old: dict, corrected: dict, manifest: dict) -> dict:
    raw = corrected["rawUnionMetrics"]["coverageAt100"]
    raw_recall = corrected["rawUnionMetrics"]["recallAt100"]
    dense = corrected["denseMetrics"]["coverageAt100"]
    dense_recall = corrected["denseMetrics"]["recallAt100"]
    bm25 = corrected["bm25Metrics"]["coverageAt100"]
    bm25_recall = corrected["bm25Metrics"]["recallAt100"]
    checks = {
        "oldMetricContradictionDetected": old.get("denseMetrics", {}).get("recallAt100", 0) > old.get("unionOracleMetrics", {}).get("recallAt100", 0),
        "rawUnionCoverageGteDenseCoverage": raw >= dense,
        "rawUnionCoverageGteBm25Coverage": raw >= bm25,
        "rawUnionRecallGteDenseRecall": raw_recall >= dense_recall,
        "rawUnionRecallGteBm25Recall": raw_recall >= bm25_recall,
        "recallCoverageSeparated": "coverageAt100" in corrected["rawUnionMetrics"] and "recallAt100" in corrected["rawUnionMetrics"],
        "rawBudgetedRrfSeparated": all(key in corrected for key in ["rawUnionMetrics", "unionBudgetedMetrics", "rrfMetrics"]),
        "noAnswerExcludedFromAnswerableRecall": corrected["caseCount"] == manifest["answerableCases"],
    }
    return {
        "schemaVersion": "agent-rag-v23-retrieval-metric-contract-audit-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "oldDenseRecallAt100": old.get("denseMetrics", {}).get("recallAt100", 0),
        "oldReportedUnionOracleAt100": old.get("unionOracleMetrics", {}).get("recallAt100", 0),
        "rootCause": "old Union Oracle was budgeted/ranked and truncated, not raw BM25 TopK union Dense TopK",
        "correctedBm25RecallAt100": bm25_recall,
        "correctedBm25CoverageAt100": bm25,
        "correctedDenseRecallAt100": dense_recall,
        "correctedDenseCoverageAt100": dense,
        "correctedRawUnionRecallAt100": corrected["rawUnionMetrics"]["recallAt100"],
        "correctedRawUnionCoverageAt100": corrected["rawUnionMetrics"]["coverageAt100"],
        "correctedRrfRecallAt100": corrected["rrfMetrics"]["recallAt100"],
        "correctedRrfCoverageAt100": corrected["rrfMetrics"]["coverageAt100"],
    }


def corrected_baseline(old: dict, corrected: dict, manifest: dict) -> dict:
    return {
        "schemaVersion": "agent-rag-v23-current-retrieval-baseline-corrected-v1",
        "status": "COMPLETE",
        "datasetHash": manifest["datasetHash"],
        "oldBaselineHash": old.get("baselineMetricsHash", ""),
        "correctedBaselineHash": corrected["configurationHash"],
        "bm25Recall": corrected["bm25Metrics"],
        "denseRecall": corrected["denseMetrics"],
        "rawUnionRecall": corrected["rawUnionMetrics"],
        "rrfRecall": corrected["rrfMetrics"],
        "unionBudgetedRecall": corrected["unionBudgetedMetrics"],
        "latencyP95": old.get("latencyP95", 0),
        "configuration": corrected["configuration"],
    }


def render_lock(manifest: dict, old: dict) -> str:
    files = [
        "v23-retrieval-qualification-v1-manifest.json",
        "v23-current-retrieval-baseline.json",
        "v23-retrieval-miss-case-analysis.json",
        "v23-retrieval-miss-taxonomy-summary.json",
        "v23-retrieval-optimization-priority-decision.json",
    ]
    hashes = "\n".join(f"- `{name}`: `{file_sha256(OUT / name)}`" for name in files)
    miss = read_json(OUT / "v23-retrieval-miss-case-analysis.json")
    return f"""# V2.3 Phase 9.2 Input Baseline Lock

| Item | Value |
|---|---|
| sourceCommit | `1a3c0c6a` |
| datasetVersion | `{manifest['datasetVersion']}` |
| datasetHash | `{manifest['datasetHash']}` |
| caseIdsHash | `{manifest['caseIdsHash']}` |
| knowledgeSnapshotHash | `{manifest['knowledgeSnapshotHash']}` |
| indexManifestHash | `{manifest['indexManifestHash']}` |
| baselineHash | `{old.get('baselineMetricsHash', '')}` |
| diagnosticCaseCount | `{miss.get('diagnosticCases', 0)}` |
| diagnosticFutureQualificationAllowed | `false` |

Frozen input artifact hashes:

{hashes}
"""


def render_contract(audit: dict, corrected: dict) -> str:
    return f"""# V2.3 Retrieval Metric Contract

Phase 9.2 separates Raw Union Oracle, Union Budgeted and RRF metrics.

The old report showed Dense Recall@100 `{audit['oldDenseRecallAt100']}` greater than reported Union Oracle@100 `{audit['oldReportedUnionOracleAt100']}`. This was a metric naming problem: the old Union value was ranked/budgeted, not raw union.

Corrected contract:

- Raw Union Oracle@K = BM25 TopK union Dense TopK, not truncated to K after union.
- Union Budgeted@N = raw union sorted by explicit min-rank rule and truncated to N.
- RRF@N = BM25 and Dense fused by reciprocal rank fusion and truncated to N.
- Recall and Coverage are reported separately.
- No-answer cases are excluded from answerable recall and reported separately.

Corrected Raw Union Coverage@100: `{audit['correctedRawUnionCoverageAt100']}`

Corrected RRF Coverage@100: `{audit['correctedRrfCoverageAt100']}`

Gate status: `{audit['status']}`
"""


if __name__ == "__main__":
    raise SystemExit(main())
