from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.evidence_coverage import PolicyAdaptiveEvidenceBudget, PolicyEvidenceCoverageSelector
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase
from scripts.run_step242f_after_sales_delta import direct_preferred_metrics
from scripts.run_step242g_after_sales_semantic_dev import DEV_GATES, evidence_query, load_cases, write_json


BINDING_DIR = ROOT / "artifacts" / "step242h_adaptive_evidence_budget" / "bound_repaired_candidate"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index_step242h_candidate" / "policy_chunks.jsonl"
OUTPUT = ROOT / "artifacts" / "step242h_adaptive_evidence_budget" / "dev_ab_repaired_index_result.json"
RETRIEVAL_WINDOW = 50
EVIDENCE_LIMIT = 3


@dataclass(frozen=True)
class Variant:
    name: str
    retrieval_k: int
    fixed_budget: int | None
    demand_aware: bool


EXPERIMENT_VARIANTS = (
    Variant("fixed5_legacy", retrieval_k=20, fixed_budget=5, demand_aware=False),
    Variant("fixed8_rank_only", retrieval_k=30, fixed_budget=8, demand_aware=False),
    Variant("fixed8_coverage_aware", retrieval_k=30, fixed_budget=8, demand_aware=True),
    Variant("adaptive5to10_coverage_aware", retrieval_k=50, fixed_budget=None, demand_aware=True),
)


def main() -> int:
    report = execute_dev_ab()
    write_json(OUTPUT, report)
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    # A HOLD is a valid experimental finding, not an execution failure.
    return 0


def execute_dev_ab() -> dict[str, Any]:
    cases = load_cases(BINDING_DIR / "dev_bound_candidate_v2.jsonl")
    started = time.perf_counter()
    retriever = PolicyEvidenceRetriever.from_jsonl(CHUNKS, enable_dense=True)
    reranker = PolicyEvidenceReranker()
    retriever_readiness = retriever.readiness()
    reranker_readiness = reranker.readiness()
    if retriever_readiness.get("retrievalMode") != "hybrid":
        raise RuntimeError("STEP242H_HYBRID_NOT_READY")
    if not reranker.enabled or reranker_readiness.get("status") != "ready":
        raise RuntimeError("STEP242H_B2_RERANKER_NOT_READY")

    candidates_by_case: dict[str, list[Any]] = {}
    query_by_case: dict[str, str] = {}
    for case in cases:
        if case.noAnswer:
            continue
        query = evidence_query(case)
        candidates = retriever.search(query, risk_hints=case.riskTypes, top_k=RETRIEVAL_WINDOW, mode="hybrid")
        if not candidates or candidates[0].retrieval.get("mode") != "hybrid":
            raise RuntimeError(f"STEP242H_HYBRID_FALLBACK:{case.caseId}")
        query_by_case[case.caseId] = query
        candidates_by_case[case.caseId] = candidates

    selector = PolicyEvidenceCoverageSelector()
    budgeter = PolicyAdaptiveEvidenceBudget()
    variants = {
        variant.name: execute_variant(
            variant,
            cases,
            candidates_by_case,
            query_by_case,
            selector,
            budgeter,
            reranker,
            retriever,
        )
        for variant in EXPERIMENT_VARIANTS
    }
    adaptive = variants["adaptive5to10_coverage_aware"]
    return {
        "schemaVersion": "step242h-adaptive-evidence-budget-dev-v1",
        "gate": adaptive["gate"],
        "scope": "Candidate index and Dev split only. The runtime index, frozen Holdout, and policy source corpus remain unchanged.",
        "protocol": {
            "hybridRetrievalWindow": RETRIEVAL_WINDOW,
            "rerankerBudget": "adaptive 5-10 only for the experiment variant",
            "finalEvidenceBundleLimit": EVIDENCE_LIMIT,
            "defaultCitationDisplayLimit": reranker.final_k,
            "noAnswerPolicy": "abstain_before_retrieval",
        },
        "runtime": {
            "requestedMode": "hybrid",
            "actualMode": "hybrid",
            "retriever": retriever_readiness,
            "reranker": reranker_readiness,
            "retrievalCandidatePool": {"count": RETRIEVAL_WINDOW, "caseCount": len(candidates_by_case)},
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
        },
        "devGates": DEV_GATES,
        "variants": variants,
        "recommendation": recommendation(variants),
        "holdoutExecuted": False,
        "limitation": "Single-Codex semantic ground truth for a personal demo; not human gold.",
    }


