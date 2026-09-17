from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from app.contracts.review_semantics import RISK_TYPE_REGISTRY
from app.risk_calibration.severity import RiskSeverityEvaluator


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
BOUNDARY_TARGET = {
    "implicit_or_paraphrase": 15,
    "lexical_mismatch": 10,
    "hard_negative": 15,
    "multi_risk_or_conflict": 10,
    "ambiguous_context": 5,
    "noisy_or_adversarial": 5,
}


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_v2_counts_schema_registry_and_candidate_statuses():
    calibration = load_jsonl("router_calibration_candidate_demo_v2.jsonl")
    boundary = load_jsonl("boundary_challenge_demo_v2.jsonl")
    rows = calibration + boundary
    assert len(calibration) == 120
    assert len(boundary) == 60
    assert all(row["labelStatus"] in {"ORIGINAL_ACCEPTED", "PROPOSED_REPAIRED", "NEEDS_ADJUDICATION"} for row in rows)
    assert all(row["labelStatus"] != "human_gold" and row["labelSource"] != "human_gold" for row in rows)
    assert all(set(row["riskTypes"]).issubset(RISK_TYPE_REGISTRY) for row in rows)
    assert all(
        row.get("evaluationTarget", "RISK_CLASSIFICATION") == "ABSTENTION"
        or row["severity"] == RiskSeverityEvaluator().evaluate(row["riskTypes"], review_text=row["textZh"]).severity
        for row in rows
    )
    assert all(row["contentHash"] == hashlib.sha256(row["textZh"].encode()).hexdigest() for row in rows)


def test_judge_aggregation_is_complete_and_matches_declared_inputs():
    rows = load_jsonl("judge_aggregation_v1.jsonl")
    assert len(rows) == 180
    assert len({row["caseId"] for row in rows}) == 180
    assert Counter(row["judgeAVerdict"] for row in rows) == {"PASS": 114, "FAIL": 60, "UNCERTAIN": 6}
    assert Counter(row["judgeBVerdict"] for row in rows if row["judgeBVerdict"]) == {"PASS": 24, "FAIL": 36}
    required = {
        "caseId", "datasetType", "originalText", "originalRiskTypes", "originalSeverity",
        "originalBoundaryType", "sourceDataset", "judgeAVerdict", "judgeARiskAssessment",
        "judgeASeverityAssessment", "judgeASuggestedRiskTypes", "judgeASuggestedSeverity",
        "judgeAReasonCodes", "judgeBVerdict", "judgeBBoundaryAssessment", "judgeBChallengeValue",
        "judgeBKeywordShortcutRisk", "judgeBMissingRiskTypes", "judgeBSuggestedBoundaryType",
        "judgeBReasonCodes", "judgeConsensusStatus",
    }
    assert all(required.issubset(row) for row in rows)


def test_boundary_distribution_and_replacement_policy():
    rows = load_jsonl("boundary_challenge_demo_v2.jsonl")
    assert Counter(row["boundaryType"] for row in rows) == BOUNDARY_TARGET
    assert sum(row["repairAction"] == "NEW_BOUNDARY_REPLACEMENT" for row in rows) == 36
    assert sum(row["repairAction"] == "KEEP" for row in rows) == 19
    assert all(row["difficulty"] == "hard" for row in rows)


def test_frozen_is_unchanged_and_quality_gates_pass():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() == FROZEN_SHA
    manifest = json.loads((DATA / "dataset_manifest_demo_v2.json").read_text(encoding="utf-8"))
    assert manifest["gate"] == "PASS"
    assert manifest["datasetSemanticGate"] == "PENDING_INDEPENDENT_REJUDGE"
    assert set(manifest["gates"].values()) == {"PASS"}
    assert manifest["deterministicValidationGate"] == "PASS"
    assert manifest["quality"]["frozenExactOverlap"] == 0
    assert manifest["quality"]["frozenNearOverlap"] == 0
    assert manifest["quality"]["frozenTemplateOverlap"] == 0
    assert manifest["quality"]["nearDuplicateCount"] == 0


def test_router_scope_covers_the_real_registry():
    scope = json.loads((DATA / "text_router_benchmark_scope_v1.json").read_text(encoding="utf-8"))["risks"]
    assert {row["riskCode"] for row in scope} == set(RISK_TYPE_REGISTRY)
    by_code = {row["riskCode"]: row for row in scope}
    assert by_code["normal_review"]["inScope"] is True
    assert by_code["rating_conflict"]["inScope"] is False
    assert by_code["modality_conflict"]["inScope"] is False
    assert by_code["low_confidence"]["inScope"] is False
    assert by_code["other"]["inScope"] is False


def test_rejudge_batches_are_small_and_do_not_anchor_on_old_verdicts():
    queue = load_jsonl("dataset_rejudge_queue_v1.jsonl")
    batches = sorted((DATA / "rejudge_batches").glob("*.json"))
    assert len(queue) == 81
    assert batches
    for path in batches:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert 1 <= len(payload["items"]) <= 20
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        assert "judgeaverdict" not in serialized
        assert "judgebverdict" not in serialized
        assert "old verdict" not in serialized


def test_security_and_judge_c_tracking():
    files = [
        DATA / "router_calibration_candidate_demo_v2.jsonl",
        DATA / "boundary_challenge_demo_v2.jsonl",
        DATA / "dataset_rejudge_queue_v1.jsonl",
        DATA / "dataset_manifest_demo_v2.json",
    ]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert "Authorization:" not in payload
    assert "api_key=" not in payload.lower()
    assert "chain-of-thought" not in payload.lower()
    resolution = json.loads((DATA / "judge_c_findings_resolution.json").read_text(encoding="utf-8"))
    assert {row["status"] for row in resolution["findings"]}.issubset({"RESOLVED", "PARTIAL", "OPEN", "OUT_OF_SCOPE"})
    assert any(row["finding"] == "Text Router scope" and row["status"] == "RESOLVED" for row in resolution["findings"])
