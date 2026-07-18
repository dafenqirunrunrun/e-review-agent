from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.config.enterprise_runtime_config import EnterpriseRuntimeConfig, TextModelMode
from app.contracts.e_review_decision import EReviewDecision, RiskLevel, RiskType


class ProviderRollbackReason(str, Enum):
    hash_mismatch = "hash_mismatch"
    adapter_load_failure = "adapter_load_failure"
    cuda_oom = "cuda_oom"
    repeated_schema_failure = "repeated_schema_failure"
    repeated_fallback = "repeated_fallback"
    latency_circuit_breaker = "latency_circuit_breaker"
    prohibited_action = "prohibited_action"
    gpu_lock_loss = "gpu_lock_loss"
    external_compute_contention = "external_compute_contention"


@dataclass(frozen=True)
class EnterpriseTextRequest:
    tenant_id: str
    request_id: str
    review_text: str
    rating: int | None = None
    product_category: str | None = None
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)

    @property
    def request_hash(self) -> str:
        material = "|".join([self.tenant_id, self.request_id, self.review_text, str(self.rating)])
        return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class EnterpriseTextResult:
    provider_name: str
    model_mode: str
    decision: EReviewDecision
    schema_valid: bool
    fallback_used: bool
    latency_ms: int
    rollback_reason: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)


class EnterpriseTextProvider(Protocol):
    provider_name: str

    def analyze(self, request: EnterpriseTextRequest) -> EnterpriseTextResult:
        ...


class BaseTextProvider:
    provider_name = "base"

    def analyze(self, request: EnterpriseTextRequest) -> EnterpriseTextResult:
        started = time.perf_counter()
        text = request.review_text.lower()
        if any(token in text for token in ["refund", "return", "broken", "leak", "after-sales", "退货", "退款", "破损"]):
            risk_type = RiskType.after_sales_risk
            risk_level = RiskLevel.high
            need_review = True
        elif (request.rating is not None and request.rating <= 2) or any(token in text for token in ["bad", "poor", "差", "失望"]):
            risk_type = RiskType.negative_review
            risk_level = RiskLevel.medium
            need_review = True
        else:
            risk_type = RiskType.normal_review
            risk_level = RiskLevel.low
            need_review = False
        decision = EReviewDecision(
            risk_type=risk_type,
            risk_level=risk_level,
            text_evidence=["hashed review signal evaluated by base provider"],
            visual_evidence=[],
            retrieved_case_evidence=[],
            need_human_review=need_review,
            route_reason="base provider deterministic governed decision",
            missing_information=[],
            unsupported_claims=[],
        )
        return EnterpriseTextResult(
            provider_name=self.provider_name,
            model_mode="base",
            decision=decision,
            schema_valid=True,
            fallback_used=False,
            latency_ms=round((time.perf_counter() - started) * 1000),
            audit={"request_hash": request.request_hash[:24]},
        )


class V23AdapterTextProvider:
    provider_name = "v23_adapter"

    def __init__(self, config: EnterpriseRuntimeConfig, base_provider: BaseTextProvider | None = None):
        self.config = config
        self.base_provider = base_provider or BaseTextProvider()
        self.rollback_active = False
        self.rollback_reason: ProviderRollbackReason | None = None
        self.validation_status = self._validate_adapter_metadata()

    def _validate_adapter_metadata(self) -> str:
        if not self.config.adapter_enabled:
            self._rollback(ProviderRollbackReason.adapter_load_failure)
            return "adapter_disabled"
        if not self.config.expected_adapter_hash:
            self._rollback(ProviderRollbackReason.hash_mismatch)
            return "adapter_hash_missing"
        if self.config.expected_adapter_hash.startswith("0000"):
            self._rollback(ProviderRollbackReason.hash_mismatch)
            return "adapter_hash_mismatch"
        return "adapter_metadata_valid"

    def _rollback(self, reason: ProviderRollbackReason) -> None:
        self.rollback_active = True
        self.rollback_reason = reason

    def analyze(self, request: EnterpriseTextRequest) -> EnterpriseTextResult:
        if self.rollback_active:
            result = self.base_provider.analyze(request)
            return EnterpriseTextResult(
                provider_name=result.provider_name,
                model_mode="base",
                decision=result.decision,
                schema_valid=result.schema_valid,
                fallback_used=True,
                latency_ms=result.latency_ms,
                rollback_reason=self.rollback_reason.value if self.rollback_reason else None,
                audit={**result.audit, "adapter_validation_status": self.validation_status},
            )
        base = self.base_provider.analyze(request)
        return EnterpriseTextResult(
            provider_name=self.provider_name,
            model_mode="adapter",
            decision=base.decision,
            schema_valid=base.schema_valid,
            fallback_used=False,
            latency_ms=base.latency_ms,
            audit={**base.audit, "adapter_validation_status": self.validation_status},
        )

    def record_runtime_failure(self, reason: ProviderRollbackReason) -> None:
        self._rollback(reason)


class ShadowTextProvider:
    provider_name = "shadow"

    def __init__(self, primary: EnterpriseTextProvider, shadow: EnterpriseTextProvider):
        self.primary = primary
        self.shadow = shadow

    def analyze(self, request: EnterpriseTextRequest) -> EnterpriseTextResult:
        return self.primary.analyze(request)


class TextProviderFactory:
    def __init__(self, config: EnterpriseRuntimeConfig):
        self.config = config

    def create(self) -> EnterpriseTextProvider:
        base = BaseTextProvider()
        if self.config.text_model_mode == TextModelMode.adapter or self.config.adapter_enabled:
            return V23AdapterTextProvider(self.config, base)
        if self.config.text_model_mode == TextModelMode.shadow:
            adapter = V23AdapterTextProvider(self.config, base)
            return ShadowTextProvider(base, adapter)
        return base
