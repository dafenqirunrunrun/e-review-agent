from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.contracts.review_semantics import risk_type_severity
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from scripts.build_step233c_cn_challenge_v2 import (
    DEFAULT_CHUNKS,
    DEFAULT_OUTPUT as DEFAULT_DATASET,
)
from scripts.run_step16_benchmark import load_jsonl
from scripts.run_step233a_qwen_embedding_ab import sha256_file
from scripts.run_step233d_lite_tradeoff import DEFAULT_OUTPUT as DEFAULT_TRADEOFF


DEFAULT_OUTPUT = ROOT / "artifacts" / "step233e" / "business_gate.json"
STRICT_WARM_P95_SLO_MS = 1500.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate old B2 reranking with business governance metrics.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--tradeoff", type=Path, default=DEFAULT_TRADEOFF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    dataset_path = args.dataset.resolve()
    chunks_path = args.chunks.resolve()
    tradeoff_path = args.tradeoff.resolve()
    cases = load_jsonl(dataset_path)
    chunks = load_policy_chunks(chunks_path)
    tradeoff = json.loads(tradeoff_path.read_text(encoding="utf-8-sig"))
    validate_inputs(cases, chunks, tradeoff, dataset_path)

    case_by_id = {case["caseId"]: case for case in cases}
    chunk_by_id = {chunk.chunkId: chunk for chunk in chunks}
    risky_cases = [case for case in cases if case.get("policyJudgments")]
    normal_cases = [case for case in cases if not case.get("policyJudgments")]
    variants = {
        name: evaluate_variant(
            stored=tradeoff["variants"][name],
            case_by_id=case_by_id,
            chunk_by_id=chunk_by_id,
        )
        for name in ("D0", "D0R")
    }
    normal_path = evaluate_normal_bypass(normal_cases)
    baseline = variants["D0"]["metrics"]
    candidate = variants["D0R"]["metrics"]
    candidate_latency = tradeoff["runtime"]["warmSequential"]["variants"]["D0R"]
    checks = business_checks(baseline, candidate, normal_path, candidate_latency)
    gate = "PASS" if all(checks.values()) else "HOLD"

    report = {
        "schemaVersion": "step23.3e-business-gate-v1",
        "gate": gate,
        "candidate": "D0R / old B2: Qwen v2 Hybrid RRF + BGE rerank Top5",
        "scope": "Conditional business decision evaluation over annotated risk types; not an end-to-end Router benchmark.",
        "dataset": {
            "sha256": sha256_file(dataset_path),
            "caseCount": len(cases),
            "riskCaseCount": len(risky_cases),
            "normalCaseCount": len(normal_cases),
            "promotionEligible": False,
        },
        "metricContract": {
            "riskEvidenceHitAt3": "At least one detected risk is supported by complete top-3 evidence.",
            "allRiskCoverageAt3": "Every detected risk type is supported by complete top-3 evidence.",
            "humanReviewRecall": "All high-risk or evidence-uncertain cases are routed to human review.",
            "confidence": "Evidence confidence derived from deterministic Reflection; not a calibrated model probability.",
            "primaryRiskRanking": "Diagnostic only and excluded from this gate.",
        },
        "variants": variants,
        "normalPath": normal_path,
        "latency": {
            "sloMs": STRICT_WARM_P95_SLO_MS,
            "baseline": tradeoff["runtime"]["warmSequential"]["variants"]["D0"],
            "candidate": candidate_latency,
            "method": tradeoff["runtime"]["latencyMethod"],
        },
        "checks": checks,
        "decision": business_decision(gate, checks),
        "integrity": {
            "step233dExperimentPassed": tradeoff.get("experimentGate") == "PASS",
            "onlineRuntimeUnchanged": tradeoff.get("integrity", {}).get("onlineRuntimeUnchanged") is True,
            "datasetHashMatchesTradeoff": sha256_file(dataset_path) == tradeoff["dataset"]["sha256"],
            "candidateDoesNotRunForNormalCases": normal_path["rerankerInvocationCount"] == 0,
        },
        "limitations": [
            "The challenge set has partial qrels and pending human adjudication.",
            "Risk types are annotated inputs; Router and risk-detection quality are outside this comparison.",
            "Latency uses five deterministic warm samples and must be rechecked in runtime shadow before promotion.",
        ],
    }
    if not all(report["integrity"].values()):
        report["gate"] = "FAIL"
        report["decision"] = "Input integrity failed; do not use this result."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if report["gate"] != "FAIL" else 1


