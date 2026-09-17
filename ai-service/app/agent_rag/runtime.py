from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent_rag.contracts import (
    ANALYZER_VERSION,
    PUBLIC_TENANT,
    SCHEMA_VERSION,
    AgentRagEvidenceBundle,
    AgentRagRequest,
    AgentRagResult,
    AgentTraceStep,
    Analysis,
    Citation,
    Decision,
    RetrievalTrace,
    RuntimeTrace,
)
from app.agent_rag.eligibility import ELIGIBILITY_VERSION, filter_eligible_candidates, utc_now
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.llm_decider import AgentRagLlmConfig, AgentRagLlmDecider, AgentRagLlmUnavailable, load_agent_rag_llm_config
from app.agent_rag.observability import log_event, metrics_registry
from app.agent_rag.knowledge import KnowledgeChunk
from app.agent_rag.phase3a_retrieval import DenseRuntimeTrace, GovernedHybridRuntime, make_embedding_provider
from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.reranker import GovernedReranker, RerankResult, load_reranker_config
from app.agent_rag.security import AgentRagSecurityDecision, AgentRagSecurityGovernor
from app.agent_rag.target_mode import AgentRagTargetConfig, load_agent_rag_target_config
from app.rag.document_contract import stable_hash
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.tenant_acl import TenantPrincipal


HIGH_RISK_TERMS = {
    "refund",
    "return",
    "broken",
    "leak",
    "unsafe",
    "fire",
    "smoke",
    "fake",
    "after-sales",
    "退货",
    "退款",
    "破损",
    "漏液",
    "起火",
    "虚假",
    "售后",
}
MEDIUM_RISK_TERMS = {"bad", "poor", "delay", "slow", "差", "失望", "延迟", "物流"}


