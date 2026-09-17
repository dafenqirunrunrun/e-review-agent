from app.agentic_workflow.workflow import IntentRouterAgent
from app.schemas.review import ReviewAnalyzeRequest


def test_intent_router_uses_rule_fallback_when_local_qwen_is_unavailable(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_INTENT_ROUTER_PROVIDER", "local_qwen")
    monkeypatch.setenv("E_REVIEW_LOCAL_QWEN_MODEL_DIR", "Z:/missing/qwen2.5")

    decision = IntentRouterAgent().route(
        ReviewAnalyzeRequest(
            review_id="router-fallback",
            product_id="P1",
            product_name="Power bank",
            review_text="refund requested because the package was broken",
            rating=1,
        )
    )

    assert decision.route == "governance_required"
    assert "after_sales_risk" in decision.risk_hints