def execute_variant(
    variant: Variant,
    cases: list[RagQualityCase],
    candidates_by_case: dict[str, list[Any]],
    query_by_case: dict[str, str],
    selector: PolicyEvidenceCoverageSelector,
    budgeter: PolicyAdaptiveEvidenceBudget,
    reranker: PolicyEvidenceReranker,
    retriever: PolicyEvidenceRetriever,
) -> dict[str, Any]:
    candidate_rows: list[RetrievalRunCase] = []
    final_bundle_rows: list[RetrievalRunCase] = []
    diagnostics: list[dict[str, Any]] = []
    reranker_ms: list[float] = []
    budgets: list[int] = []
    started = time.perf_counter()

    for case in cases:
        if case.noAnswer:
            row = RetrievalRunCase(caseId=case.caseId, abstained=True, metadata={"reason": "EMPTY_UPSTREAM_RISK_HINTS"})
            candidate_rows.append(row)
            final_bundle_rows.append(row)
            continue
        query = query_by_case[case.caseId]
        candidates = candidates_by_case[case.caseId][: variant.retrieval_k]
        plan = budgeter.plan(case.reviewText, case.riskTypes, candidates)
        candidate_limit = variant.fixed_budget if variant.fixed_budget is not None else plan.candidateLimit
        demands = plan.demands if variant.demand_aware else []
        preselection = selector.select(candidates, case.riskTypes, limit=candidate_limit, demands=demands)
        outcome = reranker.rerank(
            query,
            preselection.evidence,
            chunk_resolver=retriever.chunk_for_id,
            candidate_limit=candidate_limit,
        )
        if outcome.metadata.get("fallbackUsed") or outcome.metadata.get("effectiveMode") != "hybrid_bge_reranked":
            raise RuntimeError(f"STEP242H_RERANKER_FALLBACK:{variant.name}:{case.caseId}")
        postselection = final_evidence_bundle(
            selector,
            outcome.ranked_candidates or outcome.evidence,
            case.riskTypes,
            demands,
        )
        reranker_ms.append(float(outcome.metadata.get("durationMs", 0.0)))
        budgets.append(candidate_limit)
        candidate_rows.append(
            retrieval_row(
                case.caseId,
                (outcome.ranked_candidates or outcome.evidence)[: EVIDENCE_LIMIT + 2],
                {
                    "variant": variant.name,
                    "actualMode": "hybrid",
                    "rerankerMode": "hybrid_bge_reranked",
                    "stage": "reranked_candidate_pool",
                    "rerankerCandidateK": candidate_limit,
                },
            )
        )
        final_bundle_rows.append(
            retrieval_row(
                case.caseId,
                postselection.evidence,
                {
                    "variant": variant.name,
                    "actualMode": "hybrid",
                    "rerankerMode": "hybrid_bge_reranked",
                    "stage": "minimal_business_evidence_bundle",
                    "rerankerCandidateK": candidate_limit,
                    "budget": plan.metadata if variant.fixed_budget is None else {"mode": "fixed", "candidateLimit": candidate_limit},
                    "postselection": postselection.metadata,
                },
            )
        )
        diagnostics.append(
            {
                "caseId": case.caseId,
                "candidateCount": len(candidates),
                "budget": plan.metadata if variant.fixed_budget is None else {"mode": "fixed", "candidateLimit": candidate_limit},
                "preselection": preselection.metadata,
                "reranker": outcome.metadata,
                "postselection": postselection.metadata,
            }
        )

    evaluation = evaluate_retrieval_run(cases, candidate_rows, run_name=f"step242h_{variant.name}_candidate_pool")
    final_bundle_evaluation = evaluate_retrieval_run(
        cases,
        final_bundle_rows,
        run_name=f"step242h_{variant.name}_minimal_business_bundle",
    )
    direct = direct_preferred_metrics(cases, candidate_rows)
    final_bundle_direct = direct_preferred_metrics(cases, final_bundle_rows)
    observed = {**evaluation["metrics"], **{key: value for key, value in direct.items() if isinstance(value, (int, float))}}
    checks = {
        name: float(observed.get(name, -1.0)) == threshold if threshold in {0.0, 1.0} else float(observed.get(name, -1.0)) >= threshold
        for name, threshold in DEV_GATES.items()
    }
    return {
        "gate": "PASS" if all(checks.values()) else "HOLD",
        "configuration": {
            "retrievalCandidateK": variant.retrieval_k,
            "rerankerCandidateK": variant.fixed_budget or "adaptive_5_to_10",
            "demandAware": variant.demand_aware,
        },
        "evaluation": evaluation,
        "finalBundleEvaluation": final_bundle_evaluation,
        "directPreferred": direct,
        "finalBundlePreferred": final_bundle_direct,
        "devGateChecks": checks,
        "latency": {
            "variantDurationMs": round((time.perf_counter() - started) * 1000, 2),
            "rerankerAverageMs": round(sum(reranker_ms) / len(reranker_ms), 2) if reranker_ms else 0.0,
            "rerankerP95Ms": percentile95(reranker_ms),
        },
        "budgetDistribution": {str(value): budgets.count(value) for value in sorted(set(budgets))},
        "diagnostics": diagnostics,
    }


