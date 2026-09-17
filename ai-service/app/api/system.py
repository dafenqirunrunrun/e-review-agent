from fastapi import APIRouter

from app.core.config import settings
from app.data_governance.research_scope_gate import private_research_status
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.runtime.fast_eligibility_runtime import FastEligibilityRuntimeController


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/liveness")
def liveness():
    return {"status": "ok", "service": settings.service_name}


@router.get("/readiness")
def readiness():
    private_status = private_research_status()
    policy_status = _policy_rag_readiness()
    private_ready = private_status.get("status") in {"ok", "ready", "enabled"} or private_status.get("technical_system_readiness") == "PASS"
    ready = policy_status.get("status") in {"ready", "disabled"} and private_ready
    return {
        "status": "ready" if ready else "degraded",
        "service": settings.service_name,
        "agenticWorkflow": {
            "enabled": settings.agentic_workflow_enabled,
            "maxIterations": settings.agentic_max_iterations,
            "intentRouter": settings.intent_router_provider,
        },
        "humanReview": {"enabled": settings.human_review_enabled},
        "fastEligibilityRuntime": FastEligibilityRuntimeController().status(),
        "policyEvidenceDisplay": {"enabled": settings.policy_evidence_display_enabled},
        "langfuse": {
            "enabled": settings.langfuse_enabled,
            "configured": bool(settings.langfuse_host and __import__("os").getenv("LANGFUSE_PUBLIC_KEY") and __import__("os").getenv("LANGFUSE_SECRET_KEY")),
            "environment": settings.langfuse_environment,
            "sampleRate": settings.langfuse_sample_rate,
        },
        "policyRag": policy_status,
        "privateResearch": {"status": "ready" if private_ready else "degraded"},
    }


@router.get("/policy-index-runtime")
def policy_index_runtime():
    retriever, _ = _runtime_policy_components()
    status = _redact_policy_rag_runtime_paths(retriever.readiness())
    runtime = dict(status.get("runtimeIndex") or {})
    return {
        "status": status.get("status", "degraded"),
        "retrievalMode": status.get("retrievalMode", "unavailable"),
        "managed": bool(status.get("managed", False)),
        **runtime,
    }


def _policy_rag_readiness() -> dict:
    policy_settings = settings.policy_rag
    if not policy_settings.enabled:
        return {"status": "disabled", "config": policy_settings.redacted}
    try:
        retriever, reranker = _runtime_policy_components()
        status = _redact_policy_rag_runtime_paths(retriever.readiness())
        status["reranker"] = reranker.readiness()
        status["config"] = policy_settings.redacted
        return status
    except Exception as exc:
        return {
            "status": "degraded",
            "config": policy_settings.redacted,
            "bm25": {"status": "unavailable", "fallbackEnabled": policy_settings.bm25_fallback_enabled},
            "dense": {"status": "degraded", "reason": "readiness_check_failed"},
            "retrievalMode": "unavailable",
            "fallbackAvailable": False,
            "reason": _safe_readiness_reason(exc),
        }


def _runtime_policy_components():
    try:
        from app.api.review import agentic_workflow

        return agentic_workflow.policy_retriever, agentic_workflow.policy_reranker
    except (AttributeError, ImportError):
        return PolicyEvidenceRetriever(), PolicyEvidenceReranker()


def _safe_readiness_reason(exc: Exception) -> str:
    value = str(exc)
    if "No such file" in value or "cannot find" in value.lower():
        return "policy_index_not_available"
    return "policy_rag_readiness_check_failed"


def _redact_policy_rag_runtime_paths(status: dict) -> dict:
    public_status = dict(status)
    dense = public_status.get("dense")
    if not isinstance(dense, dict):
        return public_status
    public_dense = dict(dense)
    provider_metrics = public_dense.get("providerMetrics")
    if isinstance(provider_metrics, dict):
        public_metrics = dict(provider_metrics)
        model_path = public_metrics.get("modelPath")
        public_metrics["modelPath"] = "configured" if model_path else "not_configured"
        public_dense["providerMetrics"] = public_metrics
    public_status["dense"] = public_dense
    return public_status
