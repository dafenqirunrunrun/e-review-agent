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
    trace_nodes = [item["node"] for item in body["workflow_trace"]]
    assert {"intent_router", "light_execution", "perception", "retrieval", "judge", "audit", "report"} <= set(trace_nodes)


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


def test_analyze_review_accepts_java_null_rating_source():
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "java-null-rating-source",
            "productId": 1006002,
            "productName": "Java Admin Payload",
            "reviewText": "Five-star screenshot cashback offer.",
            "imageUrls": [],
            "rating": 5,
            "ratingSource": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["review_id"] == "java-null-rating-source"


def test_review_analyze_returns_business_governance_contract(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    response = client.post(
        "/api/v1/review/analyze",
        json={
            "reviewId": "governance-contract",
            "productId": 1006003,
            "productName": "Governance Product",
            "reviewText": "cashback for five star review, paid review incentive",
            "imageUrls": [],
            "rating": 5,
        },
    )

    assert response.status_code == 200
    contract = response.json()["review_governance"]
    assert contract["schemaVersion"] == "review-governance-v2"
    assert contract["governanceSchemaVersion"] == "review-governance-v2"
    assert contract["reviewId"] == "governance-contract"
    assert contract["decision"]["code"] in ["suggest_action", "manual_review", "auto_pass"]
    assert contract["summary"]["title"]
    assert contract["evidenceStatus"] in ["supported", "insufficient", "mismatch"]
    assert "requiresHumanReview" in contract
    assert "reflectionReason" in contract
    assert "reflectionReasonCode" in contract
    assert "failureReasons" in contract
    assert contract["riskCoverage"]
    assert contract["riskSignals"]
    assert "evidenceStatus" in contract["riskSignals"][0]
    assert contract["process"][0]["name"] == "识别是否需要严格审核"
    assert len(contract["evidenceCitations"]) <= 3
    if contract["evidenceCitations"]:
        citation = contract["evidenceCitations"][0]
        assert citation["sourceUrl"].startswith("https://")
        assert citation["contentHash"]
        assert citation["retrieval"]["mode"] in ["hybrid", "dense", "bm25_fallback"]
    if contract["decision"]["code"] != "auto_pass":
        assert contract["recommendedActions"]


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


def test_system_readiness_exposes_safe_policy_rag_status(monkeypatch):
    from app.api import system as system_api

    class RetrieverWithPrivatePath:
        def readiness(self):
            return {
                "status": "ready",
                "retrievalMode": "hybrid",
                "dense": {
                    "status": "ready",
                    "providerMetrics": {
                        "modelPath": "D:/secret/local/qwen",
                        "dimension": 1024,
                    },
                },
            }

    class RerankerStatus:
        def readiness(self):
            return {"status": "ready", "loaded": True}

    monkeypatch.setattr(
        system_api,
        "_runtime_policy_components",
        lambda: (RetrieverWithPrivatePath(), RerankerStatus()),
    )
    response = client.get("/api/v1/system/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ["ready", "degraded"]
    assert body["policyRag"]["config"]["embeddingModelPath"] in ["configured", "missing", "not_configured"]
    assert body["policyRag"]["dense"]["providerMetrics"]["modelPath"] == "configured"
    assert "D:/secret/local/qwen" not in response.text
    assert "retrievalMode" in body["policyRag"]


def test_system_readiness_observes_active_review_workflow_instances():
    from app.api import review as review_api
    from app.api import system as system_api

    retriever, reranker = system_api._runtime_policy_components()

    assert retriever is review_api.agentic_workflow.policy_retriever
    assert reranker is review_api.agentic_workflow.policy_reranker


def test_policy_index_runtime_exposes_desired_and_loaded_versions(monkeypatch):
    from app.api import system as system_api

    class RuntimeRetriever:
        def readiness(self):
            return {
                "status": "ready",
                "retrievalMode": "hybrid",
                "managed": True,
                "runtimeIndex": {
                    "desiredIndexVersion": "policy-20260917T120000-aaaaaaaa",
                    "loadedIndexVersion": "policy-20260917T120000-aaaaaaaa",
                    "reloadStatus": "ready",
                    "lastReloadError": "",
                    "loadedChunkCount": 951,
                },
            }

    monkeypatch.setattr(system_api, "_runtime_policy_components", lambda: (RuntimeRetriever(), object()))
    response = client.get("/api/v1/system/policy-index-runtime")

    assert response.status_code == 200
    assert response.json()["desiredIndexVersion"] == response.json()["loadedIndexVersion"]
    assert response.json()["loadedChunkCount"] == 951


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
