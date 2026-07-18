import time
from pathlib import Path
from typing import Any, Dict, List

from app.schemas.review import AgentSuggestion, ReviewAnalyzeRequest
from app.services.base import AnalyzerBase
from app.vlm.service import vlm_service


class ToolResult(dict):
    pass


class AgentTool:
    name = "AgentTool"
    agent_role = "Review Analyst Agent"
    agent_goal = "Analyze review context and produce explainable signals."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        step = {
            "node": self.name,
            "step": self.name,
            "agent": "LangGraphReviewAgent",
            "agent_role": self.agent_role,
            "agent_goal": self.agent_goal,
            "tool_name": self.name,
            "framework": state.get("framework", "fallback_rule_graph"),
            "status": "success",
            "input_summary": self.input_summary(state),
            "message": "",
        }
        try:
            updates = self.run(state)
            state.update(updates)
            step["output_summary"] = self.output_summary(updates)
            step["output"] = updates.get("rag_trace", step["output_summary"])
            step["message"] = step["output_summary"]
        except Exception as exc:
            step["status"] = "failed"
            step["error"] = str(exc)
            step["message"] = str(exc)
            state["error_message"] = str(exc)
            raise
        finally:
            step["duration_ms"] = int((time.perf_counter() - started) * 1000)
            state.setdefault("trace_steps", []).append(step)
        return state

    def input_summary(self, state: Dict[str, Any]) -> str:
        return str(state.get("review_id") or state.get("payload", {}).review_id)

    def output_summary(self, updates: Dict[str, Any]) -> str:
        return ", ".join(updates.keys()) or "no updates"


class ReviewContextTool(AgentTool):
    name = "load_comment_context"
    agent_role = "Review Analyst Agent"
    agent_goal = "Load comment, product, rating, and image context."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        payload: ReviewAnalyzeRequest = state["payload"]
        return ToolResult(
            review_id=payload.review_id,
            product_id=payload.product_id,
            product_name=payload.product_name,
            rating=payload.rating,
            review_text=payload.review_text,
            image_url=payload.image_urls[0] if payload.image_urls else None,
        )

    def output_summary(self, updates: Dict[str, Any]) -> str:
        return "review context loaded"


class TextSentimentTool(AgentTool):
    name = "text_sentiment_analysis"
    agent_role = "Review Analyst Agent"
    agent_goal = "Classify sentiment and extract text evidence."

    def __init__(self, analyzer: AnalyzerBase):
        self.analyzer = analyzer

    def run(self, state: Dict[str, Any]) -> ToolResult:
        return ToolResult(text_signal=self.analyzer.analyze_text(state["payload"]))

    def output_summary(self, updates: Dict[str, Any]) -> str:
        signal = updates["text_signal"]
        return f"{signal.get('sentiment_label')} score={signal.get('text_score')}"


class ImageSignalTool(AgentTool):
    name = "image_signal_extract"
    agent_role = "Review Analyst Agent"
    agent_goal = "Extract image and URL signals for multimodal judgment."

    def __init__(self, analyzer: AnalyzerBase):
        self.analyzer = analyzer

    def run(self, state: Dict[str, Any]) -> ToolResult:
        payload: ReviewAnalyzeRequest = state["payload"]
        local_images = [path for path in payload.image_urls if Path(path).exists()]
        if local_images:
            visual = vlm_service().analyze(
                {
                    "image_paths": [local_images[0]],
                    "review_text": payload.review_text,
                    "product_name": payload.product_name,
                }
            )
            image_score = {"high": 0.22, "medium": 0.38, "low": 0.72, "uncertain": 0.5}.get(
                visual.visual_risk_level,
                0.5,
            )
            evidence = list(visual.visual_evidence or [])
            if not evidence and visual.visual_findings:
                evidence = [finding.description for finding in visual.visual_findings[:3]]
            if not evidence:
                evidence = ["real local VLM image inference completed; no specific visual evidence extracted"]
            return ToolResult(
                image_signal={
                    "image_score": round(image_score, 4),
                    "image_evidence": evidence[:5],
                    "visual_schema_valid": visual.schema_valid,
                    "visual_fallback_used": visual.fallback_used,
                    "visual_latency_ms": visual.latency_ms,
                    "vlm_provider": visual.provider_name,
                    "vlm_model_name": visual.model_name,
                    "real_inference": visual.real_inference,
                    "cuda_used": visual.cuda_used,
                    "gpu_peak_memory_mb": visual.gpu_peak_memory_mb,
                },
                visual_observability={
                    "multimodal_enabled": True,
                    "image_count": len(local_images),
                    "vlm_provider": visual.provider_name,
                    "vlm_model_name": visual.model_name,
                    "visual_schema_valid": visual.schema_valid,
                    "visual_fallback_used": visual.fallback_used,
                    "visual_latency_ms": visual.latency_ms,
                    "visual_evidence_count": len(evidence),
                    "real_inference": visual.real_inference,
                    "cuda_used": visual.cuda_used,
                    "gpu_peak_memory_mb": visual.gpu_peak_memory_mb,
                },
            )
        image_signal = self.analyzer.analyze_images(payload.image_urls)
        risk_words = ["broken", "damage", "refund", "after-sales", "crack", "defect", "\u7834\u635f", "\u9000\u6b3e", "\u552e\u540e"]
        joined = " ".join(payload.image_urls).lower()
        if any(word in joined for word in risk_words):
            image_signal["image_score"] = min(image_signal.get("image_score", 0.5), 0.28)
            image_signal.setdefault("image_evidence", []).append("image_url indicates possible after-sales or damage risk")
        return ToolResult(image_signal=image_signal)

    def output_summary(self, updates: Dict[str, Any]) -> str:
        image = updates["image_signal"]
        if image.get("real_inference"):
            return f"image_score={image.get('image_score')}, real_inference=true, provider={image.get('vlm_provider')}"
        return f"image_score={image.get('image_score')}"


