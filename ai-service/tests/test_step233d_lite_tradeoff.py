from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.policy_rag.risk_priority import build_primary_evidence_query, prioritize_risks
from scripts.run_step233d_lite_tradeoff import (
    choose_tradeoff,
    rerank_conditionally,
    should_conditionally_rerank,
)


def _chunk(chunk_id: str, risk: str):
    return SimpleNamespace(
        chunkId=chunk_id,
        riskTypes=[risk],
        evidenceTags=[risk],
        heading=risk,
        sectionPath=["policy"],
        text=f"policy for {risk}",
    )


def test_primary_risk_uses_business_event_not_input_order():
    fake = prioritize_risks(
        ["rating_manipulation", "fake_review"],
        "我根本没有下单，客服让我复制五星评价，完成后返现。",
    )
    rating = prioritize_risks(
        ["fake_review", "rating_manipulation"],
        "我真实购买了商品，卡片要求五星好评返现。",
    )

    assert fake.primary_risk_type == "fake_review"
    assert rating.primary_risk_type == "rating_manipulation"


def test_primary_risk_distinguishes_completed_harm_and_supporting_dispute():
    safety = prioritize_risks(
        ["after_sales_risk", "safety_or_fraud_risk"],
        "充电器使用时冒烟，客服随后拒绝退款。",
    )
    harassment = prioritize_risks(
        ["review_suppression", "harassment_or_abuse"],
        "客服威胁上门找我，除非我删除差评。",
    )
    suppression = prioritize_risks(
        ["harassment_or_abuse", "review_suppression"],
        "平台已经删除差评，客服还辱骂了我。",
    )

    assert safety.primary_risk_type == "safety_or_fraud_risk"
    assert harassment.primary_risk_type == "harassment_or_abuse"
    assert suppression.primary_risk_type == "review_suppression"


def test_primary_query_expands_primary_but_only_labels_secondary_risk():
    decision = prioritize_risks(["fake_review", "rating_manipulation"], "用户冒充消费者发布内容")

    query = build_primary_evidence_query("用户冒充消费者发布内容", decision)

    assert "主要审核风险 虚假评价" in query
    assert "未真实购买" in query
    assert "补充风险 评分操纵" in query
    assert "五星奖励" not in query


def test_conditional_rerank_only_runs_for_multi_risk_or_unsupported_top1():
    fake = _chunk("fake", "fake_review")
    privacy = _chunk("privacy", "privacy_risk")

    assert should_conditionally_rerank({"riskTypes": ["fake_review"]}, [(1.0, fake)], "fake_review") is False
    assert should_conditionally_rerank({"riskTypes": ["fake_review"]}, [(1.0, privacy)], "fake_review") is True
    assert should_conditionally_rerank(
        {"riskTypes": ["fake_review", "rating_manipulation"]},
        [(1.0, fake)],
        "fake_review",
    ) is True


def test_conditional_reranker_keeps_primary_support_ahead_of_secondary():
    primary = _chunk("primary", "fake_review")
    secondary = _chunk("secondary", "rating_manipulation")

    class FakeReranker:
        @staticmethod
        def predict(_pairs, *, batch_size, show_progress_bar=False):
            del batch_size, show_progress_bar
            return np.asarray([0.1, 0.9], dtype="float32")

    rankings, _, pair_count = rerank_conditionally(
        FakeReranker(),
        ["query"],
        [[(1.0, primary), (0.5, secondary)]],
        [True],
        ["fake_review"],
        batch_size=2,
    )

    assert pair_count == 2
    assert [chunk.chunkId for _, chunk in rankings[0]] == ["primary", "secondary"]


def test_tradeoff_prefers_conditional_when_quality_is_near_equal_and_saves_work():
    def variant(top1: float, ndcg: float, reranks: int, omissions: int = 4):
        return {
            "metrics": {
                "primaryPolicyAccuracyAt1": top1,
                "primaryPolicyRecallAt5": 0.95,
                "pooledNdcgAt3": ndcg,
                "judgedMultiRiskCoverageAt3": 0.90,
                "highRiskPrimaryOmissionCount": omissions,
                "citationValidity": 1.0,
            },
            "rerank": {"invocationCount": reranks},
        }

    variants = {
        "D0": variant(0.70, 0.75, 0),
        "D0R": variant(0.84, 0.85, 100, omissions=2),
        "D1": variant(0.72, 0.76, 0),
        "D2": variant(0.85, 0.86, 100, omissions=2),
        "D3": variant(0.845, 0.855, 60, omissions=2),
    }

    result = choose_tradeoff(variants, {"acceptableAccuracy": 0.90})

    assert result["selectedDiagnosticVariant"] == "D3"
    assert result["conditionalRerankSavingVsAlways"] == 0.4
    assert result["candidateGate"] == "PASS_FOR_BLIND_VALIDATION"
