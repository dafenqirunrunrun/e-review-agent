from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.agent_framework.graph import run_agent_graph
from app.core.config import settings
from app.agentic_workflow.memory import GovernanceMemory
from app.agentic_workflow.runtime_checkpoint import (
    CheckpointCorruptError,
    FileWorkflowCheckpointStore,
    ReviewWorkflowState,
    SimulatedWorkflowCrash,
    WorkflowRuntime,
)
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector
from app.observability.langfuse_sidecar import LangfuseTelemetry, TRACE_SCHEMA_VERSION, WORKFLOW_VERSION
from app.observability.workflow_observer import NoopWorkflowObserver, WorkflowObserver
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.runtime import get_runtime_policy_retriever
from app.risk_calibration.assessment import SmallModelRiskAssessor
from app.observability.fast_eligibility_shadow import CurrentRouteSignal
from app.runtime.fast_eligibility_runtime import (
    FAST_SHORT_CHAIN,
    FastEligibilityRuntimeController,
    FastEligibilityRuntimeDecision,
)
from app.runtime.review_input_gate import ReviewInputGate, ReviewInputGateDecision
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse, WorkflowTraceItem
from app.services.base import AnalyzerBase


@dataclass
class IntentDecision:
    route: str
    intent: str
    risk_hints: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    confidence: float = 0.75
    requires_evidence: bool = False


@dataclass
class WorkflowPlan:
    route: str
    risk_types: list[str]
    evidence_queries: list[str]
    max_iterations: int
    next_step: str = "execution"


@dataclass
class ExecutionAssessment:
    risk_level: str
    risk_types: list[str]
    route_decision: str
    route_reason: str
    need_human_review: bool


