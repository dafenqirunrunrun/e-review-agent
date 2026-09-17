from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def scope_codes() -> tuple[set[str], set[str]]:
    rows = json.loads((DATA / "text_router_benchmark_scope_v1.json").read_text(encoding="utf-8"))["risks"]
    return ({row["riskCode"] for row in rows if row["inScope"]}, {row["riskCode"] for row in rows if not row["inScope"]})


def test_out_of_scope_codes_not_classification_gold():
    rows = load_jsonl("router_calibration_candidate_demo_v2.jsonl") + load_jsonl("boundary_challenge_demo_v2.jsonl")
    _, out_scope = scope_codes()
    classification = [row for row in rows if row.get("evaluationTarget", "RISK_CLASSIFICATION") == "RISK_CLASSIFICATION"]
    assert not [row["caseId"] for row in classification if set(row.get("benchmarkRiskTypes", row["riskTypes"])) & out_scope]


def test_abstention_cases_excluded_from_risk_metrics():
    boundary = load_jsonl("boundary_challenge_demo_v2.jsonl")
    abstention = [row for row in boundary if row.get("evaluationTarget") == "ABSTENTION"]
    assert len(abstention) == 5
    assert all(row["benchmarkRiskTypes"] == [] and row["riskTypes"] == [] for row in abstention)
    assert all(row["excludeFromRiskTypeMetrics"] is True for row in abstention)
    contract = json.loads((DATA / "text_router_metric_contract_v1.json").read_text(encoding="utf-8"))
    assert contract["riskClassificationEligibility"] == "evaluationTarget == RISK_CLASSIFICATION"
    assert set(contract["abstentionMetrics"]) == {"abstentionAccuracy", "escalationAccuracy", "falseConfidentClassificationCount"}


def test_abstention_cases_preserved_in_boundary():
    boundary = load_jsonl("boundary_challenge_demo_v2.jsonl")
    abstention = [row for row in boundary if row.get("evaluationTarget") == "ABSTENTION"]
    assert Counter(code for row in abstention for code in row["provenanceRiskTypes"]) == {"low_confidence": 4, "fake_review_suspected": 1}
    assert all(row["expectedDisposition"] == "ESCALATE_OR_ABSTAIN" for row in abstention)
    assert all(row["ambiguity"] is True and row["boundaryType"] == "ambiguous_context" for row in abstention)


def test_boundary_count_stays_60():
    assert len(load_jsonl("boundary_challenge_demo_v2.jsonl")) == 60


def test_frozen_sha_unchanged():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() == FROZEN_SHA


def test_scope_manifest_consistency():
    manifest = json.loads((DATA / "dataset_manifest_demo_v2.json").read_text(encoding="utf-8"))
    summary = manifest["benchmarkScopeSummary"]
    assert manifest["datasetRevision"] == "v2.1"
    assert manifest["scopePatchVersion"] == "step21.2.2b.1"
    assert summary["riskClassificationCaseCount"] == 175
    assert summary["abstentionCaseCount"] == 5
    assert summary["outOfScopeRiskCodeAsClassificationGoldCount"] == 0


def test_rejudge_batch_has_no_old_judge_verdict():
    for path in (DATA / "rejudge_batches").glob("*.json"):
        payload = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False).lower()
        assert "previousjudgeverdict" not in payload
        assert "judgeaverdict" not in payload
        assert "judgebverdict" not in payload
        assert "previoussuggestedrisktypes" not in payload
        assert "repairreason" not in payload


def test_rejudge_batch_contains_abstention_contract():
    items = []
    for path in (DATA / "rejudge_batches").glob("judge_a_recheck_*.json"):
        items.extend(json.loads(path.read_text(encoding="utf-8"))["items"])
    abstention = [item for item in items if item["evaluationTarget"] == "ABSTENTION"]
    assert len(abstention) == 5
    required = {"caseId", "textZh", "evaluationTarget", "expectedDisposition", "benchmarkRiskTypes", "severity", "expressionType", "ambiguity", "boundaryType"}
    assert all(required.issubset(item) for item in abstention)
    assert all(item["benchmarkRiskTypes"] == [] for item in abstention)


def test_security_scan():
    paths = [
        DATA / "boundary_challenge_demo_v2.jsonl",
        DATA / "dataset_manifest_demo_v2.json",
        DATA / "dataset_rejudge_queue_v1.jsonl",
        DATA / "text_router_metric_contract_v1.json",
        *sorted((DATA / "rejudge_batches").glob("*.json")),
    ]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