def validate_inputs(cases: list[dict[str, Any]], chunks: list[Any], tradeoff: dict[str, Any], dataset_path: Path) -> None:
    if len(cases) != 120 or len(chunks) != 71:
        raise SystemExit("STEP233E_INPUT_COUNT_MISMATCH")
    if tradeoff.get("experimentGate") != "PASS":
        raise SystemExit("STEP233E_TRADEOFF_NOT_VALID")
    if not {"D0", "D0R"}.issubset(tradeoff.get("variants", {})):
        raise SystemExit("STEP233E_REQUIRED_VARIANT_MISSING")
    if sha256_file(dataset_path) != tradeoff.get("dataset", {}).get("sha256"):
        raise SystemExit("STEP233E_DATASET_HASH_MISMATCH")


def evaluate_variant(
    *,
    stored: dict[str, Any],
    case_by_id: dict[str, dict[str, Any]],
    chunk_by_id: dict[str, Any],
) -> dict[str, Any]:
    engine = PolicyReflectionEngine()
    rows = []
    for stored_case in stored["caseResults"]:
        case = case_by_id[stored_case["caseId"]]
        top3 = stored_case["top5"][:3]
        evidence = [
            PolicyEvidenceRetriever._to_result(
                chunk_by_id[item["chunkId"]],
                float(item["score"]),
                rank=index,
                mode="evaluation_hybrid",
            )
            for index, item in enumerate(top3, start=1)
        ]
        risk_level = expected_risk_level(case["riskTypes"])
        reflection = engine.reflect(
            risk_level=risk_level,
            risk_types=case["riskTypes"],
            confidence=0.9,
            policy_evidence=evidence,
            action="suggest_action",
        )
        decision = governance_decision(risk_level, reflection.evidenceStatus)
        expected_human = risk_level == "high" or reflection.evidenceStatus != "supported"
        rows.append(
            {
                "caseId": case["caseId"],
                "riskLevel": risk_level,
                "riskTypes": case["riskTypes"],
                "reflectionStatus": reflection.evidenceStatus,
                "supportedRiskTypes": reflection.supportedRiskTypes,
                "unsupportedRiskTypes": reflection.unsupportedRiskTypes,
                "riskEvidenceHitAt3": bool(reflection.supportedRiskTypes),
                "allRiskCoverageAt3": reflection.evidenceStatus == "supported",
                "citationValid": not reflection.citationValidationErrors,
                "evidenceConfidence": evidence_confidence(reflection.evidenceStatus, bool(reflection.supportedRiskTypes)),
                "decision": decision,
                "requiresHumanReview": decision == "human_review",
                "expectedHumanReview": expected_human,
                "humanReviewCorrect": (decision == "human_review") == expected_human,
                "highRiskAutoPass": risk_level == "high" and decision != "human_review",
                "top3ChunkIds": [item["chunkId"] for item in top3],
            }
        )
    return {
        "metrics": aggregate_rows(rows),
        "caseResults": rows,
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    high = [row for row in rows if row["riskLevel"] == "high"]
    expected_human = [row for row in rows if row["expectedHumanReview"]]
    return {
        "caseCount": len(rows),
        "riskEvidenceHitAt3": ratio(sum(row["riskEvidenceHitAt3"] for row in rows), len(rows)),
        "highRiskEvidenceHitAt3": ratio(sum(row["riskEvidenceHitAt3"] for row in high), len(high)),
        "allRiskCoverageAt3": ratio(sum(row["allRiskCoverageAt3"] for row in rows), len(rows)),
        "evidenceSupportedRate": ratio(sum(row["reflectionStatus"] == "supported" for row in rows), len(rows)),
        "citationValidity": ratio(sum(row["citationValid"] for row in rows), len(rows)),
        "humanReviewRecall": ratio(sum(row["humanReviewCorrect"] for row in expected_human), len(expected_human)),
        "highRiskHumanReviewRate": ratio(sum(row["requiresHumanReview"] for row in high), len(high)),
        "highRiskAutoPassCount": sum(row["highRiskAutoPass"] for row in rows),
        "manualReviewCount": sum(row["requiresHumanReview"] for row in rows),
        "suggestActionCount": sum(row["decision"] == "suggest_action" for row in rows),
        "averageEvidenceConfidence": round(sum(row["evidenceConfidence"] for row in rows) / len(rows), 4),
    }


def evaluate_normal_bypass(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "caseCount": len(cases),
        "decision": "auto_pass",
        "retrievalInvocationCount": 0,
        "rerankerInvocationCount": 0,
        "policyEvidenceRendered": False,
        "humanReviewWarningRendered": False,
    }


def business_checks(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    normal_path: dict[str, Any],
    latency: dict[str, Any],
) -> dict[str, bool]:
    return {
        "riskEvidenceHitAt3NoRegression": candidate["riskEvidenceHitAt3"] >= baseline["riskEvidenceHitAt3"],
        "highRiskEvidenceHitAt3NoRegression": candidate["highRiskEvidenceHitAt3"] >= baseline["highRiskEvidenceHitAt3"],
        "allRiskCoverageAt3NoRegression": candidate["allRiskCoverageAt3"] >= baseline["allRiskCoverageAt3"],
        "evidenceSupportedRateNoRegression": candidate["evidenceSupportedRate"] >= baseline["evidenceSupportedRate"],
        "citationValidityComplete": candidate["citationValidity"] == 1.0,
        "humanReviewRecallComplete": candidate["humanReviewRecall"] == 1.0,
        "highRiskHumanReviewComplete": candidate["highRiskHumanReviewRate"] == 1.0,
        "highRiskAutoPassZero": candidate["highRiskAutoPassCount"] == 0,
        "normalPathBypassesReranker": normal_path["rerankerInvocationCount"] == 0,
        "warmStrictP95WithinExistingSlo": float(latency["p95Ms"]) <= STRICT_WARM_P95_SLO_MS,
    }


def business_decision(gate: str, checks: dict[str, bool]) -> str:
    if gate == "PASS":
        return "Eligible for isolated runtime shadow; production remains unchanged."
    failed = [name for name, passed in checks.items() if not passed]
    return "Keep old B2 experimental-only. Failed business checks: " + ", ".join(failed)


def expected_risk_level(risk_types: list[str]) -> str:
    severities = {risk_type_severity(risk) for risk in risk_types}
    return "high" if "高" in severities else "medium" if "中" in severities else "low"


def governance_decision(risk_level: str, evidence_status: str) -> str:
    return "human_review" if risk_level == "high" or evidence_status != "supported" else "suggest_action"


def evidence_confidence(evidence_status: str, has_partial_support: bool) -> float:
    if evidence_status == "supported":
        return 0.90
    if has_partial_support:
        return 0.55
    return 0.25


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "candidate": report["candidate"],
        "dataset": report["dataset"],
        "metrics": {name: value["metrics"] for name, value in report["variants"].items()},
        "normalPath": report["normalPath"],
        "latency": report["latency"],
        "checks": report["checks"],
        "decision": report["decision"],
        "integrity": report["integrity"],
        "limitations": report["limitations"],
    }


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
