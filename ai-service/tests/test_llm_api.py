import json

from fastapi.testclient import TestClient

from app.llm.config import ProviderConfig
from app.llm.providers import ProviderResult
from app.main import app


client = TestClient(app)


VALID_RESULT = {
    "risk_type": "after_sales_risk",
    "risk_level": "high",
    "sentiment": "negative",
    "evidence": ["使用两天后无法充电"],
    "reason": "评论明确描述了功能故障。",
    "suggestion": "建议人工核对订单和售后记录。",
    "need_human_review": True,
    "confidence": 0.91,
    "missing_information": ["订单状态"],
}


def payload():
    return {
        "review_id": "LLM-001",
        "product_id": "P-001",
        "product_name": "测试耳机",
        "review_text": "使用两天后无法充电，希望售后处理。",
        "image_urls": [],
        "rating": 1,
    }


def remote_config():
    return ProviderConfig(
        provider_name="qwen_openai_compatible",
        base_url="https://example.invalid/v1",
        model_name="qwen-test",
        api_key_env="E_REVIEW_TEST_API_KEY",
        timeout_seconds=1,
        max_retries=0,
        enabled=True,
    )


def test_provider_status_uses_local_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("E_REVIEW_LLM_PROVIDER", raising=False)
    response = client.get("/api/v1/llm/provider/status")
    assert response.status_code == 200
    body = response.json()
    assert body["current_provider"] == "local_rule_fallback"
    assert body["fallback_active"] is True
    assert "test-only-key" not in json.dumps(body).lower()
    assert "api_key_value" not in body


def test_qwen_selection_without_key_activates_fallback(monkeypatch):
    monkeypatch.setenv("E_REVIEW_LLM_PROVIDER", "qwen")
    monkeypatch.delenv("E_REVIEW_QWEN_API_KEY", raising=False)
    response = client.get("/api/v1/llm/provider/status")
    body = response.json()
    assert body["provider_name"] == "qwen_openai_compatible"
    assert body["api_key_available"] is False
    assert body["current_provider"] == "local_rule_fallback"
    assert body["fallback_active"] is True


def test_schema_validate_accepts_complete_result():
    response = client.post("/api/v1/llm/schema/validate", json={"data": VALID_RESULT})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_schema_validate_rejects_invalid_enum_and_confidence():
    invalid = dict(VALID_RESULT, risk_level="critical", confidence=1.5, evidence=None)
    response = client.post("/api/v1/llm/schema/validate", json={"data": invalid})
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "risk_level" in response.json()["error"]


def test_schema_repair_returns_valid_conservative_result():
    response = client.post("/api/v1/llm/schema/repair", json={"data": {"risk_level": "critical", "confidence": 8}})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["data"]["risk_level"] == "medium"
    assert body["data"]["confidence"] == 1.0
    assert body["data"]["need_human_review"] is True


def test_think_block_is_removed_before_json_validation():
    from app.api.llm import service

    raw = "<think>这里是不会进入结果的推理内容</think>\n```json\n" + json.dumps(VALID_RESULT, ensure_ascii=False) + "\n```"
    parsed, error = service.validate_raw(raw)
    assert error is None
    assert parsed.risk_type == "after_sales_risk"


def test_unclosed_think_prefix_is_removed_before_json_validation():
    from app.api.llm import service

    raw = "临时推理内容</think>" + json.dumps(VALID_RESULT, ensure_ascii=False)
    parsed, error = service.validate_raw(raw)
    assert error is None
    assert parsed.risk_level == "high"


def test_llm_endpoint_returns_local_rule_fallback_by_default(monkeypatch):
    monkeypatch.delenv("E_REVIEW_LLM_PROVIDER", raising=False)
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "local_rule_fallback"
    assert body["schema_valid"] is True
    assert body["need_human_review"] is True
    assert body["fallback_used"] is True
    assert body["evidence"]