class RatingSignalTool(AgentTool):
    name = "rating_signal_extract"
    agent_role = "Review Analyst Agent"
    agent_goal = "Convert star rating into a confidence signal."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        rating = state.get("rating")
        score = 0.6 if rating is None else max(0.05, min(0.95, rating / 5))
        label = "positive" if score >= 0.7 else "negative" if score <= 0.4 else "neutral"
        return ToolResult(rating_signal={"rating_score": round(score, 4), "rating_label": label})


class ModalityConflictTool(AgentTool):
    name = "modality_conflict_check"
    agent_role = "Risk Auditor Agent"
    agent_goal = "Detect conflict across text, image, and rating signals."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        text = state.get("text_signal", {})
        image = state.get("image_signal", {})
        rating = state.get("rating_signal", {})
        text_score = float(text.get("text_score", 0.5))
        image_score = float(image.get("image_score", 0.5))
        rating_score = float(rating.get("rating_score", 0.5))
        conflicts: List[str] = []
        evidence: List[str] = []
        if abs(text_score - rating_score) >= 0.35:
            conflicts.append("text_rating_conflict")
            evidence.append(f"text_score={text_score}, rating_score={rating_score}")
        if abs(text_score - image_score) >= 0.35:
            conflicts.append("text_image_conflict")
            evidence.append(f"text_score={text_score}, image_score={image_score}")
        if abs(rating_score - image_score) >= 0.35:
            conflicts.append("rating_image_conflict")
            evidence.append(f"rating_score={rating_score}, image_score={image_score}")
        conflict_score = round(max(abs(text_score - rating_score), abs(text_score - image_score), abs(rating_score - image_score)), 4)
        return ToolResult(modality_conflict={
            "conflict_score": conflict_score,
            "conflict_types": conflicts,
            "conflict_evidence": evidence,
            "explanation": "No obvious modality conflict." if not conflicts else "Signals disagree across text, image, or rating.",
        }, modality_conflict_score=conflict_score)

    def output_summary(self, updates: Dict[str, Any]) -> str:
        conflict = updates["modality_conflict"]
        return f"conflict_score={conflict['conflict_score']}, types={','.join(conflict['conflict_types']) or 'none'}"


class DominantModalityTool(AgentTool):
    name = "dominant_modality_check"
    agent_role = "Risk Auditor Agent"
    agent_goal = "Select the dominant modality and adjust confidence."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        text_score = float(state.get("text_signal", {}).get("text_score", 0.5))
        image_score = float(state.get("image_signal", {}).get("image_score", 0.5))
        rating_score = float(state.get("rating_signal", {}).get("rating_score", 0.5))
        scores = {"text": text_score, "image": image_score, "rating": rating_score}
        dominant = max(scores, key=lambda key: abs(scores[key] - 0.5))
        dominance_score = round(abs(scores[dominant] - 0.5) * 2, 4)
        conflict_score = float(state.get("modality_conflict_score", 0))
        final_confidence = round(max(0.35, min(0.95, 0.78 - conflict_score * 0.45 + dominance_score * 0.1)), 4)
        return ToolResult(dominant_modality={
            "dominant_modality": dominant,
            "dominance_score": dominance_score,
            "adjustment_reason": "confidence reduced by modality conflict" if conflict_score >= 0.35 else "signals are sufficiently aligned",
            "final_confidence": final_confidence,
            "review_required": conflict_score >= 0.35 or final_confidence < 0.55,
        })

    def output_summary(self, updates: Dict[str, Any]) -> str:
        dominant = updates["dominant_modality"]
        return f"dominant={dominant['dominant_modality']}, final_confidence={dominant['final_confidence']}"


