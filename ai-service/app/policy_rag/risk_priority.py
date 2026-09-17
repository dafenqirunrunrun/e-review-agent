from __future__ import annotations

from dataclasses import dataclass

from app.contracts.review_semantics import risk_type_label


SUPPORTED_RISKS = (
    "fake_review",
    "rating_manipulation",
    "review_suppression",
    "privacy_risk",
    "after_sales_risk",
    "safety_or_fraud_risk",
    "harassment_or_abuse",
)


# These are business-event cues, not a second risk detector. The function only
# orders risk types already emitted by the upstream risk analysis.
RISK_CUES: dict[str, tuple[tuple[str, float], ...]] = {
    "fake_review": (
        ("没买过", 5.0),
        ("没有下单", 5.0),
        ("未购买", 5.0),
        ("冒充", 4.0),
        ("水军", 4.0),
        ("刷单", 4.0),
        ("小号", 3.0),
        ("多账号", 3.0),
        ("批量发布", 3.0),
        ("复制模板", 3.0),
        ("复制这段", 3.0),
        ("编造", 3.0),
        ("虚假体验", 3.0),
    ),
    "rating_manipulation": (
        ("好评返现", 5.0),
        ("五星返现", 5.0),
        ("五星截图", 4.0),
        ("改成五星", 4.0),
        ("改成好评", 4.0),
        ("提高评分", 4.0),
        ("返现", 3.0),
        ("红包", 3.0),
        ("奖励", 2.5),
        ("话费", 2.5),
        ("赠品", 2.0),
        ("优惠券", 2.0),
        ("满分", 2.0),
        ("五星", 1.5),
    ),
    "review_suppression": (
        ("删除差评", 5.0),
        ("删掉差评", 5.0),
        ("删除评价", 4.0),
        ("删掉评价", 4.0),
        ("屏蔽评价", 4.0),
        ("隐藏评价", 4.0),
        ("下架评论", 4.0),
        ("撤回评价", 3.5),
        ("不展示", 3.0),
        ("压制", 3.0),
        ("差评", 1.0),
    ),
    "privacy_risk": (
        ("公开地址", 5.0),
        ("曝光地址", 5.0),
        ("泄露地址", 5.0),
        ("公开电话", 5.0),
        ("曝光电话", 5.0),
        ("身份证", 4.0),
        ("家庭住址", 4.0),
        ("个人信息", 3.5),
        ("隐私", 3.0),
        ("住址", 2.5),
        ("手机号", 2.5),
        ("人肉", 4.0),
    ),
    "after_sales_risk": (
        ("拒绝退款", 4.0),
        ("拒绝退货", 4.0),
        ("不予赔偿", 4.0),
        ("售后入口", 4.0),
        ("退款", 3.0),
        ("退货", 3.0),
        ("换货", 3.0),
        ("赔偿", 3.0),
        ("保修", 2.5),
        ("售后", 2.5),
        ("客服", 1.0),
    ),
    "safety_or_fraud_risk": (
        ("冒烟", 5.0),
        ("起火", 5.0),
        ("漏电", 5.0),
        ("爆炸", 5.0),
        ("烫伤", 5.0),
        ("人身安全", 5.0),
        ("假药", 5.0),
        ("假货", 4.0),
        ("骗我转账", 5.0),
        ("诱导转账", 5.0),
        ("欺诈", 4.0),
        ("诈骗", 4.0),
        ("转账", 3.0),
        ("危险", 3.0),
        ("安全问题", 3.0),
        ("发热", 2.5),
    ),
    "harassment_or_abuse": (
        ("人身威胁", 5.0),
        ("威胁上门", 5.0),
        ("上门找", 5.0),
        ("堵门", 5.0),
        ("恐吓", 4.0),
        ("威胁", 4.0),
        ("骚扰", 3.5),
        ("辱骂", 3.0),
        ("人身攻击", 3.0),
        ("不停打电话", 3.0),
    ),
}


