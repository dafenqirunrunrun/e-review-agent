from __future__ import annotations

import hashlib
import json
import re
from argparse import Namespace
from pathlib import Path

from scripts.run_step2123_reliability_analysis import (
    BOUNDARY_SHA,
    CALIBRATION_SHA,
    DEFAULT_BOUNDARY,
    DEFAULT_CALIBRATION,
    DEFAULT_FREEZE_MANIFEST,
    DEFAULT_FROZEN,
    EVALUATION_ONLY_FIELDS,
    FROZEN_GOLD_SHA,
    POLICY_ALLOWED_FIELDS,
    TIER_ORDER,
    apply_policy,
    assess_case,
    case_features,
    is_material_safety_error,
    leakage_audit,
    load_jsonl,
    policy_input_snapshot,
    run_analysis,
    signal_inventory,
    simulated_route,
    stratified_split,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "step2123"
REPORT = ROOT.parent / "docs" / "ROUTER_RELIABILITY_READINESS_REPORT.md"


def load_artifact(name: str):
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_final_dataset_hashes_and_frozen_gold_are_unchanged():
    assert file_sha(DEFAULT_CALIBRATION) == CALIBRATION_SHA
    assert file_sha(DEFAULT_BOUNDARY) == BOUNDARY_SHA
    assert file_sha(DEFAULT_FROZEN) == FROZEN_GOLD_SHA


def test_dataset_status_retains_single_judge_limitation():
    manifest = json.loads(DEFAULT_FREEZE_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["datasetSemanticGate"] == "PASS_WITH_SINGLE_JUDGE_LIMITATION"
    assert manifest["calibrationStatus"] == "SEMANTICALLY_REVIEWED_CANDIDATE"
    assert manifest["humanGold"] is False


def test_split_is_deterministic_and_exactly_80_40():
    cases = load_jsonl(DEFAULT_CALIBRATION)
    first = stratified_split(cases)
    second = stratified_split(list(reversed(cases)))
    assert first == second
    assert list(first.values()).count("FIT") == 80
    assert list(first.values()).count("VALIDATION") == 40


def test_split_is_complete_disjoint_and_uses_evaluation_metadata_only():
    cases = load_jsonl(DEFAULT_CALIBRATION)
    split = stratified_split(cases)
    assert set(split) == {row["caseId"] for row in cases}
    assert {split[row["caseId"]] for row in cases} == {"FIT", "VALIDATION"}
    assert all("source:" in " ".join(case_features(row)) for row in cases)


def test_runtime_signal_inventory_is_pre_expensive_model_only():
    inventory = signal_inventory()
    assert inventory["gate"] == "PASS"
    assert inventory["expensiveComponentsCalled"] == []
    assert all(item["availableBeforeExpensiveModel"] for item in inventory["signals"])
    assert {item["name"] for item in inventory["signals"]} >= POLICY_ALLOWED_FIELDS


def test_policy_signal_and_evaluation_metadata_are_disjoint():
    audit = leakage_audit()
    assert POLICY_ALLOWED_FIELDS.isdisjoint(EVALUATION_ONLY_FIELDS)
    assert audit["fieldOverlap"] == []
    assert audit["goldOnlyFieldReadCountDuringPolicyAssignment"] == 0
    assert audit["gate"] == "PASS"


def test_case_assessment_bypasses_llm_rag_and_full_workflow():
    case = load_jsonl(DEFAULT_CALIBRATION)[0]
    result = assess_case(case, dataset_partition="CALIBRATION", split_partition="FIT")
    assert result["error"] is None
    assert result["routeCandidate"] in {"low_touch", "governance_required", "human_review_direct"}
    assert result["predictedSeverity"] in {"low", "medium", "high", "critical"}


def test_signal_results_do_not_persist_review_text():
    result = json.loads((ARTIFACTS / "router_signal_results_v1.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "textZh" not in result
    assert "reviewText" not in result
    assert {
        "caseId", "rawConfidence", "routeCandidate", "reasonCodes", "expectedRiskTypes",
        "exactMatch", "riskTypePrecision", "riskTypeRecall", "riskTypeF1", "materialSafetyError",
    } <= set(result)


def test_raw_confidence_cardinality_is_reported_not_calibrated():
    baseline = load_artifact("cheap_router_baseline_metrics_v1.json")
    audit = baseline["rawConfidence"]
    assert audit["uniqueValueCount"] == 3
    assert audit["uniqueValues"] == [0.68, 0.84, 0.88]
    assert audit["finding"] == "LOW_CARDINALITY_CONFIDENCE"


def test_p0_assignment_depends_only_on_raw_confidence():
    base = {field: None for field in POLICY_ALLOWED_FIELDS}
    base.update({"rawConfidence": 0.88})
    assert apply_policy("P0_CONFIDENCE_ONLY", base) == "HIGH"
    base.update({"expectedRiskTypes": ["normal_review"], "exactMatch": False, "difficulty": "hard"})
    assert apply_policy("P0_CONFIDENCE_ONLY", base) == "HIGH"


def test_p1_never_reads_gold_or_slice_fields():
    row = json.loads((ARTIFACTS / "router_signal_results_v1.jsonl").read_text(encoding="utf-8").splitlines()[0])
    snapshot = policy_input_snapshot(row)
    assert set(snapshot) <= POLICY_ALLOWED_FIELDS
    assert not set(snapshot) & EVALUATION_ONLY_FIELDS
    assert apply_policy("P1_RUNTIME_SIGNALS", snapshot) in TIER_ORDER


def test_p1_has_no_unqualified_high_tier():
    tiers = load_artifact("reliability_tier_metrics_v1.json")
    assert tiers["calibrationFit"]["tiers"]["HIGH"]["count"] == 0
    assert tiers["calibrationValidation"]["tiers"]["HIGH"]["count"] == 0
    assert tiers["calibrationValidation"]["highAcceptance"]["pass"] is False


def test_p2_routes_safety_and_low_reliability_to_strict_path():
    assert simulated_route("HIGH", {"safetyGateTriggered": True, "predictedSeverity": "low"}) == "STRICT_PATH"
    assert simulated_route("LOW", {"safetyGateTriggered": False, "predictedSeverity": "low"}) == "STRICT_PATH"
    assert simulated_route("ABSTAIN", {"safetyGateTriggered": False, "predictedSeverity": "low"}) == "HUMAN_REVIEW"


def test_material_safety_error_detects_missing_high_risk_components():
    error, missing = is_material_safety_error(["paid_review", "rating_manipulation"], ["rating_manipulation"])
    assert error is True
    assert missing == ["paid_review"]
    assert is_material_safety_error(["negative_review"], ["normal_review"]) == (False, [])


def test_baseline_executes_all_180_cases_without_api_errors():
    baseline = load_artifact("cheap_router_baseline_metrics_v1.json")
    assert baseline["combined"]["caseCount"] == 180
    assert baseline["combined"]["classificationCaseCount"] == 175
    assert baseline["combined"]["abstentionCaseCount"] == 5
    assert baseline["combined"]["apiErrorCount"] == 0


def test_policy_candidate_budget_and_single_validation_check():
    candidates = load_artifact("reliability_policy_candidates_v1.json")
    assert len(candidates["policies"]) == 3
    assert candidates["selectedPolicyId"] == "P1_RUNTIME_SIGNALS"
    assert candidates["policyAdjustmentCount"] == 0
    assert candidates["validationPolicy"] == "ONE_INDEPENDENT_CHECK_AFTER_POLICY_FREEZE"


def test_low_and_abstain_capture_validation_errors():
    tiers = load_artifact("reliability_tier_metrics_v1.json")["calibrationValidation"]
    assert tiers["lowAbstainErrorCapture"]["captureRate"] >= 0.70
    assert tiers["lowAbstainErrorCapture"]["capturedErrorCount"] == tiers["lowAbstainErrorCapture"]["totalErrorCount"]


def test_boundary_abstention_targets_are_contained_by_simulation():
    simulation = load_artifact("routing_simulation_metrics_v1.json")["boundary"]
    assert simulation["abstentionSafety"]["targetCount"] == 5
    assert simulation["abstentionSafety"]["strictOrHumanCount"] >= 4
    assert simulation["abstentionSafety"]["pass"] is True


def test_boundary_high_fast_path_has_no_material_safety_error():
    simulation = load_artifact("routing_simulation_metrics_v1.json")["boundary"]
    assert simulation["fastPath"]["materialSafetyErrorCount"] == 0
    assert simulation["fastPath"]["count"] == 0


def test_readiness_gate_fails_cheap_router_but_keeps_offline_harness_ready():
    gate = load_artifact("router_readiness_gate_v1.json")
    assert gate["currentCheapRouterGate"] == "FAIL"
    assert gate["primaryReasonCode"] == "RELIABILITY_SIGNAL_NOT_SEPARABLE"
    assert gate["offlineModelRouterBenchmarkReadiness"] == "PASS"
    assert gate["step21_2_3Gate"] == "PASS_WITH_CHEAP_ROUTER_NOT_READY"
    assert gate["runtimeChanged"] is False
    assert gate["frozenBenchmarkExecuted"] is False


def test_all_required_artifacts_and_report_sections_exist():
    names = {
        "router_signal_inventory_v1.json",
        "signal_leakage_audit_v1.json",
        "reliability_split_v1.json",
        "router_signal_results_v1.jsonl",
        "cheap_router_baseline_metrics_v1.json",
        "reliability_policy_candidates_v1.json",
        "reliability_tier_metrics_v1.json",
        "routing_simulation_metrics_v1.json",
        "router_readiness_gate_v1.json",
    }
    assert names <= {path.name for path in ARTIFACTS.iterdir()}
    report = REPORT.read_text(encoding="utf-8")
    sections = [
        "Goal", "Dataset Status", "Runtime Signal Inventory", "Leakage Audit",
        "Calibration Fit / Validation Split", "Cheap Router Baseline",
        "Raw Confidence Cardinality", "Slice Results", "Reliability Policy Candidates",
        "HIGH / MEDIUM / LOW / ABSTAIN", "Error Capture", "Material Safety Errors",
        "Boundary Challenge Validation", "Fast Path Simulation", "Current Cheap Router Readiness",
        "Offline Model Router Benchmark Readiness", "Limitations", "Next Step",
    ]
    assert all(f"## {section}" in report for section in sections)


def test_analysis_is_reproducible_and_does_not_mutate_protected_inputs(tmp_path):
    before = {path: file_sha(path) for path in [DEFAULT_CALIBRATION, DEFAULT_BOUNDARY, DEFAULT_FREEZE_MANIFEST, DEFAULT_FROZEN]}
    result = run_analysis(Namespace(
        calibration=DEFAULT_CALIBRATION,
        boundary=DEFAULT_BOUNDARY,
        freeze_manifest=DEFAULT_FREEZE_MANIFEST,
        frozen=DEFAULT_FROZEN,
        output_dir=tmp_path / "artifacts",
        report=tmp_path / "report.md",
    ))
    after = {path: file_sha(path) for path in before}
    assert before == after
    assert result["readiness"]["step21_2_3Gate"] == "PASS_WITH_CHEAP_ROUTER_NOT_READY"


def test_generated_artifacts_contain_no_secrets_private_paths_pii_or_cot():
    paths = [*ARTIFACTS.iterdir(), REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert not re.search(r"reviewer(identity|id|name)", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