class SimilarCaseTool(AgentTool):
    name = "similar_case_retrieve"
    agent_role = "Case Retriever Agent"
    agent_goal = "Retrieve similar historical cases for Agentic RAG evidence."

    def __init__(self, analyzer: AnalyzerBase):
        self.analyzer = analyzer

    def run(self, state: Dict[str, Any]) -> ToolResult:
        cases = self.analyzer.retrieve_similar_cases(state["payload"])
        return ToolResult(similar_cases=cases, rag_trace=self._trace(cases))

    def output_summary(self, updates: Dict[str, Any]) -> str:
        cases = updates.get("similar_cases") or []
        if not cases:
            return "No similar cases found; continue with rule decision."
        return f"retrieved {len(cases)} similar cases by local case memory"

    def _trace(self, cases: List[Any]) -> Dict[str, Any]:
        rows = [case.model_dump() if hasattr(case, "model_dump") else dict(case) for case in (cases or [])]
        return {
            "retrieved_case_ids": [row.get("case_id") for row in rows],
            "case_titles": [row.get("case_title") or row.get("label") for row in rows],
            "match_scores": [row.get("similarity") for row in rows],
            "evidence_snippets": [row.get("reason") or row.get("review_text") for row in rows],
            "retrieval_mode": "local_keyword",
            "empty_retrieval": len(rows) == 0,
        }


class RiskDecisionTool(AgentTool):
    name = "risk_decision"
    agent_role = "Risk Auditor Agent"
    agent_goal = "Decide risk level, risk types, and escalation priority."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        text = state.get("text_signal", {})
        conflict = state.get("modality_conflict", {})
        dominant = state.get("dominant_modality", {})
        risk_types = list(text.get("risk_hits") or [])
        if conflict.get("conflict_types"):
            risk_types.append("modality_conflict")
        if dominant.get("review_required"):
            risk_types.append("low_confidence")
        label = text.get("sentiment_label", "neutral")
        if risk_types:
            risk_level = "high" if "modality_conflict" in risk_types or text.get("risk_hits") else "medium"
        elif label == "negative":
            risk_level = "medium"
        else:
            risk_level = "low"
        return ToolResult(
            sentiment_label=label,
            confidence=dominant.get("final_confidence", text.get("confidence", 0.68)),
            risk_types=risk_types,
            risk_level=risk_level,
        )


class OperationSuggestionTool(AgentTool):
    name = "operation_suggestion"
    agent_role = "Operation Advisor Agent"
    agent_goal = "Generate customer-service, operation, and after-sales advice."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        risk_level = state.get("risk_level", "low")
        label = state.get("sentiment_label", "neutral")
        if risk_level == "high":
            suggestion = AgentSuggestion(
                customer_reply="Thanks for the feedback. We have recorded this issue and will prioritize follow-up.",
                operation_advice="Route this review to customer service, verify product batch and after-sales records.",
                after_sales_suggestion="Contact the customer proactively and offer return, exchange, or compensation according to policy.",
                action="urgent_follow_up",
                priority="high",
                summary="High-risk review with conflict or after-sales signal.",
            )
        elif label == "negative":
            suggestion = AgentSuggestion(
                customer_reply="Sorry that this experience did not meet expectations. We will keep improving the product and service.",
                operation_advice="Track low-score reasons and update product page FAQ.",
                after_sales_suggestion="Guide the customer to provide photos and enter after-sales workflow if needed.",
                action="after_sales_follow_up",
                priority="medium",
                summary="Negative review needs follow-up.",
            )
        else:
            suggestion = AgentSuggestion(
                customer_reply="Thanks for your feedback. We will continue optimizing the product experience.",
                operation_advice="Use this feedback to refine product selling points and service notes.",
                after_sales_suggestion="No escalation required; keep normal observation.",
                action="observe_and_optimize",
                priority=risk_level,
                summary="No urgent risk detected.",
            )
        return ToolResult(suggestions=suggestion.model_dump())


class FinalReportTool(AgentTool):
    name = "final_report"
    agent_role = "Operation Advisor Agent"
    agent_goal = "Assemble the final explainable report and evidence."

    def run(self, state: Dict[str, Any]) -> ToolResult:
        text = state.get("text_signal", {})
        image = state.get("image_signal", {})
        evidence = (text.get("text_evidence", []) + image.get("image_evidence", []))[:8]
        return ToolResult(evidence=evidence)
