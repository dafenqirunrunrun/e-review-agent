import json
import os
from pathlib import Path

import pytest

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.llm_decider import AgentRagLlmConfig
from app.agent_rag.runtime import AgentRagRuntime
from app.llm.providers import ProviderResult


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "agent_rag" / "phase1_cases.json"


class FakeLocalQwenProvider:
    def __init__(self, content: str):
        self.content = content
        self.called = False

    def complete_json(self, prompt: str) -> ProviderResult:
        self.called = True
        assert "Evidence:" in prompt
        assert "Contract:" in prompt
        return ProviderResult(self.content, 128, 48, 17)


def _chunks():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["chunks"]


def _config(enabled=True):
    return AgentRagLlmConfig(
        provider="local_qwen3_transformers",
        enabled=enabled,
        require_grounded_context=True,
        max_citations=4,
    )


def test_v200_phase4_default_deterministic_path_is_unchanged():
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=AgentRagLlmConfig())
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-default", tenantId="tenant-a", subjectId="s1", query="broken product refund")
    )
    assert result.runtime.engineType == "model-rag"
    assert result.runtime.effectiveLlmProvider == "deterministic"
    assert result.runtime.fallbackUsed is False
    assert bundle.effectiveLlmProvider == "deterministic"


def test_v200_phase4_grounded_local_llm_can_drive_contract_decision():
    provider = FakeLocalQwenProvider(
        json.dumps(
            {
                "riskLevel": "high",
                "riskTypes": ["after_sales_risk"],
                "action": "create-risk-task",
                "summary": "Grounded local LLM detected refund risk from cited evidence.",
                "confidence": 0.88,
            }
        )
    )
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-pass", tenantId="tenant-a", subjectId="s2", query="broken product refund")
    )
    assert provider.called is True
    assert result.runtime.engineType == "grounded-local-llm-rag"
    assert result.runtime.fallbackUsed is False
    assert result.runtime.effectiveLlmProvider == "local_qwen3_transformers"
    assert result.runtime.llmGrounded is True
    assert result.decision.riskLevel == "high"
    assert bundle.llmOutputHash
    assert result.runtime.requestedAnalysisProvider == "local_qwen3_transformers"
    assert result.runtime.effectiveAnalysisProvider == "local_qwen3_transformers"
    assert result.runtime.structuredOutputValid is True
    assert bundle.structuredOutputValid is True


def test_v200_phase4_v22_schema_validates_citations_and_action_mapping():
    provider = FakeLocalQwenProvider(
        json.dumps(
            {
                "riskLevel": "high",
                "riskTypes": ["after_sales_risk"],
                "action": "block",
                "summary": "Refund and broken evidence require a governed risk task.",
                "confidence": 0.91,
                "citationIds": ["a-after-sales-1"],
                "abstain": False,
                "uncertaintyReason": None,
                "requiresHumanReview": True,
            }
        )
    )
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-v22-schema", tenantId="tenant-a", subjectId="s22", query="broken product refund")
    )
    assert provider.called is True
    assert result.decision.action == "create-risk-task"
    assert result.runtime.groundingStatus == "GROUNDED"
    assert bundle.groundingStatus == "GROUNDED"


def test_v200_phase4_invalid_citation_is_repaired_when_summary_is_grounded():
    provider = FakeLocalQwenProvider(
        json.dumps(
            {
                "riskLevel": "high",
                "riskTypes": ["after_sales_risk"],
                "action": "create-risk-task",
                "summary": "Refund evidence requires action.",
                "confidence": 0.91,
                "citationIds": ["not-in-evidence"],
                "abstain": False,
                "uncertaintyReason": None,
                "requiresHumanReview": True,
            }
        )
    )
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-bad-citation", tenantId="tenant-a", subjectId="s23", query="broken product refund")
    )
    assert provider.called is True
    assert result.runtime.engineType == "grounded-local-llm-rag"
    assert result.runtime.llmFallbackUsed is False
    assert result.runtime.groundingStatus == "GROUNDED"
    assert bundle.effectiveAnalysisProvider == "local_qwen3_transformers"


