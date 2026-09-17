import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.runtime import AgentRagRuntime
from app.agent_rag.target_mode import load_agent_rag_target_config
from app.main import app


ROOT = Path(__file__).resolve().parents[2]


def test_v200_target_mode_parser_defaults_are_safe(monkeypatch):
    monkeypatch.delenv("AGENT_RAG_TARGET_MODE", raising=False)
    cfg = load_agent_rag_target_config()
    assert cfg.target_mode == "governed-local"
    assert cfg.default_retrieval_mode == "bm25-first-semantic-hybrid"
    assert cfg.reranker_type == "deterministic"
    assert cfg.llm_provider == "rule"
    assert cfg.rule_fallback_enabled is True


def test_v200_target_mode_parser_rejects_unknown_mode():
    with pytest.raises(ValueError, match="AGENT_RAG_TARGET_MODE_UNSUPPORTED"):
        load_agent_rag_target_config({"AGENT_RAG_TARGET_MODE": "production-enterprise"})


def test_v200_dense_health_reports_target_mode(monkeypatch):
    monkeypatch.setenv("AGENT_RAG_TARGET_MODE", "enterprise-maturity-local-single-node")
    monkeypatch.setenv("RAG_DENSE_PROVIDER", "hash")
    client = TestClient(app)
    payload = client.get("/api/v1/internal/agent-rag/dense/health").json()
    assert payload["targetMode"] == "enterprise-maturity-local-single-node"
    assert payload["defaultRetrievalMode"] == "bm25-first-semantic-hybrid"
    assert payload["effectiveProviderImpl"] == "hash"


def test_v200_evidence_bundle_records_target_mode(monkeypatch):
    monkeypatch.setenv("AGENT_RAG_TARGET_MODE", "enterprise-maturity-local-single-node")
    runtime = AgentRagRuntime(
        chunks=[
            {
                "tenant_id": "tenant-a",
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "content": "refund broken return after-sales policy",
                "content_hash": "abc123abc123",
                "source_type": "policy",
                "title": "Refund policy",
            }
        ]
    )
    result, bundle = runtime.analyze(
        AgentRagRequest(
            requestId="req-target-mode",
            tenantId="tenant-a",
            subjectId="review-1",
            query="refund broken item",
        )
    )
    assert result.runtime.targetMode == "enterprise-maturity-local-single-node"
    assert result.retrieval.targetMode == "enterprise-maturity-local-single-node"
    assert bundle.targetMode == "enterprise-maturity-local-single-node"


def test_v200_provider_selection_contract_gate_reports_enterprise_tokens(monkeypatch):
    monkeypatch.setenv("AGENT_RAG_TARGET_MODE", "enterprise-maturity-local-single-node")
    monkeypatch.setenv("RAG_BGE_M3_PROVIDER_IMPL", "flagembedding")
    completed = subprocess.run(
        [sys.executable, "ai-service/scripts/readiness/run_agent_rag_provider_selection_contract_gate.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "AGENT_RAG_PROVIDER_SELECTION_CONTRACT_PASS" in completed.stdout
    assert "AGENT_RAG_RETRIEVAL_DEFAULT_PASS" in completed.stdout
    assert "AGENT_RAG_ENTERPRISE_TARGET_MODE_PASS" in completed.stdout
    payload = json.loads(
        (ROOT / "artifacts" / "agent-rag" / "v2.1-reproducibility" / "provider-selection-contract-gate-result.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"] == "PASS"
    assert payload["selectedProviderImpl"] == "flagembedding"
    assert payload["defaultRetrievalMode"] == "bm25-first-semantic-hybrid"
