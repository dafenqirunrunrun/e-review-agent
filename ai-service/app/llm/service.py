import json
import re
import time
from typing import Any, Dict, Tuple

from pydantic import ValidationError

from app.llm.config import ProviderConfig, provider_configs, selected_config
from app.llm.prompts import render_rag_review_prompt, render_repair_prompt, render_review_prompt
from app.llm.providers import OpenAICompatibleProvider, ProviderResult
from app.llm.local_qwen import LocalQwenTransformersProvider, local_qwen_status
from app.llm.schemas import ProviderStatus, ReviewRiskAnalysis, SchemaValidationResult
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse, WorkflowTraceItem
from app.services.base import AgentWorkflowBase


class LlmReviewService:
    def __init__(self, fallback_workflow: AgentWorkflowBase):
        self.fallback_workflow = fallback_workflow

    def analyze(self, payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
        fallback_response = self.fallback_workflow.run(payload)
        return self.enhance(payload, fallback_response)

    def enhance(self, payload: ReviewAnalyzeRequest, fallback_response: ReviewAnalyzeResponse) -> ReviewAnalyzeResponse:
        config = selected_config()
        rag_context = self._retrieve_rag(payload, fallback_response)
        if not config.available or config.provider_name == "local_rule_fallback":
            response = self._apply_local_fallback(fallback_response, payload, config)
            return self._apply_rag_observability(response, rag_context)

        started = time.perf_counter()
        repair_used = False
        initial_schema_error = None
        try:
            provider = self._provider(config)
            prompt_context = self._prompt_context(payload, rag_context)
            prompt = render_rag_review_prompt(prompt_context) if rag_context.get("enabled") else render_review_prompt(prompt_context)
            provider_result = provider.complete_json(prompt)
            analysis, error = self.validate_raw(provider_result.content)
            if analysis is None:
                repair_used = True
                initial_schema_error = error
                repair_result = provider.complete_json(render_repair_prompt(provider_result.content, error or "unknown validation error"))
                analysis, error = self.validate_raw(repair_result.content)
                provider_result = self._merge_usage(provider_result, repair_result)
            if analysis is None:
                response = self._apply_local_fallback(fallback_response, payload, config)
                response.repair_used = repair_used
                response.schema_error = error
                response.latency_ms = round((time.perf_counter() - started) * 1000)
                return self._apply_rag_observability(response, rag_context)
            response = self._apply_llm_result(fallback_response, analysis, config, provider_result, repair_used, initial_schema_error)
            return self._apply_rag_observability(response, rag_context)
        except Exception as exc:
            response = self._apply_local_fallback(fallback_response, payload, config)
            response.schema_error = self._safe_error(exc)
            response.latency_ms = round((time.perf_counter() - started) * 1000)
            return self._apply_rag_observability(response, rag_context)

    def provider_status(self) -> ProviderStatus:
        config = selected_config()
        local_status = local_qwen_status(config)
        usable = config.available
        if config.provider_name == "local_qwen3_transformers":
            usable = usable and local_status["local_model_available"]
        current = config.provider_name if usable else config.fallback_provider
        return ProviderStatus(
            provider_name=config.provider_name,
            base_url=config.base_url,
            model_name=config.model_name,
            api_key_env=config.api_key_env,
            api_key_available=bool(config.api_key) if config.api_key_env else True,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            enabled=config.enabled,
            fallback_provider=config.fallback_provider,
            current_provider=current,
            fallback_active=current == "local_rule_fallback",
            **local_status,
        )

    @staticmethod
    def _provider(config: ProviderConfig):
        if config.provider_name == "local_qwen3_transformers":
            return LocalQwenTransformersProvider(config)
        return OpenAICompatibleProvider(config)

    def validate_data(self, data: Dict[str, Any]) -> SchemaValidationResult:
        try:
            parsed = ReviewRiskAnalysis.model_validate(data)
            return SchemaValidationResult(valid=True, data=parsed)
        except ValidationError as exc:
            return SchemaValidationResult(valid=False, error=self._validation_error(exc))

    def repair_data(self, data: Dict[str, Any]) -> SchemaValidationResult:
        repaired = dict(data)
        repaired["risk_type"] = self._enum(
            repaired.get("risk_type"),
            {"normal_review", "negative_review", "after_sales_risk"},
            "negative_review",
        )
        repaired["risk_level"] = self._enum(repaired.get("risk_level"), {"low", "medium", "high"}, "medium")
        repaired["sentiment"] = self._enum(repaired.get("sentiment"), {"positive", "neutral", "negative"}, "neutral")
        repaired["evidence"] = self._list(repaired.get("evidence"))
        repaired["reason"] = str(repaired.get("reason") or "证据不足，已转人工复核。")
        repaired["suggestion"] = str(repaired.get("suggestion") or "请人工结合订单、图片和售后记录复核。")
        repaired["need_human_review"] = self._bool(repaired.get("need_human_review"), True)
        repaired["confidence"] = self._confidence(repaired.get("confidence"))
        repaired["missing_information"] = self._list(repaired.get("missing_information"))
        return self.validate_data(repaired)

    def validate_raw(self, raw_output: str) -> Tuple[Any, Any]:
        try:
            data = json.loads(self._extract_json(raw_output))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return None, f"invalid JSON: {exc}"
        result = self.validate_data(data)
        return result.data, result.error

    def _apply_llm_result(self, response: ReviewAnalyzeResponse, analysis: ReviewRiskAnalysis,
                          config: ProviderConfig, provider_result: ProviderResult,
                          repair_used: bool, initial_schema_error: Any = None) -> ReviewAnalyzeResponse:
        response.sentiment_label = analysis.sentiment
        response.risk_level = analysis.risk_level
        response.confidence = analysis.confidence
        response.evidence = analysis.evidence
        response.agent_suggestion.operation_advice = analysis.suggestion
        response.agent_suggestion.summary = analysis.reason
        response.llm_provider = config.provider_name
        response.model_name = config.model_name
        response.prompt_template = "review_risk_analysis_zh.md"
        response.schema_valid = True
        response.schema_error = None
        response.repair_used = repair_used
        response.fallback_used = False
        response.token_usage_input = provider_result.token_usage_input
        response.token_usage_output = provider_result.token_usage_output
        response.latency_ms = provider_result.latency_ms
        response.need_human_review = analysis.need_human_review
        response.missing_information = analysis.missing_information
        response.extra = dict(
            response.extra or {},
            risk_type=analysis.risk_type,
            llm_reason=analysis.reason,
            initial_schema_error=initial_schema_error,
        )
        tool_name = "LocalQwenTransformersTool" if config.provider_name == "local_qwen3_transformers" else "LLMProviderTool"
        self._append_trace(response, tool_name, config.provider_name, provider_result.latency_ms, "success", None)
        return response

    def _apply_local_fallback(self, response: ReviewAnalyzeResponse, payload: ReviewAnalyzeRequest,
                              requested: ProviderConfig) -> ReviewAnalyzeResponse:
        local = provider_configs()["local_rule_fallback"]
        risk_type = self._fallback_risk_type(response, payload)
        need_review = response.risk_level != "low" or response.confidence < 0.6
        response.llm_provider = local.provider_name
        response.model_name = local.model_name
        response.prompt_template = "review_risk_analysis_zh.md"
        response.schema_valid = True
        response.schema_error = None
        response.repair_used = False
        response.fallback_used = True
        response.token_usage_input = 0
        response.token_usage_output = 0
        response.latency_ms = response.latency_ms or 0
        response.need_human_review = need_review
        response.missing_information = ["缺少可验证图片或订单上下文"] if need_review and not payload.image_urls else []
        response.extra = dict(
            response.extra or {},
            risk_type=risk_type,
            requested_provider=requested.provider_name,
            engineType="rule",
            runtimeMode="public-rule",
            analyzerVersion="public-rule-v1",
            schemaVersion="2.0.0",
            fallbackUsed=response.fallback_used,
        )
        self._append_trace(response, "PublicRuleRuntimeTool", local.provider_name, 0, "success", None)
        return response

    def _prompt_context(self, payload: ReviewAnalyzeRequest, rag_context: Dict[str, object]) -> Dict[str, object]:
        return {
            "review_text": payload.review_text,
            "image_signal": ", ".join(payload.image_urls) if payload.image_urls else "未提供图片信号",
            "rating": payload.rating if payload.rating is not None else "未知",
            "product_name": payload.product_name,
            "retrieval_strategy": rag_context.get("strategy") or "disabled",
            "evidence_count": rag_context.get("hit_count") or 0,
            "retrieval_confidence": rag_context.get("top_score") or 0.0,
            "retrieved_cases": json.dumps(rag_context.get("prompt_cases") or [], ensure_ascii=False),
        }

    def _retrieve_rag(self, payload: ReviewAnalyzeRequest, fallback_response: ReviewAnalyzeResponse) -> Dict[str, object]:
        try:
            from app.rag_v2.config import load_config
            rag_config = load_config()
            enabled = payload.rag_enabled if payload.rag_enabled is not None else rag_config.enabled
            if not enabled:
                return {"enabled": False, "tool_status": "disabled", "prompt_cases": []}
            from app.rag_v2.service import rag_v2_service
            result = rag_v2_service().search({
                "query_text": payload.review_text,
                "risk_type": self._fallback_risk_type(fallback_response, payload),
                "risk_level": fallback_response.risk_level,
                "product_category": None,
                "top_k": rag_config.top_k,
                "strategy": payload.rag_strategy or rag_config.strategy,
            })
            hits = result.get("hits") or []
            prompt_cases = [{
                "case_id": row.get("case_id"), "title": row.get("title"),
                "historical_risk_type": row.get("risk_type"), "historical_risk_level": row.get("risk_level"),
                "historical_evidence": row.get("evidence"), "operation_suggestion": row.get("operation_suggestion"),
                "score": row.get("final_score"),
            } for row in hits]
            return dict(result, enabled=True, tool_status="success", prompt_cases=prompt_cases)
        except Exception as exc:
            return {
                "enabled": True, "tool_status": "failed", "prompt_cases": [], "hits": [], "hit_count": 0,
                "top_score": 0.0, "latency_ms": 0, "strategy": "unavailable",
                "error": f"{type(exc).__name__}: RAG retrieval unavailable",
            }

    def _apply_rag_observability(self, response: ReviewAnalyzeResponse,
                                 context: Dict[str, object]) -> ReviewAnalyzeResponse:
        enabled = bool(context.get("enabled"))
        response.rag_enabled = enabled
        if not enabled:
            return response
        if response.llm_provider and response.llm_provider != "local_rule_fallback":
            response.prompt_template = "review_risk_analysis_rag_zh.md"
        hits = context.get("hits") or []
        hit_count = int(context.get("hit_count") or len(hits))
        top_score = float(context.get("top_score") or 0.0)
        status = str(context.get("tool_status") or "failed")
        response.rag_strategy = str(context.get("strategy") or "unknown")
        response.retrieval_hit_count = hit_count
        response.retrieval_top_score = top_score
        response.retrieval_latency_ms = int(round(float(context.get("latency_ms") or 0)))
        response.embedding_provider = str(context.get("embedding_provider") or "bge_m3")
        response.reranker_provider = str(context.get("reranker_provider") or "none")
        response.retrieved_case_ids = [str(row.get("case_id")) for row in hits if row.get("case_id")]
        response.retrieval_query_summary = "评论风险检索查询（内容已截断）"
        evidence_count = len(response.evidence or [])
        response.evidence_sufficient = evidence_count > 0 and hit_count > 0 and status == "success"
        if response.risk_level == "high":
            route, reason, trigger = "human_review", "高风险必须人工复核", "high_risk"
        elif status != "success":
            route, reason, trigger = "fallback_human_review", "检索工具失败，使用降级结果并人工复核", "tool_failed"
        elif evidence_count == 0:
            route, reason, trigger = "human_review", "当前评论证据为空", "no_evidence"
        elif response.risk_level == "medium" and top_score < 0.35:
            route, reason, trigger = "human_review", "中风险且检索置信度较低", "low_retrieval_score"
        elif response.risk_level == "low" and response.confidence >= 0.75 and response.evidence_sufficient:
            route, reason, trigger = "operation_advice", "低风险且证据与检索结果充分", "none"
        else:
            route, reason, trigger = "human_review", "置信度或证据条件未满足自动建议门槛", "confidence_or_evidence"
        response.route_decision = route
        response.route_reason = reason
        response.human_review_trigger = trigger
        if route != "operation_advice":
            response.need_human_review = True
        response.workflow_trace.append(WorkflowTraceItem(
            node="hybrid_rag_retrieval", step="hybrid_rag_retrieval", agent="RetrievalAgent",
            agent_role="Case Retriever Agent", agent_goal="检索相似历史案例并保留证据边界",
            tool_name="HybridRagRetrieverTool", status=status,
            provider=response.embedding_provider,
            message=f"strategy={response.rag_strategy}, hits={hit_count}, top_score={top_score:.4f}",
            input_summary="评论检索摘要（不保存完整评论）",
            output_summary=f"case_ids={','.join(response.retrieved_case_ids[:5])}",
            output={
                "query_summary": "评论检索摘要（不保存完整评论）",
                "strategy": response.rag_strategy,
                "candidate_count": int(context.get("candidate_count") or 0),
                "hit_count": hit_count,
                "top_score": top_score,
                "case_ids": response.retrieved_case_ids[:5],
                "latency_ms": response.retrieval_latency_ms,
            },
            error=context.get("error"), duration_ms=response.retrieval_latency_ms,
        ))
        if response.reranker_provider not in {"none", ""}:
            response.workflow_trace.append(WorkflowTraceItem(
                node="rerank", step="rerank", agent="RetrievalAgent", agent_role="Case Retriever Agent",
                agent_goal="重排候选案例", tool_name="RerankerTool", status=status,
                provider=response.reranker_provider,
                message=f"provider={response.reranker_provider}", input_summary=f"candidate_count={context.get('candidate_count') or 0}",
                output_summary=f"hit_count={hit_count}",
                output={"provider": response.reranker_provider, "candidate_count": int(context.get("candidate_count") or 0), "hit_count": hit_count},
                duration_ms=0,
            ))
        response.workflow_trace.append(WorkflowTraceItem(
            node="evidence_sufficiency", step="evidence_sufficiency", agent="AuditAgent",
            agent_role="Risk Auditor Agent", agent_goal="判断当前证据与检索结果是否足够",
            tool_name="EvidenceSufficiencyTool", status="success", message=reason,
            input_summary=f"evidence_count={evidence_count}, hit_count={hit_count}",
            output_summary=f"route={route}, sufficient={response.evidence_sufficient}",
            output={"route_decision": route, "route_reason": reason, "evidence_sufficient": response.evidence_sufficient,
                    "human_review_trigger": trigger}, duration_ms=0,
        ))
        return response

    def _append_trace(self, response: ReviewAnalyzeResponse, tool_name: str, provider: str,
                      latency_ms: int, status: str, error: Any) -> None:
        response.workflow_trace.append(WorkflowTraceItem(
            node="llm_structured_analysis",
            step="llm_structured_analysis",
            agent="LLMReviewRiskAgent",
            agent_role="Risk Auditor Agent",
            agent_goal="生成可校验的风险解释和运营建议",
            tool_name=tool_name,
            provider=provider,
            framework="openai_compatible_provider",
            status=status,
            message=f"provider={provider}, schema_valid={response.schema_valid}",
            input_summary="评论文本、评分和图片信号摘要",
            output_summary=f"risk={response.risk_level}, human_review={response.need_human_review}",
            error=error,
            duration_ms=latency_ms,
        ))

    @staticmethod
    def _extract_json(value: str) -> str:
        text = value.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r"^.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("JSON object not found")
        return text[start:end + 1]

    @staticmethod
    def _merge_usage(first: ProviderResult, second: ProviderResult) -> ProviderResult:
        return ProviderResult(
            content=second.content,
            token_usage_input=(first.token_usage_input or 0) + (second.token_usage_input or 0),
            token_usage_output=(first.token_usage_output or 0) + (second.token_usage_output or 0),
            latency_ms=first.latency_ms + second.latency_ms,
        )

    @staticmethod
    def _validation_error(exc: ValidationError) -> str:
        return "; ".join(f"{'.'.join(map(str, row['loc']))}: {row['msg']}" for row in exc.errors())[:1000]

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc)
        if message.startswith("LOCAL_QWEN_"):
            return message[:160]
        return f"{type(exc).__name__}: provider unavailable or output invalid"[:1000]

    @staticmethod
    def _enum(value: Any, allowed: set, default: str) -> str:
        text = str(value or "").lower()
        return text if text in allowed else default

    @staticmethod
    def _list(value: Any):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.strip().lower() in {"true", "1", "yes"}:
                return True
            if value.strip().lower() in {"false", "0", "no"}:
                return False
        return default

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _fallback_risk_type(response: ReviewAnalyzeResponse, payload: ReviewAnalyzeRequest) -> str:
        text = payload.review_text.lower()
        if any(word in text for word in ["退款", "退货", "破损", "漏液", "爆炸", "售后"]):
            return "after_sales_risk"
        if response.conflict_score >= 0.35:
            return "modality_conflict"
        if response.confidence < 0.6:
            return "low_confidence"
        if response.sentiment_label == "negative":
            return "negative_review"
        return "normal_review"
