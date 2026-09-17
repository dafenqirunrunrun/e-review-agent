from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskTypeDefinition:
    code: str
    label: str
    description: str
    severity: str
    default_action: str
    evidence_tags: tuple[str, ...]


RISK_TYPE_REGISTRY: dict[str, RiskTypeDefinition] = {
    "fake_review": RiskTypeDefinition(
        code="fake_review",
        label="虚假评价",
        description="评论可能并非真实消费体验，或存在编造、组织化发布等迹象。",
        severity="高",
        default_action="进入人工复核，确认是否需要限制展示或进一步调查。",
        evidence_tags=("fake_engagement", "fake_review", "incentivized_review", "rating_manipulation"),
    ),
    "rating_manipulation": RiskTypeDefinition(
        code="rating_manipulation",
        label="评分操纵",
        description="通过返现、截图、集中打分等方式影响评分真实性。",
        severity="高",
        default_action="保留证据并进入人工复核，避免直接按普通好评处理。",
        evidence_tags=("incentivized_review", "rating_manipulation", "fake_engagement", "paid_review"),
    ),
    "paid_review": RiskTypeDefinition(
        code="paid_review",
        label="有偿评价",
        description="评论可能受到现金、返利、赠品或其他利益驱动。",
        severity="高",
        default_action="核对活动与客服记录，必要时转人工复核。",
        evidence_tags=("paid_review", "incentivized_review", "rating_manipulation"),
    ),
    "review_suppression": RiskTypeDefinition(
        code="review_suppression",
        label="压制差评",
        description="存在删除、屏蔽、威胁或干预用户负面评价展示的风险。",
        severity="高",
        default_action="转人工复核，检查评价展示、客服沟通和平台规则。",
        evidence_tags=("review_suppression",),
    ),
    "after_sales_risk": RiskTypeDefinition(
        code="after_sales_risk",
        label="售后争议",
        description="评论集中在退款、退货、破损、质量问题或售后处理争议。",
        severity="中",
        default_action="转售后或人工复核，结合订单和物流记录确认处理方式。",
        evidence_tags=("after_sales", "after_sales_risk", "consumer_rights"),
    ),
    "safety_or_fraud_risk": RiskTypeDefinition(
        code="safety_or_fraud_risk",
        label="安全或欺诈",
        description="评论涉及人身安全、商品安全、假货、欺诈或重大误导。",
        severity="高",
        default_action="优先人工复核，必要时升级安全治理处理。",
        evidence_tags=("safety_or_fraud", "safety_or_fraud_risk", "fraud", "safety"),
    ),
    "privacy_risk": RiskTypeDefinition(
        code="privacy_risk",
        label="隐私风险",
        description="评论包含个人信息、隐私泄露或敏感身份信息。",
        severity="高",
        default_action="人工确认后再决定是否隐藏敏感内容。",
        evidence_tags=("privacy", "personal_information"),
    ),
    "harassment_or_abuse": RiskTypeDefinition(
        code="harassment_or_abuse",
        label="骚扰威胁",
        description="评论或上下文包含威胁、辱骂、骚扰或攻击性表达。",
        severity="高",
        default_action="人工复核后按平台治理规则处理。",
        evidence_tags=("harassment_or_abuse", "harassment", "abuse"),
    ),
    "negative_review": RiskTypeDefinition(
        code="negative_review",
        label="负向体验",
        description="评论表达不满，但未必构成需要政策依据支撑的治理风险。",
        severity="中",
        default_action="结合订单和售后情况跟进。",
        evidence_tags=("negative_review",),
    ),
    "normal_review": RiskTypeDefinition(
        code="normal_review",
        label="普通评价",
        description="未发现需要严格治理的风险信号。",
        severity="低",
        default_action="自动通过或正常展示。",
        evidence_tags=(),
    ),
    "rating_conflict": RiskTypeDefinition(
        code="rating_conflict",
        label="评分与内容不一致",
        description="星级与评论文本情绪不一致，需要确认是否误打分或误判。",
        severity="中",
        default_action="进入人工确认或观察。",
        evidence_tags=("rating_conflict",),
    ),
    "low_confidence": RiskTypeDefinition(
        code="low_confidence",
        label="低置信度",
        description="当前信息不足，系统无法形成稳定判断。",
        severity="中",
        default_action="人工复核或补充订单、图片、售后信息。",
        evidence_tags=("low_confidence",),
    ),
    "modality_conflict": RiskTypeDefinition(
        code="modality_conflict",
        label="图文信息冲突",
        description="图片、文本、评分之间存在明显不一致。",
        severity="中",
        default_action="人工查看图片与订单上下文。",
        evidence_tags=("modality_conflict",),
    ),
    "fake_review_suspected": RiskTypeDefinition(
        code="fake_review_suspected",
        label="疑似虚假评价",
        description="存在虚假评价迹象，但证据强度不足。",
        severity="中",
        default_action="进入人工确认，不直接强处置。",
        evidence_tags=("fake_engagement", "fake_review"),
    ),
    "other": RiskTypeDefinition(
        code="other",
        label="其他风险",
        description="系统识别到需要运营关注的其他风险。",
        severity="中",
        default_action="人工查看详情后处理。",
        evidence_tags=(),
    ),
}


