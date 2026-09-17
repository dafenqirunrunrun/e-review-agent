from __future__ import annotations

import json
from pathlib import Path

from app.document_ingestion.adapters import LightweightDocumentAdapter
from app.document_ingestion.router import DocumentParserRouter
from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.audit import audit_legacy_challenge_qrels
from app.rag_quality.contract import METRIC_CONTRACT_VERSION, metric_contract
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalRunCase
from app.rag_quality.parser_metrics import aggregate_parser_results, evaluate_parsed_document
from scripts.build_step242a_rag_quality_v2 import (
    CHUNKS,
    LEGACY_DATASET,
    LEGACY_MANIFEST,
    build_dev_cases,
    build_holdout_candidates,
    load_jsonl,
    validate_cases,
)
from scripts.check_step242a_promotion_readiness import check_readiness


def _hit(chunk_id: str, rank: int) -> dict[str, object]:
    return {
        "chunkId": chunk_id,
        "score": float(10 - rank),
        "sourceName": "测试政策",
        "sourceUrl": "https://example.test/policy",
        "sectionPath": ["第二章", "第八条"],
        "clauseId": "8",
        "contentHash": "1234567890abcdef",
    }


def test_metric_contract_separates_case_hit_from_standard_recall() -> None:
    contract = metric_contract()

    assert contract["schemaVersion"] == METRIC_CONTRACT_VERSION
    assert contract["metrics"]["candidateEvidenceHitRateAt5"]["unit"] == "case"
    assert contract["metrics"]["relevantChunkRecallAt5"]["unit"] == "qrel"
    assert contract["metrics"]["relevantChunkRecallAt5"]["aggregation"] == "micro"
    assert contract["metrics"]["irMeasuresRelevantChunkRecallAt5"]["aggregation"] == "macro"
    assert contract["hardSafetyGates"]["highRiskAutoPassCount"] == 0
    assert contract["qualityThresholdPolicy"]["status"] == "PENDING_TRUSTWORTHY_BASELINE"


def test_deterministic_metrics_report_hit_recall_no_answer_and_draft_gate() -> None:
    cases = [
        RagQualityCase(
            datasetVersion="test-v1",
            caseId="risk-1",
            split="dev",
            reviewText="商家要求五星截图后返现。",
            queryStyle="explicit",
            riskTypes=["rating_manipulation", "fake_review"],
            riskLevel="high",
            qrels=[
                {"chunkId": "chunk-a", "relevance": 3, "supports": ["rating_manipulation"]},
                {"chunkId": "chunk-b", "relevance": 2, "supports": ["fake_review"]},
            ],
            qrelCompleteness="pooled_partial",
            annotationStatus="pending_human_review",
            annotationSource="test",
        ),
        RagQualityCase(
            datasetVersion="test-v1",
            caseId="normal-1",
            split="dev",
            reviewText="颜色稍浅但使用正常。",
            queryStyle="no_answer",
            riskLevel="normal",
            noAnswer=True,
            sourceLanguage="not_applicable",
            documentFormat="not_applicable",
            qrelCompleteness="draft_pool",
            annotationStatus="pending_human_review",
            annotationSource="test",
        ),
    ]
    run = [
        RetrievalRunCase(caseId="risk-1", hits=[_hit("chunk-a", 1)]),
        RetrievalRunCase(caseId="normal-1", abstained=True),
    ]

    report = evaluate_retrieval_run(cases, run, run_name="fixture")

    assert report["evaluationStatus"] == "DIAGNOSTIC_ONLY"
    assert report["promotionGate"] == "HOLD"
    assert report["metrics"]["candidateEvidenceHitRateAt5"] == 1.0
    assert report["metrics"]["relevantChunkRecallAt5"] == 0.5
    assert report["metrics"]["irMeasuresRelevantChunkRecallAt5"] == 0.5
    assert report["metrics"]["riskCoverageAt3"] == 0.0
    assert report["metrics"]["noAnswerAbstentionAccuracy"] == 1.0
    assert report["metrics"]["citationValidCaseRate"] == 1.0
    assert report["slices"]["riskType"]["rating_manipulation"]["caseCount"] == 1
    assert report["slices"]["sourceLanguage"]["mixed"]["caseCount"] == 1


