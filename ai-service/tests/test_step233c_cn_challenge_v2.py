from __future__ import annotations

import json

from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from scripts.build_step233c_cn_challenge import DEFAULT_OUTPUT as V1_DATASET, sha256_file as v1_sha256_file
from scripts.build_step233c_cn_challenge_v2 import (
    DEFAULT_CHUNKS,
    TRUE_NORMAL_HARD_NEGATIVE,
    build_cases,
    build_manifest,
    build_reflection_scenarios,
    sha256_file,
    validate,
    write_jsonl,
)


V1_FROZEN_SHA = "2FD39E01A77783113879634E7A69F45CA77133C3164AF1416564C02BA80BA7C2"


def test_v2_preserves_v1_and_adds_real_normal_hard_negatives():
    before = v1_sha256_file(V1_DATASET)
    cases = build_cases()
    after = v1_sha256_file(V1_DATASET)

    assert before == after == V1_FROZEN_SHA
    assert len(cases) == 120
    assert len(TRUE_NORMAL_HARD_NEGATIVE) == 15
    hard_negatives = [case for case in cases if case["slice"] == "normal_hard_negative"]
    assert len(hard_negatives) == 15
    assert all(case["primaryRiskType"] == "normal_review" for case in hard_negatives)
    assert all(not case["policyJudgments"] for case in hard_negatives)


def test_v2_policy_judgments_are_auditable_and_do_not_use_incomplete_lead_in():
    cases = build_cases()
    judgments = [row for case in cases for row in case["policyJudgments"]]

    assert judgments
    assert all(row["judgmentRationale"] for row in judgments)
    assert all(row["sourceLevel"] in {"A", "B"} for row in judgments)
    assert all(row["applicability"] == "indexed_policy_reference" for row in judgments)
    assert "ce069bb67cc3b294d6e7cf93" not in {row["chunkId"] for row in judgments}
    assert any(row["chunkId"] == "ff0598d26200a4e201663451" and row["primaryPolicy"] for row in judgments)
    assert any(row["chunkId"] == "74340d2418d9fcfa599e41da" and row["primaryPolicy"] for row in judgments)


def test_v2_marks_partial_qrels_and_ambiguous_labels_explicitly():
    cases = build_cases()
    rankable = [case for case in cases if case["policyJudgments"]]
    boundary = [case for case in cases if case["slice"] == "boundary_ambiguous"]

    assert all(case["qrelCompleteness"] == "pooled_partial" for case in rankable)
    assert all(case["routeEvaluationModes"] == ["text_only", "rating_aware"] for case in cases)
    assert any(case["requiresAdjudication"] for case in boundary)
    assert all(case["annotationConfidence"] in {"low", "medium"} for case in boundary)
    assert all(case["primaryPolicyChunkIds"] for case in rankable)


def test_v2_reflection_matrix_covers_three_states_and_citation_failure():
    rows = build_reflection_scenarios()
    statuses = {row["expectedEvidenceStatus"] for row in rows}

    assert len(rows) == 28
    assert statuses == {"supported", "insufficient", "mismatch"}
    assert sum(row["evidenceMode"] == "citation_incomplete" for row in rows) == 7
    assert sum(row["evidenceMode"] == "empty" for row in rows) == 7
    assert sum(row["evidenceMode"] == "mismatch" for row in rows) == 7


def test_v2_reflection_matrix_matches_real_reflection_engine():
    chunks = {chunk.chunkId: chunk for chunk in load_policy_chunks(DEFAULT_CHUNKS)}
    engine = PolicyReflectionEngine()

    for scenario in build_reflection_scenarios(DEFAULT_CHUNKS):
        evidence = [
            PolicyEvidenceRetriever._to_result(chunks[chunk_id], 1.0, rank=index, mode="evaluation")
            for index, chunk_id in enumerate(scenario["evidenceChunkIds"], start=1)
        ]
        if scenario["evidenceMutation"] == "remove_sourceUrl":
            evidence = [item.model_copy(update={"sourceUrl": ""}) for item in evidence]
        decision = engine.reflect(
            risk_level=scenario["riskLevel"],
            risk_types=scenario["riskTypes"],
            confidence=scenario["confidence"],
            policy_evidence=evidence,
            action="suggest_action",
        )

        assert decision.evidenceStatus == scenario["expectedEvidenceStatus"], scenario["scenarioId"]
        assert decision.requiresHumanReview == scenario["expectedRequiresHumanReview"], scenario["scenarioId"]


def test_v2_validation_and_manifest_forbid_promotion_claim(tmp_path):
    cases = build_cases(DEFAULT_CHUNKS)
    reflection = build_reflection_scenarios(DEFAULT_CHUNKS)
    validation = validate(cases, reflection, DEFAULT_CHUNKS)
    dataset = tmp_path / "dataset.jsonl"
    reflection_path = tmp_path / "reflection.jsonl"
    write_jsonl(cases, dataset)
    write_jsonl(reflection, reflection_path)
    manifest = build_manifest(dataset, reflection_path, validation)

    assert validation["caseCount"] == 120
    assert validation["rankingCaseCount"] == 95
    assert validation["normalCaseCount"] == 25
    assert validation["trueNormalHardNegativeCount"] == 15
    assert manifest["status"] == "FROZEN_DIAGNOSTIC"
    assert manifest["promotionEligible"] is False
    assert manifest["humanAdjudication"]["status"] == "PENDING"
    assert manifest["dataset"]["sha256"] == sha256_file(dataset)
    assert len([json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]) == 120
