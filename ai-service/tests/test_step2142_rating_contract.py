from __future__ import annotations

from app.agentic_workflow.workflow import IntentRouterAgent
from app.schemas.review import ReviewAnalyzeRequest


def request(*, rating=None, rating_source=None) -> ReviewAnalyzeRequest:
    payload = {
        "reviewId": "rating-contract",
        "productId": "P1",
        "productName": "Product",
        "reviewText": "商品符合描述，物流正常。",
        "imageUrls": [],
    }
    if rating is not None:
        payload["rating"] = rating
    if rating_source is not None:
        payload["ratingSource"] = rating_source
    return ReviewAnalyzeRequest.model_validate(payload)


def route(payload: ReviewAnalyzeRequest):
    return IntentRouterAgent(
        rule_enhancements_enabled=True,
        safety_gate_enabled=True,
    )._route_with_rules(payload)


def test_unknown_rating_not_low_rating():
    payload = request(rating=1, rating_source="UNKNOWN")
    decision = route(payload)

    assert payload.rating is None
    assert payload.rating_source == "UNKNOWN"
    assert "LOW_RATING" not in decision.reason_codes
    assert decision.route == "low_touch"


def test_real_one_star_triggers_low_rating():
    payload = request(rating=1, rating_source="USER_PROVIDED")
    decision = route(payload)

    assert payload.rating == 1
    assert payload.rating_source == "USER_PROVIDED"
    assert "LOW_RATING" in decision.reason_codes
    assert decision.route == "governance_required"


def test_rating_null_contract():
    payload = request()

    assert payload.rating is None
    assert payload.rating_source == "UNKNOWN"


def test_no_default_rating_risk():
    decision = route(request())

    assert decision.risk_hints == []
    assert decision.reason_codes == ["NO_RISK_SIGNAL"]
    assert decision.route == "low_touch"


def test_explicit_rating_without_source_remains_backward_compatible():
    payload = request(rating=1)

    assert payload.rating == 1
    assert payload.rating_source == "USER_PROVIDED"


def test_null_source_from_java_remains_backward_compatible():
    payload = ReviewAnalyzeRequest.model_validate(
        {
            "reviewId": "java-null-source",
            "productId": "P1",
            "productName": "Product",
            "reviewText": "商品符合描述，物流正常。",
            "imageUrls": [],
            "rating": 5,
            "ratingSource": None,
        }
    )

    assert payload.rating == 5
    assert payload.rating_source == "USER_PROVIDED"


def test_null_snake_case_source_remains_backward_compatible():
    payload = ReviewAnalyzeRequest.model_validate(
        {
            "review_id": "python-null-source",
            "product_id": "P1",
            "product_name": "Product",
            "review_text": "商品符合描述，物流正常。",
            "image_urls": [],
            "rating": 5,
            "rating_source": None,
        }
    )

    assert payload.rating == 5
    assert payload.rating_source == "USER_PROVIDED"
