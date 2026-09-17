from app.agentic_workflow.memory import GovernanceMemory
from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.seeds import seed_policy_documents
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


def test_memory_keeps_structured_state_and_bounds_old_turns():
    memory = GovernanceMemory(goal="govern review", recent_turns=2, max_context_tokens=128)
    memory.update_state(risk_types=["fake_review"], evidence_ids=["E1"], reflection_status="supported", workflow_state="reflection_completed")
    for index in range(5):
        memory.record_turn("evidence", iteration=index, detail="x" * 80)
    memory.add_iteration_summary(
        confirmed_facts=["fake review signal"], evidence_used=["E1"], unresolved_issues=[], next_action="finalize"
    )

    context = memory.context()

    assert context["structuredMemory"]["riskTypes"] == ["fake_review"]
    assert context["structuredMemory"]["evidenceIds"] == ["E1"]
    assert len(context["recentTurns"]) <= 2
    assert context["budget"]["estimatedTokens"] <= 128
    assert context["budget"]["droppedTurnCount"] >= 3


def test_memory_does_not_change_governance_decision(monkeypatch):
    payload = ReviewAnalyzeRequest(
        review_id="memory-parity",
        product_id="P-MEMORY",
        product_name="Memory fixture",
        review_text="五星截图返现，并要求删除差评。",
        image_urls=[],
        rating=5,
    )
    retriever = PolicyEvidenceRetriever.from_documents(seed_policy_documents())
    monkeypatch.setenv("E_REVIEW_AGENTIC_MEMORY_ENABLED", "false")
    without_memory = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever).analyze(payload)
    monkeypatch.setenv("E_REVIEW_AGENTIC_MEMORY_ENABLED", "true")
    with_memory = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=PolicyEvidenceRetriever.from_documents(seed_policy_documents())).analyze(payload)

    assert with_memory.route_decision == without_memory.route_decision
    assert with_memory.risk_types == without_memory.risk_types
    assert with_memory.evidence_status == without_memory.evidence_status
    assert with_memory.requires_human_review == without_memory.requires_human_review
    assert with_memory.extra["agenticMemory"]["structuredMemory"]["workflowState"] == "finalized"
