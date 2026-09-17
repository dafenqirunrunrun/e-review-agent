import hashlib
from pathlib import Path

from app.agentic_workflow.workflow import AgenticReviewWorkflow, IntentRouterAgent
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer
from scripts.analyze_step17_false_negatives import FROZEN_GOLD_SHA256


def payload(text: str, rating: int = 5) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(review_id="step17", product_id="P", product_name="P", review_text=text, image_urls=[], rating=rating)


def test_frozen_gold_hash_is_protected():
    dataset = Path(__file__).resolve().parents[1] / "data/benchmarks/review_governance_gold_v1.jsonl"

    assert hashlib.sha256(dataset.read_bytes()).hexdigest().upper() == FROZEN_GOLD_SHA256


def test_safety_gate_routes_implicit_high_risk_without_auto_pass():
    router = IntentRouterAgent(rule_enhancements_enabled=False, safety_gate_enabled=True)
    cases = {
        "\u6652\u4e2a\u4e94\u661f\u6211\u7ed9\u4f60\u8fd410\u5757": {"fake_review", "rating_manipulation"},
        "\u628a\u4e4b\u524d\u90a3\u6761\u8bc4\u4ef7\u5904\u7406\u4e00\u4e0b\uff0c\u6211\u7ed9\u4f60\u9000\u6b3e": {"review_suppression"},
        "\u5458\u5de5\u7edf\u4e00\u5e2e\u95e8\u5e97\u6253\u4e94\u661f": {"fake_review", "rating_manipulation"},
        "They exposed my phone number in a public reply.": {"privacy_risk"},
        "The seller used abusive language and intimidation.": {"harassment_or_abuse"},
    }
    for text, expected in cases.items():
        decision = router.route(payload(text))
        assert decision.route == "governance_required"
        assert expected <= set(decision.risk_hints)
        assert "HIGH_RISK_SAFETY_GATE" in decision.reason_codes
        assert decision.requires_evidence is True


def test_safety_gate_routes_review_visibility_and_paid_content_compositions():
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    cases = {
        "\u9875\u9762\u9690\u85cf\u6240\u6709\u4e00\u661f\u8bc4\u4ef7\uff0c\u53ea\u5c55\u793a\u5546\u5bb6\u6311\u9009\u7684\u597d\u8bc4": {"review_suppression"},
        "\u6bcf\u53d1\u5e03\u4e00\u6761\u6307\u5b9a\u5185\u5bb9\u7684\u597d\u8bc4\u5c31\u652f\u4ed8\u5341\u5143\u62a5\u916c": {"fake_review", "rating_manipulation"},
        "\u8d60\u9001\u793c\u54c1\u5238\u7684\u6761\u4ef6\u662f\u8bc4\u4ef7\u5fc5\u987b\u5199\u4e94\u661f": {"fake_review", "rating_manipulation"},
        "\u5546\u5bb6\u5a01\u80c1\u6295\u8bc9\u7528\u6237\u5e76\u8981\u6c42\u64a4\u4e0b\u8d1f\u9762\u8bc4\u4ef7": {"review_suppression"},
        "\u5de5\u4f5c\u5ba4\u63a7\u5236\u5927\u91cf\u8d26\u53f7\u7ed9\u540c\u4e00\u5bb6\u5e97\u94fa\u5237\u4e94\u661f": {"fake_review", "rating_manipulation"},
    }

    for text, expected in cases.items():
        decision = router.route(payload(text))
        assert decision.route == "governance_required"
        assert expected <= set(decision.risk_hints)
        assert "HIGH_RISK_SAFETY_GATE" in decision.reason_codes


def test_safety_gate_composition_terms_do_not_trigger_in_isolation():
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)

    for text in [
        "\u7b5b\u9009\u9875\u9762\u67e5\u770b\u4e00\u661f\u8bc4\u4ef7",
        "\u8fd9\u6b3e\u5546\u54c1\u5341\u5143\uff0c\u597d\u8bc4\u5f88\u591a",
        "\u5e73\u53f0\u9001\u793c\u54c1\u5238\uff0c\u4e0e\u8bc4\u4ef7\u65e0\u5173",
        "\u8fd9\u5bb6\u6444\u5f71\u5de5\u4f5c\u5ba4\u670d\u52a1\u4e94\u661f",
    ]:
        decision = router.route(payload(text))
        assert decision.route == "low_touch"
        assert decision.risk_hints == []


def test_normal_review_stays_light_path_with_safety_gate():
    decision = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True).route(payload("物流很快，包装完整，商品和描述一致。", rating=3))

    assert decision.route == "low_touch"
    assert decision.reason_codes == ["NO_RISK_SIGNAL"]


def test_battery_swelling_routes_to_high_risk_safety_gate():
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)

    for text in [
        "购买的电池要鼓包",
        "电池膨胀发热",
        "The battery is swollen and overheating.",
        "バッテリーが膨張しています",
        "배터리가 부풀고 과열됩니다",
    ]:
        decision = router.route(payload(text))
        assert decision.route == "governance_required"
        assert "safety_or_fraud_risk" in decision.risk_hints
        assert "HIGH_RISK_SAFETY_GATE" in decision.reason_codes
        assert decision.requires_evidence is True


def test_multilingual_after_sales_terms_are_not_reduced_to_low_confidence():
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)

    for text in ["返品を拒否されました", "환불을 거절당했습니다"]:
        decision = router.route(payload(text))
        assert decision.route == "governance_required"
        assert "after_sales_risk" in decision.risk_hints


def test_non_battery_packaging_bulge_does_not_trigger_safety_gate():
    decision = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True).route(
        payload("外包装有点鼓包，但商品本身完好。", rating=3)
    )

    assert decision.route == "low_touch"
    assert "safety_or_fraud_risk" not in decision.risk_hints


def test_shadow_audit_forces_strict_path_without_changing_router_rules():
    value = payload("works as expected")
    value.audit_mode = "shadow_strict"
    response = AgenticReviewWorkflow(analyzer=MockAnalyzer()).analyze(value)

    assert response.route_decision in {"suggest_action", "human_review"}
    assert response.extra["agentic"]["intent"]["reason_codes"] == ["SHADOW_STRICT_AUDIT"]
