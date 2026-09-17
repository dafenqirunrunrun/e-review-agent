from __future__ import annotations

from typing import Any

from app.schemas.review import (
    GovernanceAction,
    GovernanceDecision,
    GovernanceEvidenceCitation,
    GovernanceHumanReview,
    GovernanceProcessStep,
    GovernanceRiskSignal,
    GovernanceSummary,
    ReviewAnalyzeRequest,
    ReviewAnalyzeResponse,
    ReviewGovernanceContract,
)
from app.contracts.review_semantics import (
    evidence_tag_label,
    failure_reason_message,
    risk_type_description,
    risk_type_evidence_tags,
    risk_type_label,
    risk_type_severity,
)

PROCESS_LABELS = {
    "intent_router": "识别是否需要严格审核",
    "fast_eligibility_gate": "确认是否可走快速路径",
    "fast_execution": "执行快速审核",
    "light_execution": "快速完成普通评价审核",
    "planner": "拆解审核重点",
    "policy_evidence_retrieve": "查找可引用依据",
    "reflection": "核验证据是否支持结论",
    "replan": "证据不匹配后重新查找",
    "execution": "形成自动审核初判",
    "finalize": "确认最终处理方式",
    "perception": "读取评论内容",
    "retrieval": "参考历史相似案例",
    "judge": "形成初步判断",
    "audit": "检查风险等级",
    "report": "生成处理建议",
    "hybrid_rag_retrieval": "检索历史案例",
    "evidence_sufficiency": "判断依据是否充分",
    "llm_structured_analysis": "整理审核结论",
}


def attach_review_governance(payload: ReviewAnalyzeRequest, response: ReviewAnalyzeResponse) -> ReviewAnalyzeResponse:
    response.review_governance = build_review_governance(payload, response)
    return response


def build_review_governance(payload: ReviewAnalyzeRequest, response: ReviewAnalyzeResponse) -> ReviewGovernanceContract:
    decision_code = _decision_code(response)
    explicit_human_required = response.requires_human_review if response.requires_human_review is not None else response.need_human_review
    human_required = decision_code == "manual_review" or bool(explicit_human_required)
    risk_types = _risk_types(response)
    citations = _citations(response)
    reflection = _reflection(response)
    evidence_status = _evidence_status(response, citations)
    coverage = _risk_coverage(risk_types, citations, reflection)
    failure_reasons = _failure_reasons(reflection, evidence_status, risk_types, coverage)
    reflection_reason = _reflection_reason(response, evidence_status, coverage, failure_reasons)
    reason = _summary_reason(response, decision_code, reflection_reason)
    return ReviewGovernanceContract(
        governanceSchemaVersion="review-governance-v2",
        reviewId=response.review_id or payload.review_id,
        productId=response.product_id or payload.product_id,
        decision=GovernanceDecision(
            code=decision_code,
            label=_decision_label(decision_code),
            riskLevel=response.risk_level or "low",
            confidence=round(float(response.confidence or 0), 4),
            needHumanReview=human_required,
            status="待人工复核" if human_required else "已自动完成",
        ),
        summary=GovernanceSummary(
            title=_summary_title(decision_code, risk_types),
            reason=reason,
            explanation=_explanation(response, citations),
        ),
        riskTypes=risk_types,
        evidenceStatus=evidence_status,
        reflectionReason=reflection_reason,
        reflectionReasonCode=_primary_reason_code(reflection, failure_reasons, evidence_status),
        technicalReflectionReason=response.reflection_reason or str(reflection.get("technicalSummary") or ""),
        failureReasons=failure_reasons,
        riskCoverage=coverage,
        requiresHumanReview=human_required,
        riskSignals=[
            GovernanceRiskSignal(
                riskType=risk,
                label=risk_type_label(risk),
                severity=_severity(response, risk),
                matchedText=_matched_text(response, risk),
                reason=_signal_reason(risk),
                evidenceStatus=_coverage_status(risk, coverage),
                supportedBy=_coverage_supported_by(risk, coverage),
                missingEvidenceTags=_coverage_missing_tags(risk, coverage),
            )
            for risk in risk_types
        ],
        evidenceCitations=citations,
        process=_process(response),
        recommendedActions=_actions(decision_code, response),
        humanReview=GovernanceHumanReview(
            required=human_required,
            reason=reflection_reason if human_required else "当前结论和依据满足自动处理条件。",
            trigger=response.human_review_trigger,
            missingInformation=response.missing_information or [],
        ),
    )


