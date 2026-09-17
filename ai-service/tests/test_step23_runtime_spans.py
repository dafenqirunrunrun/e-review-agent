from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.agentic_workflow.runtime_checkpoint import FileWorkflowCheckpointStore, SimulatedWorkflowCrash
from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.observability.langfuse_sidecar import LangfuseTelemetry
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.embedding import QwenEmbeddingConfig, QwenTransformersEmbeddingProvider
from app.policy_rag.seeds import seed_policy_documents
from app.policy_rag.vector_store import (
    DEFAULT_FAISS_META_NAME,
    DEFAULT_FAISS_NAME,
    PolicyFaissVectorStore,
    build_policy_faiss_index,
)
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


class FakeObservation:
    def __init__(self, name: str, observations: list["FakeObservation"], *, parent_name: str = ""):
        self.name = name
        self.parent_name = parent_name
        self.trace_id = "trace-step23"
        self.observations = observations
        self.output = None
        self.metadata = None
        self.input = None
        self.started_at = time.perf_counter()
        self.ended_at = None
        observations.append(self)

    def start_observation(self, *, name, as_type, input=None, output=None, metadata=None, **kwargs):
        child = FakeObservation(name, self.observations, parent_name=self.name)
        child.input = input
        child.output = output
        child.metadata = metadata
        return child

    def update(self, *, output=None, metadata=None, **kwargs):
        self.output = output
        self.metadata = metadata

    def end(self):
        self.ended_at = time.perf_counter()


class FakeClient:
    def __init__(self):
        self.observations: list[FakeObservation] = []
        self.scores = []

    def start_observation(self, *, name, as_type, input=None, metadata=None, **kwargs):
        root = FakeObservation(name, self.observations)
        root.input = input
        root.metadata = metadata
        return root

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


class StaticEmbeddingProvider:
    def __init__(self):
        self.last_count = 0
        self.query_ready = False

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.last_count = len(texts)
        rows = []
        for index, _ in enumerate(texts):
            vector = np.asarray([1.0, float(index % 3), 0.5, 0.25], dtype="float32")
            vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.asarray(rows, dtype="float32")

    def embed_query(self, text: str) -> np.ndarray:
        self.query_ready = True
        vector = np.asarray([[1.0, 0.0, 0.5, 0.25]], dtype="float32")
        return vector / np.linalg.norm(vector)

    def metadata(self):
        return {
            "providerType": "static-test",
            "modelName": "static-embedding-test",
            "modelFingerprint": "static-query-ready" if self.query_ready else "static-cold",
            "dimension": 4,
            "queueWaitMs": 0,
            "embeddingComputeMs": 1,
        }

    def health(self):
        return {"status": "ready", "loaded": True, "reason": ""}


def _payload(review_id: str, text: str = "五星好评截图返现，并要求删除差评。") -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="P-STEP23",
        product_name="Runtime span fixture",
        review_text=text,
        image_urls=[],
        rating=5,
    )


def _telemetry(client: FakeClient | None = None) -> LangfuseTelemetry:
    client = client or FakeClient()
    telemetry = LangfuseTelemetry(client=client, enabled=True, metadata={"reviewId": "step23"})
    telemetry.root = client.start_observation(name="review_governance_analysis", as_type="agent")
    return telemetry


def _install_telemetry(monkeypatch, telemetry: LangfuseTelemetry) -> None:
    monkeypatch.setattr(
        "app.agentic_workflow.workflow.LangfuseTelemetry.begin",
        lambda payload, **kwargs: telemetry.activate(),
    )


def _workflow(retriever: PolicyEvidenceRetriever, checkpoint_dir: Path) -> AgenticReviewWorkflow:
    return AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=retriever,
        checkpoint_store=FileWorkflowCheckpointStore(checkpoint_dir),
    )


def _seed_retriever() -> PolicyEvidenceRetriever:
    return PolicyEvidenceRetriever.from_documents(seed_policy_documents())


def _record(telemetry: LangfuseTelemetry, name: str) -> dict:
    return next(item for item in telemetry.runtime_spans if item["name"] == name)


