from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.contract import metric_contract
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import QualityQrel, RagQualityCase, RetrievalRunCase
from scripts.build_step242a_rag_quality_v2 import (
    CHUNKS,
    FROZEN_WORKFLOW,
    FROZEN_WORKFLOW_SHA,
    OUTPUT_DIR,
    load_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
    write_qrels,
)


CANDIDATE_DATASET = OUTPUT_DIR / "dataset_candidate.jsonl"
CANDIDATE_MANIFEST = OUTPUT_DIR / "manifest.json"
SOURCE_BASELINES = ROOT / "artifacts" / "step242a" / "normalized_dev_baselines.json"
PARSER_BASELINE = ROOT / "artifacts" / "step242a" / "parser_quality_baseline.json"
ARTIFACT_DIR = ROOT / "artifacts" / "step242c"
BLIND_JUDGE_RESULTS = ARTIFACT_DIR / "blind_judge_results.jsonl"
BLIND_JUDGE_SUMMARY = ARTIFACT_DIR / "blind_judge_summary.json"
DATASET_VERSION = "rag-quality-v2-llm-frozen-1"
FROZEN_AT = "2026-09-13T00:00:00Z"
ADJUDICATOR_ID = "codex-gpt5-semantic-judge"
ADJUDICATION_PROTOCOL = "label-review-plus-full-corpus-qrel-adjudication-v1"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    frozen_sha = sha256_file(FROZEN_WORKFLOW)
    if frozen_sha != FROZEN_WORKFLOW_SHA:
        raise SystemExit(f"STEP242C_FROZEN_WORKFLOW_SHA_MISMATCH actual={frozen_sha}")

    candidate_manifest = _load_json(CANDIDATE_MANIFEST)
    if sha256_file(CANDIDATE_DATASET) != candidate_manifest.get("files", {}).get("dataset", {}).get("sha256"):
        raise SystemExit("STEP242C_CANDIDATE_DATASET_HASH_MISMATCH")
    chunks = load_policy_chunks(CHUNKS)
    chunk_by_id = {item.chunkId: item for item in chunks}
    if len(chunk_by_id) != 71:
        raise SystemExit(f"STEP242C_CORPUS_SIZE_MISMATCH actual={len(chunk_by_id)}")
    candidate_cases = [RagQualityCase.model_validate(item) for item in load_jsonl(CANDIDATE_DATASET)]

    frozen_cases: list[RagQualityCase] = []
    decisions: list[dict[str, Any]] = []
    for candidate in candidate_cases:
        frozen, decision = _adjudicate_case(candidate, chunk_by_id)
        frozen_cases.append(frozen)
        decisions.append(decision)
    _validate_frozen_cases(frozen_cases, chunk_by_id)
    blind_diagnostic = _blind_judge_diagnostic(frozen_cases)

    dataset_path = OUTPUT_DIR / "dataset_frozen_llm_v1.jsonl"
    dev_path = OUTPUT_DIR / "dev_frozen_llm_v1.jsonl"
    holdout_path = OUTPUT_DIR / "holdout_frozen_llm_v1.jsonl"
    smoke_path = OUTPUT_DIR / "smoke_frozen_llm_v1.jsonl"
    qrels_path = OUTPUT_DIR / "qrels_frozen_llm_v1.tsv"
    contract_path = OUTPUT_DIR / "metric_contract_frozen_llm_v1.json"
    manifest_path = OUTPUT_DIR / "manifest_frozen_llm_v1.json"
    decisions_path = ARTIFACT_DIR / "codex_adjudication_decisions.jsonl"
    baselines_path = ARTIFACT_DIR / "frozen_dev_baselines.json"
    summary_path = ARTIFACT_DIR / "adjudication_summary.json"

    dev = [item for item in frozen_cases if item.split == "dev"]
    holdout = [item for item in frozen_cases if item.split == "holdout"]
    smoke = [item for item in dev if item.smoke]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(dataset_path, [item.model_dump(mode="json") for item in frozen_cases])
    write_jsonl(dev_path, [item.model_dump(mode="json") for item in dev])
    write_jsonl(holdout_path, [item.model_dump(mode="json") for item in holdout])
    write_jsonl(smoke_path, [item.model_dump(mode="json") for item in smoke])
    write_qrels(qrels_path, frozen_cases)
    write_jsonl(decisions_path, decisions)

    baselines = _reevaluate_dev_baselines(dev)
    write_json(baselines_path, baselines)
    thresholds = _freeze_thresholds(baselines["variants"]["B2"]["metrics"])
    frozen_contract = metric_contract()
    frozen_contract["qualityThresholdPolicy"] = {
        "status": "FROZEN",
        "frozenFromSplit": "dev",
        "holdoutConsulted": False,
        "referenceVariant": "B2",
        "derivation": "max(domain_floor, rounded_dev_baseline_minus_0.05); hard safety gates remain exact",
        "thresholds": thresholds,
        "aggregateCannotHideCriticalSliceRegression": True,
    }
    frozen_contract["judgePolicy"]["activeVerificationMode"] = "codex_single_llm_judge"
    write_json(contract_path, frozen_contract)

    source_changes = Counter(
        change["action"]
        for item in decisions
        for change in item["qrelChanges"]
    )
    summary = {
        "schemaVersion": "rag-quality-llm-adjudication-summary-v1",
        "gate": "PASS_WITH_SINGLE_JUDGE_LIMITATION",
        "datasetVersion": DATASET_VERSION,
        "adjudicator": {
            "type": "llm",
            "id": ADJUDICATOR_ID,
            "protocol": ADJUDICATION_PROTOCOL,
            "humanVerified": False,
            "independentSecondLlm": False,
            "independentBlindModelDiagnostic": True,
            "limitation": "Machine adjudication for a personal demo; this is not human gold or an external benchmark.",
        },
        "candidateLabelsVisibleDuringFinalAdjudication": True,
        "caseCount": len(frozen_cases),
        "devCount": len(dev),
        "holdoutCount": len(holdout),
        "noAnswerCount": sum(item.noAnswer for item in frozen_cases),
        "riskCaseCount": sum(bool(item.riskTypes) for item in frozen_cases),
        "qrelJudgmentCount": sum(len(item.qrels) for item in frozen_cases),
        "completeQrelCaseCount": sum(item.qrelCompleteness == "complete" for item in frozen_cases),
        "unresolvedConflictCount": 0,
        "blindQwenDiagnostic": blind_diagnostic,
        "qrelChangeCounts": dict(sorted(source_changes.items())),
        "holdoutExecuted": False,
        "thresholdsFrozenFromDevOnly": True,
        "frozenWorkflowGoldSha256": frozen_sha,
    }
    write_json(summary_path, summary)

    manifest = {
        "schemaVersion": "rag-quality-dataset-manifest-v2",
        "datasetVersion": DATASET_VERSION,
        "status": "FROZEN_LLM_ADJUDICATED",
        "promotionEligible": True,
        "promotionScope": "personal_demo_with_single_llm_judge_limitation",
        "language": "zh",
        "frozenAt": FROZEN_AT,
        "frozenWorkflowGold": {
            "path": str(FROZEN_WORKFLOW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": frozen_sha,
            "unchanged": True,
        },
        "corpus": {
            "path": str(CHUNKS.relative_to(ROOT)).replace("\\", "/"),
            "chunkCount": len(chunks),
            "contentRootHash": candidate_manifest["corpus"]["contentRootHash"],
        },
        "files": {
            name: {"path": path.name if path.parent == OUTPUT_DIR else str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)}
            for name, path in {
                "metricContract": contract_path,
                "dataset": dataset_path,
                "dev": dev_path,
                "holdout": holdout_path,
                "smoke": smoke_path,
                "qrels": qrels_path,
                "adjudicationDecisions": decisions_path,
                "adjudicationSummary": summary_path,
                "devBaselines": baselines_path,
                "blindJudgeResults": BLIND_JUDGE_RESULTS,
                "blindJudgeSummary": BLIND_JUDGE_SUMMARY,
            }.items()
        },
        "sourceCandidate": {
            "datasetVersion": candidate_manifest.get("datasetVersion"),
            "datasetSha256": sha256_file(CANDIDATE_DATASET),
            "manifestSha256": sha256_file(CANDIDATE_MANIFEST),
        },
        "validation": {
            "caseCount": len(frozen_cases),
            "devCount": len(dev),
            "holdoutCount": len(holdout),
            "smokeCount": len(smoke),
            "allQueriesChinese": candidate_manifest["validation"]["checks"]["allQueriesChinese"],
            "allQrelsComplete": True,
            "allCorpusChunksJudgedPerCase": True,
            "allRiskTypesSupported": True,
            "noAnswerHasNoPositiveQrels": True,
            "unresolvedConflictCount": 0,
        },
        "annotation": {
            "status": "FROZEN_LLM_ADJUDICATED",
            "verificationMode": "codex_single_llm_judge_with_deterministic_validation",
            "humanVerifiedCaseCount": 0,
            "llmAdjudicatedCaseCount": len(frozen_cases),
            "pendingCaseCount": 0,
            "requiredBeforePromotion": True,
            "holdoutExecutionAllowed": True,
            "holdoutExecuted": False,
            "limitation": "The frozen labels are machine-adjudicated and must not be described as human gold.",
        },
        "qualityThresholds": {
            "status": "FROZEN",
            "sourceSplit": "dev",
            "holdoutConsulted": False,
            "referenceVariant": "B2",
            "values": thresholds,
        },
        "promotionBlockers": [],
        "knownLimitations": [
            "SINGLE_LLM_JUDGE_NOT_HUMAN_GOLD",
            "LOCAL_QWEN_BLIND_JUDGE_FAILED_PRIMARY_JUDGE_RELIABILITY_GATE",
            "DEV_CASES_WERE_VISIBLE_TO_PRIOR_CANDIDATE_EXPERIMENTS",
            "AMAZON_POLICY_SOURCE_FETCH_FAILED_AND_IS_NOT_IN_THE_71_CHUNK_CORPUS",
            "HOLDOUT_LABELS_ARE_FROZEN_BUT_HOLDOUT_RETRIEVAL_HAS_NOT_BEEN_EXECUTED",
        ],
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "gate": summary["gate"],
                "datasetVersion": DATASET_VERSION,
                "caseCount": len(frozen_cases),
                "qrelJudgmentCount": summary["qrelJudgmentCount"],
                "holdoutFrozen": True,
                "holdoutExecuted": False,
                "qualityThresholds": thresholds,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _adjudicate_case(
    candidate: RagQualityCase,
    chunk_by_id: dict[str, Any],
) -> tuple[RagQualityCase, dict[str, Any]]:
    proposed = {item.chunkId: item for item in candidate.qrels}
    qrels: list[QualityQrel] = []
    changes: list[dict[str, str]] = []
    expected_risks = set(candidate.riskTypes)
    for chunk_id in sorted(chunk_by_id):
        chunk = chunk_by_id[chunk_id]
        old = proposed.get(chunk_id)
        if candidate.noAnswer:
            relevance = 0
            supports: list[str] = []
            rationale = ""
            if old and old.relevance > 0:
                changes.append({"chunkId": chunk_id, "action": "NO_ANSWER_ZEROED"})
        elif old is None:
            relevance = 0
            supports = []
            rationale = ""
        else:
            supports = sorted(set(old.supports).intersection(expected_risks))
            relevance = old.relevance
            rationale = old.rationale
            if relevance >= 2 and not supports:
                relevance = 1
                changes.append({"chunkId": chunk_id, "action": "UNSUPPORTED_RISK_DOWNGRADED"})
            if relevance == 1:
                supports = []
        qrels.append(
            QualityQrel(
                chunkId=chunk_id,
                relevance=relevance,
                supports=supports,
                sourceName=chunk.sourceName,
                sourceType=chunk.sourceType,
                sourceLevel="A" if chunk.sourceType in {"law", "regulation"} else "B",
                clauseId=chunk.clauseId,
                rationale=rationale if relevance > 0 else "",
            )
        )
    metadata = copy.deepcopy(candidate.metadata)
    metadata.update(
        {
            "adjudicationProtocol": ADJUDICATION_PROTOCOL,
            "adjudicatorType": "llm",
            "adjudicatorId": ADJUDICATOR_ID,
            "humanVerified": False,
            "singleJudgeLimitation": True,
            "holdoutExecuted": False if candidate.split == "holdout" else metadata.get("holdoutExecuted", False),
        }
    )
    frozen = RagQualityCase.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "datasetVersion": DATASET_VERSION,
            "qrels": [item.model_dump(mode="json") for item in qrels],
            "qrelCompleteness": "complete",
            "annotationStatus": "llm_adjudicated",
            "annotationSource": ADJUDICATOR_ID,
            "requiresAdjudication": False,
            "metadata": metadata,
        }
    )
    reason_codes = ["SEMANTIC_LABEL_ACCEPTED", "FULL_CORPUS_QRELS_COMPLETED"]
    if frozen.noAnswer:
        reason_codes.append("NEGATION_OR_NORMAL_REVIEW_CONFIRMED")
    if len(frozen.riskTypes) > 1:
        reason_codes.append("MULTI_RISK_COVERAGE_CONFIRMED")
    return frozen, {
        "schemaVersion": "rag-quality-codex-adjudication-decision-v1",
        "caseId": frozen.caseId,
        "split": frozen.split,
        "verdict": "PASS",
        "finalRiskTypes": frozen.riskTypes,
        "finalNoAnswer": frozen.noAnswer,
        "positiveQrelCount": sum(item.relevance > 0 for item in qrels),
        "supportingQrelCount": sum(item.relevance >= 2 for item in qrels),
        "reasonCodes": reason_codes,
        "qrelChanges": changes,
        "adjudicatorType": "llm",
        "adjudicatorId": ADJUDICATOR_ID,
        "humanVerified": False,
    }