PRIMARY_QUERY_TERMS = {
    "fake_review": "虚假评价 未真实购买 冒充消费者 编造体验 刷单",
    "rating_manipulation": "评分操纵 好评返现 五星奖励 有偿评价",
    "review_suppression": "删除差评 屏蔽评价 压制负面评价",
    "privacy_risk": "隐私泄露 公开个人信息 地址 电话 身份信息",
    "after_sales_risk": "售后争议 退款 退货 赔偿 质量担保",
    "safety_or_fraud_risk": "商品安全 人身财产安全 假货 欺诈 交易安全",
    "harassment_or_abuse": "骚扰 威胁 恐吓 辱骂 人身攻击",
}


# Used only when the text provides no differentiating event evidence.
TIE_BREAK_ORDER = {
    "safety_or_fraud_risk": 7,
    "privacy_risk": 6,
    "harassment_or_abuse": 5,
    "review_suppression": 4,
    "fake_review": 3,
    "rating_manipulation": 2,
    "after_sales_risk": 1,
}


@dataclass(frozen=True)
class RiskPriorityDecision:
    primary_risk_type: str
    secondary_risk_types: tuple[str, ...]
    scores: dict[str, float]
    reason_codes: tuple[str, ...]
    ambiguous: bool


def prioritize_risks(risk_types: list[str] | tuple[str, ...], review_text: str) -> RiskPriorityDecision:
    candidates = sorted({risk for risk in risk_types if risk in SUPPORTED_RISKS})
    if not candidates:
        return RiskPriorityDecision("normal_review", (), {}, ("NO_GOVERNANCE_RISK",), False)
    if len(candidates) == 1:
        return RiskPriorityDecision(candidates[0], (), {candidates[0]: 1.0}, ("SINGLE_RISK",), False)

    text = (review_text or "").lower()
    scores = {
        risk: round(sum(weight for cue, weight in RISK_CUES.get(risk, ()) if cue in text), 3)
        for risk in candidates
    }

    # A completed suppression action is the governed event; a threat to obtain
    # deletion remains harassment-first unless deletion is described as done.
    if "review_suppression" in scores and any(
        cue in text for cue in ("已经删除", "已删除", "被删除", "已经屏蔽", "被屏蔽", "已经下架", "被下架")
    ):
        scores["review_suppression"] += 3.0
    if "harassment_or_abuse" in scores and any(
        cue in text for cue in ("威胁上门", "上门找", "堵门", "人身威胁", "恐吓")
    ):
        scores["harassment_or_abuse"] += 3.0
    if "privacy_risk" in scores and any(
        cue in text for cue in ("公开", "曝光", "泄露", "发出")
    ) and any(cue in text for cue in ("地址", "住址", "电话", "手机号", "身份证", "个人信息")):
        scores["privacy_risk"] += 3.0
    if "safety_or_fraud_risk" in scores and any(
        cue in text for cue in ("冒烟", "起火", "漏电", "爆炸", "烫伤", "假药", "诈骗", "骗我转账")
    ):
        scores["safety_or_fraud_risk"] += 3.0

    ranked = sorted(
        candidates,
        key=lambda risk: (-scores[risk], -TIE_BREAK_ORDER.get(risk, 0), risk),
    )
    top_score = scores[ranked[0]]
    second_score = scores[ranked[1]]
    reason_codes = ["TEXT_EVENT_SCORE" if top_score > 0 else "CONSERVATIVE_TIE_BREAK"]
    if top_score == second_score:
        reason_codes.append("PRIMARY_RISK_AMBIGUOUS")
    return RiskPriorityDecision(
        primary_risk_type=ranked[0],
        secondary_risk_types=tuple(ranked[1:]),
        scores=scores,
        reason_codes=tuple(reason_codes),
        ambiguous=top_score == second_score,
    )


def build_primary_evidence_query(review_text: str, decision: RiskPriorityDecision) -> str:
    primary_terms = PRIMARY_QUERY_TERMS.get(decision.primary_risk_type, risk_type_label(decision.primary_risk_type))
    secondary_labels = " ".join(risk_type_label(risk) for risk in decision.secondary_risk_types)
    parts = [
        (review_text or "")[:480].strip(),
        f"主要审核风险 {risk_type_label(decision.primary_risk_type)} {primary_terms}",
    ]
    if secondary_labels:
        parts.append(f"补充风险 {secondary_labels}")
    return " ".join(part for part in parts if part)
