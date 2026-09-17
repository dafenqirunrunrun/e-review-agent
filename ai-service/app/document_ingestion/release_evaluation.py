from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.policy_rag.embedding import PolicyEmbeddingProvider
from app.policy_rag.models import PolicySearchResult, utc_now
from app.policy_rag.retriever import PolicyEvidenceRetriever


EVALUATION_SCHEMA = "policy-release-evaluation-v1"
DEFAULT_SUITE = Path(__file__).resolve().parents[2] / "data" / "benchmarks" / "policy_release_acceptance_v1.json"
RISK_ALIASES = {
    "fake_review": {"fake_review", "fake_engagement", "paid_review", "incentivized_review"},
    "rating_manipulation": {"rating_manipulation", "fake_engagement", "paid_review", "incentivized_review"},
    "review_suppression": {"review_suppression"},
    "after_sales_risk": {"after_sales_risk", "after_sales", "safety_or_fraud_risk", "safety_or_fraud"},
}


def evaluate_policy_release(
    candidate_dir: Path,
    *,
    reference_dir: Path | None,
    provider: PolicyEmbeddingProvider,
    suite_path: Path = DEFAULT_SUITE,
) -> dict[str, Any]:
    suite_bytes = suite_path.read_bytes()
    suite = json.loads(suite_bytes.decode("utf-8-sig"))
    cases = list(suite.get("cases") or [])
    if not cases:
        raise ValueError("RELEASE_EVALUATION_SUITE_EMPTY")
    top_k = int(suite.get("topK", 5))
    candidate = _evaluate_index(candidate_dir, cases, top_k, provider)
    reference = _unavailable("NO_PUBLISHED_REFERENCE")
    if reference_dir and (reference_dir / "policy_chunks.jsonl").is_file():
        reference = _evaluate_index(reference_dir, cases, top_k, provider)
    comparison = _compare(candidate, reference)
    minimum_coverage = float(suite.get("minimumCoverage", 0.9))
    blockers: list[str] = []
    if candidate["metrics"]["criticalCoverageAt5"] < 1.0:
        blockers.append("CRITICAL_RISK_EVIDENCE_MISSING")
    if candidate["metrics"]["riskCoverageAt5"] < minimum_coverage:
        blockers.append("OVERALL_EVIDENCE_COVERAGE_LOW")
    if candidate["metrics"]["citationValidRate"] < 1.0:
        blockers.append("CITATION_INCOMPLETE")
    if candidate["metrics"]["retrievalErrorCount"]:
        blockers.append("RETRIEVAL_FAILED")
    if candidate["metrics"]["fallbackCaseCount"]:
        blockers.append("HYBRID_RETRIEVAL_DEGRADED")
    if comparison["criticalRegressionCount"]:
        blockers.append("CRITICAL_CASE_REGRESSION")
    if blockers:
        decision = "blocked"
    elif candidate["metrics"]["failedCaseCount"] or comparison["regressionCount"]:
        decision = "review_required"
    else:
        decision = "recommended"
    labels = {
        "recommended": "建议发布",
        "review_required": "建议抽查后发布",
        "blocked": "禁止发布",
    }
    return {
        "schemaVersion": EVALUATION_SCHEMA,
        "evaluatedAt": utc_now(),
        "suite": {
            "name": suite.get("name", "政策证据发布验收集"),
            "schemaVersion": suite.get("schemaVersion", ""),
            "sha256": hashlib.sha256(suite_bytes).hexdigest(),
            "caseCount": len(cases),
            "topK": top_k,
            "minimumCoverage": minimum_coverage,
        },
        "decision": decision,
        "decisionLabel": labels[decision],
        "gatePassed": decision != "blocked",
        "reasonCodes": blockers,
        "candidate": candidate,
        "reference": reference,
        "comparison": comparison,
    }