def retrieval_row(case_id: str, evidence: list[Any], metadata: dict[str, Any]) -> RetrievalRunCase:
    return RetrievalRunCase(
        caseId=case_id,
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
            for item in evidence
        ],
        metadata=metadata,
    )


def final_evidence_bundle(
    selector: PolicyEvidenceCoverageSelector,
    ranked_candidates: list[Any],
    risk_types: list[str],
    demands: list[Any],
):
    """Return one concise proof when coverage is clear, otherwise three options.

    A missing or ambiguous business demand is an uncertainty signal, not a
    reason to discard the reranker's next best official citations.
    """
    minimal = selector.select(
        ranked_candidates,
        risk_types,
        limit=EVIDENCE_LIMIT,
        demands=demands,
        backfill=False,
    )
    needs_rank_backfill = not demands or bool(minimal.metadata["uncoveredDemandCodes"])
    if not needs_rank_backfill:
        return minimal
    return selector.select(
        ranked_candidates,
        risk_types,
        limit=EVIDENCE_LIMIT,
        demands=demands,
        backfill=True,
    )


def recommendation(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = variants["fixed5_legacy"]
    adaptive = variants["adaptive5to10_coverage_aware"]
    baseline_metrics = baseline["evaluation"]["metrics"]
    adaptive_metrics = adaptive["evaluation"]["metrics"]
    improved = adaptive_metrics["candidateEvidenceHitRateAt5"] > baseline_metrics["candidateEvidenceHitRateAt5"]
    return {
        "status": "CANDIDATE_FOR_HOLDOUT" if adaptive["gate"] == "PASS" and improved else "HOLD",
        "adaptiveImprovesEvidenceHitAt5": improved,
        "baselineEvidenceHitAt5": baseline_metrics["candidateEvidenceHitRateAt5"],
        "adaptiveEvidenceHitAt5": adaptive_metrics["candidateEvidenceHitRateAt5"],
        "reason": (
            "Adaptive budget meets all Dev gates and improves the legacy fixed-5 baseline."
            if adaptive["gate"] == "PASS" and improved
            else "Dev evidence is not yet sufficient to authorize the semantic Holdout or any runtime change."
        ),
    }


def percentile95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))], 2)


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "recommendation": report["recommendation"],
        "variants": {
            name: {
                "gate": value["gate"],
                "metrics": value["evaluation"]["metrics"],
                "directPreferred": {
                    key: metric for key, metric in value["directPreferred"].items() if key != "caseResults"
                },
                "finalBundlePreferred": {
                    key: metric for key, metric in value["finalBundlePreferred"].items() if key != "caseResults"
                },
                "finalBundle": {
                    "metrics": value["finalBundleEvaluation"]["metrics"],
                    "maxEvidence": EVIDENCE_LIMIT,
                },
                "latency": value["latency"],
                "budgetDistribution": value["budgetDistribution"],
            }
            for name, value in report["variants"].items()
        },
        "holdoutExecuted": report["holdoutExecuted"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