class AgentRagRuntime:
    def __init__(
        self,
        *,
        chunks: list[dict[str, Any]],
        index_version: str = "phase1-fixture-index-v1",
        embedding_model: str = "hash-bm25-phase1",
        embedding_dimension: int = 0,
        model_available: bool = True,
        rule_fallback_enabled: bool = True,
        target_config: AgentRagTargetConfig | None = None,
        llm_config: AgentRagLlmConfig | None = None,
        llm_decider: AgentRagLlmDecider | None = None,
        dense_runtime: GovernedHybridRuntime | None = None,
    ):
        self.chunks = [dict(row) for row in chunks]
        self.index_version = index_version
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension
        self.model_available = model_available
        self.rule_fallback_enabled = rule_fallback_enabled
        self.target_config = target_config or load_agent_rag_target_config()
        self.llm_config = llm_config or load_agent_rag_llm_config()
        self.llm_decider = llm_decider or AgentRagLlmDecider(self.llm_config)
        self.dense_runtime = dense_runtime
        self.reranker_config = load_reranker_config()
        self._last_rerank_result = RerankResult(
            candidates=[],
            scores=[],
            requestedType=self.reranker_config.requested_type,
            effectiveType="not-used",
        )
        self._security_governor = AgentRagSecurityGovernor()
        self._last_security_decision = AgentRagSecurityDecision(
            originalHash="",
            sanitizedHash="",
            sanitizedQuery="",
        )
        self._last_llm_trace: dict[str, Any] = self._empty_llm_trace()
        self._last_dense_trace = self._empty_dense_trace()
        self._last_eligibility_trace: dict[str, Any] = {}
        self._idempotency: dict[str, AgentRagResult] = {}
        self._risk_tasks: set[str] = set()

    def analyze(self, request: AgentRagRequest | dict[str, Any]) -> tuple[AgentRagResult, AgentRagEvidenceBundle]:
        req = request if isinstance(request, AgentRagRequest) else AgentRagRequest.model_validate(request)
        started = time.perf_counter()
        started_at = _now()
        self._last_llm_trace = self._empty_llm_trace()
        self._last_eligibility_trace = {}
        metrics_registry.increment("requests_total")
        log_event("agent_rag_analyze_started", runtimeMode=req.runtimeMode, retrievalEnabled=req.retrieval.enabled)
        trace: list[AgentTraceStep] = []
        errors: list[str] = []
        security = self._security_governor.inspect(req.query, req.context)
        self._last_security_decision = security
        if security.sanitizedQuery != req.query or security.sanitizedContext != req.context:
            req = req.model_copy(update={"query": security.sanitizedQuery, "context": security.sanitizedContext})
        key = self._idempotency_key(req)
        if key in self._idempotency:
            cached = self._idempotency[key]
            bundle = self._bundle(cached, started_at, started_at, errors)
            metrics_registry.increment("idempotency_hit_total")
            log_event("agent_rag_analyze_idempotent_replay", status="success")
            return cached, bundle

        normalized_query = self._normalize_query(req.query)
        self._step(trace, "validate_request", req.model_dump(mode="json"), {"schemaVersion": req.schemaVersion})
        self._step(
            trace,
            "security_governance",
            {"originalHash": security.originalHash},
            {
                "governanceStatus": security.governanceStatus,
                "piiRedactionCount": security.piiRedactionCount,
                "promptInjectionDetected": security.promptInjectionDetected,
            },
        )
        if security.promptInjectionDetected:
            result = self._security_blocked_result(req, trace, started_at, started)
            self._idempotency[key] = result
            metrics_registry.increment("success_total")
            metrics_registry.increment("human_review_total")
            return result, self._bundle(result, started_at, result.audit.finishedAt, ["PROMPT_INJECTION_DETECTED"])
        self._step(trace, "classify_intent", {"query": stable_hash(req.query)}, {"intent": self._intent(normalized_query)})
        citations = self._retrieve(req, normalized_query, trace)
        decision, analysis, runtime = self._decide(req, normalized_query, citations, trace, errors)
        if decision.action == "create-risk-task":
            risk_key = self._risk_task_key(req)
            if risk_key in self._risk_tasks:
                decision = Decision(riskLevel=decision.riskLevel, riskTypes=decision.riskTypes, action="manual-review")
            else:
                self._risk_tasks.add(risk_key)
        self._step(trace, "persist_evidence", {"request": req.requestId}, {"citationCount": len(citations), "errors": errors})

        finished_at = _now()
        duration_ms = round((time.perf_counter() - started) * 1000)
        evidence_id = stable_hash({"requestId": req.requestId, "tenantId": req.tenantId, "subjectId": req.subjectId, "trace": [s.model_dump() for s in trace]})[:24]
        result = AgentRagResult(
            requestId=req.requestId,
            tenantId=TenantPrincipal.from_tenant_id(req.tenantId).tenant_id,
            subjectId=req.subjectId,
            decision=decision,
            analysis=analysis,
            retrieval=RetrievalTrace(
                used=req.retrieval.enabled,
                query=normalized_query,
                originalQuery=req.query,
                normalizedQuery=normalized_query,
                topK=req.retrieval.topK,
                returned=len(citations),
                rerankerType=self._last_rerank_result.effectiveType,
                requestedRerankerType=self._last_rerank_result.requestedType,
                effectiveRerankerType=self._last_rerank_result.effectiveType,
                rerankerModelId=self._last_rerank_result.modelId,
                rerankerRevision=self._last_rerank_result.modelRevision,
                rerankerModelName=self._last_rerank_result.modelName,
                rerankerFingerprint=self._last_rerank_result.modelFingerprint,
                rerankerInputCount=self._last_rerank_result.inputCount,
                rerankerOutputCount=self._last_rerank_result.outputCount,
                rerankerDurationMs=self._last_rerank_result.durationMs,
                rerankerFallbackUsed=self._last_rerank_result.fallbackUsed,
                rerankerFallbackReason=self._last_rerank_result.fallbackReason,
                indexVersion=self.index_version,
                embeddingModel=self.embedding_model,
                embeddingDimension=self._last_dense_trace.embeddingDimension or self.embedding_dimension,
                candidateCount=len(citations),
                citations=citations,
                retrievalEmpty=req.retrieval.enabled and not citations,
                denseProvider=self._last_dense_trace.denseProvider,
                requestedRetrievalMode=self._last_dense_trace.requestedRetrievalMode,
                effectiveRetrievalMode=self._last_dense_trace.effectiveRetrievalMode,
                modelFingerprint=self._last_dense_trace.modelFingerprint,
                faissIndexType=self._last_dense_trace.faissIndexType,
                faissMetric=self._last_dense_trace.faissMetric,
                embeddingDurationMs=int(round(self._last_dense_trace.embeddingDurationMs)),
                faissSearchDurationMs=int(round(self._last_dense_trace.faissSearchDurationMs)),
                denseFallbackUsed=self._last_dense_trace.denseFallbackUsed,
                denseFallbackReason=self._last_dense_trace.denseFallbackReason,
                targetMode=self.target_config.target_mode,
            ),
            runtime=runtime,
            audit={
                "startedAt": started_at,
                "finishedAt": finished_at,
                "durationMs": duration_ms,
                "agentPath": trace,
                "evidenceId": evidence_id,
            },
        )
        AgentRagResult.model_validate(result.model_dump(mode="json"))
        self._idempotency[key] = result
        metrics_registry.increment("success_total")
        if runtime.fallbackUsed:
            metrics_registry.increment("fallback_total")
        if decision.action == "create-risk-task":
            metrics_registry.increment("risk_task_total")
        metrics_registry.observe("request_latency_ms", duration_ms)
        log_event(
            "agent_rag_analyze_finished",
            status="success",
            durationMs=duration_ms,
            riskLevel=decision.riskLevel,
            action=decision.action,
            fallbackUsed=runtime.fallbackUsed,
        )
        return result, self._bundle(result, started_at, finished_at, errors)

    def _retrieve(self, req: AgentRagRequest, normalized_query: str, trace: list[AgentTraceStep]) -> list[Citation]:
        self._last_dense_trace = self._empty_dense_trace()
        if not req.retrieval.enabled:
            self._last_rerank_result = RerankResult(
                candidates=[],
                scores=[],
                requestedType=self.reranker_config.requested_type,
                effectiveType="not-used",
            )
            self._step(trace, "retrieve_evidence", {"enabled": False}, {"returned": 0}, "SKIPPED")
            return []
        if self.target_config.default_retrieval_mode in {"real-dense", "hybrid-real", "fixture-hash", "sparse-only"}:
            return self._retrieve_with_phase3a(req, normalized_query, trace)
        principal = TenantPrincipal.from_tenant_id(req.tenantId)
        allowed_tenants = {principal.tenant_id}
        if req.retrieval.publicTenantEnabled:
            allowed_tenants.add(PUBLIC_TENANT)
        allowed = [
            row for row in self.chunks
            if str(row.get("tenant_id") or "") in allowed_tenants and row.get("active", True) and not row.get("deleted", False)
        ]
        hits = HybridRetriever(allowed).search(normalized_query, sparse_top_k=req.retrieval.topK * 3, dense_top_k=0, fused_top_k=req.retrieval.topK)
        filtered = [hit for hit in hits if hit.fused_score >= req.retrieval.minScore]
        deduped = []
        seen: set[str] = set()
        by_chunk = {str(row["chunk_id"]): row for row in allowed}
        for hit in filtered:
            row = by_chunk[hit.chunk_id]
            dedupe_key = str(row.get("content_hash") or f"{hit.document_id}:{hit.chunk_id}")
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append((hit, row))
        ranked = sorted(deduped, key=lambda item: (item[1].get("trust_level") == "internal_verified", item[0].fused_score), reverse=True)
        candidates = [
            RetrievalCandidate(
                retrieverType="bm25-first-semantic-hybrid",
                tenantId=str(row.get("tenant_id")),
                documentId=str(row.get("document_id")),
                chunkId=str(row.get("chunk_id")),
                sparseScore=float(hit.fused_score),
                sparseRank=index,
                rawRank=index,
                fusionScore=float(hit.fused_score),
                fusionRank=index,
                row=row,
            )
            for index, (hit, row) in enumerate(ranked, start=1)
        ]
        rerank_result = GovernedReranker(self.reranker_config).rerank(
            normalized_query,
            candidates,
            top_k=req.retrieval.rerankTopK,
            tenant_id=principal.tenant_id,
            request_id=req.requestId,
        )
        self._last_rerank_result = rerank_result
        citations = [
            Citation(
                documentId=str(item.row.get("document_id")),
                chunkId=str(item.row.get("chunk_id")),
                tenantId=str(item.row.get("tenant_id")),
                sourceType=str(item.row.get("source_type") or "policy"),
                title=str(item.row.get("title") or item.row.get("document_id")),
                score=float(rerank_result.scores[rank - 1]) if rank <= len(rerank_result.scores) else float(item.fusionScore),
                rank=rank,
                contentHash=str(item.row.get("content_hash") or stable_hash(str(item.row.get("content") or ""))),
                snippet=_snippet(str(item.row.get("content") or "")),
            )
            for rank, item in enumerate(rerank_result.candidates, start=1)
        ]
        self._step(trace, "retrieve_evidence", {"tenantHash": principal.tenant_hash, "topK": req.retrieval.topK}, {"returned": len(citations)})
        self._step(
            trace,
            "rerank_evidence",
            {"candidateCount": len(filtered), "requestedRerankerType": rerank_result.requestedType},
            {
                "returned": len(citations),
                "effectiveRerankerType": rerank_result.effectiveType,
                "fallbackUsed": rerank_result.fallbackUsed,
                "fallbackReason": rerank_result.fallbackReason,
            },
        )
        return citations

    def _retrieve_with_phase3a(self, req: AgentRagRequest, normalized_query: str, trace: list[AgentTraceStep]) -> list[Citation]:
        principal = TenantPrincipal.from_tenant_id(req.tenantId)
        dense_runtime = self.dense_runtime or self._make_dense_runtime()
        evaluation_time = str(req.context.get("requestEvaluationTimeUtc") or req.context.get("evaluationTimeUtc") or utc_now())
        candidates, dense_trace = dense_runtime.search(
            normalized_query,
            tenant_id=principal.tenant_id,
            mode=self.target_config.default_retrieval_mode,  # type: ignore[arg-type]
            sparse_top_k=req.retrieval.topK * 3,
            dense_top_k=req.retrieval.topK * 3,
            fusion_top_k=req.retrieval.topK,
            rerank_top_k=None,
            evaluation_time_utc=evaluation_time,
        )
        self._last_dense_trace = dense_trace
        pre_count = len(candidates)
        candidates, eligibility = filter_eligible_candidates(candidates, tenant_id=principal.tenant_id, evaluation_time_utc=evaluation_time)
        self._last_eligibility_trace = _eligibility_trace(evaluation_time, pre_count, len(candidates), eligibility)
        rerank_result = GovernedReranker(self.reranker_config).rerank(
            normalized_query,
            candidates,
            top_k=req.retrieval.rerankTopK,
            tenant_id=principal.tenant_id,
            request_id=req.requestId,
            evaluation_time_utc=evaluation_time,
        )
        self._last_rerank_result = rerank_result
        citations = [
            Citation(
                documentId=str(item.row.get("document_id")),
                chunkId=str(item.row.get("chunk_id")),
                tenantId=str(item.row.get("tenant_id")),
                sourceType=str(item.row.get("source_type") or "policy"),
                title=str(item.row.get("title") or item.row.get("document_id")),
                score=float(rerank_result.scores[rank - 1]) if rank <= len(rerank_result.scores) else float(item.fusionScore),
                rank=rank,
                contentHash=str(item.row.get("content_hash") or stable_hash(str(item.row.get("content") or ""))),
                snippet=_snippet(str(item.row.get("content") or item.row.get("text") or "")),
            )
            for rank, item in enumerate(rerank_result.candidates, start=1)
        ]
        self._step(
            trace,
            "retrieve_evidence",
            {"tenantHash": principal.tenant_hash, "mode": dense_trace.requestedRetrievalMode},
            {"returned": len(citations), "effectiveRetrievalMode": dense_trace.effectiveRetrievalMode, "eligibleCandidateCount": len(candidates)},
        )
        self._step(
            trace,
            "rerank_evidence",
            {"candidateCount": len(candidates), "requestedRerankerType": rerank_result.requestedType},
            {
                "returned": len(citations),
                "effectiveRerankerType": rerank_result.effectiveType,
                "fallbackUsed": rerank_result.fallbackUsed,
                "fallbackReason": rerank_result.fallbackReason,
            },
        )
        return citations

    def _make_dense_runtime(self) -> GovernedHybridRuntime:
        provider = make_embedding_provider(
            self.target_config.dense_provider,
            model_path=os.getenv("RAG_BGE_M3_MODEL_PATH", "__missing__"),
            device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"),
            batch_size=int(os.getenv("RAG_BGE_M3_BATCH_SIZE", "8")),
            max_length=int(os.getenv("RAG_BGE_M3_MAX_LENGTH", "512")),
            normalize=os.getenv("RAG_BGE_M3_NORMALIZE", "true").lower() == "true",
            load_on_startup=False,
        )
        index_root = os.getenv("RAG_INDEX_ROOT", "")
        faiss_index = FaissVectorIndex(Path(index_root)) if index_root else None
        return GovernedHybridRuntime(
            chunks=_knowledge_chunks_from_rows(self.chunks),
            provider=provider,
            faiss_index=faiss_index,
            fallback_provider=os.getenv("RAG_DENSE_FALLBACK_PROVIDER", "hash"),
            real_dense_required=self.target_config.real_dense_required,
        )

    def _decide(
        self,
        req: AgentRagRequest,
        normalized_query: str,
        citations: list[Citation],
        trace: list[AgentTraceStep],
        errors: list[str],
    ) -> tuple[Decision, Analysis, RuntimeTrace]:
        invalid_model_output = bool(req.context.get("forceInvalidModelOutput"))
        force_model_unavailable = bool(req.context.get("forceModelUnavailable"))
        if req.runtimeMode == "explicit-failure":
            self._step(trace, "analyze_with_model", {"runtimeMode": req.runtimeMode}, {"status": "explicit-failure"}, "FAILED", "EXPLICIT_FAILURE")
            return (
                Decision(riskLevel="high", riskTypes=["runtime_failure"], action="explicit-failure"),
                Analysis(summary="Analysis failed explicitly; no model result was trusted.", confidence=0.0),
                RuntimeTrace(
                    engineType="explicit-failure",
                    fallbackUsed=False,
                    fallbackReason="EXPLICIT_FAILURE",
                    modelOutputValid=False,
                    validationErrors=["EXPLICIT_FAILURE"],
                    targetMode=self.target_config.target_mode,
                    requestedLlmProvider=self.llm_config.provider,
                    effectiveLlmProvider="deterministic",
                    requestedAnalysisProvider=self.llm_config.provider,
                    effectiveAnalysisProvider="deterministic",
                    llmFallbackUsed=True,
                    llmGrounded=False,
                    llmFallbackReason="EXPLICIT_FAILURE",
                    **self._security_runtime_fields(),
                ),
            )
        model_available = self.model_available and not force_model_unavailable
        if not model_available:
            errors.append("MODEL_UNAVAILABLE")
            self._step(trace, "analyze_with_model", {"modelAvailable": False}, {"fallback": True}, "FAILED", "MODEL_UNAVAILABLE")
            return self._rule_fallback(normalized_query, citations, "MODEL_UNAVAILABLE", trace)
        if invalid_model_output:
            errors.append("MODEL_OUTPUT_SCHEMA_INVALID")
            self._step(trace, "analyze_with_model", {"modelAvailable": True}, {"modelOutputValid": False}, "FAILED", "MODEL_OUTPUT_SCHEMA_INVALID")
            return self._rule_fallback(normalized_query, citations, "MODEL_OUTPUT_SCHEMA_INVALID", trace, repair_attempts=1, validation_errors=["riskLevel enum invalid"])
        if self.llm_config.enabled:
            self._last_llm_trace = self._empty_llm_trace()
            try:
                llm = self.llm_decider.decide(normalized_query, citations)
                self._last_llm_trace = {
                    "requested": self.llm_config.provider,
                    "effective": llm.provider,
                    "modelId": llm.model_id,
                    "revision": llm.model_revision,
                    "fingerprint": llm.model_fingerprint,
                    "promptVersion": llm.prompt_version,
                    "promptFingerprint": llm.prompt_fingerprint,
                    "inputTokens": llm.token_usage_input or 0,
                    "outputTokens": llm.token_usage_output or 0,
                    "durationMs": llm.latency_ms,
                    "structuredOutputValid": llm.structured_output_valid,
                    "groundingStatus": llm.grounding_status,
                    "abstained": llm.abstained,
                    "uncertaintyReason": llm.uncertainty_reason,
                    "requiresHumanReview": llm.requires_human_review,
                    "fallbackUsed": False,
                    "grounded": bool(citations),
                    "fallbackReason": "",
                    "outputHash": llm.raw_output_hash,
                }
                self._step(
                    trace,
                    "analyze_with_grounded_local_llm",
                    {"provider": self.llm_config.provider, "citationCount": len(citations)},
                    {"modelOutputValid": True, "riskLevel": llm.decision.riskLevel, "outputHash": llm.raw_output_hash},
                )
                self._step(trace, "validate_with_rules", {"riskLevel": llm.decision.riskLevel}, {"action": llm.decision.action})
                return llm.decision, llm.analysis, RuntimeTrace(
                    engineType="grounded-local-llm-rag",
                    modelName=llm.model_name,
                    fallbackUsed=False,
                    modelOutputValid=True,
                    targetMode=self.target_config.target_mode,
                    requestedLlmProvider=self.llm_config.provider,
                    effectiveLlmProvider=llm.provider,
                    requestedAnalysisProvider=self.llm_config.provider,
                    effectiveAnalysisProvider=llm.provider,
                    llmModelId=llm.model_id,
                    llmRevision=llm.model_revision,
                    llmFingerprint=llm.model_fingerprint,
                    promptVersion=llm.prompt_version,
                    promptFingerprint=llm.prompt_fingerprint,
                    llmInputTokens=llm.token_usage_input or 0,
                    llmOutputTokens=llm.token_usage_output or 0,
                    llmDurationMs=llm.latency_ms,
                    structuredOutputValid=llm.structured_output_valid,
                    groundingStatus=llm.grounding_status,
                    abstained=llm.abstained,
                    uncertaintyReason=llm.uncertainty_reason,
                    requiresHumanReview=llm.requires_human_review,
                    llmFallbackUsed=False,
                    llmGrounded=bool(citations),
                    llmFallbackReason="",
                    **self._security_runtime_fields(),
                )
            except AgentRagLlmUnavailable as exc:
                errors.append(exc.reason)
                self._last_llm_trace = {
                    "requested": self.llm_config.provider,
                    "effective": "deterministic",
                    "fallbackUsed": True,
                    "grounded": bool(citations),
                    "fallbackReason": exc.reason,
                    "outputHash": "",
                }
                self._step(
                    trace,
                    "analyze_with_grounded_local_llm",
                    {"provider": self.llm_config.provider, "citationCount": len(citations)},
                    {"fallback": True, "reason": exc.reason},
                    "FAILED",
                    exc.reason,
                )
                return self._rule_fallback(normalized_query, citations, exc.reason, trace)
        decision, analysis = self._rule_decision(normalized_query, citations)
        self._step(trace, "analyze_with_model", {"modelAvailable": True}, {"modelOutputValid": True, "riskLevel": decision.riskLevel})
        self._step(trace, "validate_with_rules", {"riskLevel": decision.riskLevel}, {"action": decision.action})
        return decision, analysis, RuntimeTrace(
            engineType="model-rag" if citations else "model-only",
            modelName="phase1-deterministic-model",
            fallbackUsed=False,
            modelOutputValid=True,
            targetMode=self.target_config.target_mode,
            requestedLlmProvider=self.llm_config.provider,
            effectiveLlmProvider="deterministic",
            requestedAnalysisProvider=self.llm_config.provider,
            effectiveAnalysisProvider="deterministic",
            llmFallbackUsed=False,
            llmGrounded=False,
            llmFallbackReason="",
            **self._security_runtime_fields(),
        )

    def _rule_fallback(
        self,
        query: str,
        citations: list[Citation],
        reason: str,
        trace: list[AgentTraceStep],
        repair_attempts: int = 0,
        validation_errors: list[str] | None = None,
    ) -> tuple[Decision, Analysis, RuntimeTrace]:
        if not self.rule_fallback_enabled:
            return (
                Decision(riskLevel="high", riskTypes=["fallback_disabled"], action="explicit-failure"),
                Analysis(summary="Rule fallback disabled; safe explicit failure returned.", confidence=0.0),
                RuntimeTrace(
                    engineType="explicit-failure",
                    fallbackUsed=False,
                    fallbackReason="RULE_FALLBACK_DISABLED",
                    modelOutputValid=False,
                    targetMode=self.target_config.target_mode,
                    requestedLlmProvider=self.llm_config.provider,
                    effectiveLlmProvider="deterministic",
                    requestedAnalysisProvider=self.llm_config.provider,
                    effectiveAnalysisProvider="deterministic",
                    llmFallbackUsed=True,
                    llmGrounded=False,
                    llmFallbackReason="RULE_FALLBACK_DISABLED",
                    **self._security_runtime_fields(),
                ),
            )
        decision, analysis = self._rule_decision(query, citations)
        self._step(trace, "validate_with_rules", {"fallbackReason": reason}, {"riskLevel": decision.riskLevel, "action": decision.action})
        return decision, analysis, RuntimeTrace(
            engineType="rule-fallback",
            modelName="",
            fallbackUsed=True,
            fallbackReason=reason,
            modelOutputValid=False,
            repairAttemptCount=repair_attempts,
            validationErrors=validation_errors or [],
            targetMode=self.target_config.target_mode,
            requestedLlmProvider=self.llm_config.provider,
            effectiveLlmProvider="deterministic",
            requestedAnalysisProvider=self.llm_config.provider,
            effectiveAnalysisProvider="deterministic",
            llmFallbackUsed=True,
            llmGrounded=False,
            llmFallbackReason=reason,
            **self._security_runtime_fields(),
        )

    def _rule_decision(self, query: str, citations: list[Citation]) -> tuple[Decision, Analysis]:
        lowered = query.lower()
        if any(term in lowered for term in HIGH_RISK_TERMS):
            risk_types = ["after_sales_risk" if any(term in lowered for term in ["refund", "return", "退货", "退款", "售后"]) else "safety_or_fraud_risk"]
            return Decision(riskLevel="high", riskTypes=risk_types, action="create-risk-task"), Analysis(summary="High-risk review signal matched governed rules.", confidence=0.82 if citations else 0.70)
        if any(term in lowered for term in MEDIUM_RISK_TERMS):
            return Decision(riskLevel="medium", riskTypes=["negative_review"], action="manual-review"), Analysis(summary="Medium-risk negative review signal matched governed rules.", confidence=0.72)
        return Decision(riskLevel="low", riskTypes=["normal_review"], action="none"), Analysis(summary="No high-risk signal was detected by Phase 1 rules.", confidence=0.78)

    def _security_blocked_result(
        self,
        req: AgentRagRequest,
        trace: list[AgentTraceStep],
        started_at: str,
        started: float,
    ) -> AgentRagResult:
        self._last_rerank_result = RerankResult(
            candidates=[],
            scores=[],
            requestedType=self.reranker_config.requested_type,
            effectiveType="not-used",
        )
        self._step(trace, "retrieve_evidence", {"enabled": False, "reason": "PROMPT_INJECTION_DETECTED"}, {"returned": 0}, "SKIPPED")
        self._step(trace, "analyze_with_model", {"modelSkipped": True}, {"route": "manual-review"}, "SKIPPED", "PROMPT_INJECTION_DETECTED")
        finished_at = _now()
        duration_ms = round((time.perf_counter() - started) * 1000)
        evidence_id = stable_hash({"requestId": req.requestId, "tenantId": req.tenantId, "subjectId": req.subjectId, "security": self._last_security_decision.sanitizedHash})[:24]
        self._last_llm_trace = {
            **self._empty_llm_trace(),
            "requested": self.llm_config.provider,
            "effective": "deterministic",
            "fallbackUsed": True,
            "fallbackReason": "PROMPT_INJECTION_SUPPRESSED",
        }
        return AgentRagResult(
            requestId=req.requestId,
            tenantId=TenantPrincipal.from_tenant_id(req.tenantId).tenant_id,
            subjectId=req.subjectId,
            decision=Decision(riskLevel="high", riskTypes=["prompt_injection"], action="manual-review"),
            analysis=Analysis(summary="Prompt injection signal detected; request was routed to human review without retrieval or model execution.", confidence=0.9),
            retrieval=RetrievalTrace(
                used=False,
                query=req.query,
                originalQuery=req.query,
                normalizedQuery=req.query,
                topK=req.retrieval.topK,
                returned=0,
                rerankerType="not-used",
                requestedRerankerType=self.reranker_config.requested_type,
                effectiveRerankerType="not-used",
                indexVersion=self.index_version,
                embeddingModel=self.embedding_model,
                embeddingDimension=self.embedding_dimension,
                candidateCount=0,
                citations=[],
                retrievalEmpty=True,
                targetMode=self.target_config.target_mode,
            ),
            runtime=RuntimeTrace(
                engineType="security-governed",
                modelName="",
                fallbackUsed=False,
                fallbackReason="",
                modelOutputValid=False,
                validationErrors=["PROMPT_INJECTION_DETECTED"],
                targetMode=self.target_config.target_mode,
                requestedLlmProvider=self.llm_config.provider,
                effectiveLlmProvider="deterministic",
                requestedAnalysisProvider=self.llm_config.provider,
                effectiveAnalysisProvider="deterministic",
                llmFallbackUsed=True,
                llmGrounded=False,
                llmFallbackReason="PROMPT_INJECTION_SUPPRESSED",
                **self._security_runtime_fields(),
            ),
            audit={
                "startedAt": started_at,
                "finishedAt": finished_at,
                "durationMs": duration_ms,
                "agentPath": trace,
                "evidenceId": evidence_id,
            },
        )

    def _security_runtime_fields(self) -> dict[str, Any]:
        security = self._last_security_decision
        return {
            "securityGovernanceStatus": security.governanceStatus,
            "piiRedactionCount": security.piiRedactionCount,
            "promptInjectionDetected": security.promptInjectionDetected,
            "promptInjectionAction": security.promptInjectionAction,
        }

    def _normalize_query(self, query: str) -> str:
        normalized = re.sub(r"\s+", " ", query.strip())
        return normalized[:1024]

    def _intent(self, query: str) -> str:
        lowered = query.lower()
        if any(term in lowered for term in HIGH_RISK_TERMS):
            return "risk_review"
        return "normal_review"

    def _idempotency_key(self, req: AgentRagRequest) -> str:
        return stable_hash("|".join([req.tenantId, req.subjectType, req.subjectId, req.requestId, ANALYZER_VERSION, self.index_version]))

    def _risk_task_key(self, req: AgentRagRequest) -> str:
        return stable_hash("|".join([req.tenantId, req.subjectType, req.subjectId, ANALYZER_VERSION, self.index_version]))

    def _step(self, trace: list[AgentTraceStep], node: str, input_value: Any, output_value: Any, status: str = "PASS", error_code: str = "") -> None:
        started = _now()
        finished = _now()
        trace.append(
            AgentTraceStep(
                nodeName=node,
                startedAt=started,
                finishedAt=finished,
                status=status,
                inputHash=stable_hash(_safe_json(input_value))[:24],
                outputHash=stable_hash(_safe_json(output_value))[:24],
                errorCode=error_code,
            )
        )

    def _empty_llm_trace(self) -> dict[str, Any]:
        return {
            "requested": self.llm_config.provider,
            "effective": "deterministic",
            "modelId": "",
            "revision": "",
            "fingerprint": "",
            "promptVersion": "",
            "promptFingerprint": "",
            "inputTokens": 0,
            "outputTokens": 0,
            "durationMs": 0,
            "structuredOutputValid": False,
            "groundingStatus": "",
            "abstained": False,
            "uncertaintyReason": "",
            "requiresHumanReview": False,
            "fallbackUsed": False,
            "grounded": False,
            "fallbackReason": "",
            "outputHash": "",
        }

    def _empty_dense_trace(self) -> DenseRuntimeTrace:
        return DenseRuntimeTrace(
            requestedRetrievalMode=self.target_config.default_retrieval_mode,
            effectiveRetrievalMode="bm25-first-semantic-hybrid",
            denseProvider="disabled",
            denseFallbackUsed=False,
            denseFallbackReason="",
        )

    def _bundle(self, result: AgentRagResult, started_at: str, finished_at: str, errors: list[str]) -> AgentRagEvidenceBundle:
        return AgentRagEvidenceBundle(
            evidenceId=result.audit.evidenceId,
            requestId=result.requestId,
            tenantId=result.tenantId,
            subjectId=result.subjectId,
            sourceCommit=_source_commit(),
            runtimeMode="rule-fallback" if result.runtime.fallbackUsed else "local-model",
            schemaVersion=SCHEMA_VERSION,
            analyzerVersion=ANALYZER_VERSION,
            indexVersion=result.retrieval.indexVersion,
            retrievalEvidence=result.retrieval.citations,
            agentTrace=result.audit.agentPath,
            decision=result.decision.model_dump(mode="json"),
            timing={"startedAt": started_at, "finishedAt": finished_at, "durationMs": result.audit.durationMs},
            errors=errors,
            targetMode=self.target_config.target_mode,
            requestedRerankerType=result.retrieval.requestedRerankerType,
            effectiveRerankerType=result.retrieval.effectiveRerankerType,
            rerankerModelName=result.retrieval.rerankerModelName,
            rerankerModelId=result.retrieval.rerankerModelId,
            rerankerRevision=result.retrieval.rerankerRevision,
            rerankerFingerprint=result.retrieval.rerankerFingerprint,
            rerankerInputCount=result.retrieval.rerankerInputCount,
            rerankerOutputCount=result.retrieval.rerankerOutputCount,
            rerankerDurationMs=result.retrieval.rerankerDurationMs,
            rerankerFallbackUsed=result.retrieval.rerankerFallbackUsed,
            rerankerFallbackReason=result.retrieval.rerankerFallbackReason,
            denseProvider=result.retrieval.denseProvider,
            requestedRetrievalMode=result.retrieval.requestedRetrievalMode,
            effectiveRetrievalMode=result.retrieval.effectiveRetrievalMode,
            modelFingerprint=result.retrieval.modelFingerprint,
            embeddingDimension=result.retrieval.embeddingDimension,
            faissIndexType=result.retrieval.faissIndexType,
            faissMetric=result.retrieval.faissMetric,
            embeddingDurationMs=result.retrieval.embeddingDurationMs,
            faissSearchDurationMs=result.retrieval.faissSearchDurationMs,
            denseFallbackUsed=result.retrieval.denseFallbackUsed,
            denseFallbackReason=result.retrieval.denseFallbackReason,
            securityGovernanceStatus=result.runtime.securityGovernanceStatus,
            piiRedactionCount=result.runtime.piiRedactionCount,
            promptInjectionDetected=result.runtime.promptInjectionDetected,
            promptInjectionAction=result.runtime.promptInjectionAction,
            inputContentHash=self._last_security_decision.originalHash,
            sanitizedContentHash=self._last_security_decision.sanitizedHash,
            requestedLlmProvider=str(self._last_llm_trace.get("requested", self.llm_config.provider)),
            effectiveLlmProvider=str(self._last_llm_trace.get("effective", "deterministic")),
            requestedAnalysisProvider=str(self._last_llm_trace.get("requested", self.llm_config.provider)),
            effectiveAnalysisProvider=str(self._last_llm_trace.get("effective", "deterministic")),
            llmModelId=str(self._last_llm_trace.get("modelId") or ""),
            llmRevision=str(self._last_llm_trace.get("revision") or ""),
            llmFingerprint=str(self._last_llm_trace.get("fingerprint") or ""),
            promptVersion=str(self._last_llm_trace.get("promptVersion") or ""),
            promptFingerprint=str(self._last_llm_trace.get("promptFingerprint") or ""),
            llmInputTokens=int(self._last_llm_trace.get("inputTokens") or 0),
            llmOutputTokens=int(self._last_llm_trace.get("outputTokens") or 0),
            llmDurationMs=int(self._last_llm_trace.get("durationMs") or 0),
            structuredOutputValid=bool(self._last_llm_trace.get("structuredOutputValid")),
            groundingStatus=str(self._last_llm_trace.get("groundingStatus") or ""),
            abstained=bool(self._last_llm_trace.get("abstained")),
            uncertaintyReason=str(self._last_llm_trace.get("uncertaintyReason") or ""),
            requiresHumanReview=bool(self._last_llm_trace.get("requiresHumanReview")),
            llmFallbackUsed=bool(self._last_llm_trace.get("fallbackUsed")),
            llmGrounded=bool(self._last_llm_trace.get("grounded")),
            llmFallbackReason=str(self._last_llm_trace.get("fallbackReason") or ""),
            llmOutputHash=str(self._last_llm_trace.get("outputHash") or ""),
            **_bundle_eligibility_fields(self._last_eligibility_trace, result),
        )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _snippet(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip())[:180]


