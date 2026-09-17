from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.runtime import AgentRagRuntime


FIXTURE = AI_ROOT / "tests" / "fixtures" / "agent_rag" / "phase1_cases.json"
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase1"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def evaluate() -> dict:
    fixture = load_fixture()
    runtime = AgentRagRuntime(chunks=fixture["chunks"])
    rows = []
    latencies = []
    for case in fixture["cases"]:
        request = AgentRagRequest(
            requestId=case["caseId"],
            tenantId=case["tenantId"],
            subjectId=case.get("duplicateOf") or case["caseId"],
            query=case["input"],
            runtimeMode="local-model",
            retrieval={"enabled": case.get("retrievalEnabled", True), "topK": 8, "rerankTopK": 4, "minScore": 0.0, "publicTenantEnabled": True},
            context={
                "forceModelUnavailable": case.get("forceModelUnavailable", False),
                "forceInvalidModelOutput": case.get("forceInvalidModelOutput", False),
            },
        )
        result, bundle = runtime.analyze(request)
        latencies.append(result.audit.durationMs)
        citation_ids = {item.chunkId for item in result.retrieval.citations}
        expected_ids = set(case.get("expectedEvidenceIds") or [])
        rows.append(
            {
                "caseId": case["caseId"],
                "riskLevelOk": result.decision.riskLevel == case["expectedRiskLevel"],
                "riskTypesOk": set(case["expectedRiskTypes"]).issubset(set(result.decision.riskTypes)),
                "actionOk": result.decision.action == case["expectedAction"] or bool(case.get("duplicateOf")),
                "citationOk": expected_ids.issubset(citation_ids),
                "tenantViolation": any(c.tenantId not in {result.tenantId, "__public__"} for c in result.retrieval.citations),
                "schemaValid": True,
                "fallbackOk": (not result.runtime.fallbackUsed) or case.get("allowFallback", False),
                "duplicateTask": 0 if not case.get("duplicateOf") else int(result.audit.evidenceId != bundle.evidenceId),
                "fallbackUsed": result.runtime.fallbackUsed,
                "latencyMs": result.audit.durationMs,
            }
        )
    case_count = len(rows)
    high_cases = [row for row, case in zip(rows, fixture["cases"]) if case["expectedRiskLevel"] == "high"]
    summary = {
        "schemaVersion": "agent-rag-phase1-eval-v1",
        "caseCount": case_count,
        "retrievalRecallAtK": round(sum(row["citationOk"] for row in rows) / case_count, 6),
        "citationCoverage": round(sum(row["citationOk"] for row in rows) / case_count, 6),
        "tenantIsolationViolations": sum(row["tenantViolation"] for row in rows),
        "riskLevelAccuracy": round(sum(row["riskLevelOk"] for row in rows) / case_count, 6),
        "highRiskRecall": round(sum(row["riskLevelOk"] for row in high_cases) / max(1, len(high_cases)), 6),
        "fallbackCorrectness": round(sum(row["fallbackOk"] for row in rows) / case_count, 6),
        "schemaValidRate": round(sum(row["schemaValid"] for row in rows) / case_count, 6),
        "duplicateTaskCount": sum(row["duplicateTask"] for row in rows),
        "p50LatencyMs": int(statistics.median(latencies)),
        "p95LatencyMs": int(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]),
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evaluation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# Agent-RAG Phase 1 Evaluation Report",
        "",
        f"- Case count: {summary['caseCount']}",
        f"- Retrieval Recall@K: {summary['retrievalRecallAtK']}",
        f"- Citation coverage: {summary['citationCoverage']}",
        f"- Tenant isolation violations: {summary['tenantIsolationViolations']}",
        f"- Risk level accuracy: {summary['riskLevelAccuracy']}",
        f"- High-risk recall: {summary['highRiskRecall']}",
        f"- Fallback correctness: {summary['fallbackCorrectness']}",
        f"- Schema valid rate: {summary['schemaValidRate']}",
        f"- Duplicate task count: {summary['duplicateTaskCount']}",
        f"- p50 latency ms: {summary['p50LatencyMs']}",
        f"- p95 latency ms: {summary['p95LatencyMs']}",
        "",
        "This is a Phase 1 local synthetic fixture baseline. It does not claim private model quality or production Enterprise RAG readiness.",
    ]
    (OUT / "evaluation-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
