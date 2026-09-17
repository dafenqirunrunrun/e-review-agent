from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase


DATA_DIR = ROOT / "data" / "benchmarks" / "rag_quality_after_sales_delta_v1"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
ARTIFACT_DIR = ROOT / "artifacts" / "step242f_after_sales_delta"


class AfterSalesEvaluationError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the real B2 policy path for the after-sales delta evaluation.")
    parser.add_argument("--split", choices=("dev", "holdout"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ARTIFACT_DIR / f"{args.split}_b2_result.json"
    report = execute(args.split)
    write_json_atomic(output, report)
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


def execute(split: str) -> dict[str, Any]:
    cases = load_cases(split)
    manifest = read_json(DATA_DIR / "manifest_llm_adjudicated_v1.json")
    validate_inputs(cases, manifest, split)
    started = time.perf_counter()
    retriever = PolicyEvidenceRetriever.from_jsonl(CHUNKS, enable_dense=True)
    reranker = PolicyEvidenceReranker()
    retrieval_readiness = retriever.readiness()
    reranker_readiness = reranker.readiness()
    if retrieval_readiness.get("retrievalMode") != "hybrid":
        raise AfterSalesEvaluationError("STEP242F_HYBRID_RETRIEVAL_NOT_READY")
    if not reranker.enabled or reranker_readiness.get("status") != "ready":
        raise AfterSalesEvaluationError("STEP242F_B2_RERANKER_NOT_READY")

    selector = PolicyEvidenceCoverageSelector()
    run_rows: list[RetrievalRunCase] = []
    pipeline_rows: list[dict[str, Any]] = []
    for case in cases:
        if case.noAnswer:
            run_rows.append(
                RetrievalRunCase(
                    caseId=case.caseId,
                    abstained=True,
                    metadata={"reason": "EMPTY_FROZEN_UPSTREAM_RISK_HINTS"},
                )
            )
            continue
        query = evidence_query(case)
        candidates = retriever.search(query, risk_hints=case.riskTypes, top_k=20, mode="hybrid")
        if not candidates or candidates[0].retrieval.get("mode") != "hybrid":
            raise AfterSalesEvaluationError(f"STEP242F_HYBRID_RETRIEVAL_FALLBACK:{case.caseId}")
        preselection = selector.select(candidates, case.riskTypes, limit=5)
        outcome = reranker.rerank(query, preselection.evidence, chunk_resolver=retriever.chunk_for_id)
        if outcome.metadata.get("fallbackUsed") or outcome.metadata.get("effectiveMode") != "hybrid_bge_reranked":
            raise AfterSalesEvaluationError(f"STEP242F_RERANKER_FALLBACK:{case.caseId}")
        postselection = selector.select(
            outcome.ranked_candidates or outcome.evidence,
            case.riskTypes,
            limit=5,
        )
        run_rows.append(
            RetrievalRunCase(
                caseId=case.caseId,
                hits=[
                    RetrievalHit(
                        chunkId=item.chunkId,
                        score=item.score,
                        sourceName=item.sourceName,
                        sourceUrl=item.sourceUrl,
                        sectionPath=item.sectionPath,
                        clauseId=item.clauseId,
                        contentHash=item.contentHash,
                    )
                    for item in postselection.evidence
                ],
                metadata={"variant": "B2", "actualMode": "hybrid", "rerankerMode": "hybrid_bge_reranked"},
            )
        )
        pipeline_rows.append(
            {
                "caseId": case.caseId,
                "query": query,
                "candidateCount": len(candidates),
                "preselection": preselection.metadata,
                "reranker": outcome.metadata,
                "postselection": postselection.metadata,
            }
        )

    evaluation = evaluate_retrieval_run(cases, run_rows, run_name=f"after_sales_delta_{split}_b2")
    direct_preferred = direct_preferred_metrics(cases, run_rows)
    threshold_checks: dict[str, bool] = {}
    if split == "holdout":
        thresholds = read_frozen_thresholds(manifest)
        threshold_checks = evaluate_thresholds(evaluation["metrics"], direct_preferred, thresholds)
        gate = "PASS" if all(threshold_checks.values()) else "FAIL"
    else:
        thresholds = {}
        gate = "PASS" if evaluation["promotionGate"] == "PASS" else "FAIL"
    return {
        "schemaVersion": "step24.2f-after-sales-delta-run-v1",
        "executedAt": utc_now(),
        "gate": gate,
        "split": split,
        "dataset": {
            "version": cases[0].datasetVersion,
            "caseCount": len(cases),
            "riskCaseCount": sum(not case.noAnswer for case in cases),
            "noAnswerCaseCount": sum(case.noAnswer for case in cases),
            "datasetSha256": sha256_file(DATA_DIR / f"{split}_llm_adjudicated_v1.jsonl"),
            "corpusContentRootHash": manifest["corpus"]["contentRootHash"],
        },
        "protocol": {
            "name": "current_runtime_b2_hybrid_coverage_rerank",
            "queryRole": "review_text_plus_after_sales_risk_plus_shared_policy_terms",
            "retrievalCandidateK": 20,
            "coverageSelectionLimit": 5,
            "rerankCandidateK": reranker.candidate_k,
            "finalEvidenceLimit": 5,
            "noAnswerPolicy": "empty_upstream_risk_hints_abstain_before_retrieval",
        },
        "runtime": {
            "requestedMode": "hybrid",
            "actualMode": "hybrid",
            "retriever": retrieval_readiness,
            "reranker": reranker_readiness,
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
        },
        "evaluation": evaluation,
        "directPreferred": direct_preferred,
        "thresholds": thresholds,
        "thresholdChecks": threshold_checks,
        "pipeline": pipeline_rows,
        "limitation": "Corpus-bound, single-Codex-adjudicated after-sales delta evaluation. It does not replace the old frozen 71-chunk benchmark or establish global workflow quality.",
    }


def load_cases(split: str) -> list[RagQualityCase]:
    path = DATA_DIR / f"{split}_llm_adjudicated_v1.jsonl"
    return [RagQualityCase.model_validate(json.loads(line)) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def validate_inputs(cases: list[RagQualityCase], manifest: dict[str, Any], split: str) -> None:
    current_hash = content_root_hash_from_jsonl(CHUNKS)
    checks = {
        "correctSplit": bool(cases) and all(case.split == split for case in cases),
        "completeQrels": all(case.qrelCompleteness == "complete" and len(case.qrels) == 123 for case in cases),
        "releaseAnnotated": all(case.annotationStatus == "llm_adjudicated" and not case.requiresAdjudication for case in cases),
        "corpusCount": manifest.get("corpus", {}).get("chunkCount") == 123,
        "corpusHash": manifest.get("corpus", {}).get("contentRootHash") == current_hash,
        "holdoutAuthorized": split != "holdout" or manifest.get("annotation", {}).get("thresholdsFrozen") is True,
        "holdoutNotConsumed": split != "holdout" or not (ARTIFACT_DIR / "holdout_execution_seal.json").exists(),
    }
    if not all(checks.values()):
        raise AfterSalesEvaluationError(f"STEP242F_INPUT_INTEGRITY_FAILED:{checks}")


def evidence_query(case: RagQualityCase) -> str:
    return " ".join(
        [
            case.reviewText[:240],
            " ".join(case.riskTypes),
            "fake review paid incentive conflict of interest review suppression refund after-sales",
        ]
    )


def direct_preferred_metrics(cases: list[RagQualityCase], rows: list[RetrievalRunCase]) -> dict[str, Any]:
    rows_by_case = {row.caseId: row for row in rows}
    risk_cases = [case for case in cases if not case.noAnswer]
    at1 = 0
    at3 = 0
    per_case: list[dict[str, Any]] = []
    for case in risk_cases:
        preferred = {qrel.chunkId for qrel in case.qrels if qrel.relevance == 3}
        hits = [hit.chunkId for hit in rows_by_case[case.caseId].hits]
        hit_at_1 = bool(hits and hits[0] in preferred)
        hit_at_3 = bool(preferred.intersection(hits[:3]))
        at1 += hit_at_1
        at3 += hit_at_3
        per_case.append({"caseId": case.caseId, "preferredChunkIds": sorted(preferred), "top3": hits[:3], "hitAt1": hit_at_1, "hitAt3": hit_at_3})
    denominator = len(risk_cases)
    return {
        "riskCaseCount": denominator,
        "directPreferredHitRateAt1": ratio(at1, denominator),
        "directPreferredHitRateAt3": ratio(at3, denominator),
        "caseResults": per_case,
    }


def read_frozen_thresholds(manifest: dict[str, Any]) -> dict[str, float]:
    policy = manifest.get("qualityThresholds") or {}
    thresholds = policy.get("thresholds")
    if policy.get("status") != "FROZEN" or not isinstance(thresholds, dict):
        raise AfterSalesEvaluationError("STEP242F_HOLDOUT_THRESHOLDS_NOT_FROZEN")
    return {str(name): float(value) for name, value in thresholds.items()}


def evaluate_thresholds(metrics: dict[str, Any], direct_preferred: dict[str, Any], thresholds: dict[str, float]) -> dict[str, bool]:
    observed = {**metrics, **{name: value for name, value in direct_preferred.items() if isinstance(value, (int, float))}}
    exact = {"citationValidCaseRate", "noAnswerAbstentionAccuracy", "unjudgedItemRateAt5", "duplicateItemRateAt5"}
    return {
        name: float(observed.get(name, -1.0)) == threshold if name in exact else float(observed.get(name, -1.0)) >= threshold
        for name, threshold in thresholds.items()
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def content_root_hash_from_jsonl(path: Path) -> str:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return hashlib.sha256("|".join(str(row["contentHash"]) for row in rows).encode("utf-8")).hexdigest()


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "split": report["split"],
        "metrics": report["evaluation"]["metrics"],
        "directPreferred": {key: value for key, value in report["directPreferred"].items() if key != "caseResults"},
        "runtime": {"actualMode": report["runtime"]["actualMode"], "durationMs": report["runtime"]["durationMs"]},
        "thresholdChecks": report["thresholdChecks"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