class IntentRouterAgent:
    def __init__(
        self,
        *,
        rule_enhancements_enabled: bool | None = None,
        safety_gate_enabled: bool | None = None,
    ):
        self.rule_enhancements_enabled = (
            settings.intent_router_rule_enhancements_enabled
            if rule_enhancements_enabled is None else rule_enhancements_enabled
        )
        self.safety_gate_enabled = settings.high_risk_safety_gate_enabled if safety_gate_enabled is None else safety_gate_enabled
        self.last_safety_gate_ms = 0.0

    def route(
        self,
        payload: ReviewAnalyzeRequest,
        *,
        observer: WorkflowObserver | None = None,
    ) -> IntentDecision:
        self.last_safety_gate_ms = 0.0
        runtime_observer = observer or NoopWorkflowObserver()
        provider = settings.intent_router_provider
        if provider in {"local_qwen", "qwen2.5", "qwen"}:
            with runtime_observer.span("local_qwen_router", "generation", metadata={"provider": provider}) as span:
                model_decision = self._route_with_local_qwen(payload)
                span.update(
                    output={
                        "route": model_decision.route if model_decision else "fallback",
                        "riskTypes": model_decision.risk_hints if model_decision else [],
                    },
                    status="success" if model_decision else "fallback",
                )
            if model_decision is not None:
                return model_decision
        with runtime_observer.span("rule_evaluation", "span", metadata={"ratingPresent": payload.rating is not None}) as span:
            decision = self._route_with_rules(payload, observer=runtime_observer)
            span.update(output={"route": decision.route, "riskTypes": decision.risk_hints})
            return decision

    def _route_with_rules(
        self,
        payload: ReviewAnalyzeRequest,
        *,
        observer: WorkflowObserver | None = None,
    ) -> IntentDecision:
        text = self._normalized_text(payload.review_text)
        trusted_low_rating = (
            payload.rating_source == "USER_PROVIDED"
            and payload.rating is not None
            and payload.rating <= 2
        )
        hints: list[str] = []
        reasons: list[str] = []
        keyword_map = {
            "after_sales_risk": [
                "refund", "return", "broken", "damage", "defect", "after-sales",
                "退款", "退货", "破损", "售后", "质量问题", "返品", "返金", "환불", "반품",
            ],
            "safety_or_fraud_risk": ["unsafe", "danger", "fraud", "counterfeit", "安全", "危险", "欺诈", "假货"],
            "fake_review": [
                "fake review", "paid review", "fabricated review", "cashback", "incentive",
                "刷单", "虚假评价", "好评返现", "返现", "晒图返现", "截图返现",
            ],
            "rating_manipulation": [
                "five star", "5 star", "rating manipulation", "paid review", "cashback", "incentive",
                "好评返现", "五星截图", "五星好评", "截图返现", "返现", "评分操纵",
            ],
            "review_suppression": [
                "delete review", "remove review", "suppress review", "unfavorable review",
                "删除差评", "删掉差评", "删掉评价", "屏蔽评价", "压制差评",
            ],
            "privacy_risk": ["privacy", "personal information", "隐私", "个人信息"],
            "harassment_or_abuse": ["threat", "harass", "abuse", "威胁", "辱骂", "骚扰"],
        }
        for risk, terms in keyword_map.items():
            if any(term in text for term in terms):
                hints.append(risk)
                reasons.append(f"{risk.upper()}_KEYWORD")
        if self.rule_enhancements_enabled:
            for risk, terms in self._semantic_phrase_map().items():
                if any(term in text for term in terms):
                    hints.append(risk)
                    reasons.append(f"{risk.upper()}_SEMANTIC_PHRASE")
        if self.safety_gate_enabled:
            safety_started = time.perf_counter()
            runtime_observer = observer or NoopWorkflowObserver()
            with runtime_observer.span("safety_gate", "guardrail") as span:
                safety_hints = self._high_risk_safety_hints(text)
                span.update(
                    output={"riskTypes": safety_hints, "triggered": bool(safety_hints)},
                    status="success" if not safety_hints else "escalated",
                )
            self.last_safety_gate_ms = round((time.perf_counter() - safety_started) * 1000, 2)
            if safety_hints:
                hints.extend(safety_hints)
                reasons.append("HIGH_RISK_SAFETY_GATE")
        if trusted_low_rating:
            reasons.append("LOW_RATING")
            if not hints:
                hints.append("after_sales_risk")
        if trusted_low_rating and any(
            term in text for term in ["good", "great", "不错", "满意", "好"]
        ):
            hints.append("rating_conflict")
            reasons.append("RATING_TEXT_CONFLICT")
        if payload.image_urls:
            reasons.append("IMAGE_PRESENT")
        if len(text.strip()) < 8 and trusted_low_rating:
            return IntentDecision("human_review_direct", "uncertain", hints or ["after_sales_risk"], ["SHORT_TEXT_LOW_RATING"], 0.55, True)
        if hints or trusted_low_rating:
            unique_hints = sorted(set(hints))
            safety_routed = "HIGH_RISK_SAFETY_GATE" in reasons
            return IntentDecision(
                "governance_required", unique_hints[0], unique_hints, sorted(set(reasons)),
                0.68 if safety_routed else 0.84, True,
            )
        return IntentDecision("low_touch", "normal_feedback", [], ["NO_RISK_SIGNAL"], 0.88, False)

    @staticmethod
    def _normalized_text(value: str) -> str:
        return " ".join((value or "").lower().replace("-", " ").split())

    @staticmethod
    def _semantic_phrase_map() -> dict[str, list[str]]:
        return {
            "fake_review": [
                "\u7f16\u9020", "\u865a\u6784", "\u5192\u5145\u4e70\u5bb6", "\u6ca1\u6709\u4e70\u8fc7", "\u6ca1\u4e70\u8fc7", "\u672a\u8d2d\u4e70", "\u627e\u4eba\u5199", "\u4eb2\u53cb", "\u5458\u5de5\u8bc4\u4ef7",
                "\u7edf\u4e00\u6a21\u677f", "\u6279\u91cf\u53d1\u5e03", "\u7ec4\u7ec7\u5047\u8bc4\u4ef7", "fabricated", "no purchase", "without using the product",
                "fake engagement", "manufacture social proof",
            ],
            "rating_manipulation": [
                "\u6ee1\u5206", "\u6253\u4e94\u661f", "\u7ed9\u4e94\u661f", "\u4e94\u9897\u661f", "\u51b2\u8bc4\u5206", "\u63d0\u9ad8\u8bc4\u5206", "\u7edf\u4e00\u597d\u8bc4", "\u4e94\u661f\u5956\u52b1",
                "five star", "five-star", "5-star", "boost the score", "favorable review",
            ],
            "review_suppression": [
                "\u5220\u8bc4", "\u64a4\u9500\u8bc4\u4ef7", "\u64a4\u56de\u8bc4\u4ef7", "\u64a4\u9500\u4f4e\u5206", "\u6539\u597d\u4e00\u70b9", "\u8fc7\u6ee4\u8d1f\u9762", "\u5220\u9664\u4f4e\u5206", "\u5c4f\u853d\u4e86\u6240\u6709\u8d1f\u9762\u8bc4\u4ef7",
                "remove the bad review", "refuse support", "suppress unfavorable", "hide criticism",
            ],
            "privacy_risk": [
                "\u624b\u673a\u53f7", "\u4f4f\u5740", "\u5730\u5740", "\u8ba2\u5355\u53f7", "\u8eab\u4efd\u8bc1", "\u8054\u7cfb\u65b9\u5f0f", "\u6cc4\u9732", "\u516c\u5f00\u4fe1\u606f",
                "phone number", "private address", "personal information", "without consent",
            ],
            "harassment_or_abuse": [
                "\u6050\u5413", "\u62a5\u590d", "\u8fb1\u9a82", "\u6cd5\u5f8b\u5a01\u80c1", "\u5a01\u80c1\u66dd\u5149", "\u6301\u7eed\u9a9a\u6270",
                "intimidation", "abusive language", "retaliation", "harassing messages",
            ],
        }

    @staticmethod
    def _high_risk_safety_hints(text: str) -> list[str]:
        """High recall gate: route ambiguous governance language, never punish it."""
        hints: set[str] = set()
        review_terms = ("\u8bc4\u4ef7", "\u8bc4\u8bba", "\u597d\u8bc4", "\u5dee\u8bc4", "\u6652\u5355", "\u6652\u4e2a", "\u6652\u56fe", "\u4e94\u661f", "\u6ee1\u5206", "review", "rating", "star", "feedback")
        incentive_terms = ("\u8fd4\u73b0", "\u8fd4", "\u7ea2\u5305", "\u8865\u8d34", "\u793c\u91d1", "\u5956\u52b1", "\u8d60\u54c1", "\u4f18\u60e0\u5238", "cashback", "coupon", "compensation", "rebate")
        review_actions = ("\u5220\u9664", "\u5220\u6389", "\u5220\u8bc4", "\u64a4\u9500", "\u64a4\u56de", "\u64a4\u4e0b", "\u4fee\u6539", "\u6539\u6210", "\u5904\u7406\u4e00\u4e0b", "remove", "delete", "withdraw", "take down", "change")
        pressure_terms = ("\u9000\u6b3e", "\u552e\u540e", "\u8865\u53d1", "\u652f\u6301", "\u5a01\u80c1", "\u62d2\u7edd", "\u9000\u8d27", "refund", "support", "return", "threat", "refuse")
        visibility_actions = ("\u9690\u85cf", "\u5c4f\u853d", "\u4e0d\u5c55\u793a", "\u4e0d\u516c\u5f00", "\u53ea\u5c55\u793a", "hide", "suppress", "do not show", "only show")
        negative_review_terms = ("\u4e00\u661f", "\u4f4e\u5206", "\u5dee\u8bc4", "\u8d1f\u9762\u8bc4\u4ef7", "one star", "one-star", "low rating", "negative review")
        paid_content_terms = ("\u652f\u4ed8", "\u62a5\u916c", "\u4ed8\u8d39", "\u4f63\u91d1", "\u6309\u6761", "pay", "paid", "commission", "per review")
        controlled_content_terms = ("\u6307\u5b9a\u5185\u5bb9", "\u7edf\u4e00\u5185\u5bb9", "\u6307\u5b9a\u6587\u6848", "\u7edf\u4e00\u6587\u6848", "\u6a21\u677f", "specified content", "scripted", "template")
        voucher_terms = ("\u793c\u54c1\u5238", "\u793c\u5238", "gift card", "voucher")
        binding_terms = ("\u5fc5\u987b", "\u6761\u4ef6", "\u624d\u80fd", "\u8981\u6c42", "required", "condition")
        positive_rating_terms = ("\u597d\u8bc4", "\u4e94\u661f", "\u6ee1\u5206", "five star", "5 star", "positive review")
        account_farming_terms = ("\u591a\u4e2a\u8d26\u53f7", "\u5927\u91cf\u8d26\u53f7", "\u6279\u91cf\u8d26\u53f7", "\u8d26\u53f7\u77e9\u9635", "multiple accounts", "many accounts", "account farm")
        coordinated_rating_terms = ("\u5237\u4e94\u661f", "\u96c6\u4e2d\u6253\u5206", "\u96c6\u4e2d\u8bc4\u5206", "\u6279\u91cf\u597d\u8bc4", "boost ratings", "mass ratings")
        fake_terms = ("\u7f16\u9020", "\u865a\u6784", "\u5192\u5145", "\u5237\u5355", "\u7edf\u4e00\u6a21\u677f", "\u7ec4\u7ec7", "\u6279\u91cf", "\u5047\u8bc4\u4ef7", "fabricated", "fake", "template", "organized")
        insider_terms = ("\u5458\u5de5", "\u4eb2\u53cb", "\u95e8\u5e97", "\u5546\u5bb6\u81ea\u8bc4", "employee", "staff", "insider")
        battery_terms = ("\u7535\u6c60", "\u7535\u82af", "\u9502\u7535", "\u5145\u7535\u5b9d", "battery", "power bank", "lithium", "電池", "バッテリー", "배터리")
        battery_hazard_terms = (
            "\u9f13\u5305", "\u9f13\u8d77", "\u9f13\u8d77\u6765", "\u81a8\u80c0", "\u53d1\u70eb", "\u8fc7\u70ed", "\u6f0f\u6db2", "\u5192\u70df", "\u8d77\u706b", "\u7206\u70b8",
            "swollen", "swelling", "bulging", "puffed", "overheat", "overheating", "leaking", "smoke", "fire", "explode",
            "膨張", "発熱", "煙", "発火", "爆発", "부풀", "과열", "연기", "화재", "폭발",
        )
        severe_product_hazards = ("\u8d77\u706b", "\u7206\u70b8", "\u6f0f\u7535", "\u89e6\u7535", "\u4e2d\u6bd2", "caught fire", "exploded", "electric shock")
        has_review = any(term in text for term in review_terms)
        if any(term in text for term in incentive_terms) and has_review:
            hints.update({"fake_review", "rating_manipulation"})
        if any(term in text for term in review_actions) and (has_review or "\u4f4e\u5206" in text) and any(term in text for term in pressure_terms):
            hints.add("review_suppression")
        if any(term in text for term in visibility_actions) and any(term in text for term in negative_review_terms):
            hints.add("review_suppression")
        if has_review and any(term in text for term in paid_content_terms) and any(term in text for term in controlled_content_terms):
            hints.update({"fake_review", "rating_manipulation"})
        if has_review and any(term in text for term in voucher_terms) and any(term in text for term in binding_terms) and any(term in text for term in positive_rating_terms):
            hints.update({"fake_review", "rating_manipulation"})
        if any(term in text for term in account_farming_terms) and any(term in text for term in coordinated_rating_terms):
            hints.update({"fake_review", "rating_manipulation"})
        if any(term in text for term in fake_terms) and (has_review or "\u8d2d\u4e70\u4f53\u9a8c" in text or "purchase" in text):
            hints.add("fake_review")
        if any(term in text for term in insider_terms) and has_review:
            hints.update({"fake_review", "rating_manipulation"})
        if (
            any(term in text for term in battery_terms)
            and any(term in text for term in battery_hazard_terms)
        ) or any(term in text for term in severe_product_hazards):
            hints.add("safety_or_fraud_risk")
        if any(term in text for term in ("\u624b\u673a\u53f7", "\u4f4f\u5740", "\u8eab\u4efd\u8bc1", "\u8ba2\u5355\u53f7", "\u8054\u7cfb\u65b9\u5f0f", "phone number", "private address", "personal information")):
            hints.add("privacy_risk")
        if any(term in text for term in ("\u6050\u5413", "\u62a5\u590d", "\u8fb1\u9a82", "intimidation", "abusive language", "harassing")):
            hints.add("harassment_or_abuse")
        return sorted(hints)

    def _route_with_local_qwen(self, payload: ReviewAnalyzeRequest) -> IntentDecision | None:
        try:
            from app.llm.config import ProviderConfig
            from app.llm.local_qwen import LocalQwenTransformersProvider

            config = ProviderConfig(
                provider_name="local_qwen3_transformers",
                base_url="local://transformers",
                model_name=settings.intent_router_model,
                api_key_env="",
                timeout_seconds=max(1, settings.intent_router_timeout_ms // 1000),
                max_retries=0,
                enabled=True,
            )
            prompt = (
                "Return one JSON object for e-commerce review triage. "
                "Allowed route: low_touch, governance_required, human_review_direct. "
                "Allowed intent: normal_feedback, negative_feedback, after_sales_risk, safety_or_fraud_risk, "
                "fake_review, rating_manipulation, review_suppression, rating_conflict, multimodal_review, privacy_risk, uncertain. "
                "Fields: route, intent, riskHints array, reasonCodes array, confidence number, requiresEvidence boolean.\n"
                f"rating={payload.rating}; rating_source={payload.rating_source}; "
                f"image_count={len(payload.image_urls)}; review={payload.review_text[:700]}"
            )
            raw = LocalQwenTransformersProvider(config).complete_json(prompt).content
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return IntentDecision(
                route=self._enum(data.get("route"), {"low_touch", "governance_required", "human_review_direct"}, "governance_required"),
                intent=self._enum(
                    data.get("intent"),
                    {
                        "normal_feedback",
                        "negative_feedback",
                        "after_sales_risk",
                        "safety_or_fraud_risk",
                        "fake_review",
                        "rating_manipulation",
                        "review_suppression",
                        "rating_conflict",
                        "multimodal_review",
                        "privacy_risk",
                        "uncertain",
                    },
                    "uncertain",
                ),
                risk_hints=self._list(data.get("riskHints")),
                reason_codes=self._list(data.get("reasonCodes")) or ["LOCAL_QWEN_INTENT_ROUTER"],
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
                requires_evidence=bool(data.get("requiresEvidence", True)),
            )
        except Exception:
            return None

    @staticmethod
    def _enum(value: Any, allowed: set[str], default: str) -> str:
        text = str(value or "").strip()
        return text if text in allowed else default

    @staticmethod
    def _list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if value in (None, ""):
            return []
        return [str(value)]


class AgenticReviewWorkflow:
    def __init__(
        self,
        *,
        analyzer: AnalyzerBase,
        policy_retriever: PolicyEvidenceRetriever | None = None,
        policy_reranker: PolicyEvidenceReranker | None = None,
        intent_router: IntentRouterAgent | None = None,
        checkpoint_store: FileWorkflowCheckpointStore | None = None,
        fast_runtime_controller: FastEligibilityRuntimeController | None = None,
        input_gate: ReviewInputGate | None = None,
        crash_after_node: str = "",
    ):
        self.analyzer = analyzer
        self.intent_router = intent_router or IntentRouterAgent()
        self.policy_retriever = policy_retriever or get_runtime_policy_retriever()
        self.policy_reranker = policy_reranker or PolicyEvidenceReranker()
        self.evidence_coverage_selector = PolicyEvidenceCoverageSelector()
        self.reflector = PolicyReflectionEngine()
        self.risk_assessor = SmallModelRiskAssessor()
        self.fast_runtime_controller = fast_runtime_controller or FastEligibilityRuntimeController()
        self.input_gate = input_gate or ReviewInputGate()
        self.checkpoint_store = checkpoint_store or (
            FileWorkflowCheckpointStore(settings.agentic_checkpoint_dir)
            if settings.agentic_checkpoint_enabled else None
        )
        self.crash_after_node = crash_after_node

    def analyze(self, payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
        LangfuseTelemetry.clear_current()
        try:
            return self._analyze(payload)
        except BaseException as exc:
            telemetry = LangfuseTelemetry.current()
            if telemetry is not None:
                telemetry.fail(exc)
            raise

    def _analyze(self, payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
        input_started = time.perf_counter()
        input_decision = self.input_gate.evaluate(payload.review_text)
        if not input_decision.should_continue:
            telemetry = self._begin_telemetry(payload)
            with telemetry.span("review_input_gate", "guardrail") as span:
                response = self._input_guidance_response(payload, input_decision, input_started)
                span.update(output=input_decision.metadata(), status="success")
            return self._observe_response(
                telemetry,
                response,
                (response.extra or {}).get("latencyBreakdown", {}),
            )
        if input_decision.processingText and input_decision.processingText != payload.review_text:
            payload = payload.model_copy(update={"review_text": input_decision.processingText})
        try:
            runtime = self._runtime(payload)
        except CheckpointCorruptError:
            telemetry = self._begin_telemetry(payload)
            with telemetry.span("checkpoint_recovery", "span", metadata={"checkpointState": ReviewWorkflowState.FAILED.value}) as span:
                response = self._checkpoint_corrupt_response(payload)
                span.update(output={"decision": response.route_decision}, status="needs_review")
            return self._observe_response(telemetry, response)
        telemetry = self._begin_telemetry(payload, execution_id=runtime.checkpoint.id if runtime else "")
        if runtime:
            final = runtime.final_response()
            if final:
                with telemetry.span("checkpoint_reuse", "span", metadata={"checkpointState": runtime.checkpoint.currentState}) as span:
                    response = ReviewAnalyzeResponse.model_validate(final)
                    if "riskAssessment" not in (response.extra or {}):
                        with telemetry.span("intent_router", "chain", metadata={"reason": "cached_assessment_backfill"}) as router_span:
                            cached_intent = self.intent_router.route(payload, observer=telemetry)
                            router_span.update(output={"route": cached_intent.route, "riskTypes": cached_intent.risk_hints})
                        with telemetry.span("risk_calibration", "evaluator"):
                            self._attach_risk_assessment(response, payload, cached_intent)
                    if settings.agentic_memory_enabled and "agenticMemory" not in (response.extra or {}):
                        cached_memory = self._new_memory(payload)
                        if cached_memory:
                            cached_memory.update_state(
                                risk_types=response.risk_types,
                                reflection_status=response.evidence_status or "unchecked",
                                human_decision="pending" if response.requires_human_review else "not_required",
                                workflow_state="finalized",
                            )
                            self._attach_memory(response, cached_memory)
                    span.update(output={"checkpointState": runtime.checkpoint.currentState, "decision": response.route_decision})
                return self._observe_response(telemetry, response)
        workflow_started = time.perf_counter()
        latency: dict[str, float] = {"intentRouterMs": 0.0, "safetyGateMs": 0.0, "fastEligibilityMs": 0.0, "riskDetectionMs": 0.0, "evidenceQueryBuildMs": 0.0, "evidenceAgentMs": 0.0, "policyRerankerMs": 0.0, "reflectionMs": 0.0, "persistenceMs": 0.0}
        memory = self._new_memory(payload)
        if runtime and runtime.completed("evidence_1") and not runtime.completed("reflection_1"):
            return self._resume_after_evidence(payload, runtime, memory, latency, workflow_started, telemetry)
        max_iterations = settings.agentic_max_iterations
        intent_started = time.perf_counter()
        if runtime:
            runtime.transition(ReviewWorkflowState.ROUTING)
            runtime.start_node("intent_router", {"reviewId": payload.review_id, "rating": payload.rating})
        with telemetry.span("intent_router", "chain", metadata={"maxIterations": max_iterations}) as span:
            intent = self.intent_router.route(payload, observer=telemetry)
            span.update(
                output={
                    "route": intent.route,
                    "riskTypes": intent.risk_hints,
                    "reasonCodes": intent.reason_codes,
                }
            )
        latency["intentRouterMs"] = round((time.perf_counter() - intent_started) * 1000, 2)
        latency["safetyGateMs"] = self.intent_router.last_safety_gate_ms
        if memory:
            memory.update_state(risk_types=intent.risk_hints, workflow_state="intent_routed")
            memory.record_turn("intent_router", route=intent.route, intent=intent.intent, riskHints=intent.risk_hints, requiresEvidence=intent.requires_evidence)
        if payload.audit_mode == "shadow_strict" and intent.route == "low_touch":
            # Shadow mode is observational: it never changes the persisted business outcome.
            intent = IntentDecision("governance_required", "negative_review", ["negative_review"], ["SHADOW_STRICT_AUDIT"], 0.5, True)
        trace: list[WorkflowTraceItem] = [
            self._trace(
                "intent_router",
                "IntentRouterAgent",
                "success",
                f"route={intent.route}, intent={intent.intent}",
                output={
                    "route": intent.route,
                    "intent": intent.intent,
                    "riskHints": intent.risk_hints,
                    "reasonCodes": intent.reason_codes,
                    "confidence": intent.confidence,
                    "requiresEvidence": intent.requires_evidence,
                },
            )
        ]
        fast_runtime = None
        fast_started = time.perf_counter()
        with telemetry.span("fast_eligibility", "guardrail", metadata={"route": intent.route}) as span:
            try:
                fast_runtime = self.fast_runtime_controller.decide_admission(
                    payload,
                    CurrentRouteSignal(
                        route=intent.route,
                        intent=intent.intent,
                        risk_hints=tuple(intent.risk_hints),
                        reason_codes=tuple(intent.reason_codes),
                        safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in intent.reason_codes,
                    ),
                )
                span.update(
                    output=fast_runtime.metadata() if fast_runtime else {"executedChain": "baseline"},
                    status="fallback" if fast_runtime and fast_runtime.failClosed else "success",
                )
            except Exception as exc:
                # Admission uncertainty must never silently enter the short chain.
                fast_runtime = None
                span.update(metadata={"errorType": type(exc).__name__}, status="fallback")
        latency["fastEligibilityMs"] = round((time.perf_counter() - fast_started) * 1000, 2)
        if fast_runtime and fast_runtime.enabled:
            trace.append(
                self._trace(
                    "fast_eligibility_gate",
                    "FastEligibilityGate",
                    "success" if not fast_runtime.failClosed else "fallback",
                    f"executedChain={fast_runtime.executedChain}, reason={fast_runtime.reasonCode}",
                    output=fast_runtime.metadata(),
                )
            )
        if runtime:
            runtime.finish_node("intent_router", intent.__dict__, memory=self._memory_snapshot(memory))
        if intent.route == "low_touch" and not (fast_runtime and fast_runtime.fast_executed):
            denial_reason = fast_runtime.reasonCode if fast_runtime else "FAST_ELIGIBILITY_UNAVAILABLE"
            intent = IntentDecision(
                route="governance_required",
                intent="uncertain",
                risk_hints=["low_confidence"],
                reason_codes=[*intent.reason_codes, denial_reason, "FAST_ELIGIBILITY_NOT_PROVEN"],
                confidence=min(intent.confidence, 0.59),
                requires_evidence=True,
            )
            trace.append(
                self._trace(
                    "fast_eligibility_escalation",
                    "FastEligibilityGate",
                    "fallback",
                    "short-chain safety was not proven; escalated to the evidence-backed long chain",
                    output={"effectiveRoute": intent.route, "riskTypes": intent.risk_hints, "reasonCode": denial_reason},
                )
            )
        if intent.route == "human_review_direct":
            if runtime:
                runtime.transition(ReviewWorkflowState.RISK_ANALYSIS)
                runtime.start_node("risk_analysis", {"route": intent.route})
            risk_started = time.perf_counter()
            with telemetry.span("risk_analysis", "agent", metadata={"route": intent.route}) as span:
                response = run_agent_graph(payload, self.analyzer)
                span.update(output={"riskTypes": response.risk_types, "riskLevel": response.risk_level})
            latency["riskDetectionMs"] = round((time.perf_counter() - risk_started) * 1000, 2)
            with telemetry.span("governance_finalize", "span", metadata={"route": intent.route}) as finalize_span:
                response.workflow_trace = trace + response.workflow_trace
                with telemetry.span("direct_human_review", "span", metadata={"route": intent.route}) as span:
                    response.need_human_review = True
                    response.requires_human_review = True
                    response.route_decision = "human_review"
                    response.route_reason = "Intent router sent the review directly to human review."
                    response.evidence_status = "insufficient"
                    response.reflection_reason = "评论被意图识别直接送入人工复核，未进入自动政策证据闭环。"
                    span.update(output={"decision": response.route_decision, "requiresHumanReview": True})
                response.extra = {
                    **(response.extra or {}),
                    "agentic": {"route": intent.route, "intent": intent.__dict__, "iterations": 0, "finalDecision": self._final_decision(response)},
                }
                with telemetry.span("risk_calibration", "evaluator") as span:
                    self._attach_risk_assessment(response, payload, intent)
                    span.update(output=(response.extra or {}).get("riskAssessment", {}))
                self._attach_memory(response, memory)
                self._attach_fast_runtime(response, fast_runtime)
                response = self._attach_latency(response, latency, workflow_started)
                finalize_span.update(output=self._final_decision(response))
            if runtime:
                runtime.finish_node("risk_analysis", {"response": response.model_dump()}, memory=self._memory_snapshot(memory))
                runtime.transition(ReviewWorkflowState.DECISION)
                with telemetry.span("checkpoint_persist", "span", metadata={"checkpointState": ReviewWorkflowState.WAIT_HUMAN.value}):
                    self._finalize_runtime(runtime, response, ReviewWorkflowState.WAIT_HUMAN, memory)
            return self._observe_response(telemetry, response, latency)
        if intent.route == "low_touch" and fast_runtime and fast_runtime.fast_executed:
            fast_executed = bool(fast_runtime and fast_runtime.fast_executed)
            if runtime:
                runtime.transition(ReviewWorkflowState.RISK_ANALYSIS)
                runtime.start_node("fast_execution" if fast_executed else "risk_analysis", {"route": intent.route})
            risk_started = time.perf_counter()
            execution_span_name = "fast_execution" if fast_executed else "light_execution"
            with telemetry.span(execution_span_name, "agent", metadata={"route": intent.route}) as span:
                response = run_agent_graph(payload, self.analyzer)
                span.update(output={"riskTypes": response.risk_types, "riskLevel": response.risk_level})
            latency["riskDetectionMs"] = round((time.perf_counter() - risk_started) * 1000, 2)
            with telemetry.span("governance_finalize", "span", metadata={"route": intent.route}) as finalize_span:
                response.workflow_trace = trace + [
                    self._trace(
                        "fast_execution" if fast_executed else "light_execution",
                        "FastExecutionAgent" if fast_executed else "LightExecutionAgent",
                        "success",
                        "eligible review completed through the deterministic fast chain"
                        if fast_executed else "low-touch analysis completed",
                    )
                ] + response.workflow_trace
                response.route_decision = "auto_close"
                response.route_reason = "No strong risk signal from intent router."
                response.need_human_review = False
                response.requires_human_review = False
                response.evidence_sufficient = True
                response.evidence_status = "supported"
                response.reflection_reason = "未命中治理风险，轻路径自动审核通过。"
                response.extra = {
                    **(response.extra or {}),
                    "agentic": {
                        "route": intent.route,
                        "intent": intent.__dict__,
                        "iterations": 0 if fast_executed else 1,
                        "finalDecision": self._final_decision(response),
                    },
                }
                with telemetry.span("risk_calibration", "evaluator") as span:
                    self._attach_risk_assessment(response, payload, intent)
                    span.update(output=(response.extra or {}).get("riskAssessment", {}))
                if memory:
                    memory.update_state(reflection_status="supported", human_decision="not_required", workflow_state="finalized")
                    memory.add_iteration_summary(confirmed_facts=["No governance risk signal was detected."], evidence_used=[], unresolved_issues=[], next_action="finalize")
                self._attach_memory(response, memory)
                self._attach_fast_runtime(response, fast_runtime)
                response = self._attach_fast_latency(
                    response,
                    latency,
                    workflow_started,
                    skip_reason="FAST_SHORT_CHAIN" if fast_executed else "LOW_TOUCH_NOT_REQUIRED",
                )
                finalize_span.update(output=self._final_decision(response))
            if runtime:
                runtime.finish_node(
                    "fast_execution" if fast_executed else "risk_analysis",
                    {"response": response.model_dump()},
                    memory=self._memory_snapshot(memory),
                )
                runtime.transition(ReviewWorkflowState.DECISION)
                with telemetry.span("checkpoint_persist", "span", metadata={"checkpointState": ReviewWorkflowState.COMPLETED.value}):
                    self._finalize_runtime(runtime, response, ReviewWorkflowState.COMPLETED, memory)
            return self._observe_response(telemetry, response, latency)

        if runtime:
            runtime.transition(ReviewWorkflowState.RISK_ANALYSIS)
            runtime.start_node("risk_analysis", {"route": intent.route})
        risk_started = time.perf_counter()
        with telemetry.span(
            "base_signal_analysis",
            "agent",
            metadata={"route": intent.route, "analyzerProvider": self.analyzer.__class__.__name__},
        ) as span:
            response = run_agent_graph(payload, self.analyzer)
            span.update(output={"baseRiskTypes": response.risk_types, "baseRiskLevel": response.risk_level})
        latency["riskDetectionMs"] = round((time.perf_counter() - risk_started) * 1000, 2)
        with telemetry.span("planner", "agent", metadata={"maxIterations": max_iterations}) as span:
            plan = self._plan(payload, intent, max_iterations)
            span.update(output={"route": plan.route, "riskTypes": plan.risk_types, "nextAction": plan.next_step})
        with telemetry.span(
            "execution_assessment",
            "agent",
            input={
                "baseRiskTypes": response.risk_types,
                "baseRiskLevel": response.risk_level,
                "plannedRiskTypes": plan.risk_types,
            },
            metadata={"decisionSource": "governance_workflow"},
        ) as span:
            assessment = self._assess_execution(response, intent, plan)
            span.update(
                output={
                    "mergedRiskTypes": assessment.risk_types,
                    "detectedRiskLevel": assessment.risk_level,
                    "decision": assessment.route_decision,
                    "requiresHumanReview": assessment.need_human_review,
                    "decisionSource": "governance_workflow",
                }
            )
        response.risk_level = assessment.risk_level
        response.route_decision = assessment.route_decision
        response.route_reason = assessment.route_reason
        response.need_human_review = assessment.need_human_review
        response.requires_human_review = assessment.need_human_review
        response.risk_types = plan.risk_types
        response.extra = {**(response.extra or {}), "risk_types": plan.risk_types}
        if memory:
            memory.update_state(risk_types=plan.risk_types, workflow_state="planned")
            memory.record_turn("planner", route=plan.route, riskTypes=plan.risk_types, maxIterations=plan.max_iterations)

        trace.append(self._trace("planner", "PlannerAgent", "success", "strict governance plan prepared", output=plan.__dict__))
        trace.append(self._trace("execution", "ExecutionAgent", "success", assessment.route_reason, output=assessment.__dict__))
        if runtime:
            runtime.finish_node(
                "risk_analysis",
                {"response": response.model_dump(), "intent": intent.__dict__, "plan": plan.__dict__, "assessment": assessment.__dict__},
                memory=self._memory_snapshot(memory),
            )

        last_reflection = None
        completed_iterations = 0
        evidence_bundle: dict[str, Any] = {"citations": [], "iterations": []}
        reranker_runs: list[dict[str, object]] = []
        for iteration in range(1, max_iterations + 1):
            with telemetry.span(
                f"iteration_{iteration}",
                "chain",
                metadata={"iteration": iteration, "maxIterations": max_iterations, "riskTypes": plan.risk_types},
            ) as iteration_span:
                completed_iterations = iteration
                query_started = time.perf_counter()
                with telemetry.span("evidence_query_build", "span", metadata={"iteration": iteration}) as query_span:
                    query = self._evidence_query(payload, plan, iteration)
                    query_span.update(output={"query": query, "riskTypes": plan.risk_types})
                latency["evidenceQueryBuildMs"] += round((time.perf_counter() - query_started) * 1000, 2)
                retrieval_error = ""
                retrieval_error_type = ""
                if runtime:
                    runtime.transition(ReviewWorkflowState.EVIDENCE_RETRIEVAL)
                    runtime.start_node(f"evidence_{iteration}", {"iteration": iteration, "riskTypes": plan.risk_types})
                # Retrieve a small, wider RRF pool only for governance. The local
                # BGE reranker still receives five candidates, so model cost stays flat.
                base_top_k = max(settings.policy_rag.retrieval_top_k, 5)
                coverage_limit = 5
                top_k = max(base_top_k, coverage_limit * 4) if self.policy_reranker.enabled else base_top_k
                evidence_started = time.perf_counter()
                with telemetry.span("evidence_agent", "chain", metadata={"iteration": iteration, "topK": top_k}) as evidence_span:
                    try:
                        policy_evidence = self.policy_retriever.search(
                            query,
                            risk_hints=plan.risk_types,
                            top_k=top_k,
                            observer=telemetry,
                        )
                        policy_evidence = self._dedupe_evidence(policy_evidence)
                    except Exception as exc:
                        retrieval_error = str(exc)[:240]
                        retrieval_error_type = type(exc).__name__
                        policy_evidence = []
                    retrieved_candidate_count = len(policy_evidence)
                    evidence_span.update(
                        output={
                            "iteration": iteration,
                            "candidateCount": retrieved_candidate_count,
                            "evidenceIds": [item.evidenceId for item in policy_evidence],
                            "retrievalFailed": bool(retrieval_error),
                        },
                        metadata={"errorType": retrieval_error_type} if retrieval_error else None,
                        status="fallback" if retrieval_error else "success",
                    )
                latency["evidenceAgentMs"] += round((time.perf_counter() - evidence_started) * 1000, 2)
                coverage_metadata: dict[str, object] = {}
                if policy_evidence:
                    preselection = self.evidence_coverage_selector.select(
                        policy_evidence,
                        plan.risk_types,
                        limit=coverage_limit,
                    )
                    policy_evidence = preselection.evidence
                    coverage_metadata["beforeRerank"] = preselection.metadata
                reranker_metadata: dict[str, object] = {}
                if self.policy_reranker.enabled and policy_evidence:
                    reranker_started = time.perf_counter()
                    with telemetry.span(
                        "policy_rerank",
                        "span",
                        metadata={"iteration": iteration, "candidateCount": len(policy_evidence)},
                    ) as reranker_span:
                        resolver = getattr(self.policy_retriever, "chunk_for_id", lambda _chunk_id: None)
                        outcome = self.policy_reranker.rerank(query, policy_evidence, chunk_resolver=resolver)
                        ranked_candidates = outcome.ranked_candidates or outcome.evidence
                        postselection = self.evidence_coverage_selector.select(
                            ranked_candidates,
                            plan.risk_types,
                            limit=coverage_limit,
                        )
                        policy_evidence = postselection.evidence
                        coverage_metadata["afterRerank"] = postselection.metadata
                        reranker_metadata = dict(outcome.metadata)
                        reranker_span.update(
                            output={
                                "effectiveMode": reranker_metadata.get("effectiveMode"),
                                "candidateCount": reranker_metadata.get("candidateCount"),
                                "outputCount": reranker_metadata.get("outputCount"),
                                "fallbackUsed": reranker_metadata.get("fallbackUsed"),
                                "durationMs": reranker_metadata.get("durationMs"),
                            },
                            metadata={"fallbackReason": reranker_metadata.get("fallbackReason", "")},
                            status="fallback" if reranker_metadata.get("fallbackUsed") else "success",
                        )
                    latency["policyRerankerMs"] += round((time.perf_counter() - reranker_started) * 1000, 2)
                    reranker_runs.append({"iteration": iteration, **reranker_metadata})
                evidence_rows = [item.model_dump() for item in policy_evidence]
                evidence_ids = [item.evidenceId for item in policy_evidence]
                if memory:
                    memory.update_state(evidence_ids=evidence_ids, workflow_state="evidence_retrieved")
                    memory.record_turn("evidence", iteration=iteration, evidenceIds=evidence_ids, citationCount=len(evidence_ids), retrievalFailed=bool(retrieval_error))
                evidence_bundle["iterations"].append(
                    {
                        "iteration": iteration,
                        "candidateCount": retrieved_candidate_count,
                        "citationCount": len(evidence_rows),
                        "reranker": reranker_metadata,
                        "coverageSelection": coverage_metadata,
                    }
                )
                # Reflection evaluates the current iteration, so the API must expose
                # that same evidence snapshot after a replan.
                evidence_bundle["citations"] = evidence_rows[:3]
                trace.append(
                    self._trace(
                        "policy_evidence_retrieve",
                        "EvidenceAgent",
                        "failed" if retrieval_error else "success",
                        f"retrieved {len(policy_evidence)} policy citations" if not retrieval_error else "policy evidence retrieval failed",
                        output={"iteration": iteration, "query": query, "policyEvidence": evidence_rows, "error": retrieval_error},
                    )
                )
                if reranker_metadata:
                    trace.append(
                        self._trace(
                            "policy_evidence_rerank",
                            "PolicyEvidenceReranker",
                            "fallback" if reranker_metadata.get("fallbackUsed") else "success",
                            "local BGE reranked policy candidates"
                            if not reranker_metadata.get("fallbackUsed")
                            else "local BGE unavailable; retained original RRF order",
                            output={"iteration": iteration, **reranker_metadata},
                        )
                    )
                if coverage_metadata:
                    trace.append(
                        self._trace(
                            "policy_evidence_coverage",
                            "PolicyEvidenceCoverageSelector",
                            "success",
                            "selected retrieved evidence to cover detected policy risks before rank backfill",
                            output={"iteration": iteration, **coverage_metadata},
                        )
                    )
                if runtime:
                    runtime.finish_node(
                        f"evidence_{iteration}",
                        {"response": response.model_dump(), "intent": intent.__dict__, "plan": plan.__dict__, "assessment": assessment.__dict__, "evidence": evidence_rows, "retrievalError": retrieval_error, "reranker": reranker_metadata, "coverageSelection": coverage_metadata, "iteration": iteration},
                        memory=self._memory_snapshot(memory),
                    )
                    if self.crash_after_node in {"evidence", f"evidence_{iteration}"}:
                        raise SimulatedWorkflowCrash(f"SIMULATED_CRASH_AFTER_EVIDENCE_{iteration}")
                    runtime.transition(ReviewWorkflowState.REFLECTION)
                    runtime.start_node(f"reflection_{iteration}", {"iteration": iteration, "evidenceIds": evidence_ids})
                reflection_started = time.perf_counter()
                with telemetry.span("reflection_agent", "evaluator", metadata={"iteration": iteration}) as reflection_span:
                    reflection = self.reflector.reflect(
                        risk_level=response.risk_level,
                        risk_types=plan.risk_types or ["negative_review"],
                        confidence=response.confidence,
                        policy_evidence=policy_evidence,
                        action=response.route_decision or "none",
                        retrieval_error=retrieval_error,
                    )
                    reflection_span.update(
                        output={
                            "evidenceStatus": reflection.evidenceStatus,
                            "reasonCodes": reflection.reasonCodes or (["ALL_RISKS_SUPPORTED"] if reflection.passed else []),
                            "supportedRiskTypes": reflection.supportedRiskTypes,
                            "unsupportedRiskTypes": reflection.unsupportedRiskTypes,
                            "requiresHumanReview": reflection.requiresHumanReview,
                        },
                        status="success" if reflection.passed else "needs_review",
                    )
                latency["reflectionMs"] += round((time.perf_counter() - reflection_started) * 1000, 2)
                last_reflection = reflection
                response.evidence_status = reflection.evidenceStatus
                response.reflection_reason = reflection.summary
                if memory:
                    memory.update_state(reflection_status=reflection.evidenceStatus, workflow_state="reflection_completed")
                    memory.add_iteration_summary(
                        confirmed_facts=[f"Detected risks: {', '.join(plan.risk_types) or 'none'}", f"Reflection status: {reflection.evidenceStatus}"],
                        evidence_used=evidence_ids,
                        unresolved_issues=list(reflection.unsupportedRiskTypes),
                        next_action="finalize" if reflection.passed else ("replan" if iteration < max_iterations else "human_review"),
                    )
                trace.append(
                    self._trace(
                        "reflection",
                        "ReflectionAgent",
                        "success" if reflection.passed else "failed",
                        reflection.summary,
                        output={"iteration": iteration, **reflection.model_dump()},
                    )
                )
                if runtime:
                    runtime.finish_node(f"reflection_{iteration}", reflection.model_dump(), memory=self._memory_snapshot(memory))
                next_action = "finalize" if reflection.passed else ("replan" if iteration < max_iterations else "human_review")
                iteration_span.update(
                    output={
                        "iteration": iteration,
                        "evidenceStatus": reflection.evidenceStatus,
                        "evidenceCount": len(policy_evidence),
                        "nextAction": next_action,
                    },
                    status="success" if reflection.passed else ("replan" if iteration < max_iterations else "needs_review"),
                )
                if reflection.passed:
                    response.retrieval_hit_count = max(response.retrieval_hit_count, len(policy_evidence))
                    response.retrieved_case_ids = response.retrieved_case_ids + [item.chunkId or item.evidenceId for item in policy_evidence]
                    response.evidence_sufficient = True
                    if response.risk_level == "high":
                        response.need_human_review = True
                        response.requires_human_review = True
                        response.route_decision = "human_review"
                        response.route_reason = "High-risk review has matching evidence and requires human confirmation."
                    else:
                        response.need_human_review = False
                        response.requires_human_review = False
                        response.route_decision = "suggest_action"
                        response.route_reason = "Risk signals are supported by structured evidence; system recommends an operational action."
                    break
                if iteration < max_iterations:
                    with telemetry.span("replan", "agent", metadata={"iteration": iteration + 1}) as replan_span:
                        trace.append(
                            self._trace(
                                "replan",
                                "ReplannerAgent",
                                "success",
                                "reflection failed; expanded policy retrieval constraints",
                                output={"iteration": iteration + 1, "replanHints": reflection.replanHints},
                            )
                        )
                        replan_span.update(
                            output={
                                "nextIteration": iteration + 1,
                                "unsupportedRiskTypes": reflection.unsupportedRiskTypes,
                            }
                        )
                else:
                    response.need_human_review = True
                    response.requires_human_review = True
                    response.route_decision = "human_review"
                    response.route_reason = "Reflection unresolved after max iterations."
                    response.evidence_sufficient = False
                    response.human_review_trigger = reflection.evidenceStatus

        with telemetry.span("governance_finalize", "span", metadata={"route": intent.route}) as finalize_span:
            trace.append(self._trace("finalize", "FinalizeAgent", "success", response.route_reason or "workflow finalized", output=self._final_decision(response)))
            response.workflow_trace = trace + response.workflow_trace
            response.rag_enabled = True
            response.rag_strategy = "policy_rag_hybrid_with_bm25_fallback"
            response.extra = {
                **(response.extra or {}),
                "agentic": {
                    "route": intent.route,
                    "intent": intent.__dict__,
                    "plan": plan.__dict__,
                    "execution": assessment.__dict__,
                    "evidenceBundle": evidence_bundle,
                    "reranker": reranker_runs[-1] if reranker_runs else {},
                    "iterations": completed_iterations,
                    "reflection": None if last_reflection is None else last_reflection.model_dump(),
                    "finalDecision": self._final_decision(response),
                },
            }
            with telemetry.span("risk_calibration", "evaluator") as span:
                self._attach_risk_assessment(response, payload, intent)
                span.update(output=(response.extra or {}).get("riskAssessment", {}))
            if memory:
                memory.update_state(
                    human_decision="pending" if response.requires_human_review else "not_required",
                    workflow_state="finalized",
                )
            self._attach_memory(response, memory)
            self._attach_fast_runtime(response, fast_runtime)
            response = self._attach_latency(response, latency, workflow_started)
            finalize_span.update(output=self._final_decision(response))
        if runtime:
            runtime.transition(ReviewWorkflowState.DECISION)
            target_state = ReviewWorkflowState.WAIT_HUMAN if response.requires_human_review else ReviewWorkflowState.COMPLETED
            with telemetry.span("checkpoint_persist", "span", metadata={"checkpointState": target_state.value}):
                self._finalize_runtime(runtime, response, target_state, memory)
        return self._observe_response(telemetry, response, latency)

    def _resume_after_evidence(
        self,
        payload: ReviewAnalyzeRequest,
        runtime: WorkflowRuntime,
        memory: GovernanceMemory | None,
        latency: dict[str, float],
        workflow_started: float,
        telemetry: LangfuseTelemetry,
    ) -> ReviewAnalyzeResponse:
        """Resume the first unfinished reflection without repeating retrieval work."""
        with telemetry.span(
            "checkpoint_resume",
            "span",
            metadata={
                "resumeOccurred": True,
                "resumeFromState": ReviewWorkflowState.EVIDENCE_RETRIEVAL.value,
                "retryCount": runtime.checkpoint.retryCount,
            },
        ) as resume_span:
            saved = runtime.checkpoint.nodeOutputs["evidence_1"]
            response = ReviewAnalyzeResponse.model_validate(saved["response"])
            intent = IntentDecision(**saved["intent"])
            plan = WorkflowPlan(**saved["plan"])
            assessment = ExecutionAssessment(**saved["assessment"])
            evidence = [PolicySearchResult.model_validate(item) for item in saved.get("evidence", [])]
            retrieval_error = str(saved.get("retrievalError", ""))
            reranker_metadata = dict(saved.get("reranker", {}) or {})
            resume_span.update(output={"evidenceCount": len(evidence), "evidenceIds": [item.evidenceId for item in evidence]})
        runtime.transition(ReviewWorkflowState.REFLECTION)
        runtime.start_node("reflection_1", {"resume": True, "evidenceIds": [item.evidenceId for item in evidence]})
        reflection_started = time.perf_counter()
        with telemetry.span("reflection_agent", "evaluator", metadata={"iteration": 1, "resumeOccurred": True}) as span:
            reflection = self.reflector.reflect(
                risk_level=response.risk_level,
                risk_types=plan.risk_types or ["negative_review"],
                confidence=response.confidence,
                policy_evidence=evidence,
                action=response.route_decision or "none",
                retrieval_error=retrieval_error,
            )
            span.update(
                output={
                    "evidenceStatus": reflection.evidenceStatus,
                    "reasonCodes": reflection.reasonCodes,
                    "supportedRiskTypes": reflection.supportedRiskTypes,
                    "unsupportedRiskTypes": reflection.unsupportedRiskTypes,
                    "requiresHumanReview": reflection.requiresHumanReview,
                },
                status="success" if reflection.passed else "needs_review",
            )
        latency["reflectionMs"] = round((time.perf_counter() - reflection_started) * 1000, 2)
        with telemetry.span("governance_finalize", "span", metadata={"route": intent.route, "resumeOccurred": True}) as finalize_span:
            response.evidence_status = reflection.evidenceStatus
            response.reflection_reason = reflection.summary
            response.evidence_sufficient = reflection.passed
            if reflection.passed and response.risk_level != "high":
                response.need_human_review = response.requires_human_review = False
                response.route_decision = "suggest_action"
                response.route_reason = "Risk signals are supported by structured evidence; system recommends an operational action."
            else:
                response.need_human_review = response.requires_human_review = True
                response.route_decision = "human_review"
                response.route_reason = (
                    "High-risk review has matching evidence and requires human confirmation."
                    if reflection.passed else "Reflection unresolved after checkpoint recovery."
                )
            response.workflow_trace = [
                self._trace("checkpoint_resume", "WorkflowRuntime", "success", "resumed from durable evidence checkpoint"),
                self._trace("reflection", "ReflectionAgent", "success" if reflection.passed else "failed", reflection.summary, output=reflection.model_dump()),
                self._trace("finalize", "FinalizeAgent", "success", response.route_reason, output=self._final_decision(response)),
            ] + response.workflow_trace
            response.rag_enabled = True
            response.rag_strategy = "policy_rag_hybrid_with_bm25_fallback"
            response.extra = {
                **(response.extra or {}),
                "runtimeRecovery": {
                    "resumeOccurred": True,
                    "resumeFromState": ReviewWorkflowState.EVIDENCE_RETRIEVAL.value,
                    "workflowExecutionId": runtime.checkpoint.id,
                    "retryCount": runtime.checkpoint.retryCount,
                },
                "agentic": {
                    "route": intent.route,
                    "intent": intent.__dict__,
                    "plan": plan.__dict__,
                    "execution": assessment.__dict__,
                    "evidenceBundle": {"citations": [item.model_dump() for item in evidence[:3]], "iterations": [{"iteration": 1, "citationCount": len(evidence)}]},
                    "reranker": reranker_metadata,
                    "iterations": 1,
                    "reflection": reflection.model_dump(),
                    "finalDecision": self._final_decision(response),
                },
            }
            with telemetry.span("risk_calibration", "evaluator") as span:
                self._attach_risk_assessment(response, payload, intent)
                span.update(output=(response.extra or {}).get("riskAssessment", {}))
            if memory:
                memory.update_state(
                    risk_types=plan.risk_types,
                    evidence_ids=[item.evidenceId for item in evidence],
                    reflection_status=reflection.evidenceStatus,
                    human_decision="pending" if response.requires_human_review else "not_required",
                    workflow_state="finalized",
                )
                memory.add_iteration_summary(
                    confirmed_facts=[f"Recovered from evidence checkpoint; reflection status: {reflection.evidenceStatus}"],
                    evidence_used=[item.evidenceId for item in evidence],
                    unresolved_issues=list(reflection.unsupportedRiskTypes),
                    next_action="human_review" if response.requires_human_review else "finalize",
                )
            self._attach_memory(response, memory)
            response = self._attach_latency(response, latency, workflow_started)
            finalize_span.update(output=self._final_decision(response))
        runtime.finish_node("reflection_1", reflection.model_dump(), memory=self._memory_snapshot(memory))
        runtime.transition(ReviewWorkflowState.DECISION)
        target_state = ReviewWorkflowState.WAIT_HUMAN if response.requires_human_review else ReviewWorkflowState.COMPLETED
        with telemetry.span("checkpoint_persist", "span", metadata={"checkpointState": target_state.value, "resumeOccurred": True}):
            self._finalize_runtime(runtime, response, target_state, memory)
        return self._observe_response(telemetry, response, latency)

    def _observe_response(
        self,
        telemetry: LangfuseTelemetry,
        response: ReviewAnalyzeResponse,
        latency: dict[str, Any] | None = None,
    ) -> ReviewAnalyzeResponse:
        try:
            telemetry.bind_metadata(self.policy_retriever.observability_metadata())
        except Exception:
            pass
        telemetry.complete(response, latency=latency)
        return response

    def _runtime(self, payload: ReviewAnalyzeRequest) -> WorkflowRuntime | None:
        if self.checkpoint_store is None or not payload.review_id:
            return None
        return WorkflowRuntime(self.checkpoint_store, payload.review_id)

    def _checkpoint_corrupt_response(self, payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
        """Fail closed without replacing a corrupted durable record."""
        response = run_agent_graph(payload, self.analyzer)
        response.need_human_review = response.requires_human_review = True
        response.route_decision = "human_review"
        response.route_reason = "Workflow checkpoint is unreadable; human review is required."
        response.evidence_sufficient = False
        response.evidence_status = "insufficient"
        response.reflection_reason = "当前运行记录无法读取，系统未生成自动处置建议，建议人工复核。"
        response.extra = {
            **(response.extra or {}),
            "runtimeCheckpoint": {"state": ReviewWorkflowState.FAILED.value, "errorCode": "WORKFLOW_CHECKPOINT_CORRUPT"},
        }
        response.workflow_trace = [
            self._trace("runtime_checkpoint", "WorkflowRuntime", "failed", "workflow checkpoint is unreadable"),
        ] + response.workflow_trace
        return response

    def _input_guidance_response(
        self,
        payload: ReviewAnalyzeRequest,
        decision: ReviewInputGateDecision,
        started: float,
    ) -> ReviewAnalyzeResponse:
        response = run_agent_graph(payload, self.analyzer)
        response.route_decision = "auto_close"
        response.route_reason = "Input gate identified obvious non-review conversational content."
        response.risk_level = "low"
        response.risk_types = []
        response.need_human_review = False
        response.requires_human_review = False
        response.evidence_sufficient = True
        response.evidence_status = "not_required"
        response.reflection_reason = decision.message
        response.rag_enabled = False
        response.workflow_trace = [
            self._trace(
                "review_input_gate",
                "ReviewInputGate",
                "success",
                decision.message,
                output=decision.metadata(),
            )
        ] + response.workflow_trace
        response.extra = {
            **(response.extra or {}),
            "inputGate": decision.metadata(),
            "agentic": {
                "route": "not_applicable",
                "intent": {
                    "route": "not_applicable",
                    "intent": "non_review_input",
                    "risk_hints": [],
                    "reason_codes": [decision.reasonCode],
                    "confidence": 1.0,
                    "requires_evidence": False,
                },
                "iterations": 0,
            },
        }
        response.extra["agentic"]["finalDecision"] = self._final_decision(response)
        latency = {
            "inputGateMs": round((time.perf_counter() - started) * 1000, 2),
            "intentRouterMs": 0.0,
            "safetyGateMs": 0.0,
            "fastEligibilityMs": 0.0,
            "riskDetectionMs": 0.0,
            "evidenceQueryBuildMs": 0.0,
            "evidenceAgentMs": 0.0,
            "policyRerankerMs": 0.0,
            "reflectionMs": 0.0,
            "persistenceMs": 0.0,
        }
        return self._attach_fast_latency(response, latency, started, skip_reason="INPUT_GUIDANCE")

    @staticmethod
    def _memory_snapshot(memory: GovernanceMemory | None) -> dict[str, Any]:
        if memory is None:
            return {}
        context = memory.context()
        return {
            "structuredMemory": context["structuredMemory"],
            "iterationSummaries": context["iterationSummaries"],
            "contextBudget": context["budget"],
        }

    def _finalize_runtime(
        self,
        runtime: WorkflowRuntime,
        response: ReviewAnalyzeResponse,
        target: ReviewWorkflowState,
        memory: GovernanceMemory | None,
    ) -> None:
        response.extra = {
            **(response.extra or {}),
            "runtimeCheckpoint": {
                "id": runtime.checkpoint.id,
                "state": target.value,
                "completedNodes": [*runtime.checkpoint.completedNodes, "finalize"],
            },
        }
        runtime.finalize(response.model_dump(), target, memory=self._memory_snapshot(memory))

    @staticmethod
    def _plan(payload: ReviewAnalyzeRequest, intent: IntentDecision, max_iterations: int) -> WorkflowPlan:
        risk_types = [risk for risk in intent.risk_hints if risk != "rating_conflict"]
        if not risk_types:
            risk_types = [intent.intent] if intent.intent not in {"uncertain", "negative_feedback"} else ["negative_review"]
        queries = [
            payload.review_text[:240],
            " ".join(risk_types),
            "fake review paid incentive conflict of interest review suppression refund after-sales",
        ]
        return WorkflowPlan(
            route="strict_governance",
            risk_types=sorted(set(risk_types)),
            evidence_queries=[query for query in queries if query.strip()],
            max_iterations=max_iterations,
        )

    @staticmethod
    def _assess_execution(response: ReviewAnalyzeResponse, intent: IntentDecision, plan: WorkflowPlan) -> ExecutionAssessment:
        high_risks = {"review_suppression", "safety_or_fraud_risk", "privacy_risk", "harassment_or_abuse"}
        medium_risks = {"fake_review", "rating_manipulation", "after_sales_risk", "negative_review"}
        risk_level = response.risk_level or "low"
        if set(plan.risk_types).intersection(high_risks):
            risk_level = "high"
        elif set(plan.risk_types).intersection(medium_risks) and risk_level == "low":
            risk_level = "medium"
        need_human = risk_level == "high" or intent.route == "human_review_direct"
        route = "human_review" if need_human else "suggest_action"
        reason = (
            "High-risk signal needs evidence-backed human confirmation."
            if need_human
            else "Governance signal detected; continue evidence-backed action recommendation."
        )
        return ExecutionAssessment(
            risk_level=risk_level,
            risk_types=plan.risk_types,
            route_decision=route,
            route_reason=reason,
            need_human_review=need_human,
        )

    @staticmethod
    def _evidence_query(payload: ReviewAnalyzeRequest, plan: WorkflowPlan, iteration: int) -> str:
        if iteration <= 1:
            return " ".join(plan.evidence_queries)
        return " ".join(
            [
                payload.review_text[:240],
                " ".join(plan.risk_types),
                "policy evidence citation source section clause",
                "虚假评价 好评返现 删除差评 售后 退款 破损",
            ]
        )

    @staticmethod
    def _final_decision(response: ReviewAnalyzeResponse) -> dict[str, Any]:
        risk_assessment = (response.extra or {}).get("riskAssessment", {})
        decision = response.route_decision or ""
        automation_boundary = (
            "human_review_required"
            if response.requires_human_review
            else "advisory_only"
            if decision == "suggest_action"
            else "automatic_no_action"
            if decision in {"auto_pass", "auto_close"}
            else "deferred_or_manual"
        )
        return {
            "routeDecision": response.route_decision,
            "routeReason": response.route_reason,
            "riskLevel": response.risk_level,
            "operationalRiskLevel": response.risk_level,
            "calibratedSeverity": risk_assessment.get("severity", response.risk_level),
            "calibrationAdvisoryOnly": True,
            "advisoryOnly": decision == "suggest_action",
            "actionExecuted": False,
            "automationBoundary": automation_boundary,
            "decisionSource": "governance_workflow",
            "needHumanReview": response.need_human_review,
            "evidenceSufficient": response.evidence_sufficient,
            "evidenceStatus": response.evidence_status,
            "reflectionReason": response.reflection_reason,
            "retrievalHitCount": response.retrieval_hit_count,
        }

    def _begin_telemetry(self, payload: ReviewAnalyzeRequest, *, execution_id: str = "") -> LangfuseTelemetry:
        telemetry = LangfuseTelemetry.begin(payload, execution_id=execution_id)
        metadata = {
            "traceSchemaVersion": TRACE_SCHEMA_VERSION,
            "workflowVersion": WORKFLOW_VERSION,
            "serviceName": settings.langfuse_service_name,
            "runtimeRelease": settings.langfuse_release or TRACE_SCHEMA_VERSION,
            "routerProvider": settings.intent_router_provider,
            "routerPolicyVersion": f"intent-router-{settings.intent_router_provider}-v1",
        }
        try:
            metadata.update(self.policy_retriever.observability_metadata())
        except Exception:
            pass
        try:
            metadata.update(self.policy_reranker.observability_metadata())
        except Exception:
            pass
        telemetry.bind_metadata(metadata)
        return telemetry

    @staticmethod
    def _dedupe_evidence(items: list[Any]) -> list[Any]:
        seen = set()
        unique = []
        for item in items:
            key = item.contentHash or item.evidenceId
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _attach_latency(self, response: ReviewAnalyzeResponse, latency: dict[str, float], started: float) -> ReviewAnalyzeResponse:
        retrieval = dict(getattr(self.policy_retriever, "last_search_timings", {}) or {})
        active_dense_store = getattr(self.policy_retriever, "active_dense_store", None)
        dense_store = active_dense_store() if callable(active_dense_store) else getattr(self.policy_retriever, "dense_store", None)
        provider = dense_store.provider.metadata() if dense_store and getattr(dense_store, "provider", None) else {}
        cache_hit = bool(retrieval.get("cacheHit", False))
        latency.update({
            "embeddingQueueWaitMs": 0.0 if cache_hit else float(provider.get("queueWaitMs", 0)),
            "embeddingComputeMs": 0.0 if cache_hit else float(provider.get("embeddingComputeMs", 0)),
            "bm25Ms": float(retrieval.get("bm25Ms", 0)),
            "faissSearchMs": float(retrieval.get("faissSearchMs", 0)),
            "rrfMs": float(retrieval.get("rrfMs", 0)),
            "policyRerankerMs": float(latency.get("policyRerankerMs", 0)),
            "totalMs": round((time.perf_counter() - started) * 1000, 2),
        })
        readiness = self.policy_retriever.readiness()
        response.extra = {
            **(response.extra or {}),
            "latencyBreakdown": latency,
            "policyRetrieval": {
                "requestedMode": "hybrid",
                "actualMode": readiness.get("retrievalMode", "unavailable"),
                "fallbackReason": self.policy_retriever.last_dense_error,
                "bm25LatencyMs": latency["bm25Ms"],
            },
        }
        return response

    @staticmethod
    def _attach_fast_latency(
        response: ReviewAnalyzeResponse,
        latency: dict[str, float],
        started: float,
        *,
        skip_reason: str = "FAST_SHORT_CHAIN",
    ) -> ReviewAnalyzeResponse:
        latency.update({
            "embeddingQueueWaitMs": 0.0,
            "embeddingComputeMs": 0.0,
            "bm25Ms": 0.0,
            "faissSearchMs": 0.0,
            "rrfMs": 0.0,
            "policyRerankerMs": 0.0,
            "totalMs": round((time.perf_counter() - started) * 1000, 2),
        })
        response.extra = {
            **(response.extra or {}),
            "latencyBreakdown": latency,
            "policyRetrieval": {
                "requestedMode": "not_required",
                "actualMode": "not_executed",
                "fallbackReason": skip_reason,
                "bm25LatencyMs": 0.0,
            },
        }
        return response

    @staticmethod
    def _attach_fast_runtime(
        response: ReviewAnalyzeResponse,
        decision: FastEligibilityRuntimeDecision | None,
    ) -> None:
        if decision is None or not decision.enabled:
            return
        response.extra = {
            **(response.extra or {}),
            "fastEligibilityRuntime": {
                **decision.metadata(),
                "skipModelEnhancement": decision.executedChain == FAST_SHORT_CHAIN,
            },
        }

    @staticmethod
    def _new_memory(payload: ReviewAnalyzeRequest) -> GovernanceMemory | None:
        if not settings.agentic_memory_enabled:
            return None
        return GovernanceMemory(
            goal=f"Govern review {payload.review_id or 'pending'} with traceable policy evidence.",
            recent_turns=settings.agentic_memory_recent_turns,
            max_context_tokens=settings.agentic_memory_max_context_tokens,
        )

    @staticmethod
    def _attach_memory(response: ReviewAnalyzeResponse, memory: GovernanceMemory | None) -> None:
        if memory is None:
            return
        response.extra = {
            **(response.extra or {}),
            "agenticMemory": {
                "structuredMemory": memory.context()["structuredMemory"],
                "iterationSummaries": memory.context()["iterationSummaries"],
                "contextBudget": memory.context()["budget"],
                "diagnostics": memory.diagnostics(),
            },
        }

    def _attach_risk_assessment(
        self,
        response: ReviewAnalyzeResponse,
        payload: ReviewAnalyzeRequest,
        intent: IntentDecision,
    ) -> None:
        risk_types = response.risk_types or intent.risk_hints or ["normal_review"]
        assessment = self.risk_assessor.assess(
            risk_types=risk_types,
            raw_confidence=intent.confidence,
            reason_codes=intent.reason_codes,
            review_text=payload.review_text,
            evidence_status=response.evidence_status or "",
            model_provider=f"intent-router:{settings.intent_router_provider}",
        )
        response.extra = {**(response.extra or {}), "riskAssessment": assessment.model_dump()}

    @staticmethod
    def _trace(node: str, agent: str, status: str, message: str, *, output: Any | None = None) -> WorkflowTraceItem:
        started = time.perf_counter()
        return WorkflowTraceItem(
            node=node,
            step=node,
            agent=agent,
            agent_role=agent,
            agent_goal="Govern review risk with bounded evidence and human-review routing.",
            tool_name=agent,
            framework="agentic_planner_execution_reflection",
            status=status,
            message=message,
            output_summary=message,
            output=output,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
