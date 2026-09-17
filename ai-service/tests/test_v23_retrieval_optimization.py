from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def _read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_v23_retrieval_dataset_manifest_is_unseen_and_sanitized():
    manifest = _read("v23-retrieval-qualification-v1-manifest.json")
    assert manifest["datasetVersion"] == "v23-retrieval-qualification-v1"
    assert manifest["totalCases"] == 300
    assert manifest["answerableCases"] == 240
    assert manifest["noAnswerCases"] == 60
    assert manifest["calibrationCounts"]["answerable"] >= 100
    assert manifest["evaluationCounts"]["answerable"] >= 100
    assert manifest["challengeCounts"]["answerable"] >= 40
    assert manifest["leakageAudit"]["oldDiagnosticCaseOverlap"] == 0
    assert manifest["leakageAudit"]["oldQueryHashOverlap"] == 0
    assert manifest["leakageAudit"]["caseFamilyCrossSplitCount"] == 0
    assert manifest["leakageAudit"]["documentFamilyCrossSplitCount"] == 0
    assert all("query" not in case and case["queryStored"] is False for case in manifest["cases"])


def test_v23_retrieval_dataset_gate_passes_without_quality_claim():
    gate = _read("v23-retrieval-dataset-gate.json")
    assert gate["status"] == "PASS"
    assert gate["checks"]["answerableLabelAuditComplete"] is True
    assert gate["checks"]["noAnswerCorpusAuditComplete"] is True
    assert "RETRIEVAL_QUALITY_VERIFIED" in gate["forbiddenClaims"]


def test_v23_current_retrieval_baseline_is_complete_not_quality_pass():
    baseline = _read("v23-current-retrieval-baseline.json")
    gate = _read("v23-retrieval-baseline-gate.json")
    assert baseline["status"] == "COMPLETE"
    assert gate["status"] == "PASS"
    assert baseline["bm25Executions"] == baseline["denseExecutions"] == baseline["rrfExecutions"] == 240
    for key in ("bm25Metrics", "denseMetrics", "rrfMetrics", "unionOracleMetrics"):
        assert baseline[key]["recallAt100"] >= baseline[key]["recallAt10"]
    assert gate["qualityClaim"] == "BASELINE_COMPLETE_NOT_QUALITY_PASS"


def test_v23_retrieval_miss_analysis_consumes_old_miss_cases():
    analysis = _read("v23-retrieval-miss-case-analysis.json")
    taxonomy = _read("v23-retrieval-miss-taxonomy-summary.json")
    gate = _read("v23-retrieval-miss-analysis-gate.json")
    assert analysis["diagnosticCases"] == 90
    assert analysis["futureQualificationUseAllowed"] is False
    assert taxonomy["consumed"] is True
    assert taxonomy["candidateKRecoverable"] == 90
    assert taxonomy["unionTop100Coverage"] == 1.0
    assert gate["status"] == "PASS"
    assert all(row["primaryMissType"] for row in analysis["cases"])
    assert all("query" not in row for row in analysis["cases"])


def test_v23_phase_90_91_gate_passes_as_foundation_only():
    gate = _read("v23-phase-90-91-gate.json")
    assert gate["status"] == "PASS"
    assert "E_REVIEW_V23_RETRIEVAL_OPTIMIZATION_FOUNDATION_PASS" in gate["tokens"]
    assert gate["qualityClaim"] == "FOUNDATION_PASS_NOT_RETRIEVAL_QUALITY_PASS"
    assert gate["checks"]["noSensitiveDataLeak"] is True
