from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class TextModelMode(str, Enum):
    base = "base"
    adapter = "adapter"
    shadow = "shadow"


class RAGMode(str, Enum):
    disabled = "disabled"
    dense = "dense"
    sparse = "sparse"
    hybrid = "hybrid"
    hybrid_rerank = "hybrid_rerank"


class AgentMode(str, Enum):
    direct = "direct"
    rag_assisted = "rag_assisted"
    governed_agent = "governed_agent"


class EnterpriseRuntimeConfig(BaseModel):
    text_model_mode: TextModelMode = TextModelMode.base
    adapter_enabled: bool = False
    adapter_path: str | None = None
    expected_adapter_hash: str | None = None
    rag_mode: RAGMode = RAGMode.hybrid
    agent_mode: AgentMode = AgentMode.governed_agent
    dense_top_k: int = Field(default=20, ge=1, le=100)
    sparse_top_k: int = Field(default=20, ge=1, le=100)
    fused_top_k: int = Field(default=12, ge=1, le=50)
    rerank_top_k: int = Field(default=8, ge=1, le=50)
    max_context_chunks: int = Field(default=6, ge=0, le=20)
    max_agent_steps: int = Field(default=8, ge=1, le=16)
    max_tool_calls: int = Field(default=4, ge=0, le=12)
    request_timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    tool_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    shadow_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_cache_ttl: int = Field(default=300, ge=0, le=86400)
    idempotency_ttl: int = Field(default=900, ge=0, le=86400)
    tenant_id_required: bool = True
    pii_redaction_enabled: bool = True
    prompt_injection_guard_enabled: bool = True
    metrics_enabled: bool = True
    audit_log_enabled: bool = True

    @field_validator("adapter_path")
    @classmethod
    def reject_absolute_adapter_path(cls, value: str | None) -> str | None:
        if value and Path(value).is_absolute():
            raise ValueError("adapter_path must not be an absolute path in Git-tracked configuration")
        return value

    @field_validator("expected_adapter_hash")
    @classmethod
    def validate_adapter_hash(cls, value: str | None) -> str | None:
        if value and (len(value) < 12 or any(ch not in "0123456789abcdefABCDEF" for ch in value)):
            raise ValueError("expected_adapter_hash must be a hex digest prefix")
        return value.lower() if value else value

    def safe_public_status(self) -> dict[str, Any]:
        return {
            "text_model_mode": self.text_model_mode.value,
            "adapter_enabled": self.adapter_enabled,
            "adapter_hash_configured": bool(self.expected_adapter_hash),
            "rag_mode": self.rag_mode.value,
            "agent_mode": self.agent_mode.value,
            "shadow_sample_rate": self.shadow_sample_rate,
            "tenant_id_required": self.tenant_id_required,
            "pii_redaction_enabled": self.pii_redaction_enabled,
            "prompt_injection_guard_enabled": self.prompt_injection_guard_enabled,
            "metrics_enabled": self.metrics_enabled,
            "audit_log_enabled": self.audit_log_enabled,
        }


def load_enterprise_runtime_config(env: dict[str, str] | None = None) -> EnterpriseRuntimeConfig:
    source = env or os.environ
    values: dict[str, Any] = {}
    mapping = {
        "text_model_mode": "EREVIEW_TEXT_MODEL_MODE",
        "adapter_enabled": "EREVIEW_ADAPTER_ENABLED",
        "adapter_path": "EREVIEW_ADAPTER_PATH",
        "expected_adapter_hash": "EREVIEW_ADAPTER_EXPECTED_HASH",
        "rag_mode": "EREVIEW_RAG_MODE",
        "agent_mode": "EREVIEW_AGENT_MODE",
        "shadow_sample_rate": "EREVIEW_SHADOW_SAMPLE_RATE",
    }
    for field_name, env_name in mapping.items():
        if env_name in source:
            values[field_name] = _coerce(source[env_name])
    try:
        return EnterpriseRuntimeConfig(**values)
    except ValidationError:
        raise


def _coerce(value: str) -> Any:
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
