from __future__ import annotations

import json
import re
import pytest

from scripts.build_step233c_cn_challenge import (
    SLICE_CASES,
    build_cases,
    build_manifest,
    sha256_file,
    validate_cases,
    write_dataset,
)
from scripts.run_step233c_cn_challenge import assert_frozen_dataset, ndcg_at_k, paired_comparison, promotion_gate


def test_step233c_dataset_is_120_unique_chinese_cases_with_expected_slices():
    cases = build_cases()

    assert len(cases) == 120
    assert {name: len(rows) for name, rows in SLICE_CASES.items()} == {
        "multi_risk_precedence": 35,
        "implicit_colloquial": 30,
        "hard_negative": 20,
        "normal_easy": 15,
        "long_noisy": 10,
        "boundary_ambiguous": 10,
    }
    assert len({case["reviewText"] for case in cases}) == 120
    assert all(re.search(r"[\u4e00-\u9fff]", case["reviewText"]) for case in cases)
    assert all(not re.search(r"[A-Za-z]", case["reviewText"]) for case in cases)


def test_step233c_qrels_are_primary_first_and_reference_real_policy_chunks():
    cases = build_cases()
    validation = validate_cases(cases, chunks_path=_real_chunks())

    assert validation["rankingCaseCount"] == 105
    assert validation["normalCaseCount"] == 15
    assert validation["oldGoldExactOverlapCount"] == 0
    assert validation["uniquePolicyChunkCount"] >= 12
    for case in cases:
        assert case["riskTypes"][0] == case["primaryRiskType"]
        if case["primaryRiskType"] != "normal_review":
            assert any(
                row["relevance"] == 3 and case["primaryRiskType"] in row["supports"]
                for row in case["policyRelevance"]
            )


def test_step233c_freeze_manifest_binds_exact_dataset_hash(tmp_path):
    output = tmp_path / "challenge.jsonl"
    cases = build_cases()
    validation = validate_cases(cases, chunks_path=_real_chunks())
    sha256 = write_dataset(cases, output)
    manifest = build_manifest(output, sha256, validation)

    assert manifest["status"] == "FROZEN"
    assert manifest["sha256"] == sha256_file(output)
    assert manifest["construction"]["labelsAssignedBeforeCandidateExecution"] is True
    assert manifest["construction"]["candidateOutputsUsedForLabels"] is False
    assert manifest["promotionGate"]["candidate"] == "B2"
    assert len([json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]) == 120


def test_step233c_frozen_guard_rejects_dataset_mutation(tmp_path):
    output = tmp_path / "challenge.jsonl"
    manifest_path = tmp_path / "challenge.manifest.json"
    cases = build_cases()
    validation = validate_cases(cases, chunks_path=_real_chunks())
    sha256 = write_dataset(cases, output)
    manifest_path.write_text(json.dumps(build_manifest(output, sha256, validation)), encoding="utf-8")
    output.write_text(output.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="STEP233C_DATASET_HASH_MISMATCH"):
        assert_frozen_dataset(output, manifest_path)


def test_step233c_ndcg_rewards_primary_policy_order():
    ideal = [3, 3, 2]

    perfect = ndcg_at_k([3, 3, 2], ideal, 3)
    secondary_first = ndcg_at_k([2, 3, 3], ideal, 3)
    unrelated_first = ndcg_at_k([0, 3, 2], ideal, 3)

    assert perfect == 1.0
    assert perfect > secondary_first > unrelated_first


def test_step233c_pairwise_comparison_is_query_aligned_and_deterministic():
    baseline = [
        {"primaryAt1": True, "ndcgAt3": 0.8},
        {"primaryAt1": False, "ndcgAt3": 0.6},
        {"primaryAt1": True, "ndcgAt3": 0.7},
    ]
    candidate = [
        {"primaryAt1": True, "ndcgAt3": 0.9},
        {"primaryAt1": True, "ndcgAt3": 0.8},
        {"primaryAt1": False, "ndcgAt3": 0.6},
    ]

    first = paired_comparison(baseline, candidate)
    second = paired_comparison(baseline, candidate)

    assert first == second
    assert first["primaryAt1"]["b2Wins"] == 1
    assert first["primaryAt1"]["v1Wins"] == 1


def test_step233c_promotion_gate_never_averages_away_a_safety_omission():
    metrics = {
        "primaryPolicyAccuracyAt1": 1.0,
        "ndcgAt3": 1.0,
        "multiRiskCoverageAt3": 1.0,
        "candidateRecallAt5": 1.0,
        "reflectionAccuracy": 1.0,
        "decisionAccuracy": 1.0,
        "highRiskPrimaryOmissionCount": 0,
        "citationValidity": 1.0,
    }
    baseline = {"metrics": dict(metrics), "slices": {"multi_risk_precedence": dict(metrics)}}
    candidate = {"metrics": dict(metrics), "slices": {"multi_risk_precedence": dict(metrics)}}

    assert promotion_gate(baseline, candidate, {"frozen": True})["status"] == "PASS"
    candidate["metrics"]["highRiskPrimaryOmissionCount"] = 1
    assert promotion_gate(baseline, candidate, {"frozen": True})["status"] == "HOLD"


def _real_chunks():
    from scripts.build_step233c_cn_challenge import DEFAULT_CHUNKS

    return DEFAULT_CHUNKS
