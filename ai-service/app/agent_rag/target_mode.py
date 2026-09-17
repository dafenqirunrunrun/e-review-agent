from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal


TargetMode = Literal[
    "development-fixture",
    "governed-local",
    "enterprise-maturity-local-single-node",
]

SUPPORTED_TARGET_MODES: set[str] = {
    "development-fixture",
    "governed-local",
    "enterprise-maturity-local-single-node",
}

DEFAULT_TARGET_MODE: TargetMode = "governed-local"
DEFAULT_RETRIEVAL_MODE = "bm25-first-semantic-hybrid"


@dataclass(frozen=True)
class AgentRagTargetConfig:
    target_mode: TargetMode
    dense_provider: str
    bge_m3_provider_impl: str
    default_retrieval_mode: str
    reranker_type: str
    llm_provider: str
    rule_fallback_enabled: bool
    evidence_enabled: bool
    real_dense_required: bool

    def as_health_payload(self) -> dict[str, Any]:
        return {
            "targetMode": self.target_mode,
            "denseProvider": self.dense_provider,
            "bgeM3ProviderImpl": self.bge_m3_provider_impl,
            "defaultRetrievalMode": self.default_retrieval_mode,
            "rerankerType": self.reranker_type,
            "llmProvider": self.llm_provider,
            "ruleFallbackEnabled": self.rule_fallback_enabled,
            "evidenceEnabled": self.evidence_enabled,
            "realDenseRequired": self.real_dense_required,
        }


def load_agent_rag_target_config(env: dict[str, str] | None = None) -> AgentRagTargetConfig:
    values = env if env is not None else os.environ
    target_mode = _target_mode(values.get("AGENT_RAG_TARGET_MODE", DEFAULT_TARGET_MODE))
    return AgentRagTargetConfig(
        target_mode=target_mode,
        dense_provider=values.get("RAG_DENSE_PROVIDER", "hash").strip() or "hash",
        bge_m3_provider_impl=values.get("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls").strip() or "legacy-cls",
        default_retrieval_mode=values.get("RAG_DEFAULT_RETRIEVAL_MODE", DEFAULT_RETRIEVAL_MODE).strip()
        or DEFAULT_RETRIEVAL_MODE,
        reranker_type=values.get("RAG_RERANKER_TYPE", "deterministic").strip() or "deterministic",
        llm_provider=values.get("AGENT_LLM_PROVIDER", "rule").strip() or "rule",
        rule_fallback_enabled=_env_bool(values.get("RAG_RULE_FALLBACK_ENABLED"), default=True),
        evidence_enabled=_env_bool(values.get("RAG_EVIDENCE_ENABLED"), default=True),
        real_dense_required=_env_bool(values.get("RAG_REAL_DENSE_REQUIRED"), default=False),
    )


def _target_mode(raw_value: str) -> TargetMode:
    value = (raw_value or DEFAULT_TARGET_MODE).strip()
    if value not in SUPPORTED_TARGET_MODES:
        allowed = ",".join(sorted(SUPPORTED_TARGET_MODES))
        raise ValueError(f"AGENT_RAG_TARGET_MODE_UNSUPPORTED:{value}:allowed={allowed}")
    return value  # type: ignore[return-value]


def _env_bool(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None or raw_value == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
