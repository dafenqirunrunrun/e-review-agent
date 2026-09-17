from __future__ import annotations

import json
from pathlib import Path

from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.models import RagQualityCase
from scripts.build_step242a_rag_quality_v2 import CHUNKS, FROZEN_WORKFLOW, FROZEN_WORKFLOW_SHA, load_jsonl, sha256_file
from scripts.check_step242a_promotion_readiness import check_readiness


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "benchmarks" / "rag_quality_v2"
ARTIFACTS = ROOT / "artifacts" / "step242c"


def _cases(name: str) -> list[RagQualityCase]:
    return [RagQualityCase.model_validate(item) for item in load_jsonl(DATA / name)]


def test_llm_frozen_dataset_has_complete_explicit_qrels() -> None:
    cases = _cases("dataset_frozen_llm_v1.jsonl")
    corpus_ids = {item.chunkId for item in load_policy_chunks(CHUNKS)}

    assert len(cases) == 120
    assert sum(item.split == "dev" for item in cases) == 80
    assert sum(item.split == "holdout" for item in cases) == 40
    assert all(item.annotationStatus == "llm_adjudicated" for item in cases)
    assert all(item.qrelCompleteness == "complete" for item in cases)
    assert all(item.requiresAdjudication is False for item in cases)
    assert all(len(item.qrels) == 71 for item in cases)
    assert all({qrel.chunkId for qrel in item.qrels} == corpus_ids for item in cases)


def test_no_answer_and_risk_support_invariants_hold() -> None:
    cases = _cases("dataset_frozen_llm_v1.jsonl")
    for case in cases:
        positives = [item for item in case.qrels if item.relevance >= 2]
        if case.noAnswer:
            assert not positives
            assert not case.riskTypes
        else:
            supported = {risk for item in positives for risk in item.supports}
            assert set(case.riskTypes) <= supported


def test_holdout_is_hash_frozen_but_not_executed() -> None:
    manifest = json.loads((DATA / "manifest_frozen_llm_v1.json").read_text(encoding="utf-8"))
    holdout = DATA / manifest["files"]["holdout"]["path"]

    assert manifest["status"] == "FROZEN_LLM_ADJUDICATED"
    assert sha256_file(holdout) == manifest["files"]["holdout"]["sha256"]
    assert manifest["annotation"]["holdoutExecutionAllowed"] is True
    assert manifest["annotation"]["holdoutExecuted"] is False
    assert manifest["qualityThresholds"]["sourceSplit"] == "dev"
    assert manifest["qualityThresholds"]["holdoutConsulted"] is False
    assert manifest["qualityThresholds"]["status"] == "FROZEN"


def test_machine_adjudication_is_not_mislabeled_as_human_gold() -> None:
    manifest = json.loads((DATA / "manifest_frozen_llm_v1.json").read_text(encoding="utf-8"))
    summary = json.loads((ARTIFACTS / "adjudication_summary.json").read_text(encoding="utf-8"))

    assert manifest["annotation"]["humanVerifiedCaseCount"] == 0
    assert manifest["annotation"]["llmAdjudicatedCaseCount"] == 120
    assert "not be described as human gold" in manifest["annotation"]["limitation"]
    assert summary["gate"] == "PASS_WITH_SINGLE_JUDGE_LIMITATION"
    assert summary["adjudicator"]["humanVerified"] is False
    assert summary["blindQwenDiagnostic"]["primaryJudgeEligible"] is False
    assert summary["blindQwenDiagnostic"]["pairwiseExactAgreementRate"] == 0.666667
    assert summary["blindQwenDiagnostic"]["judgeA"]["riskMicroF1"] == 0.680498


def test_frozen_readiness_passes_with_declared_single_judge_limitation() -> None:
    report = check_readiness(
        dataset_path=DATA / "dataset_frozen_llm_v1.jsonl",
        manifest_path=DATA / "manifest_frozen_llm_v1.json",
        parser_baseline_path=ROOT / "artifacts" / "step242a" / "parser_quality_baseline.json",
        retrieval_baseline_path=ARTIFACTS / "frozen_dev_baselines.json",
    )

    assert report["gate"] == "READY_WITH_SINGLE_JUDGE_LIMITATION"
    assert report["checks"]["allCasesReleaseVerified"] is True
    assert report["checks"]["allCasesHumanVerified"] is False
    assert report["checks"]["qualityThresholdsFrozen"] is True
    assert report["holdoutExecuted"] is False


def test_original_frozen_workflow_gold_is_unchanged() -> None:
    assert sha256_file(FROZEN_WORKFLOW) == FROZEN_WORKFLOW_SHA
