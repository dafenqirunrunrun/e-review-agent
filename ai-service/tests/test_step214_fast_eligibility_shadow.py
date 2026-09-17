from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agentic_workflow.workflow import IntentRouterAgent
from app.main import app
from app.observability import fast_eligibility_shadow as shadow
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse


client = TestClient(app)


def evaluator(tmp_path):
    return shadow.FastEligibilityShadowEvaluator(
        policy_path="artifacts/step213h_fast_eligibility_gate/fast_eligibility_policy_v1.json",
        output_dir=tmp_path / "artifacts",
        report_path=tmp_path / "FAST_ELIGIBILITY_SHADOW_REPORT.md",
    )


def payload(review_id: str, text: str, rating: int = 5) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="P-shadow",
        product_name="Shadow Product",
        review_text=text,
        image_urls=[],
        rating=rating,
    )


def signal(value: ReviewAnalyzeRequest) -> shadow.CurrentRouteSignal:
    decision = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)._route_with_rules(value)
    return shadow.CurrentRouteSignal(
        route=decision.route,
        intent=decision.intent,
        risk_hints=tuple(decision.risk_hints),
        reason_codes=tuple(decision.reason_codes),
        safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in decision.reason_codes,
    )


def test_shadow_records_required_fields_without_review_text(tmp_path):
    target = evaluator(tmp_path)
    record = target.observe(payload("normal-1", "商品很好，物流也很快。"), signal(payload("normal-1", "商品很好，物流也很快。")))

    assert record["shadowDecision"] == shadow.FAST_SHORT_CHAIN
    assert record["currentDecision"] == "low_touch"
    assert record["reasonCodes"] == ["CLEAR_ORDINARY_REVIEW"]
    assert record["estimatedCostSaving"] == 1.0
    assert record["shadowOnly"] is True
    assert record["chainExecuted"] is False
    serialized = (tmp_path / "artifacts" / "fast_shadow_decisions.jsonl").read_text(encoding="utf-8")
    assert "商品很好" not in serialized


def test_high_risk_and_safety_signals_never_enter_shadow_fast(tmp_path):
    target = evaluator(tmp_path)
    risky = payload("risk-1", "商家要求五星截图后返现。")
    unsafe = payload("risk-2", "收到商品后漏电，非常危险。", rating=1)

    first = target.observe(risky, signal(risky))
    second = target.observe(unsafe, signal(unsafe))

    assert first["shadowDecision"] == shadow.LONG_ANALYSIS_CHAIN
    assert second["shadowDecision"] == shadow.LONG_ANALYSIS_CHAIN
    metrics = target.metrics()
    assert metrics["highRiskShadowFast"] == 0
    assert metrics["safetyShadowFast"] == 0


def test_gate_thresholds_and_output_files(tmp_path):
    target = evaluator(tmp_path)
    samples = [
        payload("fast-1", "商品很好，值得推荐。"),
        payload("fast-2", "尺寸偏小，但换货流程清楚。", 4),
        payload("long-1", "商家要求五星截图后返现。"),
        payload("long-2", "删除差评才给退款。", 1),
        payload("long-3", "情况没有说明清楚，暂时无法判断。", 3),
    ]
    for item in samples:
        target.observe(item, signal(item))

    metrics = target.finalize({"mode": "test"})
    assert metrics["shadowFastCount"] == 2
    assert metrics["shadowLongCount"] == 3
    assert metrics["longAnalysisReduction"] == 0.4
    assert metrics["potentialCostSaving"] == 0.4
    assert metrics["step21_4Gate"] == "PASS"
    assert (tmp_path / "artifacts" / "fast_shadow_metrics.json").exists()
    assert (tmp_path / "FAST_ELIGIBILITY_SHADOW_REPORT.md").exists()


def test_policy_integrity_is_enforced(tmp_path):
    source = json.loads(
        open("artifacts/step213h_fast_eligibility_gate/fast_eligibility_policy_v1.json", encoding="utf-8").read()
    )
    source["patterns"]["hardLong"] = "tampered"
    bad_policy = tmp_path / "policy.json"
    bad_policy.write_text(json.dumps(source), encoding="utf-8")

    try:
        shadow.FrozenFastEligibilityPolicy(bad_policy)
    except RuntimeError as exc:
        assert str(exc) == "FAST_ELIGIBILITY_POLICY_INTEGRITY_FAILED"
    else:
        raise AssertionError("tampered frozen policy was accepted")


def test_shadow_gate_contract():
    assert shadow.shadow_gate(0.20, 0, 0)[0] == "PASS"
    assert shadow.shadow_gate(0.10, 0, 0)[0] == "PASS_WITH_LIMITATIONS"
    assert shadow.shadow_gate(0.09, 0, 0) == ("FAIL", "ESTIMATED_LONG_REDUCTION_BELOW_10_PERCENT")
    assert shadow.shadow_gate(0.50, 1, 0) == ("FAIL", "HIGH_OR_SAFETY_RISK_ROUTED_TO_SHADOW_FAST")


def test_shadow_failure_does_not_change_api_response(monkeypatch):
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_SHADOW_ENABLED", "true")
    calls = []

    def broken_shadow(request: ReviewAnalyzeRequest, response: ReviewAnalyzeResponse) -> None:
        calls.append(request.review_id)
        raise RuntimeError("shadow unavailable")

    monkeypatch.setattr("app.api.review.observe_fast_eligibility_shadow", broken_shadow)
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "shadow-fail-open",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "商品很好，值得推荐。",
            "imageUrls": [],
            "rating": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["review_id"] == "shadow-fail-open"
    assert calls == ["shadow-fail-open"]


def test_disabled_shadow_does_not_create_records(monkeypatch, tmp_path):
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_SHADOW_ENABLED", "false")
    monkeypatch.setattr(shadow, "_default_evaluator", evaluator(tmp_path))
    response = ReviewAnalyzeResponse.model_validate(
        client.post(
            "/api/v1/review/analyze",
            json={
                "reviewId": "shadow-disabled",
                "productId": "P1",
                "productName": "Product",
                "reviewText": "商品很好，值得推荐。",
                "imageUrls": [],
                "rating": 5,
            },
        ).json()
    )
    shadow.observe_fast_eligibility_shadow(payload("shadow-disabled", "商品很好，值得推荐。"), response)

    assert not (tmp_path / "artifacts" / "fast_shadow_decisions.jsonl").exists()


def test_runtime_canary_decision_is_not_written_to_shadow_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_SHADOW_ENABLED", "false")
    monkeypatch.setattr(shadow, "_default_evaluator", evaluator(tmp_path))
    response = ReviewAnalyzeResponse.model_validate(
        client.post(
            "/api/v1/review/analyze",
            json={
                "reviewId": "runtime-shadow-dedup",
                "productId": "P1",
                "productName": "Product",
                "reviewText": "商品很好，物流也很快。",
                "imageUrls": [],
                "rating": 5,
            },
        ).json()
    )
    response.extra = {
        **(response.extra or {}),
        "fastEligibilityRuntime": {"canarySelected": True, "executedChain": "FAST_SHORT_CHAIN"},
    }

    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_SHADOW_ENABLED", "true")
    shadow.observe_fast_eligibility_shadow(payload("runtime-shadow-dedup", "商品很好，物流也很快。"), response)

    assert not (tmp_path / "artifacts" / "fast_shadow_decisions.jsonl").exists()