def _decision_code(response: ReviewAnalyzeResponse) -> str:
    route = (response.route_decision or "").lower()
    if route in {"human_review", "fallback_human_review"}:
        return "manual_review"
    if route in {"suggest_action", "operation_advice"}:
        return "suggest_action"
    if route in {"auto_close", "auto_pass"}:
        return "auto_pass"
    if response.need_human_review:
        return "manual_review"
    if response.risk_level == "low" and response.confidence >= 0.7:
        return "auto_pass"
    return "suggest_action"


def _decision_label(code: str) -> str:
    return {
        "auto_pass": "自动通过",
        "suggest_action": "建议处理",
        "manual_review": "需人工复核",
    }.get(code, "建议处理")


def _summary_title(code: str, risk_types: list[str]) -> str:
    if code == "auto_pass":
        return "未发现需要拦截的风险信号"
    if risk_types:
        return risk_type_label(risk_types[0])
    return "发现需要处理的评价风险"


def _summary_reason(response: ReviewAnalyzeResponse, code: str, reflection_reason: str) -> str:
    if code == "auto_pass":
        return _default_reason(response, code)
    if code == "manual_review":
        return reflection_reason or _default_reason(response, code)
    return response.agent_suggestion.operation_advice if response.agent_suggestion else _default_reason(response, code)


def _default_reason(response: ReviewAnalyzeResponse, code: str) -> str:
    if code == "auto_pass":
        return "评论风险较低，系统已完成自动审核。"
    if code == "manual_review":
        return "当前置信度、风险等级或证据条件需要人工确认。"
    return response.agent_suggestion.operation_advice if response.agent_suggestion else "建议运营人员按审核建议处理。"


def _explanation(response: ReviewAnalyzeResponse, citations: list[GovernanceEvidenceCitation]) -> str:
    if citations:
        return "系统已将评论风险与可追溯依据进行匹配，审核人员可按编号查看引用来源。"
    if response.risk_level == "low":
        return "系统未召回必须引用的政策依据，按普通评价完成自动处理。"
    return "当前证据不足或未完全匹配风险类型，建议进入人工复核。"


def _risk_types(response: ReviewAnalyzeResponse) -> list[str]:
    extra = response.extra or {}
    values: list[str] = []
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    intent = agentic.get("intent") if isinstance(agentic.get("intent"), dict) else {}
    values.extend(_as_list(intent.get("risk_hints") or intent.get("riskHints")))
    values.extend(_as_list(extra.get("risk_types")))
    values.extend(_as_list(extra.get("risk_type")))
    if not values:
        if response.risk_level in {"high", "medium"}:
            values.append("negative_review")
        else:
            values.append("normal_review")
    seen = set()
    unique = []
    for item in values:
        if item and item != "rating_conflict" and item not in seen:
            seen.add(item)
            unique.append(item)
    if len(unique) > 1:
        unique = [item for item in unique if item not in {"normal_review", "normal_feedback"}]
    return unique or ["normal_review"]


def _citations(response: ReviewAnalyzeResponse) -> list[GovernanceEvidenceCitation]:
    records: list[dict[str, Any]] = []
    for step in response.workflow_trace or []:
        output = step.output if isinstance(step.output, dict) else {}
        policy_items = output.get("policyEvidence") if isinstance(output, dict) else None
        if isinstance(policy_items, list):
            records.extend(item for item in policy_items if isinstance(item, dict))
    citations = []
    for index, item in enumerate(records[:3], start=1):
        citations.append(
            GovernanceEvidenceCitation(
                id=f"E{index}",
                sourceName=str(item.get("sourceName") or "未知来源"),
                sourceType=str(item.get("sourceType") or "policy"),
                sourceLevel=_source_level(str(item.get("sourceType") or "")),
                sourceUrl=str(item.get("sourceUrl") or ""),
                sectionPath=[str(value) for value in item.get("sectionPath") or []],
                clauseId=str(item.get("clauseId") or ""),
                snippet=str(item.get("snippet") or "")[:220],
                riskTypes=[str(value) for value in item.get("riskTypes") or []],
                evidenceTags=[str(value) for value in item.get("evidenceTags") or []],
                contentHash=str(item.get("contentHash") or ""),
                retrieval=_retrieval(item),
            )
        )
    return citations


