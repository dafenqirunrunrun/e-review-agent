import asyncio
import sys
from pathlib import Path

import pytest

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.config.enterprise_runtime_config import EnterpriseRuntimeConfig, TextModelMode, load_enterprise_runtime_config
from app.llm.enterprise_providers import (
    BaseTextProvider,
    EnterpriseTextRequest,
    ProviderRollbackReason,
    TextProviderFactory,
    V23AdapterTextProvider,
)
from app.runtime.shadow_execution import ShadowExecutionQueue, aggregate_shadow_result


def test_v170_runtime_config_defaults_are_enterprise_safe():
    config = EnterpriseRuntimeConfig()
    assert config.text_model_mode.value == "base"
    assert config.adapter_enabled is False
    assert config.rag_mode.value == "hybrid"
    assert config.agent_mode.value == "governed_agent"
    assert config.shadow_sample_rate == 0.0
    assert "adapter_path" not in config.safe_public_status()


@pytest.mark.parametrize("adapter_path", ["/private/adapter", "Z:/private/adapter"])
def test_v170_runtime_config_rejects_absolute_adapter_path(adapter_path):
    with pytest.raises(ValueError):
        EnterpriseRuntimeConfig(adapter_path=adapter_path)


def test_v170_runtime_config_loads_feature_flags_without_secret_paths():
    config = load_enterprise_runtime_config(
        {
            "EREVIEW_TEXT_MODEL_MODE": "adapter",
            "EREVIEW_ADAPTER_ENABLED": "true",
            "EREVIEW_ADAPTER_EXPECTED_HASH": "abc123def456",
            "EREVIEW_SHADOW_SAMPLE_RATE": "0.25",
        }
    )
    assert config.text_model_mode == TextModelMode.adapter
    assert config.adapter_enabled is True
    assert config.shadow_sample_rate == 0.25


def test_v170_adapter_provider_rolls_back_on_hash_mismatch():
    config = EnterpriseRuntimeConfig(
        text_model_mode=TextModelMode.adapter,
        adapter_enabled=True,
        expected_adapter_hash="0000abcdef12",
    )
    provider = V23AdapterTextProvider(config)
    result = provider.analyze(_request("bad return broken product"))
    assert provider.rollback_active is True
    assert result.model_mode == "base"
    assert result.fallback_used is True
    assert result.rollback_reason == ProviderRollbackReason.hash_mismatch.value


def test_v170_provider_factory_defaults_to_base():
    provider = TextProviderFactory(EnterpriseRuntimeConfig()).create()
    result = provider.analyze(_request("good quality"))
    assert result.model_mode == "base"
    assert result.schema_valid is True
    assert result.decision.risk_type == "normal_review"


def test_v170_shadow_queue_is_bounded_and_non_blocking():
    queue = ShadowExecutionQueue(maxsize=2)

    async def noop():
        base = BaseTextProvider().analyze(_request("good"))
        return aggregate_shadow_result(_request("good"), base, base)

    async def run():
        assert await queue.submit(noop) is True
        assert await queue.submit(noop) is True
        assert await queue.submit(noop) is False
        assert queue.dropped_count == 1
        result = await queue.drain_once()
        assert result is not None
        assert result.risk_type_agreement is True

    asyncio.run(run())


def _request(text: str) -> EnterpriseTextRequest:
    return EnterpriseTextRequest(tenant_id="tenant-a", request_id="req-1", review_text=text, rating=5)