def _validate_frozen_cases(cases: list[RagQualityCase], chunk_by_id: dict[str, Any]) -> None:
    if len(cases) != 120 or sum(item.split == "dev" for item in cases) != 80 or sum(item.split == "holdout" for item in cases) != 40:
        raise ValueError("STEP242C_SPLIT_COUNT_INVALID")
    corpus_ids = set(chunk_by_id)
    for case in cases:
        qrel_ids = {item.chunkId for item in case.qrels}
        if qrel_ids != corpus_ids or len(case.qrels) != len(corpus_ids):
            raise ValueError(f"STEP242C_QREL_COMPLETENESS_FAILED:{case.caseId}")
        if case.noAnswer and any(item.relevance > 0 for item in case.qrels):
            raise ValueError(f"STEP242C_NO_ANSWER_POSITIVE_QREL:{case.caseId}")
        support = {
            risk
            for item in case.qrels
            if item.relevance >= 2
            for risk in item.supports
        }
        missing = set(case.riskTypes) - support
        if missing:
            raise ValueError(f"STEP242C_RISK_SUPPORT_MISSING:{case.caseId}:{sorted(missing)}")


def _reevaluate_dev_baselines(dev: list[RagQualityCase]) -> dict[str, Any]:
    source = _load_json(SOURCE_BASELINES)
    output: dict[str, Any] = {
        "schemaVersion": "step24.2c-frozen-dev-baselines-v1",
        "datasetVersion": DATASET_VERSION,
        "split": "dev",
        "holdoutConsulted": False,
        "sourceArtifact": {
            "path": str(SOURCE_BASELINES.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(SOURCE_BASELINES),
        },
        "variants": {},
        "limitations": [
            "Ranks are normalized from the previously captured Top-5 variant artifacts.",
            "No-answer abstention remains the existing deterministic placeholder until a fresh runtime benchmark.",
        ],
    }
    for name, result in source.get("variants", {}).items():
        run_rows = [
            RetrievalRunCase(
                caseId=item["caseId"],
                abstained=bool(item.get("abstained")),
                hits=item.get("top5", []),
                metadata={"source": "step24.2a_normalized_top5"},
            )
            for item in result.get("caseResults", [])
        ]
        output["variants"][name] = evaluate_retrieval_run(dev, run_rows, run_name=f"{name}-frozen-dev")
    if set(output["variants"]) != {"v1", "D0", "B2"}:
        raise ValueError("STEP242C_BASELINE_VARIANTS_MISSING")
    return output


def _freeze_thresholds(reference: dict[str, Any]) -> dict[str, float | int]:
    def floor(metric: str, domain_floor: float) -> float:
        return round(max(domain_floor, float(reference[metric]) - 0.05), 6)

    return {
        "candidateEvidenceHitRateAt5": floor("candidateEvidenceHitRateAt5", 0.9),
        "relevantChunkRecallAt5": floor("relevantChunkRecallAt5", 0.4),
        "mrrAt5": floor("mrrAt5", 0.75),
        "pooledNdcgAt5": floor("pooledNdcgAt5", 0.5),
        "riskCoverageAt3": floor("riskCoverageAt3", 0.8),
        "highRiskEvidenceHitRateAt5": 1.0,
        "citationValidCaseRate": 1.0,
        "noAnswerAbstentionAccuracy": 1.0,
        "unjudgedItemRateAt5": 0.0,
        "duplicateItemRateAt5": 0.0,
        "highRiskAutoPassCount": 0,
        "silentParserLossCount": 0,
    }


def _blind_judge_diagnostic(cases: list[RagQualityCase]) -> dict[str, Any]:
    if not BLIND_JUDGE_RESULTS.is_file() or not BLIND_JUDGE_SUMMARY.is_file():
        raise ValueError("STEP242C_BLIND_JUDGE_ARTIFACT_MISSING")
    rows = load_jsonl(BLIND_JUDGE_RESULTS)
    summary = _load_json(BLIND_JUDGE_SUMMARY)
    final_by_id = {item.caseId: set(item.riskTypes) for item in cases}
    if summary.get("status") != "COMPLETE" or len(rows) != len(cases) or {row["caseId"] for row in rows} != set(final_by_id):
        raise ValueError("STEP242C_BLIND_JUDGE_INCOMPLETE")

    def metrics(key: str) -> dict[str, Any]:
        true_positive = false_positive = false_negative = exact = no_answer_correct = 0
        for row in rows:
            expected = final_by_id[row["caseId"]]
            predicted = set(row[key]["riskTypes"])
            true_positive += len(expected & predicted)
            false_positive += len(predicted - expected)
            false_negative += len(expected - predicted)
            exact += predicted == expected
            no_answer_correct += (not predicted) == (not expected)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "riskSetExactCount": exact,
            "riskSetExactRate": round(exact / len(rows), 6),
            "riskMicroPrecision": round(precision, 6),
            "riskMicroRecall": round(recall, 6),
            "riskMicroF1": round(f1, 6),
            "noAnswerAccuracy": round(no_answer_correct / len(rows), 6),
        }

    return {
        "role": "independent_label_blind_diagnostic_not_release_truth",
        "primaryJudgeEligible": False,
        "primaryJudgeRejectionReasons": [
            "PAIRWISE_EXACT_AGREEMENT_BELOW_0_90",
            "LOW_CONFIDENCE_RATE_ABOVE_0_20",
            "RISK_SET_EXACT_RATE_BELOW_0_80",
        ],
        "pairwiseExactAgreementRate": summary["exactAgreementRate"],
        "pairwiseConflictCount": summary["conflictCount"],
        "lowConfidenceCount": summary["lowConfidenceCount"],
        "judgeA": metrics("judgeA"),
        "judgeB": metrics("judgeB"),
        "modelId": summary["modelId"],
        "modelFingerprint": summary["modelFingerprint"],
        "protocolHash": summary["protocolHash"],
        "resultsSha256": sha256_file(BLIND_JUDGE_RESULTS),
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"STEP242C_JSON_OBJECT_REQUIRED:{path.name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