def _source_level(source_type: str) -> str:
    lowered = source_type.lower()
    if lowered in {"regulation", "law"}:
        return "A"
    if "platform" in lowered or "policy" in lowered:
        return "B"
    return "C"


def _process(response: ReviewAnalyzeResponse) -> list[GovernanceProcessStep]:
    steps: list[GovernanceProcessStep] = []
    seen = set()
    for item in response.workflow_trace or []:
        node = item.node or item.step or "unknown"
        if node in seen:
            continue
        seen.add(node)
        if node not in PROCESS_LABELS and len(steps) >= 5:
            continue
        steps.append(
            GovernanceProcessStep(
                order=len(steps) + 1,
                name=PROCESS_LABELS.get(node, node),
                status="完成" if item.status == "success" else "需关注",
                summary=(item.output_summary or item.message or "")[:120],
            )
        )
        if len(steps) >= 6:
            break
    return steps


def _actions(code: str, response: ReviewAnalyzeResponse) -> list[GovernanceAction]:
    if code == "auto_pass":
        return [
            GovernanceAction(code="confirm_pass", label="确认通过", style="primary"),
            GovernanceAction(code="watch", label="加入观察"),
        ]
    if code == "manual_review":
        return [
            GovernanceAction(code="open_manual_review", label="进入人工复核", style="warning", requiresHuman=True),
            GovernanceAction(code="request_more_evidence", label="要求补充证据", requiresHuman=True),
            GovernanceAction(code="override", label="人工改判", requiresHuman=True),
        ]
    return [
        GovernanceAction(code="accept_suggestion", label="采纳建议", style="primary"),
        GovernanceAction(code="manual_check", label="转人工核查", requiresHuman=True),
        GovernanceAction(code="mark_false_positive", label="标记误判"),
    ]


def _severity(response: ReviewAnalyzeResponse, risk: str) -> str:
    if risk in {"fake_review", "rating_manipulation", "review_suppression", "safety_or_fraud_risk"}:
        return "高"
    return risk_type_severity(risk, {"high": "高", "medium": "中", "low": "低"}.get(response.risk_level or "low", "中"))


def _matched_text(response: ReviewAnalyzeResponse, risk: str) -> str | None:
    for text in (response.text_evidence or []) + (response.evidence or []):
        if text:
            return str(text)[:40]
    return risk_type_label(risk)


def _signal_reason(risk: str) -> str:
    return risk_type_description(risk)


def _evidence_status(response: ReviewAnalyzeResponse, citations: list[GovernanceEvidenceCitation]) -> str:
    if response.evidence_status:
        return response.evidence_status
    if response.evidence_sufficient is True:
        return "supported"
    if response.evidence_sufficient is False:
        return "insufficient"
    return "supported" if citations else "insufficient"


def _reflection_reason(
    response: ReviewAnalyzeResponse,
    evidence_status: str,
    coverage: list[dict[str, Any]],
    failure_reasons: list[dict[str, Any]],
) -> str:
    reflection = _reflection(response)
    summary = reflection.get("summary")
    if summary and _looks_human_readable(str(summary)):
        return str(summary)
    if evidence_status == "supported":
        return "当前政策依据能够支持该风险判断。"
    if failure_reasons:
        return str(failure_reasons[0].get("message") or failure_reason_message(str(failure_reasons[0].get("code"))))
    missing = [item.get("label") for item in coverage if item.get("status") != "supported"]
    if missing:
        return "以下风险缺少对应政策依据：" + "、".join(str(item) for item in missing) + "。建议人工复核。"
    if response.evidence_sufficient is True:
        return "当前政策依据能够支持该风险判断。"
    return "证据不足或与风险类型不完全匹配，需要人工确认。"


def _retrieval(item: dict[str, Any]) -> dict[str, Any]:
    retrieval = item.get("retrieval") if isinstance(item.get("retrieval"), dict) else {}
    mode = retrieval.get("mode") or item.get("retrievalMode") or "bm25_fallback"
    score = retrieval.get("score", item.get("score", 0.0))
    try:
        score = round(float(score), 6)
    except Exception:
        score = 0.0
    return {"mode": str(mode), "score": score}