def test_remote_provider_valid_json_is_applied(monkeypatch):
    config = remote_config()
    monkeypatch.setenv(config.api_key_env, "test-only-key")
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    monkeypatch.setattr(
        "app.llm.service.OpenAICompatibleProvider.complete_json",
        lambda self, prompt: ProviderResult(json.dumps(VALID_RESULT, ensure_ascii=False), 120, 80, 25),
    )
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    body = response.json()
    assert body["llm_provider"] == "qwen_openai_compatible"
    assert body["model_name"] == "qwen-test"
    assert body["schema_valid"] is True
    assert body["repair_used"] is False
    assert body["fallback_used"] is False
    assert body["token_usage_input"] == 120


def test_invalid_provider_output_triggers_repair(monkeypatch):
    config = remote_config()
    monkeypatch.setenv(config.api_key_env, "test-only-key")
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    outputs = iter([
        ProviderResult('{"risk_level":"critical"}', 10, 5, 8),
        ProviderResult(json.dumps(VALID_RESULT, ensure_ascii=False), 20, 10, 9),
    ])
    monkeypatch.setattr("app.llm.service.OpenAICompatibleProvider.complete_json", lambda self, prompt: next(outputs))
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    body = response.json()
    assert body["schema_valid"] is True
    assert body["repair_used"] is True
    assert body["fallback_used"] is False
    assert body["token_usage_input"] == 30


def test_repair_failure_uses_local_fallback(monkeypatch):
    config = remote_config()
    monkeypatch.setenv(config.api_key_env, "test-only-key")
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    monkeypatch.setattr(
        "app.llm.service.OpenAICompatibleProvider.complete_json",
        lambda self, prompt: ProviderResult("not-json", 4, 2, 3),
    )
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    body = response.json()
    assert body["llm_provider"] == "local_rule_fallback"
    assert body["repair_used"] is True
    assert body["fallback_used"] is True
    assert body["schema_error"]


def test_local_qwen_load_failure_uses_fallback(monkeypatch):
    config = ProviderConfig(
        provider_name="local_qwen3_transformers",
        base_url="local://transformers",
        model_name="Qwen/Qwen3-1.7B",
        api_key_env="",
        timeout_seconds=120,
        max_retries=0,
        enabled=True,
    )
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    monkeypatch.setattr(
        "app.llm.service.LocalQwenTransformersProvider.complete_json",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("LOCAL_QWEN_MODEL_NOT_AVAILABLE")),
    )
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    body = response.json()
    assert body["llm_provider"] == "local_rule_fallback"
    assert body["fallback_used"] is True
    assert body["schema_error"] == "LOCAL_QWEN_MODEL_NOT_AVAILABLE"


def test_local_qwen_valid_output_uses_transformers_tool(monkeypatch):
    config = ProviderConfig(
        provider_name="local_qwen3_transformers",
        base_url="local://transformers",
        model_name="Qwen/Qwen3-1.7B",
        api_key_env="",
        timeout_seconds=120,
        max_retries=0,
        enabled=True,
    )
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    monkeypatch.setattr(
        "app.llm.service.LocalQwenTransformersProvider.complete_json",
        lambda self, prompt: ProviderResult(json.dumps(VALID_RESULT, ensure_ascii=False), 88, 64, 321),
    )
    response = client.post("/api/v1/llm/review/analyze", json=payload())
    body = response.json()
    assert body["llm_provider"] == "local_qwen3_transformers"
    assert body["fallback_used"] is False
    assert body["workflow_trace"][-1]["tool_name"] == "LocalQwenTransformersTool"


def test_local_qwen_smoke_endpoint_reports_fallback_when_unavailable(monkeypatch):
    config = ProviderConfig(
        provider_name="local_qwen3_transformers",
        base_url="local://transformers",
        model_name="Qwen/Qwen3-1.7B",
        api_key_env="",
        timeout_seconds=120,
        max_retries=0,
        enabled=True,
    )
    monkeypatch.setattr("app.llm.service.selected_config", lambda: config)
    monkeypatch.setattr(
        "app.llm.service.LocalQwenTransformersProvider.complete_json",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("LOCAL_QWEN_DEPENDENCY_NOT_AVAILABLE")),
    )
    response = client.post(
        "/api/v1/llm/local-qwen/smoke-test",
        json={"comment_text": "刚收到就破损，要求退款", "rating": 1, "image_signal": "包装破损图片"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["provider"] == "local_rule_fallback"
    assert body["fallback_used"] is True