def test_no_answer_with_exposed_evidence_fails_safe_gate() -> None:
    case = RagQualityCase(
        datasetVersion="test-v1",
        caseId="normal-2",
        split="dev",
        reviewText="包装普通，没有其他问题。",
        queryStyle="no_answer",
        riskLevel="normal",
        noAnswer=True,
        sourceLanguage="not_applicable",
        documentFormat="not_applicable",
        qrelCompleteness="complete",
        annotationStatus="human_verified",
        annotationSource="human",
        requiresAdjudication=False,
    )

    report = evaluate_retrieval_run(
        [case],
        [RetrievalRunCase(caseId="normal-2", hits=[_hit("irrelevant", 1)])],
        run_name="unsafe-no-answer",
    )

    assert report["metrics"]["noAnswerAbstentionAccuracy"] == 0.0
    assert report["metrics"]["fabricatedNoAnswerCitationCount"] == 1
    assert report["promotionGate"] == "HOLD"


def test_parser_quality_scorer_detects_structure_and_traceability(tmp_path: Path) -> None:
    source = tmp_path / "policy.html"
    source.write_text(
        "<h1>评论规范</h1><h2>有偿评价</h2><p>禁止返现换取五星。</p>"
        "<table><tr><th>风险</th><th>动作</th></tr><tr><td>评分操纵</td><td>人工复核</td></tr></table>",
        encoding="utf-8",
    )
    document = DocumentParserRouter(adapters=[LightweightDocumentAdapter()]).parse(
        source,
        document_id="quality-html-1",
        language="zh",
    )

    result = evaluate_parsed_document(
        document,
        {
            "fixtureId": "quality-html",
            "expectedFormat": "html",
            "requiredAnchors": ["返现", "人工复核"],
            "orderedAnchors": ["评论规范", "有偿评价", "返现"],
            "requiredNodeTypes": ["title", "section", "table", "table_row"],
            "requiredSectionPaths": ["评论规范 / 有偿评价"],
            "requiredTableCells": ["评分操纵", "人工复核"],
            "requiredRouteReasons": ["TEXT_STRUCTURE_NATIVE"],
        },
    )
    aggregate = aggregate_parser_results([result])

    assert result["passed"] is True
    assert result["metrics"]["anchorRecall"] == 1.0
    assert result["metrics"]["tableCellRecall"] == 1.0
    assert aggregate["hardSafetyGate"] == "PASS"


def test_candidate_dataset_has_guarded_80_40_24_split() -> None:
    legacy = load_jsonl(LEGACY_DATASET)
    chunks = load_policy_chunks(CHUNKS)
    dev = build_dev_cases(legacy)
    holdout = build_holdout_candidates(legacy)
    validation = validate_cases([*dev, *holdout], legacy, chunks)

    assert validation["caseCount"] == 120
    assert validation["devCount"] == 80
    assert validation["holdoutCount"] == 40
    assert validation["smokeCount"] == 24
    assert all(item.candidateExposure for item in dev)
    assert all(not item.candidateExposure for item in holdout)
    assert all(item.annotationStatus == "pending_human_review" for item in [*dev, *holdout])


def test_legacy_qrel_audit_blocks_promotion_without_rewriting_source() -> None:
    cases = load_jsonl(LEGACY_DATASET)
    chunks = load_policy_chunks(CHUNKS)
    manifest = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8-sig"))

    report = audit_legacy_challenge_qrels(cases, chunks, manifest)

    assert report["status"] == "DIAGNOSTIC_VALID_PROMOTION_BLOCKED"
    assert report["promotionEligible"] is False
    assert report["judgedCorpusCoverage"] == 0.352113
    assert report["unjudgedChunkCount"] == 46
    assert report["missingChunkReferences"] == []


def test_promotion_readiness_holds_pending_candidate(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    case = RagQualityCase(
        datasetVersion="candidate",
        caseId="pending-1",
        split="dev",
        reviewText="商家要求五星返现。",
        queryStyle="explicit",
        riskTypes=["rating_manipulation"],
        riskLevel="high",
        qrelCompleteness="draft_pool",
        annotationStatus="pending_human_review",
        annotationSource="candidate",
    )
    dataset.write_text(json.dumps(case.model_dump(mode="json"), ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"status": "ANNOTATION_PENDING", "files": {"dataset": {"sha256": "not-ready"}}}),
        encoding="utf-8",
    )
    parser_baseline = tmp_path / "parser.json"
    parser_baseline.write_text(json.dumps({"hardSafetyGate": "FAIL"}), encoding="utf-8")
    retrieval_baseline = tmp_path / "retrieval.json"
    retrieval_baseline.write_text(json.dumps({"variants": {"v1": {"evaluationStatus": "DIAGNOSTIC_ONLY"}}}), encoding="utf-8")

    report = check_readiness(
        dataset_path=dataset,
        manifest_path=manifest,
        parser_baseline_path=parser_baseline,
        retrieval_baseline_path=retrieval_baseline,
    )

    assert report["gate"] == "HOLD"
    assert "allCasesHumanVerified" in report["blockers"]
    assert "parserHardSafetyGatePassed" in report["blockers"]