def _reflection(response: ReviewAnalyzeResponse) -> dict[str, Any]:
    extra = response.extra or {}
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    reflection = agentic.get("reflection") if isinstance(agentic.get("reflection"), dict) else {}
    return reflection


def _risk_coverage(
    risk_types: list[str],
    citations: list[GovernanceEvidenceCitation],
    reflection: dict[str, Any],
) -> list[dict[str, Any]]:
    reflected = reflection.get("riskCoverage")
    if isinstance(reflected, list) and reflected:
        return [_normalize_coverage_item(item) for item in reflected if isinstance(item, dict)]
    rows = []
    for risk in risk_types:
        required = set(risk_type_evidence_tags(risk) or (risk,))
        matched = [
            citation.id
            for citation in citations
            if set(citation.evidenceTags + citation.riskTypes).intersection(required)
        ]
        rows.append(
            {
                "riskType": risk,
                "label": risk_type_label(risk),
                "status": "supported" if matched or risk == "normal_review" else "insufficient",
                "statusText": "已支持" if matched or risk == "normal_review" else "证据不足",
                "supportedBy": matched[:3],
                "missingEvidenceTags": [] if matched or risk == "normal_review" else [evidence_tag_label(tag) for tag in sorted(required)],
            }
        )
    return rows


def _normalize_coverage_item(item: dict[str, Any]) -> dict[str, Any]:
    risk = str(item.get("riskType") or item.get("risk_type") or "")
    status = str(item.get("status") or "insufficient")
    return {
        "riskType": risk,
        "label": str(item.get("label") or risk_type_label(risk)),
        "status": status,
        "statusText": str(item.get("statusText") or ("已支持" if status == "supported" else "证据不足")),
        "supportedBy": [str(value) for value in item.get("supportedBy") or []],
        "missingEvidenceTags": [str(value) for value in item.get("missingEvidenceTags") or []],
    }


def _failure_reasons(
    reflection: dict[str, Any],
    evidence_status: str,
    risk_types: list[str],
    coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reflected = reflection.get("failureReasons")
    if isinstance(reflected, list) and reflected:
        return [
            {"code": str(item.get("code") or "UNKNOWN"), "message": str(item.get("message") or failure_reason_message(str(item.get("code") or "UNKNOWN")))}
            for item in reflected
            if isinstance(item, dict)
        ]
    if evidence_status == "supported":
        return []
    missing = [item for item in coverage if item.get("status") != "supported"]
    if evidence_status == "mismatch":
        code = "PARTIAL_RISK_COVERAGE" if len(missing) < len(risk_types) else "TAG_MISMATCH"
        message = failure_reason_message(code)
        if missing:
            message += " 缺少依据：" + "、".join(str(item.get("label")) for item in missing) + "。"
        return [{"code": code, "message": message}]
    return [{"code": "NO_EVIDENCE", "message": failure_reason_message("NO_EVIDENCE") + " 建议人工复核。"}]


def _primary_reason_code(reflection: dict[str, Any], failure_reasons: list[dict[str, Any]], evidence_status: str) -> str:
    code = reflection.get("primaryReasonCode")
    if code:
        return str(code)
    if failure_reasons:
        return str(failure_reasons[0].get("code") or "UNKNOWN")
    return "SUPPORTED" if evidence_status == "supported" else "NO_EVIDENCE"


def _coverage_status(risk: str, coverage: list[dict[str, Any]]) -> str:
    for item in coverage:
        if item.get("riskType") == risk:
            return str(item.get("status") or "insufficient")
    return "unchecked"


def _coverage_supported_by(risk: str, coverage: list[dict[str, Any]]) -> list[str]:
    for item in coverage:
        if item.get("riskType") == risk:
            return [str(value) for value in item.get("supportedBy") or []]
    return []


def _coverage_missing_tags(risk: str, coverage: list[dict[str, Any]]) -> list[str]:
    for item in coverage:
        if item.get("riskType") == risk:
            return [str(value) for value in item.get("missingEvidenceTags") or []]
    return []


def _looks_human_readable(value: str) -> bool:
    technical_tokens = ["route=", "evidenceStatus=", "Reflection unresolved", "High-risk signal", "Governance signal"]
    return not any(token in value for token in technical_tokens)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]
