import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent_rag.contracts import AgentRagRequest, AgentRagResult
from app.agent_rag.runtime import AgentRagRuntime


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "agent_rag" / "phase1_cases.json"
ROOT = Path(__file__).resolve().parents[2]


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _runtime(model_available=True):
    return AgentRagRuntime(chunks=_fixture()["chunks"], model_available=model_available)


def test_v200_request_contract_rejects_missing_tenant_and_bad_schema():
    with pytest.raises(ValidationError):
        AgentRagRequest(requestId="r1", tenantId="", subjectId="s1", query="refund")
    with pytest.raises(ValidationError):
        AgentRagRequest(requestId="r1", tenantId="tenant-a", subjectId="s1", query="refund", schemaVersion="1.0.0")


def test_v200_result_contract_and_evidence_bundle_are_schema_valid():
    result, bundle = _runtime().analyze(AgentRagRequest(requestId="r1", tenantId="tenant-a", subjectId="s1", query="broken product refund"))
    AgentRagResult.model_validate(result.model_dump(mode="json"))
    assert result.requestId == bundle.requestId == "r1"
    assert result.audit.evidenceId == bundle.evidenceId
    assert bundle.agentTrace
    assert all(step.inputHash and step.outputHash for step in bundle.agentTrace)


def test_v200_tenant_isolation_allows_private_current_tenant_and_public_only():
    result, _ = _runtime().analyze(AgentRagRequest(requestId="r2", tenantId="tenant-a", subjectId="s2", query="tenant b refund private"))
    tenants = {item.tenantId for item in result.retrieval.citations}
    assert "tenant-b" not in tenants
    assert tenants <= {"tenant-a", "__public__"}


def test_v200_unknown_tenant_retrieves_only_public_or_empty():
    result, _ = _runtime().analyze(AgentRagRequest(requestId="r3", tenantId="unknown-tenant", subjectId="s3", query="refund broken product"))
    assert {item.tenantId for item in result.retrieval.citations} <= {"__public__"}


def test_v200_retrieval_deduplicates_citations_by_content_hash():
    fixture = _fixture()
    duplicate = dict(fixture["chunks"][0])
    duplicate["chunk_id"] = "a-after-sales-duplicate"
    fixture["chunks"].append(duplicate)
    result, _ = AgentRagRuntime(chunks=fixture["chunks"]).analyze(AgentRagRequest(requestId="r4", tenantId="tenant-a", subjectId="s4", query="broken product refund"))
    hashes = [item.contentHash for item in result.retrieval.citations]
    assert len(hashes) == len(set(hashes))


def test_v200_empty_retrieval_does_not_fabricate_citations():
    result, _ = _runtime().analyze(AgentRagRequest(requestId="r5", tenantId="tenant-a", subjectId="s5", query="botanical unrelated sentence"))
    assert result.retrieval.retrievalEmpty is True
    assert result.retrieval.citations == []


def test_v200_model_unavailable_uses_rule_fallback_without_low_risk_downgrade():
    result, _ = _runtime(model_available=False).analyze(AgentRagRequest(requestId="r6", tenantId="tenant-a", subjectId="s6", query="unsafe fire smoke"))
    assert result.runtime.engineType == "rule-fallback"
    assert result.runtime.fallbackUsed is True
    assert result.decision.riskLevel == "high"
    assert result.decision.action == "create-risk-task"


def test_v200_invalid_model_output_falls_back_and_records_validation_error():
    result, _ = _runtime().analyze(
        AgentRagRequest(
            requestId="r7",
            tenantId="tenant-b",
            subjectId="s7",
            query="fake counterfeit promotion",
            context={"forceInvalidModelOutput": True},
        )
    )
    assert result.runtime.fallbackUsed is True
    assert result.runtime.repairAttemptCount == 1
    assert result.runtime.validationErrors
    assert result.decision.riskLevel == "high"


def test_v200_idempotency_prevents_duplicate_risk_task_creation():
    runtime = _runtime()
    first, first_bundle = runtime.analyze(AgentRagRequest(requestId="r8a", tenantId="tenant-a", subjectId="same-review", query="broken product refund"))
    second, second_bundle = runtime.analyze(AgentRagRequest(requestId="r8b", tenantId="tenant-a", subjectId="same-review", query="broken product refund"))
    assert first.decision.action == "create-risk-task"
    assert second.decision.action == "manual-review"
    assert first_bundle.requestId == "r8a"
    assert second_bundle.requestId == "r8b"


def test_v200_phase1_eval_e2e_and_gate_scripts_generate_real_evidence():
    commands = [
        [sys.executable, "ai-service/scripts/evaluation/run_agent_rag_phase1_eval.py"],
        [sys.executable, "ai-service/scripts/e2e/run_agent_rag_phase1_e2e.py"],
        [sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase1_gate.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
        assert completed.stdout
    gate = json.loads((ROOT / "artifacts" / "agent-rag" / "v2.0-phase1" / "phase1-gate-result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    assert gate["checks"]["tenantIsolation"] is True
