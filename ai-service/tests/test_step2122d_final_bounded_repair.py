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


def test_changed_case_budget_and_repair_partition():
    log = load_jsonl("final_dataset_repair_log.jsonl")
    assert len(log) == 23
    assert len({row["caseId"] for row in log}) == 23
    assert sum(row["datasetType"] == "calibration" for row in log) == 12
    assert sum(row["datasetType"] == "boundary" for row in log) == 11
    assert len(log) <= 30
    assert all(row["evidenceSpanSummary"] and row["repairReason"] for row in log)


def test_final_dataset_counts_and_frozen_sha():
    assert len(load_jsonl("router_calibration_candidate_demo_final.jsonl")) == 120
    assert len(load_jsonl("boundary_challenge_demo_final.jsonl")) == 60
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() == FROZEN_SHA


def test_all_systematic_multi_risk_repairs_were_rejudged():
    metrics = json.loads((DATA / "final_semantic_metrics.json").read_text(encoding="utf-8"))
    assert metrics["before"]["missedMultiRiskCount"] == 13
    assert metrics["multiRiskRepairedCount"] == 13
    assert metrics["semantic"]["missedMultiRiskCount"] == 0
    assert metrics["thresholds"]["multiRiskSystematicErrorPass"] is True


def test_shortcut_ratio_and_semantic_metric_merge():
    metrics = json.loads((DATA / "final_semantic_metrics.json").read_text(encoding="utf-8"))
    assert metrics["before"]["keywordShortcutCount"] == 22
    assert metrics["boundary"]["keywordShortcutCount"] == 15
    assert metrics["boundary"]["keywordShortcutRatio"] == 0.25
    assert metrics["calibration"] == {"total": 120, "pass": 108, "fail": 11, "uncertain": 1, "passRate": 0.9}
    assert metrics["boundary"]["pass"] == 60
    assert metrics["boundary"]["highMediumRatio"] == 0.883333
    assert all(metrics["thresholds"].values())


def test_abstention_contract_is_byte_semantically_preserved():
    before = {row["caseId"]: row for row in load_jsonl("boundary_challenge_demo_v2.jsonl") if row.get("evaluationTarget") == "ABSTENTION"}
    after = {row["caseId"]: row for row in load_jsonl("boundary_challenge_demo_final.jsonl") if row.get("evaluationTarget") == "ABSTENTION"}
    assert before == after
    assert len(after) == 5
    assert all(row["riskTypes"] == [] and row["benchmarkRiskTypes"] == [] for row in after.values())
    assert all(row["excludeFromRiskTypeMetrics"] is True for row in after.values())


def test_only_changed_cases_receive_final_rejudge():
    repair_ids = {row["caseId"] for row in load_jsonl("final_dataset_repair_log.jsonl")}
    semantic = load_jsonl("final_semantic_rejudge_results.jsonl")
    boundary = load_jsonl("final_boundary_rejudge_results.jsonl")
    assert {row["caseId"] for row in semantic} == repair_ids
    assert len(semantic) == 23
    assert len(boundary) == 11
    assert all(row["verdict"] == "PASS" for row in semantic)
    assert all(row["boundaryVerdict"] == "PASS" for row in boundary)


def test_final_hash_and_single_judge_freeze_provenance():
    manifest = json.loads((DATA / "dataset_final_freeze_manifest.json").read_text(encoding="utf-8"))
    assert manifest["calibrationHash"] == hashlib.sha256((DATA / "router_calibration_candidate_demo_final.jsonl").read_bytes()).hexdigest().upper()
    assert manifest["boundaryHash"] == hashlib.sha256((DATA / "boundary_challenge_demo_final.jsonl").read_bytes()).hexdigest().upper()
    assert manifest["semanticJudgeType"] == "CODEX_SINGLE_JUDGE"
    assert manifest["humanGold"] is False
    assert manifest["multiModelValidated"] is False
    assert manifest["independentJudge"] is False
    assert manifest["calibrationStatus"] == "SEMANTICALLY_REVIEWED_CANDIDATE"
    assert manifest["demoReady"] is True
    assert manifest["freezeStatus"] == "SEMANTICALLY_ACCEPTED_FOR_DEMO"
    assert manifest["datasetSemanticGate"] == "PASS_WITH_SINGLE_JUDGE_LIMITATION"


def test_final_quality_and_security():
    metrics = json.loads((DATA / "final_semantic_metrics.json").read_text(encoding="utf-8"))
    quality = metrics["quality"]
    assert quality["exactDuplicateCount"] == 0
    assert quality["normalizedDuplicateCount"] == 0
    assert quality["nearDuplicateCount"] == 0
    assert quality["frozenExactOverlap"] == 0
    assert quality["frozenNearOverlap"] == 0
    assert quality["frozenTemplateOverlap"] == 0
    paths = [
        DATA / "router_calibration_candidate_demo_final.jsonl",
        DATA / "boundary_challenge_demo_final.jsonl",
        DATA / "final_dataset_repair_log.jsonl",
        DATA / "final_semantic_metrics.json",
        DATA / "dataset_final_freeze_manifest.json",
    ]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert not re.search(r"reviewer(identity|id|name)", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
