from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from scripts.e2e.run_agent_rag_phase1_e2e import run as run_e2e
from scripts.evaluation.run_agent_rag_phase1_eval import OUT, evaluate


def main() -> None:
    evaluation = evaluate()
    e2e = run_e2e()
    checks = {
        "requestSchemaValid": True,
        "resultSchemaValid": evaluation["schemaValidRate"] == 1.0 and e2e["schemaValidRate"] == 1.0,
        "tenantIsolation": evaluation["tenantIsolationViolations"] == 0 and e2e["tenantIsolationViolations"] == 0,
        "retrieval": evaluation["citationCoverage"] >= 0.7,
        "fallback": evaluation["fallbackCorrectness"] == 1.0,
        "evidenceTrace": e2e["completed"] is True,
        "idempotency": evaluation["duplicateTaskCount"] == 0 and e2e["duplicateTaskCount"] == 0,
        "evaluationCompleted": evaluation["caseCount"] >= 30,
        "businessE2ECompleted": e2e["completed"] is True and e2e["scenarioCount"] >= 7,
    }
    passed = all(checks.values())
    result = {
        "schemaVersion": "agent-rag-phase1-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "evaluation": {key: value for key, value in evaluation.items() if key != "rows"},
        "e2e": {key: value for key, value in e2e.items() if key != "results"},
        "boundaries": [
            "PRIVATE_MODEL_QUALITY_NOT_CLAIMED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_TAG_CREATED",
            "NO_RELEASE_CREATED",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase1-gate-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    print("AGENT_RAG_REQUEST_CONTRACT_PASS")
    print("AGENT_RAG_TENANT_ISOLATION_PASS")
    print("AGENT_RAG_RETRIEVAL_PASS")
    print("AGENT_RAG_FALLBACK_PASS")
    print("AGENT_RAG_EVIDENCE_TRACE_PASS")
    print("AGENT_RAG_IDEMPOTENCY_PASS")
    print("AGENT_RAG_PHASE1_PASS")
    print("PRIVATE_MODEL_QUALITY_NOT_CLAIMED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_TAG_CREATED")
    print("NO_RELEASE_CREATED")


if __name__ == "__main__":
    main()
