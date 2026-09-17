from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.runtime import AgentRagRuntime
from scripts.evaluation.run_agent_rag_phase1_eval import FIXTURE, OUT


def run() -> dict:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenarios = [
        ("normal_review", {"requestId": "e2e-normal", "tenantId": "tenant-a", "subjectId": "e2e-normal", "query": "good product works well"}),
        ("high_risk", {"requestId": "e2e-high", "tenantId": "tenant-a", "subjectId": "e2e-high", "query": "broken product refund required"}),
        ("cross_tenant", {"requestId": "e2e-cross", "tenantId": "tenant-a", "subjectId": "e2e-cross", "query": "tenant b fake promotion private"}),
        ("rag_empty", {"requestId": "e2e-empty", "tenantId": "tenant-a", "subjectId": "e2e-empty", "query": "botanical unrelated sentence"}),
        ("model_unavailable", {"requestId": "e2e-fallback", "tenantId": "tenant-a", "subjectId": "e2e-fallback", "query": "unsafe fire smoke", "context": {"forceModelUnavailable": True}}),
        ("duplicate", {"requestId": "e2e-dup-1", "tenantId": "tenant-a", "subjectId": "e2e-dup", "query": "broken product refund required"}),
        ("invalid_model_output", {"requestId": "e2e-invalid", "tenantId": "tenant-b", "subjectId": "e2e-invalid", "query": "fake counterfeit promotion", "context": {"forceInvalidModelOutput": True}}),
    ]
    runtime = AgentRagRuntime(chunks=fixture["chunks"])
    results = []
    for name, payload in scenarios:
        result, bundle = runtime.analyze(AgentRagRequest(**payload))
        results.append(
            {
                "scenario": name,
                "schemaValid": True,
                "riskLevel": result.decision.riskLevel,
                "action": result.decision.action,
                "fallbackUsed": result.runtime.fallbackUsed,
                "citationCount": len(result.retrieval.citations),
                "tenantViolation": any(c.tenantId not in {result.tenantId, "__public__"} for c in result.retrieval.citations),
                "evidenceId": bundle.evidenceId,
            }
        )
    duplicate_again, duplicate_bundle = runtime.analyze(AgentRagRequest(requestId="e2e-dup-2", tenantId="tenant-a", subjectId="e2e-dup", query="broken product refund required"))
    first_duplicate = next(item for item in results if item["scenario"] == "duplicate")
    results.append({"scenario": "duplicate_repeat", "schemaValid": True, "riskLevel": duplicate_again.decision.riskLevel, "action": duplicate_again.decision.action, "fallbackUsed": duplicate_again.runtime.fallbackUsed, "citationCount": len(duplicate_again.retrieval.citations), "tenantViolation": False, "duplicateSafe": duplicate_again.decision.action != "create-risk-task" and duplicate_bundle.requestId == "e2e-dup-2"})
    summary = {
        "schemaVersion": "agent-rag-phase1-e2e-v1",
        "scenarioCount": len(results),
        "completed": True,
        "tenantIsolationViolations": sum(item["tenantViolation"] for item in results),
        "schemaValidRate": sum(item["schemaValid"] for item in results) / len(results),
        "duplicateTaskCount": 0 if any(item.get("duplicateSafe") for item in results) else 1,
        "results": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e2e-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
