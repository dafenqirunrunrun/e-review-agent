from __future__ import annotations

import hashlib
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config.enterprise_runtime_config import EnterpriseRuntimeConfig
from app.contracts.e_review_decision import E_REVIEW_DECISION_SCHEMA_VERSION
from app.llm.enterprise_providers import EnterpriseTextRequest, TextProviderFactory
from app.observability.metrics import metrics_registry
from app.platform.idempotency import InMemoryIdempotencyStore, idempotency_key
from app.platform.security import PIIRedactor, PromptInjectionGuard, SafeStructuredLogger


router = APIRouter(prefix="/e-review", tags=["enterprise-e-review"])
_store = InMemoryIdempotencyStore()
_config = EnterpriseRuntimeConfig()


class EnterpriseAnalyzeRequest(BaseModel):
    request_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    tenant_id: str = Field(min_length=1)
    review_text: str = Field(min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)
    product_category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/analyze")
def analyze(payload: EnterpriseAnalyzeRequest) -> dict:
    return _analyze(payload, rag=False)


@router.post("/analyze/rag")
def analyze_rag(payload: EnterpriseAnalyzeRequest) -> dict:
    return _analyze(payload, rag=True)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "e-review-enterprise", "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION}


@router.get("/metrics")
def metrics() -> dict:
    return metrics_registry.snapshot()


@router.get("/runtime-status")
def runtime_status() -> dict:
    return _config.safe_public_status()


def _analyze(payload: EnterpriseAnalyzeRequest, rag: bool) -> dict:
    started = time.perf_counter()
    guard = PromptInjectionGuard().inspect(payload.review_text)
    redacted, redaction_count = PIIRedactor().redact(payload.review_text)
    payload_hash = hashlib.sha256(redacted.encode("utf-8", errors="replace")).hexdigest()
    key = payload.idempotency_key or idempotency_key(payload.tenant_id, "/api/v1/e-review/analyze", payload.model_dump(), E_REVIEW_DECISION_SCHEMA_VERSION)
    cached = _store.get(key)
    if cached:
        metrics_registry.inc("idempotency_hit_total")
        metrics_registry.observe("request_latency_ms", round((time.perf_counter() - started) * 1000, 4))
        return cached
    provider = TextProviderFactory(_config).create()
    result = provider.analyze(
        EnterpriseTextRequest(
            tenant_id=payload.tenant_id,
            request_id=payload.request_id,
            review_text=redacted,
            rating=payload.rating,
            product_category=payload.product_category,
        )
    )
    response = {
        "decision": result.decision.model_dump(mode="json"),
        "evidence_references": [],
        "review_required": result.decision.need_human_review or guard["blocked"],
        "fallback": result.fallback_used,
        "trace_id": hashlib.sha256(f"{payload.tenant_id}:{payload.request_id}".encode()).hexdigest()[:24],
        "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "schema_valid": result.schema_valid,
        "rag_enabled": rag,
        "prompt_injection_detected": guard["blocked"],
        "pii_redaction_count": redaction_count,
        "audit": SafeStructuredLogger().event(
            trace_id=hashlib.sha256(payload.request_id.encode()).hexdigest()[:16],
            request_id=payload.request_id,
            tenant_hash=hashlib.sha256(payload.tenant_id.encode()).hexdigest()[:16],
            input_hash=payload_hash[:24],
            route="human_review" if guard["blocked"] else "model_decision",
            retrieval_count=0,
            model_mode=result.model_mode,
            tool_names=[],
            latency_ms=result.latency_ms,
            schema_status="valid" if result.schema_valid else "invalid",
            fallback_status=result.fallback_used,
        ),
    }
    _store.put(key, response, _config.idempotency_ttl)
    metrics_registry.inc("requests_total")
    metrics_registry.inc("success_total")
    metrics_registry.observe("request_latency_ms", round((time.perf_counter() - started) * 1000, 4))
    metrics_registry.observe("model_latency_ms", result.latency_ms)
    metrics_registry.observe("pii_redaction_count", redaction_count)
    if rag:
        metrics_registry.inc("rag_requests_total")
    if guard["blocked"]:
        metrics_registry.inc("prompt_injection_total")
    if result.fallback_used:
        metrics_registry.inc("fallback_total")
    if response["review_required"]:
        metrics_registry.inc("human_review_total")
    return response