def _source_commit() -> str:
    env = os.getenv("GITHUB_SHA")
    if env:
        return env
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _knowledge_chunks_from_rows(rows: list[dict[str, Any]]) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for index, row in enumerate(rows):
        content = str(row.get("content") or row.get("text") or "")
        if not content.strip():
            continue
        chunks.append(
            KnowledgeChunk(
                chunkId=str(row.get("chunk_id") or row.get("chunkId") or stable_hash(content)[:24]),
                documentId=str(row.get("document_id") or row.get("documentId") or "document"),
                tenantId=str(row.get("tenant_id") or row.get("tenantId") or "__public__"),
                chunkIndex=int(row.get("chunk_index") or row.get("chunkIndex") or index),
                text=content,
                tokenCount=max(1, len(content.split())),
                contentHash=str(row.get("content_hash") or row.get("contentHash") or stable_hash(content)),
                sectionTitle=str(row.get("section_title") or row.get("sectionTitle") or ""),
                sourceType=_knowledge_source_type(row.get("source_type") or row.get("sourceType") or "policy"),
                documentVersion=str(row.get("document_version") or row.get("documentVersion") or "1"),
                effectiveFrom=str(row.get("effective_from") or row.get("effectiveFrom") or "1970-01-01T00:00:00Z"),
                effectiveTo=row.get("effective_to") or row.get("effectiveTo"),
                status="active" if row.get("active", True) and not row.get("deleted", False) else "deleted",
                title=str(row.get("title") or row.get("document_id") or row.get("documentId") or "document"),
                visibility=str(row.get("visibility") or "tenant"),
            )
        )
    return chunks