EVIDENCE_TAG_LABELS = {
    "fake_engagement": "虚假参与",
    "fake_review": "虚假评价",
    "incentivized_review": "利益诱导评价",
    "paid_review": "有偿评价",
    "rating_manipulation": "评分操纵",
    "review_suppression": "压制差评",
    "after_sales": "售后争议",
    "after_sales_risk": "售后争议",
    "consumer_rights": "消费者权益",
    "privacy": "隐私信息",
    "personal_information": "个人信息",
    "harassment_or_abuse": "骚扰威胁",
    "safety_or_fraud": "安全或欺诈",
    "safety_or_fraud_risk": "安全或欺诈",
    "rating_conflict": "评分冲突",
    "modality_conflict": "图文冲突",
    "low_confidence": "低置信度",
}


FAILURE_REASON_LABELS = {
    "NO_EVIDENCE": "当前没有召回可验证政策依据。",
    "PARTIAL_RISK_COVERAGE": "部分风险类型缺少对应政策依据。",
    "TAG_MISMATCH": "召回政策与当前风险类型不一致。",
    "CITATION_INCOMPLETE": "政策依据的来源、条款路径或内容哈希不完整。",
    "SOURCE_INVALID": "召回结果包含无效政策来源。",
    "RETRIEVAL_FAILED": "政策检索暂时失败，已降级为人工复核。",
    "LOW_CONFIDENCE": "系统置信度偏低，需要人工确认。",
    "UNSUPPORTED_ACTION": "当前建议动作需要人工确认后才能执行。",
}


EVIDENCE_STATUS_LABELS = {
    "supported": "证据充分",
    "insufficient": "证据不足",
    "mismatch": "证据不匹配",
}


def risk_type_definition(code: str) -> RiskTypeDefinition:
    return RISK_TYPE_REGISTRY.get(code) or RiskTypeDefinition(
        code=code,
        label=code,
        description="未登记的风险类型，请结合审核上下文确认。",
        severity="中",
        default_action="人工查看后处理。",
        evidence_tags=(),
    )


def risk_type_label(code: str) -> str:
    return risk_type_definition(code).label


def risk_type_description(code: str) -> str:
    return risk_type_definition(code).description


def risk_type_severity(code: str, fallback: str = "中") -> str:
    definition = RISK_TYPE_REGISTRY.get(code)
    return definition.severity if definition else fallback


def risk_type_evidence_tags(code: str) -> tuple[str, ...]:
    return risk_type_definition(code).evidence_tags


def evidence_tag_label(code: str) -> str:
    return EVIDENCE_TAG_LABELS.get(code, risk_type_label(code))


def failure_reason_message(code: str) -> str:
    return FAILURE_REASON_LABELS.get(code, code)
