from __future__ import annotations

from fastapi.testclient import TestClient

from app.agentic_workflow.workflow import IntentRouterAgent
from app.api import review as review_api
from app.main import app
from app.observability.fast_eligibility_shadow import (
    FAST_SHORT_CHAIN,
    LONG_ANALYSIS_CHAIN,
    CurrentRouteSignal,
)
from app.runtime.fast_eligibility_runtime import (
    BASELINE_CHAIN,
    FastEligibilityRuntimeController,
)
from app.schemas.review import ReviewAnalyzeRequest


client = TestClient(app)


def payload(review_id: str, text: str, *, rating: int | None = None, images: list[str] | None = None):
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="P-step215",
        product_name="Runtime Product",
        review_text=text,
        image_urls=images or [],
        rating=rating,
        rag_enabled=False,
    )


def current(value: ReviewAnalyzeRequest) -> CurrentRouteSignal:
    decision = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)._route_with_rules(value)
    return CurrentRouteSignal(
        route=decision.route,
        intent=decision.intent,
        risk_hints=tuple(decision.risk_hints),
        reason_codes=tuple(decision.reason_codes),
        safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in decision.reason_codes,
    )


def test_runtime_disabled_keeps_baseline_chain():
    value = payload("runtime-disabled", "商品很好，物流也很快。", rating=5)
    result = FastEligibilityRuntimeController(enabled=False, canary_percent=100).decide(value, current(value))

    assert result.executedChain == BASELINE_CHAIN
    assert result.reasonCode == "FAST_RUNTIME_DISABLED"


def test_clear_ordinary_review_executes_fast_chain():
    value = payload("runtime-fast", "商品很好，物流也很快。", rating=5)
    result = FastEligibilityRuntimeController(enabled=True, canary_percent=100).decide(value, current(value))

    assert result.policyDecision == FAST_SHORT_CHAIN
    assert result.executedChain == FAST_SHORT_CHAIN
    assert result.reasonCode == "CLEAR_ORDINARY_REVIEW"
    assert result.policyHash


def test_governance_and_safety_signals_stay_on_baseline():
    low_rating = payload("runtime-low-rating", "尺寸偏小，但是商品还能使用。", rating=1)
    high_risk = payload("runtime-high-risk", "商家要求五星截图后返现。", rating=5)
    controller = FastEligibilityRuntimeController(enabled=True, canary_percent=100)

    low_result = controller.decide(low_rating, current(low_rating))
    high_result = controller.decide(high_risk, current(high_risk))

    assert low_result.executedChain == BASELINE_CHAIN
    assert low_result.reasonCode == "CURRENT_GOVERNANCE_ROUTE_OVERRIDE"
    assert low_result.failClosed is True
    assert high_result.executedChain == BASELINE_CHAIN
    assert high_result.fast_executed is False


def test_image_and_policy_failure_fall_back_to_baseline(tmp_path):
    image_review = payload(
        "runtime-image",
        "商品很好，物流也很快。",
        rating=5,
        images=["https://example.com/review.jpg"],
    )
    image_result = FastEligibilityRuntimeController(enabled=True, canary_percent=100).decide(
        image_review, current(image_review)
    )
    missing_result = FastEligibilityRuntimeController(
        enabled=True,
        canary_percent=100,
        policy_path=tmp_path / "missing-policy.json",
    ).decide(image_review.model_copy(update={"image_urls": []}), current(image_review.model_copy(update={"image_urls": []})))

    assert image_result.executedChain == BASELINE_CHAIN
    assert image_result.reasonCode == "IMAGE_REVIEW_BASELINE_OVERRIDE"
    assert missing_result.executedChain == BASELINE_CHAIN
    assert missing_result.reasonCode == "FAST_POLICY_UNAVAILABLE"
    assert missing_result.failClosed is True


def test_canary_zero_keeps_baseline_without_policy_execution():
    value = payload("runtime-canary-zero", "商品很好，物流也很快。", rating=5)
    result = FastEligibilityRuntimeController(
        enabled=True,
        canary_percent=0,
        policy_path="missing-policy-is-not-loaded.json",
    ).decide(value, current(value))

    assert result.canarySelected is False
    assert result.executedChain == BASELINE_CHAIN
    assert result.reasonCode == "CANARY_NOT_SELECTED"