def _knowledge_source_type(value: Any) -> str:
    text = str(value or "policy").strip()
    legacy_map = {
        "taxonomy": "public-regulation",
    }
    return legacy_map.get(text, text)


def _eligibility_trace(evaluation_time: str, pre_count: int, eligible_count: int, decisions: list[Any]) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for decision in decisions:
        if not decision.eligible:
            reason_counts[decision.reasonCode] = reason_counts.get(decision.reasonCode, 0) + 1
    return {
        "evidenceEligibilityVersion": ELIGIBILITY_VERSION,
        "evidenceEvaluationTimeUtc": evaluation_time,
        "preRerankerCandidateCount": pre_count,
        "eligibleCandidateCount": eligible_count,
        "ineligibleCandidateCount": max(0, pre_count - eligible_count),
        "expiredRejectedCount": reason_counts.get("EXPIRED", 0),
        "inactiveRejectedCount": reason_counts.get("INACTIVE", 0) + reason_counts.get("DISABLED", 0),
        "tenantRejectedCount": reason_counts.get("TENANT_MISMATCH", 0) + reason_counts.get("TENANT_SCOPE_INVALID", 0),
        "notYetEffectiveRejectedCount": reason_counts.get("NOT_YET_EFFECTIVE", 0),
    }


def _bundle_eligibility_fields(trace: dict[str, Any], result: AgentRagResult) -> dict[str, Any]:
    return {
        "evidenceEligibilityVersion": str(trace.get("evidenceEligibilityVersion") or ""),
        "evidenceEvaluationTimeUtc": str(trace.get("evidenceEvaluationTimeUtc") or ""),
        "preRerankerCandidateCount": int(trace.get("preRerankerCandidateCount") or 0),
        "eligibleCandidateCount": int(trace.get("eligibleCandidateCount") or 0),
        "ineligibleCandidateCount": int(trace.get("ineligibleCandidateCount") or 0),
        "expiredRejectedCount": int(trace.get("expiredRejectedCount") or 0),
        "inactiveRejectedCount": int(trace.get("inactiveRejectedCount") or 0),
        "tenantRejectedCount": int(trace.get("tenantRejectedCount") or 0),
        "notYetEffectiveRejectedCount": int(trace.get("notYetEffectiveRejectedCount") or 0),
        "maximumFinalK": int(result.retrieval.topK or 5),
        "acceptedEvidenceCount": len(result.retrieval.citations),
        "rejectedEvidenceCount": max(0, int(trace.get("eligibleCandidateCount") or 0) - len(result.retrieval.citations)),
        "lowScoreBackfillCount": 0,
        "analysisInvocationDecision": "INVOKED" if result.retrieval.citations else "SKIPPED_NO_EVIDENCE",
    }
