from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_review():
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "R001",
            "product_id": "P001",
            "product_name": "真无线降噪耳机",
            "review_text": "耳机音质不错，但是续航一般，充电盒有点容易留下指纹。",
            "image_urls": ["http://example.com/a.jpg"],
            "rating": 4,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == "R001"
    assert body["product_id"] == "P001"
    assert body["sentiment_label"] in ["positive", "neutral", "negative"]
    assert len(body["workflow_trace"]) == 5


def test_analyze_review_accepts_java_camel_case_payload():
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "manual-test",
            "productId": 1006002,
            "productName": "Java Admin Payload",
            "reviewText": "Delivery was fast, but the product became hot after two days.",
            "imageUrls": ["https://example.com/review-1.jpg"],
            "rating": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == "manual-test"
    assert body["product_id"] == "1006002"
    assert "scores" in body
    assert "evidence" in body
    assert body["similar_cases"][0]["label"] in ["positive", "neutral", "negative"]
    assert body["workflow_trace"][0]["agent"]


def test_empty_review_text_rejected():
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "R002",
            "product_id": "P001",
            "product_name": "真无线降噪耳机",
            "review_text": "",
            "image_urls": [],
            "rating": 4,
        },
    )
    assert response.status_code == 422


def test_agent_framework_status():
    response = client.get("/api/v1/agent-framework/status")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "langgraph"
    assert "fallback_enabled" in body
    assert "api_key_available" in body


def test_agent_framework_analyze_has_modality_outputs():
    response = client.post(
        "/api/v1/agent-framework/analyze",
        json={
            "review_id": "framework-test",
            "product_id": "P900",
            "product_name": "Framework Product",
            "review_text": "Looks okay but refund requested because the package was broken.",
            "image_urls": ["https://example.com/refund-broken-package.jpg"],
            "rating": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["framework"] in ["langgraph", "fallback_rule_graph"]
    assert "modality_conflict" in body
    assert "dominant_modality" in body
    assert body["modality_conflict"]["conflict_score"] >= 0
    assert body["dominant_modality"]["dominant_modality"] in ["text", "image", "rating"]
    assert len(body["workflow_trace"]) >= 9


def test_review_analyze_uses_framework_when_enabled(monkeypatch):
    monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "true")
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "framework-enabled",
            "product_id": "P901",
            "product_name": "Framework Enabled Product",
            "review_text": "The product is beautiful but the rating is low because service was slow.",
            "image_urls": ["https://example.com/product.jpg"],
            "rating": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["framework"] in ["langgraph", "fallback_rule_graph"]
    assert "modality_conflict" in body
    assert body["llm_provider"] == "local_rule_fallback"
    assert body["schema_valid"] is True


def test_framework_fallback_when_node_fails(monkeypatch):
    from app.agent_framework import graph

    def broken_tools(_analyzer):
        raise RuntimeError("forced graph failure")

    monkeypatch.setattr(graph, "build_tools", broken_tools)
    response = client.post(
        "/api/v1/agent-framework/analyze",
        json={
            "review_id": "framework-fallback",
            "product_id": "P902",
            "product_name": "Fallback Product",
            "review_text": "The product is acceptable.",
            "image_urls": [],
            "rating": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["framework"] == "legacy_rule_agent"
    assert body["fallback_used"] is True
