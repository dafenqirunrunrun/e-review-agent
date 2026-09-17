from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.observability.langfuse_sidecar import LangfuseTelemetry, _safe
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.seeds import seed_policy_documents
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer
from types import SimpleNamespace


class FakeObservation:
    def __init__(self, name, observations):
        self.name = name
        self.trace_id = "trace-test"
        self.observations = observations
        self.output = None
        self.metadata = None
        observations.append(self)

    def start_observation(self, *, name, as_type, output=None, metadata=None, **kwargs):
        child = FakeObservation(name, self.observations)
        child.output = output
        child.metadata = metadata
        return child

    def update(self, *, output=None, metadata=None, **kwargs):
        self.output = output
        self.metadata = metadata

    def end(self):
        return None


class FakeClient:
    def __init__(self):
        self.observations = []
        self.scores = []

    def start_observation(self, *, name, as_type, input=None, metadata=None, **kwargs):
        result = FakeObservation(name, self.observations)
        result.input = input
        result.metadata = metadata
        return result

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    @staticmethod
    def create_trace_id(*, seed):
        return f"trace-{seed}"


def _payload(review_id="langfuse-sidecar"):
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="P-LANGFUSE",
        product_name="Langfuse fixture",
        review_text="请联系 13800138000 或 person@example.com，五星截图返现。",
        image_urls=[],
        rating=5,
    )


def test_langfuse_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    telemetry = LangfuseTelemetry.begin(_payload())
    assert telemetry.root is None
    assert telemetry.enabled is False


def test_langfuse_sidecar_uses_safe_summary_and_scores(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse.local")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    client = FakeClient()
    telemetry = LangfuseTelemetry.begin(_payload(), client_factory=lambda: client)
    monkeypatch.setattr("app.agentic_workflow.workflow.LangfuseTelemetry.begin", lambda payload, **kwargs: LangfuseTelemetry())
    workflow = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=PolicyEvidenceRetriever.from_documents(seed_policy_documents()),
        checkpoint_store=None,
    )
    response = workflow.analyze(_payload("langfuse-sidecar-run"))
    telemetry.complete(response, latency=response.extra["latencyBreakdown"])

    serialized = str([(item.name, item.output, item.metadata, getattr(item, "input", None)) for item in client.observations])
    assert "13800138000" not in serialized
    assert "person@example.com" not in serialized
    assert "五星截图返现" not in serialized
    assert {"intent_router", "risk_analysis", "risk_calibration", "policy_retrieval", "reflection_agent", "governance_finalize"}.issubset({item.name for item in client.observations})
    assert {item["name"] for item in client.scores} >= {
        "citation_valid", "evidence_supported", "api_success", "risk_severity_level",
        "raw_confidence", "calibrated_confidence", "escalation_candidate",
    }


def test_redaction_masks_secrets_and_paths():
    safe = _safe({"authorization": "Bearer abc", "reviewText": "13800138000", "modelPath": r"D:\private\model"})
    assert safe["authorization"] == "[REDACTED]"
    assert safe["reviewText"]["redacted"] is True
    assert "D:\\private\\model" not in str(safe)


def test_unreachable_or_failing_export_is_fail_open(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse.down")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    class BrokenClient:
        def start_observation(self, **kwargs):
            raise TimeoutError("export timeout")

    telemetry = LangfuseTelemetry.begin(_payload(), client_factory=BrokenClient)
    assert telemetry.root is None
    assert telemetry.export_failures == 1


def test_direct_human_review_completes_root_trace_when_evidence_is_unset():
    client = FakeClient()
    telemetry = LangfuseTelemetry(client=client, enabled=True)
    telemetry.root = client.start_observation(name="review_governance_analysis", as_type="agent")
    response = SimpleNamespace(
        extra={"agentic": {"route": "human_review_direct"}, "runtimeCheckpoint": {"state": "WAIT_HUMAN"}},
        review_governance=None,
        route_decision="human_review",
        risk_types=[],
        risk_level="low",
        evidence_status="insufficient",
        requires_human_review=True,
        evidence_sufficient=None,
        rag_strategy=None,
        rag_enabled=False,
        workflow_trace=[],
    )

    telemetry.complete(response)

    assert telemetry.export_failures == 0
    assert "direct_human_review" in {item.name for item in client.observations}
    assert {item["name"] for item in client.scores} >= {"human_review_required", "evidence_supported"}


def test_checkpoint_resume_trace_only_emits_recovery_nodes():
    client = FakeClient()
    telemetry = LangfuseTelemetry(client=client, enabled=True)
    telemetry.root = client.start_observation(name="review_governance_analysis", as_type="agent")
    response = SimpleNamespace(
        extra={
            "agentic": {"route": "governance_required"},
            "runtimeCheckpoint": {"state": "WAIT_HUMAN", "completedNodes": ["intent_router", "risk_analysis", "evidence_1", "reflection_1", "finalize"]},
            "runtimeRecovery": {"resumeOccurred": True, "resumeFromState": "EVIDENCE_RETRIEVAL", "retryCount": 0},
        },
        review_governance=None,
        route_decision="human_review",
        risk_types=["fake_review"],
        risk_level="high",
        evidence_status="supported",
        requires_human_review=True,
        evidence_sufficient=True,
        rag_strategy="policy_rag_hybrid_with_bm25_fallback",
        rag_enabled=True,
        workflow_trace=[],
    )

    telemetry.complete(response)

    names = {item.name for item in client.observations}
    assert {"review_governance_analysis", "reflection_agent", "checkpoint_persist", "governance_finalize"} <= names
    assert names.isdisjoint({"intent_router", "risk_analysis", "policy_retrieval", "dense_embedding", "faiss_search", "evidence_agent"})
    assert telemetry.root.metadata["resumeOccurred"] is True
    assert telemetry.root.metadata["resumeFromState"] == "EVIDENCE_RETRIEVAL"