def test_v200_phase4_invalid_citation_still_falls_back_when_ungrounded():
    provider = FakeLocalQwenProvider(
        json.dumps(
            {
                "riskLevel": "high",
                "riskTypes": ["after_sales_risk"],
                "action": "create-risk-task",
                "summary": "Completely unrelated astronomy telescope claim.",
                "confidence": 0.91,
                "citationIds": ["not-in-evidence"],
                "abstain": False,
                "uncertaintyReason": None,
                "requiresHumanReview": True,
            }
        )
    )
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-bad-citation-ungrounded", tenantId="tenant-a", subjectId="s23b", query="broken product refund")
    )
    assert provider.called is True
    assert result.runtime.engineType == "rule-fallback"
    assert result.runtime.llmFallbackReason == "AGENT_RAG_LLM_OUTPUT_UNGROUNDED"
    assert "AGENT_RAG_LLM_OUTPUT_UNGROUNDED" in bundle.errors


def test_v200_phase4_no_grounded_context_falls_back_without_calling_llm():
    provider = FakeLocalQwenProvider("{}")
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-no-context", tenantId="tenant-a", subjectId="s3", query="botanical unrelated sentence")
    )
    assert provider.called is False
    assert result.runtime.engineType == "rule-fallback"
    assert result.runtime.fallbackUsed is True
    assert result.runtime.llmFallbackReason == "AGENT_RAG_LLM_NO_GROUNDED_CONTEXT"
    assert bundle.llmFallbackReason == "AGENT_RAG_LLM_NO_GROUNDED_CONTEXT"


def test_v200_phase4_invalid_llm_json_falls_back_and_records_reason():
    provider = FakeLocalQwenProvider("not-json")
    runtime = AgentRagRuntime(chunks=_chunks(), llm_config=_config(), llm_decider=None)
    runtime.llm_decider.provider = provider
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="llm-bad-json", tenantId="tenant-a", subjectId="s4", query="broken product refund")
    )
    assert provider.called is True
    assert result.runtime.engineType == "rule-fallback"
    assert result.runtime.fallbackUsed is True
    assert result.runtime.llmFallbackReason == "AGENT_RAG_LLM_OUTPUT_JSON_INVALID"
    assert "AGENT_RAG_LLM_OUTPUT_JSON_INVALID" in bundle.errors


@pytest.mark.real_llm
@pytest.mark.real_llm_runtime
def test_v22_real_qwen3_executes_through_formal_agent_runtime(monkeypatch):
    manifest = os.environ.get("AGENT_RAG_V22_ASSET_MANIFEST")
    if not manifest:
        pytest.skip("AGENT_RAG_V22_ASSET_MANIFEST is required for real LLM runtime verification")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "local_qwen3_transformers")
    monkeypatch.setenv("AGENT_REAL_LLM_REQUIRED", "true")
    monkeypatch.setenv("AGENT_LLM_DEVICE", "cuda")
    monkeypatch.setenv("AGENT_LLM_DTYPE", "float16")
    monkeypatch.setenv("AGENT_LLM_ENABLE_THINKING", "false")
    monkeypatch.setenv("AGENT_LLM_MAX_INPUT_TOKENS", "2048")
    monkeypatch.setenv("AGENT_LLM_MAX_OUTPUT_TOKENS", "192")
    monkeypatch.setenv("AGENT_LLM_TIMEOUT_MS", "120000")
    runtime = AgentRagRuntime(chunks=_chunks())
    result, bundle = runtime.analyze(
        AgentRagRequest(
            requestId="real-qwen3-runtime",
            tenantId="tenant-a",
            subjectId="real-llm-1",
            query="Customer reports a broken product and requests a refund after receiving unsafe packaging.",
        )
    )
    assert result.runtime.engineType == "grounded-local-llm-rag"
    assert result.runtime.fallbackUsed is False
    assert result.runtime.effectiveAnalysisProvider == "local_qwen3_transformers"
    assert result.runtime.llmModelId == "Qwen/Qwen3-1.7B"
    assert result.runtime.llmRevision == "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    assert result.runtime.llmInputTokens > 0
    assert result.runtime.llmOutputTokens > 0
    assert result.runtime.llmDurationMs > 0
    assert result.runtime.structuredOutputValid is True
    assert result.runtime.groundingStatus in {"GROUNDED", "ABSTAINED"}
    assert bundle.effectiveAnalysisProvider == "local_qwen3_transformers"
    assert bundle.llmOutputHash
