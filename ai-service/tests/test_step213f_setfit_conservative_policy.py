from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary
from scripts import run_step213f_setfit_conservative_policy as policy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213f_setfit_conservative_policy"
STEP213E_OUTPUT = ROOT / "artifacts" / "step213e_setfit_binary_router"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def gate_metrics(**updates) -> dict:
    metrics = {
        "longRequiredRecall": 0.96,
        "fastCoverage": 0.21,
        "highRiskFalseFastCount": 0,
        "materialSafetyFalseFastCount": 0,
    }
    metrics.update(updates)
    return metrics


def test_threshold_candidates_fixed():
    sweep = read_json("setfit_threshold_sweep_v1.json")
    assert tuple(sweep["candidateThresholds"]) == policy.THRESHOLD_CANDIDATES == (0.5, 0.6, 0.7, 0.8, 0.9)
    assert [row["threshold"] for row in sweep["candidates"]] == list(policy.THRESHOLD_CANDIDATES)


def test_threshold_selected_from_dev_only():
    selection = read_json("setfit_policy_selection_v1.json")
    sweep = read_json("setfit_threshold_sweep_v1.json")
    assert selection["selectionPartition"] == "FIT_INTERNAL_DEV_16_ONLY"
    assert sweep["selectionPartition"] == "FIT_INTERNAL_DEV_16_ONLY"
    assert selection["selectedThreshold"] in sweep["candidateThresholds"]


def test_validation_not_used_for_selection():
    selection = read_json("setfit_policy_selection_v1.json")
    sweep = read_json("setfit_threshold_sweep_v1.json")
    assert selection["validationUsed"] is False
    assert sweep["validationUsed"] is False


def test_no_model_retrain():
    selection = read_json("setfit_policy_selection_v1.json")
    gate = read_json("setfit_threshold_gate_v1.json")
    snapshot = json.loads((STEP213E_OUTPUT / "setfit_binary_model_snapshot_v1.json").read_text(encoding="utf-8"))
    assert selection["modelRetrained"] is False
    assert gate["modelRetrained"] is False
    assert selection["modelArtifactHashBefore"] == selection["modelArtifactHashAfter"]
    assert selection["modelSnapshot"]["classificationHeadSha"] == snapshot["classificationHeadSha"]


def test_high_risk_false_fast_gate():
    assert policy.candidate_gate(gate_metrics(highRiskFalseFastCount=1)) == (
        "FAIL_SAFETY",
        "SETFIT_BINARY_ROUTER_UNSAFE",
    )


def test_safety_false_fast_gate():
    assert policy.candidate_gate(gate_metrics(materialSafetyFalseFastCount=1)) == (
        "FAIL_SAFETY",
        "SETFIT_BINARY_ROUTER_UNSAFE",
    )


def test_long_recall_metric():
    rows = read_jsonl("setfit_validation_conservative_v1.jsonl")
    metrics = read_json("setfit_validation_metrics_conservative_v1.json")
    long_rows = [row for row in rows if row["binaryTarget"] == binary.LONG_REQUIRED]
    captured = sum(row["finalPrediction"] == binary.LONG_REQUIRED for row in long_rows)
    assert metrics["longRequiredRecall"] == baseline.safe_ratio(captured, len(long_rows))


def test_fast_coverage_metric():
    rows = read_jsonl("setfit_validation_conservative_v1.jsonl")
    metrics = read_json("setfit_validation_metrics_conservative_v1.json")
    fast_count = sum(row["finalPrediction"] == binary.FAST_ELIGIBLE for row in rows)
    assert metrics["fastCoverage"] == baseline.safe_ratio(fast_count, len(rows))
    assert sum(metrics["predictionDistribution"].values()) == 40


def test_boundary_after_freeze():
    selection = read_json("setfit_policy_selection_v1.json")
    gate = read_json("setfit_threshold_gate_v1.json")
    boundary = read_json("setfit_boundary_metrics_conservative_v1.json")
    assert selection["boundaryUsed"] is False
    assert gate["boundaryAfterFreezeGate"] == "PASS"
    assert boundary["caseCount"] == 60


def test_hard_negative_slice():
    hard = read_json("setfit_boundary_metrics_conservative_v1.json")["hardNegative"]
    assert hard["caseCount"] == 15
    assert hard["fastTargetCount"] == 11
    assert hard["falseEscalationCount"] == 11
    assert hard["fastRecall"] == 0.0


def test_abstention_capture():
    abstention = read_json("setfit_boundary_metrics_conservative_v1.json")["abstentionLongCapture"]
    assert abstention == {"targetCount": 5, "captured": 5, "rate": 1.0}


def test_frozen_not_executed():
    selection = read_json("setfit_policy_selection_v1.json")
    sweep = read_json("setfit_threshold_sweep_v1.json")
    gate = read_json("setfit_threshold_gate_v1.json")
    assert selection["frozenUsed"] is False
    assert sweep["frozenUsed"] is False
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_dataset_read_only():
    gate = read_json("setfit_threshold_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA
    assert gate["datasetReadOnlyGate"] == "PASS"


def test_policy_determinism():
    candidates = read_json("setfit_threshold_sweep_v1.json")["candidates"]
    first = policy.select_policy(candidates)
    second = policy.select_policy(json.loads(json.dumps(candidates)))
    selection = read_json("setfit_policy_selection_v1.json")
    assert first == second
    assert first["threshold"] == selection["selectedThreshold"] == 0.5


def test_no_safe_candidate_is_not_candidate_pass():
    selection = read_json("setfit_policy_selection_v1.json")
    gate = read_json("setfit_threshold_gate_v1.json")
    assert selection["safetyFeasibleCandidateFound"] is False
    assert gate["thresholdSelectionGate"] == "PASS_WITH_NO_SAFE_CANDIDATE"
    assert gate["setfitRouterCandidateGate"] == "FAIL_SAFETY"


def test_no_external_or_qwen_calls():
    gate = read_json("setfit_threshold_gate_v1.json")
    assert gate["externalApiCallCount"] == 0
    assert gate["qwenCallCount"] == 0


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [policy.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "textZh" not in payload and "sanitizedText" not in payload