def test_authoritative_admission_only_allows_explicit_fast_proof(tmp_path):
    clear = payload("admission-clear", "商品很好，物流也很快。", rating=5)
    uncertain = payload("admission-uncertain", "这个东西感觉有点奇怪。", rating=None)
    controller = FastEligibilityRuntimeController()

    clear_result = controller.decide_admission(clear, current(clear))
    uncertain_result = controller.decide_admission(uncertain, current(uncertain))
    unavailable_result = FastEligibilityRuntimeController(
        policy_path=tmp_path / "missing-policy.json"
    ).decide_admission(clear, current(clear))

    assert clear_result.executedChain == FAST_SHORT_CHAIN
    assert uncertain_result.executedChain == LONG_ANALYSIS_CHAIN
    assert uncertain_result.reasonCode == "FAST_ELIGIBILITY_NOT_PROVEN"
    assert unavailable_result.executedChain == LONG_ANALYSIS_CHAIN
    assert unavailable_result.failClosed is True


def test_api_fast_chain_skips_llm_and_policy_retrieval(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_CANARY_PERCENT", "100")
    monkeypatch.setattr(review_api.agentic_workflow, "checkpoint_store", None)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("long-chain dependency executed")

    monkeypatch.setattr(review_api.llm_service, "enhance", forbidden)
    monkeypatch.setattr(review_api.agentic_workflow.policy_retriever, "search", forbidden)
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "step215-api-fast",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "商品很好，物流也很快。",
            "imageUrls": [],
            "rating": 5,
            "ragEnabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    runtime = body["extra"]["fastEligibilityRuntime"]
    nodes = {item["node"] for item in body["workflow_trace"]}
    assert runtime["executedChain"] == FAST_SHORT_CHAIN
    assert runtime["skipModelEnhancement"] is True
    assert body["extra"]["policyRetrieval"]["actualMode"] == "not_executed"
    assert body["review_governance"]["decision"]["code"] == "auto_pass"
    assert {"fast_eligibility_gate", "fast_execution"}.issubset(nodes)
    assert {"planner", "policy_evidence_retrieve", "reflection"}.isdisjoint(nodes)


def test_authoritative_api_admission_is_independent_of_historical_canary_switch(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED", "false")
    monkeypatch.setattr(review_api.agentic_workflow, "checkpoint_store", None)
    baseline = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "step215-baseline",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "商品很好，物流也很快。",
            "imageUrls": [],
            "rating": 5,
            "ragEnabled": False,
        },
    )
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_CANARY_PERCENT", "100")
    activated = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "step215-activated",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "商品很好，物流也很快。",
            "imageUrls": [],
            "rating": 5,
            "ragEnabled": False,
        },
    )

    assert baseline.status_code == activated.status_code == 200
    assert baseline.json()["extra"]["fastEligibilityRuntime"]["executedChain"] == FAST_SHORT_CHAIN
    assert activated.json()["extra"]["fastEligibilityRuntime"]["executedChain"] == FAST_SHORT_CHAIN
    assert baseline.json()["review_governance"]["decision"]["code"] == activated.json()["review_governance"]["decision"]["code"]
    assert baseline.json()["risk_types"] == activated.json()["risk_types"]


def test_unproven_low_touch_input_runs_complete_long_chain(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setattr(review_api.agentic_workflow, "checkpoint_store", None)
    retrieval_calls = []

    def empty_retrieval(*_args, **_kwargs):
        retrieval_calls.append(True)
        return []

    monkeypatch.setattr(review_api.agentic_workflow.policy_retriever, "search", empty_retrieval)
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "admission-long-chain",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "这个东西感觉有点奇怪。",
            "imageUrls": [],
            "rating": None,
            "ratingSource": "UNKNOWN",
            "ragEnabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    nodes = {item["node"] for item in body["workflow_trace"]}
    assert body["extra"]["fastEligibilityRuntime"]["executedChain"] == LONG_ANALYSIS_CHAIN
    assert body["extra"]["agentic"]["route"] == "governance_required"
    assert body["risk_types"] == ["low_confidence"]
    assert body["requires_human_review"] is True
    assert {"planner", "policy_evidence_retrieve", "reflection"}.issubset(nodes)
    assert "fast_execution" not in nodes
    assert retrieval_calls


def test_obvious_non_review_input_never_creates_manual_review(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setattr(review_api.agentic_workflow, "checkpoint_store", None)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("policy retrieval must not run for conversational input")

    monkeypatch.setattr(review_api.agentic_workflow.policy_retriever, "search", forbidden)
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "non-review-greeting",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "你好啊",
            "imageUrls": [],
            "rating": None,
            "ratingSource": "UNKNOWN",
            "ragEnabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    nodes = {item["node"] for item in body["workflow_trace"]}
    assert body["route_decision"] == "auto_close"
    assert body["requires_human_review"] is False
    assert body["extra"]["inputGate"]["decision"] == "input_guidance"
    assert body["review_governance"]["decision"]["code"] == "auto_pass"
    assert {"planner", "policy_evidence_retrieve", "reflection"}.isdisjoint(nodes)
