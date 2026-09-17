from __future__ import annotations

from app.policy_rag.evidence_coverage import (
    PolicyAdaptiveEvidenceBudget,
    PolicyEvidenceCoverageSelector,
    PolicyEvidenceDemand,
)
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.reflection import PolicyReflectionEngine


def test_coverage_selector_keeps_one_candidate_per_supported_risk_before_rank_backfill():
    selector = PolicyEvidenceCoverageSelector()
    candidates = [
        _evidence("rank-1", ["fake_review"], ["fake_engagement"]),
        _evidence("rank-2", ["rating_manipulation"], ["rating_manipulation"]),
        _evidence("rank-3", ["privacy_risk"], ["privacy"]),
        _evidence("rank-4", ["after_sales_risk"], ["after_sales"]),
        _evidence("rank-5", ["fake_review"], ["fake_review"]),
    ]

    result = selector.select(
        candidates,
        ["fake_review", "after_sales_risk", "privacy_risk"],
        limit=5,
    )

    assert [item.chunkId for item in result.evidence[:3]] == ["rank-1", "rank-3", "rank-4"]
    assert result.metadata["coveredRiskTypes"] == ["fake_review", "after_sales_risk", "privacy_risk"]
    assert result.metadata["uncoveredRiskTypes"] == []
    assert result.metadata["coverageApplied"] is True


def test_coverage_selector_never_invents_policy_support_for_a_missing_risk():
    selector = PolicyEvidenceCoverageSelector()
    evidence = [_evidence("only-fake", ["fake_review"], ["fake_engagement"])]

    selection = selector.select(evidence, ["fake_review", "after_sales_risk"], limit=5)
    reflection = PolicyReflectionEngine().reflect(
        risk_level="high",
        risk_types=["fake_review", "after_sales_risk"],
        confidence=0.9,
        policy_evidence=selection.evidence,
        action="human_review",
    )

    assert selection.metadata["coveredRiskTypes"] == ["fake_review"]
    assert selection.metadata["uncoveredRiskTypes"] == ["after_sales_risk"]
    assert reflection.evidenceStatus == "mismatch"
    assert reflection.unsupportedRiskTypes == ["after_sales_risk"]


def test_coverage_selector_uses_rank_order_when_no_governed_risk_is_requested():
    selector = PolicyEvidenceCoverageSelector()
    candidates = [_evidence("rank-1", [], []), _evidence("rank-2", [], [])]

    result = selector.select(candidates, ["negative_review"], limit=5)

    assert [item.chunkId for item in result.evidence] == ["rank-1", "rank-2"]
    assert result.metadata["requestedRiskTypes"] == []
    assert result.metadata["coverageApplied"] is False


def test_coverage_selector_can_stop_once_current_business_coverage_is_complete():
    selector = PolicyEvidenceCoverageSelector()
    candidates = [
        _evidence("risk-a", ["fake_review"], ["fake_engagement"]),
        _evidence("risk-b", ["after_sales_risk"], ["after_sales"]),
        _evidence("rank-backfill", ["fake_review"], ["fake_engagement"]),
    ]

    result = selector.select(
        candidates,
        ["fake_review", "after_sales_risk"],
        limit=3,
        backfill=False,
    )

    assert [item.chunkId for item in result.evidence] == ["risk-a", "risk-b"]
    assert result.metadata["selectedCount"] == 2
    assert result.metadata["rankBackfillApplied"] is False


def test_adaptive_budget_expands_when_a_specific_after_sales_evidence_is_below_top5():
    budget = PolicyAdaptiveEvidenceBudget()
    candidates = [
        _evidence(f"rank-{index}", ["after_sales_risk"], ["after_sales"])
        for index in range(1, 6)
    ]
    candidates.append(
        _evidence(
            "terms-at-rank-6",
            ["after_sales_risk"],
            ["after_sales"],
            snippet="经营者不得利用格式条款限制售后服务，也应显著提示消费者。",
        )
    )

    plan = budget.plan("店铺用固定条款限制售后，却没有显著提醒。", ["after_sales_risk"], candidates)
    selected = PolicyEvidenceCoverageSelector().select(
        candidates,
        ["after_sales_risk"],
        limit=plan.candidateLimit,
        demands=plan.demands,
    )

    assert plan.candidateLimit == 7
    assert plan.metadata["lateDemandCodes"] == ["after_sales_terms_information"]
    assert "terms-at-rank-6" in selected.metadata["selectedChunkIds"]
    assert selected.metadata["coveredDemandCodes"] == ["after_sales_terms_information"]


def test_adaptive_budget_does_not_expand_when_no_candidate_can_cover_the_demand():
    plan = PolicyAdaptiveEvidenceBudget().plan(
        "商家一直拖着退款不处理。",
        ["after_sales_risk"],
        [_evidence("generic", ["after_sales_risk"], ["after_sales"])],
    )

    assert plan.candidateLimit == 5
    assert plan.metadata["uncoveredDemandCodes"] == ["after_sales_refund_delay"]


def test_adaptive_delay_demand_does_not_treat_any_refund_clause_as_delay_evidence():
    budget = PolicyAdaptiveEvidenceBudget()
    demand = next(
        item
        for item in budget.demands_for("商家一直拖着退款不处理。", ["after_sales_risk"])
        if item.code == "after_sales_refund_delay"
    )
    generic_refund = _evidence(
        "generic-refund",
        ["after_sales_risk"],
        ["after_sales"],
        snippet="经营者应当及时办理退款和退货。",
    )
    delay = _evidence(
        "delay",
        ["after_sales_risk"],
        ["after_sales"],
        snippet="经营者不得故意拖延或者无理拒绝消费者的退货请求。",
    )

    assert budget.demand_supports_evidence(demand, generic_refund) is False
    assert budget.demand_supports_evidence(demand, delay) is True


def test_adaptive_quality_demand_does_not_treat_generic_return_freight_as_quality_remedy():
    budget = PolicyAdaptiveEvidenceBudget()
    demand = next(
        item
        for item in budget.demands_for("商品破损退货，商家要我承担必要运费。", ["after_sales_risk"])
        if item.code == "after_sales_quality_remedy"
    )
    generic_freight = _evidence(
        "generic-freight",
        ["after_sales_risk"],
        ["after_sales"],
        snippet="商品退回所产生的运费依法由消费者承担。",
    )
    quality_remedy = _evidence(
        "quality-remedy",
        ["after_sales_risk"],
        ["after_sales"],
        snippet="商品不符合质量要求时，消费者可以要求经营者履行更换、修理等义务，必要费用由经营者承担。",
    )

    assert budget.demand_supports_evidence(demand, generic_freight) is False
    assert budget.demand_supports_evidence(demand, quality_remedy) is True


def _evidence(
    chunk_id: str,
    risk_types: list[str],
    tags: list[str],
    *,
    snippet: str = "A short, valid policy evidence snippet.",
) -> PolicySearchResult:
    return PolicySearchResult(
        evidenceId="E0",
        chunkId=chunk_id,
        sourceType="regulation",
        sourceName="Test policy",
        sourceUrl=f"https://example.test/{chunk_id}",
        title=chunk_id,
        snippet=snippet,
        riskTypes=risk_types,
        evidenceTags=tags,
        score=1.0,
        contentHash=f"hash-{chunk_id}",
        sectionPath=["Test", chunk_id],
        clauseId=chunk_id,
    )
