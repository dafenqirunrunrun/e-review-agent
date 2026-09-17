import pytest

from app.agentic_workflow.runtime_checkpoint import (
    CheckpointCorruptError,
    FileWorkflowCheckpointStore,
    ReviewWorkflowState,
    SimulatedWorkflowCrash,
    WorkflowRuntime,
)
from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.seeds import seed_policy_documents
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


class CountingRetriever(PolicyEvidenceRetriever):
    def __init__(self):
        seed = PolicyEvidenceRetriever.from_documents(seed_policy_documents())
        super().__init__(seed.chunks)
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return super().search(*args, **kwargs)


def _payload(review_id: str) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="P-CHECKPOINT",
        product_name="Checkpoint fixture",
        review_text="五星好评截图返现，并要求删除差评。",
        image_urls=[],
        rating=5,
    )


def test_state_machine_rejects_illegal_transition_and_persists_checkpoint(tmp_path):
    store = FileWorkflowCheckpointStore(tmp_path)
    runtime = WorkflowRuntime(store, "checkpoint-state")

    with pytest.raises(ValueError, match="ILLEGAL_WORKFLOW_TRANSITION"):
        runtime.transition(ReviewWorkflowState.COMPLETED)

    runtime.transition(ReviewWorkflowState.ROUTING)
    runtime.start_node("router", {"review": "r"})
    runtime.finish_node("router", {"route": "governance_required"})
    loaded = store.load("checkpoint-state")

    assert loaded is not None
    assert loaded.currentState == "ROUTING"
    assert loaded.completedNodes == ["router"]
    assert loaded.nodeExecutions[0].inputHash
    assert loaded.nodeExecutions[0].outputHash


def test_retry_marks_non_retryable_and_bounded_temporary_failures(tmp_path):
    runtime = WorkflowRuntime(FileWorkflowCheckpointStore(tmp_path), "checkpoint-retry")
    runtime.transition(ReviewWorkflowState.ROUTING)
    runtime.start_node("router", {})
    assert runtime.fail_node("router", RuntimeError("bad request"), retryable=False) is False
    assert runtime.checkpoint.nodeExecutions[-1].retryReason == "non_retryable_failure"

    runtime.start_node("router-retry", {})
    assert runtime.fail_node("router-retry", TimeoutError("temporary"), retryable=True) is True
    runtime.start_node("router-retry-2", {})
    assert runtime.fail_node("router-retry-2", TimeoutError("temporary"), retryable=True) is False


def test_evidence_checkpoint_recovers_at_reflection_without_retrieval_repeat(tmp_path):
    store = FileWorkflowCheckpointStore(tmp_path)
    retriever = CountingRetriever()
    payload = _payload("checkpoint-resume")
    crashing = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(), policy_retriever=retriever, checkpoint_store=store, crash_after_node="evidence_1"
    )

    with pytest.raises(SimulatedWorkflowCrash):
        crashing.analyze(payload)

    crashed = store.load(payload.review_id)
    assert crashed is not None
    assert crashed.currentState == "EVIDENCE_RETRIEVAL"
    assert crashed.completedNodes == ["intent_router", "risk_analysis", "evidence_1"]
    retrieval_calls_before_resume = retriever.calls

    recovered = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever, checkpoint_store=store).analyze(payload)
    restored = store.load(payload.review_id)

    assert retriever.calls == retrieval_calls_before_resume
    assert restored.currentState in {"COMPLETED", "WAIT_HUMAN"}
    assert "reflection_1" in restored.completedNodes
    assert any(item.node == "checkpoint_resume" for item in recovered.workflow_trace)
    assert recovered.route_decision in {"suggest_action", "human_review"}
    assert recovered.extra["runtimeRecovery"] == {
        "resumeOccurred": True,
        "resumeFromState": "EVIDENCE_RETRIEVAL",
        "workflowExecutionId": crashed.id,
        "retryCount": 0,
    }
    for node in ("intent_router", "risk_analysis", "evidence_1"):
        assert sum(item.nodeName == node and item.status == "SUCCESS" for item in restored.nodeExecutions) == 1
    assert restored.retryCount == 0

    uninterrupted = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=CountingRetriever(),
        checkpoint_store=FileWorkflowCheckpointStore(tmp_path / "uninterrupted"),
    ).analyze(_payload("checkpoint-uninterrupted"))
    assert recovered.route_decision == uninterrupted.route_decision
    assert recovered.risk_types == uninterrupted.risk_types
    assert recovered.evidence_status == uninterrupted.evidence_status
    assert recovered.requires_human_review == uninterrupted.requires_human_review


def test_completed_checkpoint_returns_idempotent_final_response(tmp_path):
    store = FileWorkflowCheckpointStore(tmp_path)
    retriever = CountingRetriever()
    payload = _payload("checkpoint-idempotent")
    workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever, checkpoint_store=store)

    first = workflow.analyze(payload)
    calls_after_first = retriever.calls
    second = workflow.analyze(payload)

    assert retriever.calls == calls_after_first
    assert second.route_decision == first.route_decision
    assert second.evidence_status == first.evidence_status
    assert second.extra["runtimeCheckpoint"]["state"] in {"COMPLETED", "WAIT_HUMAN"}


def test_corrupted_checkpoint_is_detected(tmp_path):
    store = FileWorkflowCheckpointStore(tmp_path)
    path = store._path("checkpoint-corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CheckpointCorruptError, match="WORKFLOW_CHECKPOINT_CORRUPT"):
        WorkflowRuntime(store, "checkpoint-corrupt")

    response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), checkpoint_store=store).analyze(_payload("checkpoint-corrupt"))
    assert response.route_decision == "human_review"
    assert response.extra["runtimeCheckpoint"]["state"] == "FAILED"
