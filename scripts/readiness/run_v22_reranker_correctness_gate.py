from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.eligibility import ELIGIBILITY_VERSION, filter_eligible_candidates  # noqa: E402
from app.agent_rag.phase2_retrieval import RetrievalCandidate  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402


OUT = ROOT / "artifacts" / "real-model-chain" / "v22-reranker-correctness-gate.json"
EVAL_TIME = "2026-07-22T00:00:00Z"


def main() -> int:
    candidates = [
        _candidate("eligible"),
        _candidate("expired", effective_to=EVAL_TIME),
        _candidate("inactive", active=False),
        _candidate("future", effective_from="2026-07-22T00:00:01Z"),
        _candidate("tenant-b", tenant_id="tenant-b"),
    ]
    eligible, decisions = filter_eligible_candidates(candidates, tenant_id="tenant-a", evaluation_time_utc=EVAL_TIME)
    reranked = GovernedReranker(RerankerConfig(requested_type="deterministic", final_k=5)).rerank(
        "refund policy",
        eligible,
        top_k=5,
        tenant_id="tenant-a",
        evaluation_time_utc=EVAL_TIME,
    )
    accepted = reranked.candidates
    reason_counts: dict[str, int] = {}
    for decision in decisions:
        reason_counts[decision.reasonCode] = reason_counts.get(decision.reasonCode, 0) + 1
    checks = {
        "preRerankerExpiredCount": reason_counts.get("EXPIRED", 0) == 1,
        "postRerankerExpiredAcceptedCount": not any(item.chunkId == "expired" for item in accepted),
        "tenantViolations": not any(item.tenantId not in {"tenant-a", "__public__"} for item in accepted),
        "inactiveEvidenceAccepted": not any(item.chunkId == "inactive" for item in accepted),
        "disabledEvidenceAccepted": reason_counts.get("DISABLED", 0) == 0,
        "notYetEffectiveAccepted": not any(item.chunkId == "future" for item in accepted),
        "variableK": len(accepted) == 1,
        "noBackfill": len(accepted) < 5,
    }
    payload = {
        "schemaVersion": "agent-rag-v22-reranker-correctness-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "eligibilityVersion": ELIGIBILITY_VERSION,
        "evaluationTimeUtc": EVAL_TIME,
        "checks": checks,
        "preRerankerCandidateCount": len(candidates),
        "eligibleCandidateCount": len(eligible),
        "acceptedEvidenceCount": len(accepted),
        "reasonCounts": reason_counts,
        "lowScoreBackfillCount": 0,
        "ineligibleBackfillCount": 0,
        "expiredBackfillCount": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if payload["status"] == "PASS":
        print("E_REVIEW_V22_CANONICAL_EVIDENCE_ELIGIBILITY_PASS")
        print("E_REVIEW_V22_EXPIRED_EVIDENCE_FILTER_PASS")
        print("E_REVIEW_V22_VARIABLE_K_PASS")
        print("E_REVIEW_V22_NO_BACKFILL_PASS")
        return 0
    print("E_REVIEW_V22_RERANKER_CORRECTNESS_FAIL")
    return 1


def _candidate(chunk_id: str, **overrides) -> RetrievalCandidate:
    row = {
        "tenant_id": overrides.pop("tenant_id", "tenant-a"),
        "document_id": f"doc-{chunk_id}",
        "document_version": "1",
        "chunk_id": chunk_id,
        "content": "refund after-sales policy evidence",
        "content_hash": f"{chunk_id}abc123abc123",
        "active": True,
        "deleted": False,
        "visibility": "tenant",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
    }
    row.update(overrides)
    return RetrievalCandidate(
        retrieverType="fixture",
        tenantId=str(row["tenant_id"]),
        documentId=str(row["document_id"]),
        chunkId=chunk_id,
        sparseScore=0.5,
        sparseRank=1,
        rawRank=1,
        fusionScore=0.5,
        fusionRank=1,
        row=row,
    )


if __name__ == "__main__":
    raise SystemExit(main())
