import os
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    base_url: str
    model_name: str
    api_key_env: str
    timeout_seconds: int
    max_retries: int
    enabled: bool
    fallback_provider: str = "local_rule_fallback"

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()

    @property
    def available(self) -> bool:
        if self.provider_name == "local_rule_fallback":
            return True
        if self.provider_name == "local_qwen3_transformers":
            return self.enabled
        if not self.api_key_env:
            return self.enabled and bool(self.base_url and self.model_name)
        return self.enabled and bool(self.api_key and self.base_url and self.model_name)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def provider_configs() -> Dict[str, ProviderConfig]:
    timeout = _env_int("E_REVIEW_LLM_TIMEOUT_SECONDS", 30)
    retries = _env_int("E_REVIEW_LLM_MAX_RETRIES", 2)
    return {
        "qwen_openai_compatible": ProviderConfig(
            provider_name="qwen_openai_compatible",
            base_url=os.getenv("E_REVIEW_QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/"),
            model_name=os.getenv("E_REVIEW_QWEN_MODEL", "qwen-plus"),
            api_key_env="E_REVIEW_QWEN_API_KEY",
            timeout_seconds=timeout,
            max_retries=retries,
            enabled=_env_bool("E_REVIEW_QWEN_ENABLED", True),
        ),
        "deepseek_openai_compatible": ProviderConfig(
            provider_name="deepseek_openai_compatible",
            base_url=os.getenv("E_REVIEW_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
            model_name=os.getenv("E_REVIEW_DEEPSEEK_MODEL", "deepseek-chat"),
            api_key_env="E_REVIEW_DEEPSEEK_API_KEY",
            timeout_seconds=timeout,
            max_retries=retries,
            enabled=_env_bool("E_REVIEW_DEEPSEEK_ENABLED", True),
        ),
        "local_qwen3_transformers": ProviderConfig(
            provider_name="local_qwen3_transformers",
            base_url="local://transformers",
            model_name=os.getenv("E_REVIEW_LOCAL_QWEN_MODEL", "Qwen/Qwen3-1.7B"),
            api_key_env="",
            timeout_seconds=_env_int("E_REVIEW_LOCAL_QWEN_TIMEOUT_SECONDS", 120),
            max_retries=0,
            enabled=_env_bool("E_REVIEW_LOCAL_QWEN_ENABLED", True),
        ),
        "local_qwen3_openai_compatible": ProviderConfig(
            provider_name="local_qwen3_openai_compatible",
            base_url=os.getenv("E_REVIEW_LOCAL_QWEN_BASE_URL", "http://127.0.0.1:8009/v1").rstrip("/"),
            model_name=os.getenv("E_REVIEW_LOCAL_QWEN_MODEL_NAME", "Qwen/Qwen3-1.7B"),
            api_key_env="",
            timeout_seconds=_env_int("E_REVIEW_LOCAL_QWEN_TIMEOUT_SECONDS", 120),
            max_retries=retries,
            enabled=_env_bool("E_REVIEW_LOCAL_QWEN_OPENAI_ENABLED", True),
        ),
        "local_rule_fallback": ProviderConfig(
            provider_name="local_rule_fallback",
            base_url="local://rule-agent",
            model_name="e-review-rule-agent",
            api_key_env="",
            timeout_seconds=0,
            max_retries=0,
            enabled=True,
        ),
    }


def selected_provider_name() -> str:
    aliases = {
        "qwen": "qwen_openai_compatible",
        "deepseek": "deepseek_openai_compatible",
        "local": "local_rule_fallback",
        "fallback": "local_rule_fallback",
        "local_qwen": "local_qwen3_transformers",
        "qwen3_local": "local_qwen3_transformers",
    }
    raw = os.getenv("E_REVIEW_LLM_PROVIDER", "local_rule_fallback").strip().lower()
    return aliases.get(raw, raw)


def selected_config() -> ProviderConfig:
    configs = provider_configs()
    return configs.get(selected_provider_name(), configs["local_rule_fallback"])
