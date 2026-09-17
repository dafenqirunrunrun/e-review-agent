from __future__ import annotations

import time
import uuid
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agentic_workflow.workflow import IntentDecision, IntentRouterAgent
from app.core.config import settings
from app.contracts.review_semantics import (
    evidence_tag_label,
    risk_type_definition,
    risk_type_label,
)
from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.runtime import get_runtime_policy_retriever
from app.policy_rag.risk_priority import build_primary_evidence_query, prioritize_risks
from app.observability.fast_eligibility_shadow import CurrentRouteSignal
from app.runtime.fast_eligibility_runtime import FastEligibilityRuntimeController
from app.runtime.review_input_gate import ReviewInputGate, ReviewInputGateDecision
from app.schemas.review import ReviewAnalyzeRequest


class PolicyPlaygroundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["evidence_search", "audit_simulation"] = "evidence_search"
    topK: int = Field(default=3, ge=1, le=5)
    indexTarget: Literal["current", "candidate"] = "current"
    candidateVersion: str = Field(default="", pattern=r"^(|policy-[0-9]{8}T[0-9]{6}-[0-9a-f]{8})$")


@dataclass(frozen=True)
class PlaygroundDecision:
    code: str
    label: str
    tone: str


class PolicyEvidencePlayground:
    """Read-only policy evidence sandbox used by the operations console."""

    def __init__(
        self,
        *,
        retriever: PolicyEvidenceRetriever | None = None,
        router: IntentRouterAgent | None = None,
        reranker: PolicyEvidenceReranker | None = None,
        reflector: PolicyReflectionEngine | None = None,
        fast_runtime_controller: FastEligibilityRuntimeController | None = None,
        input_gate: ReviewInputGate | None = None,
    ):
        self.retriever = retriever or get_runtime_policy_retriever()
        self.router = router or IntentRouterAgent()
        self.reranker = reranker or PolicyEvidenceReranker()
        self.reflector = reflector or PolicyReflectionEngine()
        self.fast_runtime_controller = fast_runtime_controller or FastEligibilityRuntimeController()
        self.input_gate = input_gate or ReviewInputGate()
        self.coverage_selector = PolicyEvidenceCoverageSelector()
        self._candidate_retrievers: dict[str, PolicyEvidenceRetriever] = {}
        self._candidate_lock = threading.Lock()

    def query(self, payload: PolicyPlaygroundRequest) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = "playground-" + uuid.uuid4().hex[:12]
        query_text = payload.query.strip()
        input_decision = self.input_gate.evaluate(query_text)
        if not input_decision.should_continue:
            return self._guidance_response(payload, request_id, query_text, started, input_decision)

        review = ReviewAnalyzeRequest(
            reviewId=request_id,
            productId="POLICY-PLAYGROUND",
            productName="政策证据试查",
            reviewText=input_decision.processingText or query_text,
            rating=None,
            ratingSource="UNKNOWN",
        )
        intent = self.router.route(review)
        fast_admission = self.fast_runtime_controller.decide_admission(
            review,
            CurrentRouteSignal(
                route=intent.route,
                intent=intent.intent,
                risk_hints=tuple(intent.risk_hints),
                reason_codes=tuple(intent.reason_codes),
                safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in intent.reason_codes,
            ),
        )
        if intent.route == "low_touch" and fast_admission.fast_executed:
            return self._normal_response(
                payload,
                request_id,
                intent,
                started,
                fast_admission=fast_admission.metadata(),
            )

        effective_route = intent.route
        if intent.route == "low_touch":
            effective_route = "governance_required"
            intent = IntentDecision(
                route=effective_route,
                intent="uncertain",
                risk_hints=["low_confidence"],
                reason_codes=[*intent.reason_codes, fast_admission.reasonCode, "FAST_ELIGIBILITY_NOT_PROVEN"],
                confidence=min(intent.confidence, 0.59),
                requires_evidence=True,
            )

        risks = list(dict.fromkeys(intent.risk_hints or ["low_confidence"]))
        priority = prioritize_risks(risks, payload.query)
        retrieval_query = build_primary_evidence_query(payload.query, priority)
        retrieval_error = ""
        runtime_retriever: PolicyEvidenceRetriever | None = None
        target_metadata = {
            "indexTarget": payload.indexTarget,
            "requestedIndexVersion": payload.candidateVersion if payload.indexTarget == "candidate" else "",
        }
        candidates: list[PolicySearchResult] = []
        try:
            runtime_retriever = self._retriever_for(payload)
            # Match the production workflow: keep a wider, bounded pool so a
            # second risk is not discarded before coverage selection/rerank.
            candidate_k = 20 if self.reranker.enabled else min(20, max(payload.topK * 4, 10))
            candidates = runtime_retriever.search(
                retrieval_query,
                risk_hints=risks,
                top_k=candidate_k,
                mode="hybrid",
            )
        except Exception as exc:
            retrieval_error = self._safe_error(exc)

        coverage_meta: dict[str, Any] = {}
        reranker_meta: dict[str, Any] = {
            "status": "disabled",
            "effectiveMode": "rrf",
            "fallbackUsed": False,
        }
        ranked = candidates
        if candidates:
            preselection = self.coverage_selector.select(
                candidates,
                risks,
                limit=5,
                backfill=True,
            )
            coverage_meta["beforeRerank"] = preselection.metadata
            reranked = self.reranker.rerank(
                retrieval_query,
                preselection.evidence,
                chunk_resolver=runtime_retriever.chunk_for_id if runtime_retriever else None,
            )
            reranker_meta = reranked.metadata
            ranked = reranked.ranked_candidates or reranked.evidence or preselection.evidence

        selected = self.coverage_selector.select(
            ranked,
            risks,
            limit=payload.topK,
            backfill=False,
        )
        coverage_meta["afterRerank"] = selected.metadata
        evidence = selected.evidence
        risk_level = self._risk_level(risks)
        reflection = self.reflector.reflect(
            risk_level=risk_level,
            risk_types=risks,
            confidence=intent.confidence,
            policy_evidence=evidence,
            action="none",
            retrieval_error=retrieval_error,
        )
        requires_human_review = reflection.requiresHumanReview or (
            payload.mode == "audit_simulation" and risk_level == "high"
        )
        decision = self._decision(reflection.evidenceStatus, requires_human_review)
        actual_mode = self._actual_mode(evidence)
        readiness = runtime_retriever.readiness() if runtime_retriever else {}
        metadata = runtime_retriever.observability_metadata() if runtime_retriever else {}
        return {
            "requestId": request_id,
            "mode": payload.mode,
            "query": payload.query.strip(),
            "isolated": True,
            "route": effective_route,
            "decision": decision.__dict__,
            "riskLevel": risk_level,
            "riskTypes": risks,
            "risks": self._risk_rows(risks, reflection.riskCoverage),
            "evidenceStatus": reflection.evidenceStatus,
            "evidenceStatusLabel": self._evidence_status_label(reflection.evidenceStatus),
            "reflectionReason": reflection.summary,
            "reasonCodes": reflection.reasonCodes,
            "requiresHumanReview": requires_human_review,
            "evidence": [self._evidence_row(item) for item in evidence],
            "technical": {
                "requestedMode": "hybrid",
                "actualMode": actual_mode,
                "candidateCount": len(candidates),
                "displayCount": len(evidence),
                "retrievalMs": round((time.perf_counter() - started) * 1000, 2),
                "indexVersion": str(metadata.get("managedIndexVersion") or metadata.get("policyIndexVersion") or "")[:16],
                "indexChunkCount": readiness.get("chunkCount", 0),
                "fallbackReason": runtime_retriever.last_dense_error if runtime_retriever else retrieval_error,
                **target_metadata,
                "inputGate": input_decision.metadata(),
                "fastEligibility": fast_admission.metadata(),
                "coverageSelection": coverage_meta,
                "reranker": {
                    "status": reranker_meta.get("status"),
                    "effectiveMode": reranker_meta.get("effectiveMode"),
                    "fallbackUsed": bool(reranker_meta.get("fallbackUsed")),
                    "fallbackReason": reranker_meta.get("fallbackReason", ""),
                    "durationMs": reranker_meta.get("durationMs", 0.0),
                },
            },
        }

    def _guidance_response(
        self,
        payload: PolicyPlaygroundRequest,
        request_id: str,
        query: str,
        started: float,
        input_decision: ReviewInputGateDecision,
    ) -> dict[str, Any]:
        return {
            "requestId": request_id,
            "mode": payload.mode,
            "query": query,
            "isolated": True,
            "route": "input_guidance",
            "decision": PlaygroundDecision("input_guidance", "请描述需要核对的问题", "info").__dict__,
            "riskLevel": "low",
            "riskTypes": [],
            "risks": [],
            "evidenceStatus": "not_required",
            "evidenceStatusLabel": "尚未检索",
            "reflectionReason": input_decision.message,
            "reasonCodes": [input_decision.reasonCode],
            "requiresHumanReview": False,
            "evidence": [],
            "technical": {
                "requestedMode": "not_required",
                "actualMode": "not_executed",
                "candidateCount": 0,
                "displayCount": 0,
                "retrievalMs": round((time.perf_counter() - started) * 1000, 2),
                "indexVersion": "",
                "indexChunkCount": 0,
                "fallbackReason": "",
                "indexTarget": payload.indexTarget,
                "requestedIndexVersion": payload.candidateVersion if payload.indexTarget == "candidate" else "",
                "inputGate": input_decision.metadata(),
                "coverageSelection": {},
                "reranker": {"status": "not_executed", "effectiveMode": "not_executed", "fallbackUsed": False},
            },
        }

    def _normal_response(
        self,
        payload: PolicyPlaygroundRequest,
        request_id: str,
        intent: IntentDecision,
        started: float,
        *,
        fast_admission: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "requestId": request_id,
            "mode": payload.mode,
            "query": payload.query.strip(),
            "isolated": True,
            "route": intent.route,
            "decision": PlaygroundDecision("normal_review", "未发现治理风险", "success").__dict__,
            "riskLevel": "low",
            "riskTypes": [],
            "risks": [],
            "evidenceStatus": "not_required",
            "evidenceStatusLabel": "无需政策依据",
            "reflectionReason": "当前输入未命中需要政策治理的风险信号，不启动证据检索。",
            "reasonCodes": intent.reason_codes,
            "requiresHumanReview": False,
            "evidence": [],
            "technical": {
                "requestedMode": "not_required",
                "actualMode": "not_executed",
                "candidateCount": 0,
                "displayCount": 0,
                "retrievalMs": round((time.perf_counter() - started) * 1000, 2),
                "indexVersion": "",
                "indexChunkCount": 0,
                "fallbackReason": "",
                "indexTarget": payload.indexTarget,
                "requestedIndexVersion": payload.candidateVersion if payload.indexTarget == "candidate" else "",
                "fastEligibility": fast_admission or {},
                "coverageSelection": {},
                "reranker": {"status": "not_executed", "effectiveMode": "not_executed", "fallbackUsed": False},
            },
        }

    @staticmethod
    def _decision(status: str, requires_human_review: bool) -> PlaygroundDecision:
        if status == "supported":
            if requires_human_review:
                return PlaygroundDecision("manual_review", "证据充分，建议人工确认", "warning")
            return PlaygroundDecision("evidence_ready", "已找到可用政策依据", "success")
        if status == "mismatch":
            return PlaygroundDecision("manual_review", "依据不匹配，需人工判断", "danger")
        return PlaygroundDecision("manual_review", "依据不足，需人工判断", "danger")

    @staticmethod
    def _risk_level(risks: list[str]) -> str:
        severities = {risk_type_definition(risk).severity for risk in risks}
        if "高" in severities:
            return "high"
        if "中" in severities:
            return "medium"
        return "low"

    @staticmethod
    def _risk_rows(risks: list[str], coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_code = {str(item.get("riskType")): item for item in coverage}
        rows = []
        for code in risks:
            definition = risk_type_definition(code)
            status = by_code.get(code, {})
            rows.append(
                {
                    "code": code,
                    "label": definition.label,
                    "description": definition.description,
                    "severity": definition.severity,
                    "evidenceStatus": status.get("status", "insufficient"),
                    "evidenceStatusLabel": status.get("statusText", "证据不足"),
                    "supportedBy": status.get("supportedBy", []),
                }
            )
        return rows

    @staticmethod
    def _evidence_row(item: PolicySearchResult) -> dict[str, Any]:
        return {
            "evidenceId": item.evidenceId,
            "sourceName": item.sourceName,
            "sourceType": item.sourceType,
            "sourceUrl": item.sourceUrl,
            "sectionPath": item.sectionPath,
            "clauseId": item.clauseId,
            "title": item.title,
            "snippet": item.snippet,
            "riskTypes": item.riskTypes,
            "riskLabels": [risk_type_label(code) for code in item.riskTypes],
            "evidenceTags": item.evidenceTags,
            "evidenceTagLabels": [evidence_tag_label(code) for code in item.evidenceTags],
            "contentHash": item.contentHash,
            "retrieval": item.retrieval or {"mode": item.retrievalMode, "score": item.score},
        }

    @staticmethod
    def _actual_mode(evidence: list[PolicySearchResult]) -> str:
        if not evidence:
            return "unavailable"
        mode = str((evidence[0].retrieval or {}).get("mode") or evidence[0].retrievalMode)
        if "hybrid" in mode:
            return "hybrid"
        if "dense" in mode:
            return "dense"
        return "bm25_fallback"

    @staticmethod
    def _evidence_status_label(status: str) -> str:
        return {"supported": "证据充分", "mismatch": "证据不匹配"}.get(status, "证据不足")

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        name = type(exc).__name__.upper()
        return name if name.endswith("ERROR") else f"{name}_ERROR"

    def _retriever_for(self, payload: PolicyPlaygroundRequest) -> PolicyEvidenceRetriever:
        if payload.indexTarget == "current":
            return self.retriever
        version = payload.candidateVersion
        if not re.fullmatch(r"policy-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}", version):
            raise ValueError("CANDIDATE_VERSION_REQUIRED")
        cached = self._candidate_retrievers.get(version)
        if cached is not None:
            return cached
        with self._candidate_lock:
            cached = self._candidate_retrievers.get(version)
            if cached is not None:
                return cached
            directory = self._candidate_directory(version)
            manifest = json.loads((directory / "release_manifest.json").read_text(encoding="utf-8-sig"))
            evaluation = manifest.get("releaseEvaluation") or {}
            if manifest.get("version") != version or evaluation.get("schemaVersion") != "policy-release-evaluation-v1":
                raise ValueError("CANDIDATE_INDEX_NOT_VERIFIED")
            provider = self._embedding_provider()
            candidate = PolicyEvidenceRetriever.from_jsonl(
                directory / "policy_chunks.jsonl",
                enable_dense=settings.policy_rag.dense_enabled,
                embedding_provider=provider,
            )
            self._candidate_retrievers[version] = candidate
            return candidate

    @staticmethod
    def _candidate_directory(version: str) -> Path:
        root = PolicyEvidenceRetriever._resolve_managed_root(settings.policy_rag.managed_index_root)
        versions_root = (root / "versions").resolve()
        candidates = (
            (versions_root / f"{version}.staging").resolve(),
            (versions_root / version).resolve(),
        )
        directory = next(
            (item for item in candidates if item.is_relative_to(versions_root) and item.is_dir()),
            None,
        )
        if directory is None:
            raise ValueError("CANDIDATE_INDEX_UNAVAILABLE")
        required = ("release_manifest.json", "policy_chunks.jsonl")
        if any(not (directory / name).is_file() for name in required):
            raise ValueError("CANDIDATE_INDEX_INCOMPLETE")
        return directory

    def _embedding_provider(self):
        active_dense_store = getattr(self.retriever, "active_dense_store", None)
        dense_store = active_dense_store() if callable(active_dense_store) else getattr(self.retriever, "dense_store", None)
        if dense_store is not None:
            return dense_store.provider
        managed_resolver = getattr(self.retriever, "_managed_retriever", None)
        managed = managed_resolver() if callable(managed_resolver) else None
        if managed is not None and managed.dense_store is not None:
            return managed.dense_store.provider
        return None
