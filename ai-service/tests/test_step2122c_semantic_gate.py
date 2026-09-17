from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_semantic_result_schema_and_count():
    rows = load_jsonl("semantic_rejudge_results_v1.jsonl")
    required = {
        "caseId", "verdict", "riskTypesAssessment", "severityAssessment",
        "expressionAssessment", "multiRiskAssessment", "abstentionAssessment",
        "naturalChinese", "suggestedRiskTypes", "suggestedSeverity", "reasonCodes",
    }
    assert len(rows) == 81
    assert all(required == set(row) for row in rows)
    assert all(row["verdict"] in {"PASS", "FAIL", "UNCERTAIN"} for row in rows)


def test_boundary_result_schema_and_count():
    rows = load_jsonl("boundary_rejudge_results_v1.jsonl")
    required = {
        "caseId", "boundaryVerdict", "boundaryTypeAssessment", "challengeValue",
        "keywordShortcutRisk", "abstentionBoundaryValid", "possibleMissingRiskTypes",
        "suggestedBoundaryType", "reasonCodes",
    }
    assert len(rows) == 41
    assert all(required == set(row) for row in rows)
    assert all(row["challengeValue"] in {"HIGH", "MEDIUM", "LOW"} for row in rows)


def test_abstention_contract_is_judged_separately():
    results = load_jsonl("semantic_rejudge_results_v1.jsonl")
    abstention = [row for row in results if row["abstentionAssessment"] != "NOT_APPLICABLE"]
    assert len(abstention) == 5
    assert all(row["abstentionAssessment"] == "CORRECT" for row in abstention)
    metrics = json.loads((DATA / "semantic_gate_metrics_v1.json").read_text(encoding="utf-8"))
    assert metrics["abstention"] == {"caseCount": 5, "correctCount": 5, "incorrectCount": 0, "uncertainCount": 0, "abstentionAccuracy": 1.0}


def test_semantic_and_boundary_metric_calculation():
    metrics = json.loads((DATA / "semantic_gate_metrics_v1.json").read_text(encoding="utf-8"))
    assert metrics["calibration"] == {"total": 120, "pass": 96, "fail": 23, "uncertain": 1, "passRate": 0.8}
    assert metrics["boundary"]["total"] == 60
    assert metrics["boundary"]["pass"] == 54
    assert metrics["boundary"]["fail"] == 6
    assert metrics["boundary"]["passRate"] == 0.9
    assert metrics["boundary"]["highMediumRatio"] == 0.833333


def test_shortcut_ratio_and_multi_risk_tracking_fail_honestly():
    metrics = json.loads((DATA / "semantic_gate_metrics_v1.json").read_text(encoding="utf-8"))
    assert metrics["boundary"]["keywordShortcutCount"] == 22
    assert metrics["boundary"]["keywordShortcutRatio"] == 0.366667
    assert metrics["semantic"]["missedMultiRiskCount"] == 13
    assert metrics["thresholds"]["keywordShortcutPass"] is False
    assert metrics["thresholds"]["multiRiskSystematicErrorPass"] is False
    assert metrics["gate"] == "FAIL"


def test_frozen_hash_unchanged():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() == FROZEN_SHA


def test_final_freeze_hashes_and_single_judge_provenance():
    manifest = json.loads((DATA / "dataset_final_freeze_manifest.json").read_text(encoding="utf-8"))
    final_revision = manifest["datasetVersion"] == "evaluation-dataset-demo-v2.2-final"
    calibration_name = "router_calibration_candidate_demo_final.jsonl" if final_revision else "router_calibration_candidate_demo_v2.jsonl"
    boundary_name = "boundary_challenge_demo_final.jsonl" if final_revision else "boundary_challenge_demo_v2.jsonl"
    assert manifest["calibrationHash"] == hashlib.sha256((DATA / calibration_name).read_bytes()).hexdigest().upper()
    assert manifest["boundaryHash"] == hashlib.sha256((DATA / boundary_name).read_bytes()).hexdigest().upper()
    semantic_name = "final_semantic_rejudge_results.jsonl" if final_revision else "semantic_rejudge_results_v1.jsonl"
    boundary_result_name = "final_boundary_rejudge_results.jsonl" if final_revision else "boundary_rejudge_results_v1.jsonl"
    assert manifest["semanticResultsHash"] == hashlib.sha256((DATA / semantic_name).read_bytes()).hexdigest().upper()
    assert manifest["boundaryResultsHash"] == hashlib.sha256((DATA / boundary_result_name).read_bytes()).hexdigest().upper()
    assert manifest["semanticJudgeType"] == "CODEX_SINGLE_JUDGE"
    assert manifest["humanGold"] is False
    assert manifest["multiModelValidated"] is False
    assert manifest["independentJudge"] is False
    assert manifest["demoReady"] is final_revision
    assert manifest["freezeStatus"] == ("SEMANTICALLY_ACCEPTED_FOR_DEMO" if final_revision else "NOT_FROZEN_GATE_FAILED")
    assert "SINGLE_JUDGE_LIMITATION" in manifest["limitations"]


def test_no_final_minimal_repair_when_defects_exceed_limit():
    metrics = json.loads((DATA / "semantic_gate_metrics_v1.json").read_text(encoding="utf-8"))
    assert metrics["finalMinimalRepair"]["performed"] is False
    assert metrics["semantic"]["riskTypeMismatchCount"] > 5


def test_security_scan():
    paths = [
        DATA / "semantic_rejudge_results_v1.jsonl",
        DATA / "boundary_rejudge_results_v1.jsonl",
        DATA / "semantic_gate_metrics_v1.json",
        DATA / "dataset_final_freeze_manifest.json",
    ]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert not re.search(r"reviewer(identity|id|name)", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
