from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.agent_rag.embedding_provider import DisabledEmbeddingProvider, HashEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.llm_decider import agent_rag_llm_status
from app.agent_rag.observability import gpu_gate, metrics_registry, model_residency_snapshot
from app.agent_rag.phase3a_retrieval import make_bge_m3_provider
from app.agent_rag.security import load_agent_rag_security_config
from app.agent_rag.target_mode import load_agent_rag_target_config


router = APIRouter(prefix="/internal/agent-rag", tags=["internal-agent-rag"])


@router.get("/live")
def live():
    return {"status": "live", "service": "agent-rag-runtime"}


@router.get("/ready")
def ready():
    health = dense_health()
    status = "ready" if health.get("status") == "ready" and health.get("indexCompatible") is not False else "degraded"
    return {
        "status": status,
        "runtime": health,
        "gpu": gpu_gate.snapshot().__dict__,
        "residency": model_residency_snapshot(),
        "degraded": status != "ready",
    }


@router.get("/metrics")
def metrics():
    return {
        "status": "ok",
        "metrics": metrics_registry.snapshot(),
        "gpu": gpu_gate.snapshot().__dict__,
        "residency": model_residency_snapshot(),
        "llm": agent_rag_llm_status(),
    }


@router.get("/metrics/openmetrics", response_class=PlainTextResponse)
def metrics_openmetrics():
    return metrics_registry.openmetrics()


@router.get("/security/health")
def security_health():
    config = load_agent_rag_security_config()
    return {
        "status": "ready",
        "piiRedactionEnabled": config.pii_redaction_enabled,
        "promptInjectionGuardEnabled": config.prompt_injection_guard_enabled,
        "promptInjectionAction": config.prompt_injection_action,
        "auditRetentionDays": config.audit_retention_days,
        "secureExportEnabled": config.secure_export_enabled,
        "rawPromptPersistence": False,
    }


@router.get("/dense/health")
def dense_health():
    target_config = load_agent_rag_target_config()
    requested = os.getenv("RAG_DENSE_PROVIDER", "hash")
    fallback = os.getenv("RAG_DENSE_FALLBACK_PROVIDER", "hash")
    index_root = os.getenv("RAG_INDEX_ROOT", "")
    if requested == "bge-m3":
        model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
        provider = make_bge_m3_provider(
            provider_impl=os.getenv("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls"),
            model_path=model_path if model_path else "__missing__",
            device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"),
            batch_size=int(os.getenv("RAG_BGE_M3_BATCH_SIZE", "8")),
            max_length=int(os.getenv("RAG_BGE_M3_MAX_LENGTH", "512")),
            normalize=os.getenv("RAG_BGE_M3_NORMALIZE", "true").lower() == "true",
            load_on_startup=False,
            use_fp16=os.getenv("RAG_BGE_M3_USE_FP16", "false").lower() == "true",
        )
        metadata = provider.metadata()
        status = provider.health()
    elif requested == "hash":
        metadata = HashEmbeddingProvider().metadata()
        status = {"status": "ready", "loaded": True, "reason": ""}
    else:
        provider = DisabledEmbeddingProvider("DENSE_PROVIDER_DISABLED")
        metadata = provider.metadata()
        status = provider.health()
    active_index = ""
    if index_root:
        try:
            active_index = FaissVectorIndex(Path(index_root)).active_version() or ""
        except Exception:
            active_index = ""
    requested_impl = os.getenv("RAG_BGE_M3_PROVIDER_IMPL", "") if requested == "bge-m3" else requested
    effective_impl = metadata.get("providerImpl", metadata["providerType"])
    fallback_used = effective_impl != requested_impl and requested != "disabled"
    index_compatible = False
    index_provider_impl = ""
    index_fingerprint = ""
    if index_root and active_index:
        try:
            manifest, _ = FaissVectorIndex(Path(index_root))._read_version(active_index)
            index_provider_impl = manifest.providerImpl
            index_fingerprint = manifest.effectiveEmbeddingFingerprint
            index_compatible = index_fingerprint == metadata.get("effectiveEmbeddingFingerprint") and index_provider_impl == effective_impl
        except Exception:
            index_compatible = False
    gpu_snapshot = gpu_gate.snapshot().__dict__
    residency_snapshot = model_residency_snapshot()
    return {
        "status": "ready" if metadata["providerType"] in {"bge-m3", "bge-m3-legacy-cls", "hash"} else "degraded",
        "targetMode": target_config.target_mode,
        "defaultRetrievalMode": target_config.default_retrieval_mode,
        "requestedProvider": requested,
        "requestedProviderImpl": requested_impl,
        "effectiveProvider": metadata["providerType"],
        "effectiveProviderImpl": effective_impl,
        "providerConformance": metadata.get("providerConformance", ""),
        "library": metadata.get("library", ""),
        "libraryVersion": metadata.get("libraryVersion", ""),
        "modelLoaded": bool(metadata["loaded"]),
        "modelFingerprint": metadata["modelFingerprint"],
        "assetFingerprint": metadata.get("assetFingerprint", ""),
        "providerFingerprint": metadata.get("providerFingerprint", ""),
        "effectiveEmbeddingFingerprint": metadata.get("effectiveEmbeddingFingerprint", ""),
        "device": metadata["device"],
        "embeddingDimension": metadata["dimension"],
        "normalize": metadata.get("normalize", False),
        "activeIndexVersion": active_index,
        "indexVersion": active_index,
        "indexProviderImpl": index_provider_impl,
        "indexEffectiveEmbeddingFingerprint": index_fingerprint,
        "indexCompatible": index_compatible,
        "indexLoaded": bool(active_index),
        "fallbackUsed": fallback_used,
        "fallbackReason": None if not fallback_used else status.get("reason", ""),
        "fallbackProvider": fallback,
        "reason": status.get("reason", ""),
        "gpu": gpu_snapshot,
        "residency": residency_snapshot,
        "llm": agent_rag_llm_status(),
    }
