"""Langfuse v4 sidecar with strict redaction and no business-path dependency."""
from __future__ import annotations

import hashlib
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from app.agent_trace.runtime_context import current_trace_context
from app.core.config import settings
from app.observability.workflow_observer import NoopSpan, SpanHandle


_CURRENT_TELEMETRY: ContextVar[Any | None] = ContextVar("e_review_langfuse_telemetry", default=None)
TRACE_SCHEMA_VERSION = "review-agent-runtime-v2"
WORKFLOW_VERSION = "review-agentic-v1"


def _hash(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _safe(value: Any) -> Any:
    """Keep telemetry useful without exporting review text, PII, secrets, or paths."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in ("token", "secret", "authorization", "password", "api_key", "email", "phone", "address")):
                result[str(key)] = "[REDACTED]"
            elif normalized in {"reviewtext", "review_text", "snippet", "query", "prompt", "input"}:
                result[str(key)] = {"redacted": True, "hash": _hash(item), "length": len(str(item))}
            elif normalized in {
                "requestedmode", "actualmode", "fallbackreason", "route", "checkpointstate",
                "workflowexecutionid", "langfusetraceid", "evidencestatus", "risklevel",
                "risktypes", "evidenceids", "completednodes", "resumeoccurred",
                "resumefromstate", "retrycount", "riskseverity", "confidencebucket",
                "complexity", "severityreasons", "routingrecommendation", "calibratorversion",
                "status", "errortype", "durationms", "iteration", "maxiterations",
                "nextaction", "reasoncodes", "topk", "evidencecount", "cachehit",
                "queuewaitms", "embeddingcomputems", "bm25ms", "densems",
                "faisssearchms", "rrfms", "resultcount", "fallbackused",
                "runtimespancount", "runtimeinstrumentation", "requireshumanreview",
                "supportedrisktypes", "unsupportedrisktypes", "retrievalfailed",
                "decision", "evidencestatus", "provider", "triggered", "ratingpresent",
                "executedchain", "dimension", "vectorcount", "nextiteration",
                "batchcount", "baserisktype", "baserisktypes", "baserisklevel",
                "plannedrisktypes", "mergedrisktypes", "detectedrisklevel",
                "operationalrisklevel", "calibratedseverity", "advisoryonly",
                "actionexecuted", "automationboundary", "decisionsource",
                "calibrationadvisoryonly", "analyzerprovider", "traceschemaversion",
                "runtimerelease", "servicename", "routerprovider",
                "routerpolicyversion", "policyindexversion", "policychunkcount",
                "embeddingmodel", "embeddingmodelfingerprint", "embeddingprovider",
                "embeddingdimension", "routereason", "reflectionreason",
                "evidencesufficient", "retrievalhitcount", "needhumanreview",
                "policydecision", "reasoncode", "modelprovider",
            }:
                result[str(key)] = _safe_technical(item)
            else:
                result[str(key)] = _safe(item)
        return result
    if isinstance(value, list):
        return [_safe(item) for item in value[:20]]
    if isinstance(value, str):
        return {"hash": _hash(value), "length": len(value)}
    return value


def _safe_technical(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [str(item)[:80] for item in value[:20]]
    if isinstance(value, dict):
        return {str(key)[:80]: _safe_technical(item) for key, item in list(value.items())[:20]}
    return str(value)[:120] if value is not None else None


class _LangfuseRuntimeSpan:
    def __init__(
        self,
        telemetry: "LangfuseTelemetry",
        observation: Any,
        *,
        name: str,
        parent_name: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.telemetry = telemetry
        self.observation = observation
        self.name = name
        self.parent_name = parent_name
        self.started = time.perf_counter()
        self.output: dict[str, Any] = {}
        self.metadata = dict(metadata or {})
        self.status = "success"
        self.ended = False

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        if output:
            self.output.update(output)
        if metadata:
            self.metadata.update(metadata)
        if status:
            self.status = status

    def close(self, *, error_type: str = "") -> None:
        if self.ended:
            return
        self.ended = True
        duration_ms = round((time.perf_counter() - self.started) * 1000, 2)
        final_metadata = {
            **self.metadata,
            "status": "error" if error_type else self.status,
            "durationMs": duration_ms,
        }
        if error_type:
            final_metadata["errorType"] = error_type
        self.telemetry.runtime_spans.append(
            {
                "name": self.name,
                "parentName": self.parent_name,
                "status": final_metadata["status"],
                "durationMs": duration_ms,
                "metadata": _safe(final_metadata),
                "output": _safe(self.output),
            }
        )
        if not self.observation:
            return
        try:
            self.observation.update(output=_safe(self.output), metadata=_safe(final_metadata))
        except Exception:
            self.telemetry.export_failures += 1
        try:
            self.observation.end()
        except Exception:
            self.telemetry.export_failures += 1


@dataclass
class LangfuseTelemetry:
    """A request-scoped best-effort Langfuse v4 trace."""

    client: Any | None = None
    root: Any | None = None
    enabled: bool = False
    export_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_spans: list[dict[str, Any]] = field(default_factory=list)
    _span_stack: list[tuple[str, Any]] = field(default_factory=list)
    _completed: bool = False

    @classmethod
    def begin(
        cls,
        payload: Any,
        *,
        execution_id: str = "",
        client_factory: Callable[[], Any] | None = None,
    ) -> "LangfuseTelemetry":
        if not settings.langfuse_enabled:
            return cls()
        telemetry = cls(enabled=True)
        try:
            if not settings.langfuse_host or not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
                telemetry.enabled = False
                return telemetry
            os.environ.setdefault("OTEL_SERVICE_NAME", settings.langfuse_service_name)
            if client_factory:
                telemetry.client = client_factory()
            else:
                from langfuse import Langfuse
                telemetry.client = Langfuse(
                    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                    base_url=settings.langfuse_host,
                    timeout=2,
                    environment=settings.langfuse_environment,
                    release=settings.langfuse_release or None,
                    sample_rate=settings.langfuse_sample_rate,
                )
            context = current_trace_context()
            external_identity = f"{getattr(payload, 'review_id', '')}:{execution_id or (context.request_id if context else 'request')}"
            trace_id = telemetry.client.create_trace_id(seed=external_identity)
            telemetry.metadata = {
                "reviewId": str(getattr(payload, "review_id", "")),
                "requestId": context.request_id if context else "not_available",
                "requestTraceId": context.trace_id if context else "not_available",
                "workflowVersion": WORKFLOW_VERSION,
                "traceSchemaVersion": TRACE_SCHEMA_VERSION,
                "serviceName": settings.langfuse_service_name,
                "runtimeRelease": settings.langfuse_release or TRACE_SCHEMA_VERSION,
                "governanceSchemaVersion": "review-governance-v2",
                "environment": settings.langfuse_environment,
                "langfuseTraceId": trace_id,
                "workflowExecutionId": execution_id or "not_available",
            }
            trace_context = {"trace_id": trace_id}
            telemetry.root = telemetry.client.start_observation(
                name="review_governance_analysis",
                as_type="agent",
                trace_context=trace_context,
                input={"review": {"redacted": True, "reviewId": telemetry.metadata["reviewId"]}},
                metadata=telemetry.metadata,
                version=settings.langfuse_release or None,
            )
            _CURRENT_TELEMETRY.set(telemetry)
        except Exception:
            telemetry.export_failures += 1
            telemetry.enabled = False
            telemetry.root = None
        return telemetry

    @classmethod
    def current(cls) -> "LangfuseTelemetry | None":
        current = _CURRENT_TELEMETRY.get()
        return current if isinstance(current, cls) else None

    @classmethod
    def clear_current(cls) -> None:
        _CURRENT_TELEMETRY.set(None)

    def activate(self) -> "LangfuseTelemetry":
        """Bind a manually constructed telemetry object to the current request."""
        _CURRENT_TELEMETRY.set(self)
        return self

    def bind_metadata(self, metadata: dict[str, Any] | None) -> None:
        """Attach non-sensitive runtime version data after dependencies are resolved."""
        if not metadata:
            return
        self.metadata.update(metadata)
        if not self.root:
            return
        try:
            self.root.update(metadata=_safe(self.metadata))
        except Exception:
            self.export_failures += 1

    def fail(self, exc: BaseException) -> None:
        """Close a failed root trace without exporting exception messages."""
        if not self.root or self._completed:
            self.clear_current()
            return
        metadata = {
            **self.metadata,
            "status": "error",
            "errorType": type(exc).__name__,
            "runtimeInstrumentation": bool(self.runtime_spans),
            "runtimeSpanCount": len(self.runtime_spans),
        }
        try:
            self.root.update(
                output=_safe({"status": "error", "errorType": type(exc).__name__}),
                metadata=metadata,
                level="ERROR",
                status_message=type(exc).__name__,
            )
        except Exception:
            self.export_failures += 1
        try:
            self.root.end()
        except Exception:
            self.export_failures += 1
        self._completed = True
        self.clear_current()

    @contextmanager
    def span(
        self,
        name: str,
        kind: str = "span",
        *,
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[SpanHandle]:
        """Measure a real workflow interval while keeping export fail-open."""
        if not self.root:
            yield NoopSpan()
            return
        parent_name, parent = self._span_stack[-1] if self._span_stack else ("review_governance_analysis", self.root)
        observation = None
        try:
            observation = parent.start_observation(
                name=name,
                as_type=kind,
                input=_safe(input or {}),
                metadata=_safe(metadata or {}),
            )
        except Exception:
            self.export_failures += 1
        runtime_span = _LangfuseRuntimeSpan(
            self,
            observation,
            name=name,
            parent_name=parent_name,
            metadata=metadata,
        )
        if observation:
            self._span_stack.append((name, observation))
        try:
            yield runtime_span
        except BaseException as exc:
            runtime_span.close(error_type=type(exc).__name__)
            raise
        else:
            runtime_span.close()
        finally:
            if observation and self._span_stack and self._span_stack[-1][1] is observation:
                self._span_stack.pop()

    def complete(self, response: Any, *, latency: dict[str, Any] | None = None) -> None:
        if not self.root or self._completed:
            self.clear_current()
            return
        try:
            extra = getattr(response, "extra", {}) or {}
            agentic = extra.get("agentic", {})
            checkpoint = extra.get("runtimeCheckpoint", {})
            recovery = extra.get("runtimeRecovery", {})
            risk_assessment = extra.get("riskAssessment", {})
            resumed = bool(recovery.get("resumeOccurred"))
            retrieval = getattr(getattr(response, "review_governance", None), "evidenceCitations", []) or []
            root_output = {
                "decision": getattr(response, "route_decision", None),
                "riskTypes": getattr(response, "risk_types", []),
                "operationalRiskLevel": getattr(response, "risk_level", None),
                "calibratedSeverity": risk_assessment.get("severity", getattr(response, "risk_level", None)),
                "calibrationAdvisoryOnly": True,
                "rawConfidence": risk_assessment.get("rawConfidence"),
                "calibratedConfidence": risk_assessment.get("calibratedConfidence"),
                "confidenceBucket": risk_assessment.get("confidenceBucket"),
                "complexity": risk_assessment.get("complexity"),
                "severityReasons": risk_assessment.get("severityReasons", []),
                "escalationCandidate": risk_assessment.get("escalationCandidate", False),
                "evidenceStatus": getattr(response, "evidence_status", None),
                "requiresHumanReview": getattr(response, "requires_human_review", None),
                "advisoryOnly": getattr(response, "route_decision", None) == "suggest_action",
                "actionExecuted": False,
                "automationBoundary": self._automation_boundary(response),
                "decisionSource": "governance_workflow",
                "checkpointState": checkpoint.get("state"),
                "completedNodes": self._semantic_completed_nodes(checkpoint.get("completedNodes", [])),
                "resumeOccurred": resumed,
                "resumeFromState": recovery.get("resumeFromState"),
            }
            root_metadata = {
                **self.metadata,
                "checkpointExecutionId": checkpoint.get("id", "not_available"),
                "resumeOccurred": resumed,
                "resumeFromState": recovery.get("resumeFromState", ""),
                "retryCount": recovery.get("retryCount", 0),
                "runtimeInstrumentation": bool(self.runtime_spans),
                "runtimeSpanCount": len(self.runtime_spans),
            }
            self.root.update(output=_safe(root_output), metadata=root_metadata)
            # Compatibility fallback for non-workflow callers. Instrumented workflows
            # emit spans at the real execution sites and must not be duplicated here.
            if not self.runtime_spans:
                if not resumed:
                    self._span("intent_router", "chain", {"route": agentic.get("route"), "riskTypes": agentic.get("plan", {}).get("risk_types", [])})
                    self._span("risk_analysis", "agent", {"riskTypes": getattr(response, "risk_types", []), "riskLevel": getattr(response, "risk_level", None)})
                    if agentic.get("route") == "human_review_direct":
                        self._span("direct_human_review", "span", {"requiresHumanReview": True, "reason": "intent_router_direct"})
                    self._span("risk_calibration", "evaluator", risk_assessment)
                    self._retrieval_span(response, latency or {})
                    self._span("evidence_agent", "chain", {"evidenceCount": len(retrieval), "evidenceIds": [getattr(item, "id", "") for item in retrieval]})
                self._span("reflection_agent", "evaluator", {"reflectionStatus": getattr(response, "evidence_status", None), "requiresHumanReview": getattr(response, "requires_human_review", None)})
                self._span("checkpoint_persist", "span", {"checkpointState": checkpoint.get("state"), "completedNodes": checkpoint.get("completedNodes", []), "resumeOccurred": resumed, "resumeFromState": recovery.get("resumeFromState"), "retryCount": recovery.get("retryCount", 0)})
                self._span("governance_finalize", "span", root_output)
            self._scores(response)
            self.root.end()
            self._completed = True
        except Exception:
            self.export_failures += 1
            try:
                self.root.end()
            except Exception:
                self.export_failures += 1
            self._completed = True
        finally:
            self.clear_current()

    def _retrieval_span(self, response: Any, latency: dict[str, Any]) -> None:
        retrieval = dict(latency)
        policy_retrieval = (getattr(response, "extra", {}) or {}).get("policyRetrieval", {})
        parent = self._start("policy_retrieval", "retriever", {
            "requestedMode": policy_retrieval.get("requestedMode", "hybrid"),
            "actualMode": policy_retrieval.get("actualMode", self._retrieval_mode(response)),
            "topK": 3,
            "cacheHit": retrieval.get("cacheHit", False),
            "fallbackReason": policy_retrieval.get("fallbackReason", self._fallback_reason(response)),
            "bm25LatencyMs": policy_retrieval.get("bm25LatencyMs", retrieval.get("bm25Ms", 0)),
        })
        if not parent:
            return
        for name, key, kind in (("bm25", "bm25Ms", "span"), ("dense_embedding", "embeddingComputeMs", "embedding"), ("faiss_search", "faissSearchMs", "span"), ("rrf", "rrfMs", "span")):
            child = parent.start_observation(name=name, as_type=kind, metadata=_safe({"latencyMs": retrieval.get(key, 0)}))
            child.end()
        parent.end()

    def _span(self, name: str, kind: str, output: dict[str, Any]) -> None:
        span = self._start(name, kind, output)
        if span:
            span.end()

    def _start(self, name: str, kind: str, output: dict[str, Any]) -> Any | None:
        try:
            return self.root.start_observation(name=name, as_type=kind, output=_safe(output))
        except Exception:
            self.export_failures += 1
            return None

    def _scores(self, response: Any) -> None:
        decision = getattr(response, "route_decision", "")
        high_auto_pass = bool(getattr(response, "risk_level", "") == "high" and decision in {"auto_pass", "auto_close"})
        risk_assessment = (getattr(response, "extra", {}) or {}).get("riskAssessment", {})
        severity_value = {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(risk_assessment.get("severity"), 0)
        values = {
            "citation_valid": int(getattr(response, "evidence_status", "") == "supported"),
            "evidence_supported": int(bool(getattr(response, "evidence_sufficient", False))),
            "human_review_required": int(bool(getattr(response, "requires_human_review", False))),
            "high_risk_auto_pass": int(high_auto_pass),
            "api_success": 1,
            "risk_severity_level": severity_value,
            "raw_confidence": float(risk_assessment.get("rawConfidence", 0.0)),
            "calibrated_confidence": float(risk_assessment.get("calibratedConfidence", 0.0)),
            "escalation_candidate": int(bool(risk_assessment.get("escalationCandidate", False))),
        }
        for name, value in values.items():
            try:
                self.client.create_score(name=name, value=value, trace_id=self.root.trace_id, data_type="NUMERIC")
            except Exception:
                self.export_failures += 1

    @staticmethod
    def _retrieval_mode(response: Any) -> str:
        return str(getattr(response, "rag_strategy", "not_available") or "not_available")

    @staticmethod
    def _fallback_reason(response: Any) -> str:
        return "not_available" if not getattr(response, "rag_enabled", False) else ""

    @staticmethod
    def _automation_boundary(response: Any) -> str:
        if bool(getattr(response, "requires_human_review", False)):
            return "human_review_required"
        if getattr(response, "route_decision", "") == "suggest_action":
            return "advisory_only"
        if getattr(response, "route_decision", "") in {"auto_pass", "auto_close"}:
            return "automatic_no_action"
        return "deferred_or_manual"

    @staticmethod
    def _semantic_completed_nodes(nodes: Any) -> list[str]:
        aliases = {
            "risk_analysis": "execution_assessment",
            "finalize": "governance_finalize",
        }
        completed: list[str] = []
        for node in nodes if isinstance(nodes, list) else []:
            semantic_name = aliases.get(node, node)
            if isinstance(node, str) and node.startswith("evidence_"):
                semantic_name = "evidence_agent"
            elif isinstance(node, str) and node.startswith("reflection_"):
                semantic_name = "reflection_agent"
            if semantic_name not in completed:
                completed.append(semantic_name)
        return completed

    @classmethod
    def record_human_feedback(
        cls,
        *,
        trace_id: str,
        human_decision: str,
        ai_decision: str,
        override_reason_code: str = "",
    ) -> bool:
        """Mirror an already-persisted human outcome without changing governance state."""
        if not settings.langfuse_enabled or not trace_id:
            return False
        try:
            from langfuse import Langfuse
            import os

            if not settings.langfuse_host or not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
                return False
            client = Langfuse(
                public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                base_url=settings.langfuse_host,
                timeout=2,
                environment=settings.langfuse_environment,
            )
            override = int(human_decision != ai_decision)
            metadata = {
                "humanDecision": human_decision,
                "finalDecision": human_decision,
                "overrideReasonCode": override_reason_code or "not_provided",
                "feedbackSource": "human_review",
            }
            client.create_score(name="human_override", value=override, trace_id=trace_id, data_type="NUMERIC", metadata=metadata)
            client.create_score(name="final_decision_match", value=1 - override, trace_id=trace_id, data_type="NUMERIC", metadata=metadata)
            return True
        except Exception:
            return False