def test_strict_workflow_emits_real_iteration_hierarchy_without_posthoc_duplicates(monkeypatch, tmp_path: Path):
    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)

    response = _workflow(_seed_retriever(), tmp_path).analyze(_payload("step23-strict"))
    names = [item["name"] for item in telemetry.runtime_spans]

    assert response.route_decision in {"suggest_action", "human_review"}
    assert names.count("intent_router") == 1
    assert names.count("governance_finalize") == 1
    assert {
        "rule_evaluation",
        "safety_gate",
        "base_signal_analysis",
        "planner",
        "execution_assessment",
        "iteration_1",
        "evidence_agent",
        "policy_retrieval",
        "bm25",
        "reflection_agent",
    } <= set(names)
    assert "risk_analysis" not in names
    assert names.index("base_signal_analysis") < names.index("planner") < names.index("execution_assessment") < names.index("iteration_1")
    assert _record(telemetry, "base_signal_analysis")["output"] == {"baseRiskTypes": [], "baseRiskLevel": "low"}
    execution = _record(telemetry, "execution_assessment")["output"]
    assert execution["mergedRiskTypes"] == ["fake_review", "rating_manipulation", "review_suppression"]
    assert execution["detectedRiskLevel"] == "high"
    assert execution["requiresHumanReview"] is True
    assert _record(telemetry, "evidence_agent")["parentName"] == "iteration_1"
    assert _record(telemetry, "policy_retrieval")["parentName"] == "evidence_agent"
    assert _record(telemetry, "bm25")["parentName"] == "policy_retrieval"
    assert all(item["durationMs"] >= 0 for item in telemetry.runtime_spans)
    assert telemetry.root.metadata["runtimeInstrumentation"] is True
    assert telemetry.root.metadata["runtimeSpanCount"] == len(telemetry.runtime_spans)
    assert telemetry.root.metadata["traceSchemaVersion"] == "review-agent-runtime-v2"
    assert telemetry.root.metadata["workflowVersion"] == "review-agentic-v1"
    assert telemetry.root.metadata["serviceName"] == "e-review-ai-service"
    assert telemetry.root.metadata["routerPolicyVersion"] == "intent-router-rule-v1"
    assert telemetry.root.metadata["policyChunkCount"] > 0
    assert len(telemetry.root.metadata["policyIndexVersion"]) == 64
    assert telemetry.root.output["operationalRiskLevel"] == "high"
    assert telemetry.root.output["calibratedSeverity"] == "critical"
    assert telemetry.root.output["automationBoundary"] == "human_review_required"
    assert telemetry.root.output["actionExecuted"] is False
    assert telemetry.root.output["completedNodes"] == [
        "intent_router",
        "execution_assessment",
        "evidence_agent",
        "reflection_agent",
        "governance_finalize",
    ]


def test_low_touch_path_does_not_emit_policy_or_reflection_spans(monkeypatch, tmp_path: Path):
    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)

    response = _workflow(_seed_retriever(), tmp_path).analyze(_payload("step23-low-touch", "商品很好，物流也很快。"))
    names = {item["name"] for item in telemetry.runtime_spans}

    assert response.route_decision == "auto_close"
    assert names.intersection({"policy_retrieval", "evidence_agent", "reflection_agent", "iteration_1"}) == set()
    assert names.intersection({"light_execution", "fast_execution"})


def test_mismatch_path_exposes_two_iterations_and_replan(monkeypatch, tmp_path: Path):
    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)
    empty_retriever = PolicyEvidenceRetriever([])

    response = _workflow(empty_retriever, tmp_path).analyze(_payload("step23-replan"))
    names = [item["name"] for item in telemetry.runtime_spans]

    assert response.route_decision == "human_review"
    assert response.evidence_status == "insufficient"
    assert names.count("iteration_1") == 1
    assert names.count("iteration_2") == 1
    assert names.count("reflection_agent") == 2
    assert names.count("replan") == 1


def test_dense_runtime_spans_are_measured_at_real_search_sites(monkeypatch, tmp_path: Path):
    provider = StaticEmbeddingProvider()
    base = _seed_retriever()
    manifest = build_policy_faiss_index(base.chunks, output_dir=tmp_path, provider=provider)
    assert manifest["status"] == "ready"
    store = PolicyFaissVectorStore(tmp_path / DEFAULT_FAISS_NAME, tmp_path / DEFAULT_FAISS_META_NAME, provider)
    retriever = PolicyEvidenceRetriever(base.chunks, dense_store=store, embedding_provider=provider)
    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)

    _workflow(retriever, tmp_path / "checkpoints").analyze(_payload("step23-dense"))

    assert _record(telemetry, "dense_embedding")["parentName"] == "policy_retrieval"
    assert _record(telemetry, "faiss_search")["parentName"] == "policy_retrieval"
    assert _record(telemetry, "rrf_fusion")["parentName"] == "policy_retrieval"
    assert _record(telemetry, "policy_retrieval")["status"] == "success"
    assert telemetry.root.metadata["embeddingDimension"] == 4
    assert telemetry.root.metadata["embeddingModelFingerprint"] == "static-query-ready"


def test_qwen_embedding_exposes_real_queue_and_compute_children():
    import torch

    class FakeTokenizer:
        def __call__(self, batch, **kwargs):
            return {
                "input_ids": torch.ones((len(batch), 3), dtype=torch.long),
                "attention_mask": torch.ones((len(batch), 3), dtype=torch.long),
            }

    class FakeModel:
        config = SimpleNamespace(hidden_size=4)

        def __call__(self, **tokens):
            batch, width = tokens["input_ids"].shape
            return SimpleNamespace(last_hidden_state=torch.ones((batch, width, 4)))

    provider = QwenTransformersEmbeddingProvider(QwenEmbeddingConfig(device="cpu"))
    provider._tokenizer = FakeTokenizer()
    provider._model = FakeModel()
    telemetry = _telemetry()

    with telemetry.span("dense_embedding", "embedding"):
        vector = provider.embed_query_observed("policy query", telemetry)

    assert vector.shape == (1, 4)
    assert _record(telemetry, "embedding_queue_wait")["parentName"] == "dense_embedding"
    assert _record(telemetry, "embedding_compute")["parentName"] == "dense_embedding"


