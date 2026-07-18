from app.schemas.review import AgentSuggestion, ReviewAnalyzeRequest, ReviewAnalyzeResponse, WorkflowTraceItem
from app.services.base import AgentWorkflowBase, AnalyzerBase


class RuleAgentWorkflow(AgentWorkflowBase):
    def __init__(self, analyzer: AnalyzerBase):
        self.analyzer = analyzer

    def run(self, payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
        text_result = self.analyzer.analyze_text(payload)
        image_result = self.analyzer.analyze_images(payload.image_urls)
        similar_cases = self.analyzer.retrieve_similar_cases(payload)

        text_score = text_result["text_score"]
        image_score = image_result["image_score"]
        fusion_score = round(text_score * 0.72 + image_score * 0.28, 4)
        conflict_score = round(abs(text_score - image_score), 4)
        label = text_result["sentiment_label"]
        risk_level = self._risk_level(text_result, conflict_score)
        suggestion = self._suggest(payload, label, risk_level)
        suggestion.action = self._action(label, risk_level)
        suggestion.priority = risk_level
        suggestion.summary = suggestion.operation_advice

        scores = self._scores(label, fusion_score)
        evidence = (text_result["text_evidence"] + image_result["image_evidence"])[:8]
        trace = [
            self._trace_item("perception", "PerceptionAgent", "Text and image signals parsed.", "Review Analyst Agent"),
            self._trace_item("retrieval", "RetrievalAgent", "Similar review cases retrieved.", "Case Retriever Agent"),
            self._trace_item("judge", "JudgeAgent", "Sentiment label and confidence calculated.", "Review Analyst Agent"),
            self._trace_item("audit", "AuditAgent", "Risk level checked.", "Risk Auditor Agent"),
            self._trace_item("report", "ReportAgent", "Customer service and operation advice generated.", "Operation Advisor Agent"),
        ]

        return ReviewAnalyzeResponse(
            review_id=payload.review_id,
            product_id=payload.product_id,
            sentiment_label=label,
            confidence=text_result["confidence"],
            scores=scores,
            evidence=evidence,
            text_score=text_score,
            image_score=image_score,
            fusion_score=fusion_score,
            conflict_score=conflict_score,
            risk_level=risk_level,
            text_evidence=text_result["text_evidence"],
            image_evidence=image_result["image_evidence"],
            similar_cases=similar_cases,
            agent_suggestion=suggestion,
            workflow_trace=trace,
        )

    def _scores(self, label: str, fusion_score: float):
        positive = max(0.05, min(0.95, fusion_score))
        negative = max(0.05, min(0.95, 1 - fusion_score))
        neutral = max(0.05, min(0.95, 1 - abs(fusion_score - 0.5) * 2))
        if label == "positive":
            positive = max(positive, 0.72)
        elif label == "negative":
            negative = max(negative, 0.72)
        else:
            neutral = max(neutral, 0.72)
        return {
            "positive": round(positive, 4),
            "neutral": round(neutral, 4),
            "negative": round(negative, 4),
        }

    def _trace_item(self, node: str, agent: str, message: str, agent_role: str) -> WorkflowTraceItem:
        return WorkflowTraceItem(
            node=node,
            step=node,
            agent=agent,
            agent_role=agent_role,
            agent_goal=self._agent_goal(agent_role),
            status="success",
            message=message,
            output=message,
            tool_name=node,
            output_summary=message,
        )

    def _agent_goal(self, agent_role: str) -> str:
        if agent_role == "Case Retriever Agent":
            return "Retrieve historical cases and evidence snippets."
        if agent_role == "Risk Auditor Agent":
            return "Audit risk level, risk types, and review priority."
        if agent_role == "Operation Advisor Agent":
            return "Generate operation and after-sales suggestions."
        return "Analyze text, image, rating, sentiment, and confidence."

    def _risk_level(self, text_result, conflict_score: float) -> str:
        if text_result.get("risk_hits"):
            return "high"
        if conflict_score >= 0.35 or text_result["sentiment_label"] == "negative":
            return "medium"
        return "low"

    def _action(self, sentiment_label: str, risk_level: str) -> str:
        if risk_level == "high":
            return "urgent_follow_up"
        if sentiment_label == "negative":
            return "after_sales_follow_up"
        if sentiment_label == "neutral":
            return "observe_and_optimize"
        return "positive_case"

    def _suggest(self, payload: ReviewAnalyzeRequest, sentiment_label: str, risk_level: str) -> AgentSuggestion:
        if risk_level == "high":
            return AgentSuggestion(
                customer_reply="Thanks for the feedback. We have recorded this issue and will prioritize follow-up.",
                operation_advice="Review product detail copy, quality description, and recent negative-review trends.",
                after_sales_suggestion="Contact the customer proactively and offer return, exchange, or compensation according to policy.",
            )
        if sentiment_label == "negative":
            return AgentSuggestion(
                customer_reply="Sorry that this experience did not meet expectations. We will keep improving the product and service.",
                operation_advice="Track low-score reasons and add clearer usage notes or product-page reminders.",
                after_sales_suggestion="Guide the customer to provide photos and enter the after-sales workflow if needed.",
            )
        if sentiment_label == "neutral":
            return AgentSuggestion(
                customer_reply="Thanks for the honest feedback. We will share your suggestions with the operation team.",
                operation_advice="Extract both advantages and shortcomings to improve product selling points.",
                after_sales_suggestion="Provide usage guidance or FAQ links if the customer has functional questions.",
            )
        return AgentSuggestion(
            customer_reply="Thanks for your support and recognition. We welcome more experience sharing.",
            operation_advice="Use this review as a positive case for product selling-point optimization.",
            after_sales_suggestion="Keep normal after-sales observation; no escalation is required.",
        )