def _evaluate_index(
    directory: Path,
    cases: list[dict[str, Any]],
    top_k: int,
    provider: PolicyEmbeddingProvider,
) -> dict[str, Any]:
    try:
        retriever = PolicyEvidenceRetriever.from_jsonl(
            directory / "policy_chunks.jsonl",
            enable_dense=True,
            embedding_provider=provider,
        )
        readiness = retriever.readiness()
        results = [_evaluate_case(retriever, case, top_k) for case in cases]
    except Exception as exc:
        return _unavailable(type(exc).__name__.upper())
    total_demands = sum(len(item["expectedRiskTypes"]) for item in results)
    supported_demands = sum(len(item["supportedRiskTypes"]) for item in results)
    critical = [item for item in results if item["critical"]]
    citation_valid = [item for item in results if item["citationValid"]]
    failed = [item for item in results if not item["passed"]]
    fallback = [item for item in results if item["actualMode"] != "hybrid"]
    errors = [item for item in results if item["errorCode"]]
    return {
        "available": True,
        "retrievalMode": readiness.get("retrievalMode", "unavailable"),
        "metrics": {
            "caseCount": len(results),
            "passedCaseCount": len(results) - len(failed),
            "failedCaseCount": len(failed),
            "casePassRate": _ratio(len(results) - len(failed), len(results)),
            "riskCoverageAt5": _ratio(supported_demands, total_demands),
            "criticalCoverageAt5": _ratio(sum(1 for item in critical if item["passed"]), len(critical)),
            "citationValidRate": _ratio(len(citation_valid), len(results)),
            "fallbackCaseCount": len(fallback),
            "retrievalErrorCount": len(errors),
        },
        "cases": results,
    }


def _evaluate_case(retriever: PolicyEvidenceRetriever, case: dict[str, Any], top_k: int) -> dict[str, Any]:
    expected = list(dict.fromkeys(case.get("expectedRiskTypes") or []))
    hits: list[PolicySearchResult] = []
    error_code = ""
    try:
        hits = retriever.search(str(case.get("query") or ""), risk_hints=expected, top_k=top_k, mode="hybrid")
    except Exception as exc:
        error_code = type(exc).__name__.upper()
    supported = [risk for risk in expected if any(_supports(hit, risk) for hit in hits)]
    unsupported = [risk for risk in expected if risk not in supported]
    citation_valid = bool(hits) and all(_citation_valid(hit) for hit in hits)
    actual_mode = str((hits[0].retrieval or {}).get("mode") or hits[0].retrievalMode) if hits else "unavailable"
    passed = not unsupported and citation_valid and actual_mode == "hybrid" and not error_code
    return {
        "caseId": str(case.get("caseId") or ""),
        "query": str(case.get("query") or ""),
        "critical": bool(case.get("critical")),
        "expectedRiskTypes": expected,
        "supportedRiskTypes": supported,
        "unsupportedRiskTypes": unsupported,
        "passed": passed,
        "citationValid": citation_valid,
        "actualMode": actual_mode,
        "errorCode": error_code,
        "topHits": [
            {
                "chunkId": hit.chunkId,
                "sourceName": hit.sourceName,
                "clauseId": hit.clauseId,
                "riskTypes": hit.riskTypes,
                "evidenceTags": hit.evidenceTags,
            }
            for hit in hits[:3]
        ],
    }


def _supports(hit: PolicySearchResult, risk: str) -> bool:
    aliases = RISK_ALIASES.get(risk, {risk})
    return bool(aliases.intersection({*hit.riskTypes, *hit.evidenceTags}))


def _citation_valid(hit: PolicySearchResult) -> bool:
    return bool(hit.sourceName and hit.sourceUrl and hit.contentHash and (hit.sectionPath or hit.clauseId))


def _compare(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    if not candidate.get("available") or not reference.get("available"):
        return {
            "available": False,
            "improvementCount": 0,
            "regressionCount": 0,
            "criticalRegressionCount": 0,
            "unchangedCount": 0,
            "regressions": [],
        }
    previous = {item["caseId"]: item for item in reference.get("cases") or []}
    improvements = []
    regressions = []
    unchanged = 0
    for item in candidate.get("cases") or []:
        old = previous.get(item["caseId"])
        if old is None:
            continue
        if item["passed"] and not old["passed"]:
            improvements.append(item)
        elif old["passed"] and not item["passed"]:
            regressions.append(item)
        else:
            unchanged += 1
    return {
        "available": True,
        "improvementCount": len(improvements),
        "regressionCount": len(regressions),
        "criticalRegressionCount": sum(1 for item in regressions if item["critical"]),
        "unchangedCount": unchanged,
        "regressions": regressions,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "retrievalMode": "unavailable",
        "metrics": {
            "caseCount": 0,
            "passedCaseCount": 0,
            "failedCaseCount": 0,
            "casePassRate": 0.0,
            "riskCoverageAt5": 0.0,
            "criticalCoverageAt5": 0.0,
            "citationValidRate": 0.0,
            "fallbackCaseCount": 0,
            "retrievalErrorCount": 1,
        },
        "cases": [],
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