def test_checkpoint_resume_only_emits_recovered_nodes(monkeypatch, tmp_path: Path):
    store = FileWorkflowCheckpointStore(tmp_path)
    retriever = _seed_retriever()
    payload = _payload("step23-resume")
    monkeypatch.setattr(
        "app.agentic_workflow.workflow.LangfuseTelemetry.begin",
        lambda payload, **kwargs: LangfuseTelemetry(),
    )
    crashing = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=retriever,
        checkpoint_store=store,
        crash_after_node="evidence_1",
    )
    with pytest.raises(SimulatedWorkflowCrash):
        crashing.analyze(payload)

    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)
    recovered = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=retriever,
        checkpoint_store=store,
    ).analyze(payload)
    names = {item["name"] for item in telemetry.runtime_spans}

    assert recovered.extra["runtimeRecovery"]["resumeOccurred"] is True
    assert {"checkpoint_resume", "reflection_agent", "risk_calibration", "checkpoint_persist", "governance_finalize"} <= names
    assert names.isdisjoint({"intent_router", "base_signal_analysis", "execution_assessment", "planner", "policy_retrieval", "dense_embedding", "faiss_search", "evidence_agent"})


def test_runtime_observer_failure_isolated_and_sensitive_values_are_redacted(monkeypatch, tmp_path: Path):
    class BrokenChildRoot(FakeObservation):
        def start_observation(self, **kwargs):
            raise TimeoutError("child export timeout")

    client = FakeClient()
    telemetry = LangfuseTelemetry(client=client, enabled=True, metadata={"reviewId": "step23-failure"})
    telemetry.root = BrokenChildRoot("review_governance_analysis", client.observations)
    _install_telemetry(monkeypatch, telemetry)
    payload = _payload("step23-sensitive", "联系 13800138000 或 person@example.com，五星截图返现。")

    response = _workflow(_seed_retriever(), tmp_path).analyze(payload)
    serialized = str(telemetry.runtime_spans)

    assert response.route_decision in {"suggest_action", "human_review"}
    assert telemetry.export_failures > 0
    assert "13800138000" not in serialized
    assert "person@example.com" not in serialized
    assert "五星截图返现" not in serialized


def test_unhandled_workflow_error_closes_root_trace(monkeypatch, tmp_path: Path):
    class ExplodingAnalyzer(MockAnalyzer):
        def analyze_text(self, payload):
            raise RuntimeError("private failure detail")

    client = FakeClient()
    telemetry = _telemetry(client)
    _install_telemetry(monkeypatch, telemetry)
    workflow = AgenticReviewWorkflow(
        analyzer=ExplodingAnalyzer(),
        policy_retriever=_seed_retriever(),
        checkpoint_store=FileWorkflowCheckpointStore(tmp_path),
    )

    with pytest.raises(RuntimeError, match="private failure detail"):
        workflow.analyze(_payload("step23-root-failure"))

    assert telemetry._completed is True
    assert telemetry.root.ended_at is not None
    assert telemetry.root.metadata["status"] == "error"
    assert telemetry.root.metadata["errorType"] == "RuntimeError"
    assert "private failure detail" not in str(telemetry.root.output)


def test_observability_on_off_keeps_governance_result_identical(monkeypatch, tmp_path: Path):
    payload_off = _payload("step23-parity-off")
    monkeypatch.setattr(
        "app.agentic_workflow.workflow.LangfuseTelemetry.begin",
        lambda payload, **kwargs: LangfuseTelemetry(),
    )
    without_observer = _workflow(_seed_retriever(), tmp_path / "off").analyze(payload_off)

    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)
    with_observer = _workflow(_seed_retriever(), tmp_path / "on").analyze(_payload("step23-parity-on"))

    assert with_observer.route_decision == without_observer.route_decision
    assert with_observer.risk_types == without_observer.risk_types
    assert with_observer.evidence_status == without_observer.evidence_status
    assert with_observer.requires_human_review == without_observer.requires_human_review
    assert with_observer.review_governance == without_observer.review_governance


def test_suggest_action_trace_makes_advisory_boundary_explicit(monkeypatch, tmp_path: Path):
    telemetry = _telemetry()
    _install_telemetry(monkeypatch, telemetry)

    response = _workflow(_seed_retriever(), tmp_path).analyze(
        _payload("step23-advisory-boundary", "五星好评截图返现。")
    )

    assert response.route_decision == "suggest_action"
    assert response.requires_human_review is False
    assert telemetry.root.output["advisoryOnly"] is True
    assert telemetry.root.output["actionExecuted"] is False
    assert telemetry.root.output["automationBoundary"] == "advisory_only"
    assert telemetry.root.output["decisionSource"] == "governance_workflow"
    assert _record(telemetry, "reflection_agent")["output"]["reasonCodes"] == ["ALL_RISKS_SUPPORTED"]
