from __future__ import annotations

import re
from dataclasses import dataclass

from app.policy_rag.evidence_semantics import evidence_supports_risk, governed_risk_types
from app.policy_rag.models import PolicySearchResult


@dataclass(frozen=True)
class PolicyEvidenceCoverageOutcome:
    """Evidence selected for policy coverage before rank-only backfill."""

    evidence: list[PolicySearchResult]
    metadata: dict[str, object]


@dataclass(frozen=True)
class PolicyEvidenceDemand:
    """A concrete business question a policy citation should answer.

    ``riskType`` remains the stable governance contract.  A demand only makes
    candidate selection less generic when one broad risk type covers several
    materially different questions, such as after-sales disputes.
    """

    code: str
    riskType: str
    queryTerms: tuple[str, ...]
    evidenceTerms: tuple[str, ...]


@dataclass(frozen=True)
class PolicyEvidenceBudgetPlan:
    """Deterministic pre-rerank budget with an auditable explanation."""

    candidateLimit: int
    demands: list[PolicyEvidenceDemand]
    metadata: dict[str, object]


class PolicyAdaptiveEvidenceBudget:
    """Choose a small reranker budget from coverage need, not a fixed Top-K.

    The policy path deliberately uses rules rather than another model: it is
    reproducible, inexpensive, and exposes the reason a review spent more
    reranker capacity.  The budget applies after Hybrid retrieval, never
    manufactures a missing citation.
    """

    minimum = 5
    maximum = 10

    _AFTER_SALES_PROFILES: tuple[PolicyEvidenceDemand, ...] = (
        PolicyEvidenceDemand(
            code="after_sales_quality_remedy",
            riskType="after_sales_risk",
            queryTerms=("质量", "破损", "故障", "不合格", "修理", "维修", "换货", "更换"),
            evidenceTerms=("不符合质量要求", "修理", "维修", "更换", "必要费用"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_unqualified_goods",
            riskType="after_sales_risk",
            queryTerms=("认定不合格", "已经被认定"),
            evidenceTerms=("认定为不合格", "应当负责退货"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_return_conditions",
            riskType="after_sales_risk",
            queryTerms=("普通商品", "七天内", "无理由退货"),
            evidenceTerms=("依法履行七日无理由退货义务", "消费者有权自收到商品之日起七日内退货"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_exception",
            riskType="after_sales_risk",
            queryTerms=("定制", "定作", "鲜活", "易腐", "软件", "数字"),
            evidenceTerms=("消费者确认", "定作", "鲜活易腐", "音像制品", "计算机软件"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_confirmed_exception",
            riskType="after_sales_risk",
            queryTerms=("激活", "试用", "贬损", "确认过"),
            evidenceTerms=("消费者在购买时确认", "一经激活", "价值贬损"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_return_notice",
            riskType="after_sales_risk",
            queryTerms=("退货通知", "已经过期", "第七天"),
            evidenceTerms=("七日内向网络商品销售者发出退货通知", "签收商品的次日开始起算"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_exception_confirmation_process",
            riskType="after_sales_risk",
            queryTerms=("购买流程", "标成不能退", "显著确认"),
            evidenceTerms=("明确标注", "显著的确认程序"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_terms_information",
            riskType="after_sales_risk",
            queryTerms=("条款", "提醒", "看不清", "固定条款"),
            evidenceTerms=("格式条款", "提请消费者注意", "重大利害关系"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_online_information",
            riskType="after_sales_risk",
            queryTerms=("联系方式", "经营联系信息", "网店", "线上购买"),
            evidenceTerms=("售后服务", "经营地址", "联系方式"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_refund_delay",
            riskType="after_sales_risk",
            queryTerms=("拖延", "拖着", "不处理", "推诿", "无理拒绝", "迟迟"),
            evidenceTerms=("故意拖延", "无理拒绝"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_return_contact",
            riskType="after_sales_risk",
            queryTerms=("退货地址", "地址", "联系人", "联系电话", "联系信息"),
            evidenceTerms=("退货地址", "退货联系人", "退货联系电话"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_refund_timing",
            riskType="after_sales_risk",
            queryTerms=("收到退回", "十天", "十五天", "退款到账", "返还价款", "钱没退"),
            evidenceTerms=("收到退回商品之日起七日内", "返还消费者支付的商品价款"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_refund_method",
            riskType="after_sales_risk",
            queryTerms=("店铺余额", "原路退款", "支付方式", "退款方式"),
            evidenceTerms=("比照购买商品的支付方式", "消费者明确表示同意"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_actual_paid_price",
            riskType="after_sales_risk",
            queryTerms=("实际支付", "满减", "实付"),
            evidenceTerms=("消费者实际支出的价款", "多退少补"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_return_method",
            riskType="after_sales_risk",
            queryTerms=("指定快递", "退货方式", "快递退货", "上门取货"),
            evidenceTerms=("不应当限制消费者的退货方式", "有偿上门取货"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_statutory_exception_scope",
            riskType="after_sales_risk",
            queryTerms=("概不退换", "扩大不适用", "普通商品"),
            evidenceTerms=("消费者定作", "鲜活易腐", "音像制品", "计算机软件"),
        ),
        PolicyEvidenceDemand(
            code="after_sales_confirmed_exception_scope",
            riskType="after_sales_risk",
            queryTerms=("概不退换", "扩大不适用", "普通商品"),
            evidenceTerms=("消费者在购买时确认", "经消费者在购买时确认", "一经激活", "价值贬损"),
        ),
    )

    def plan(
        self,
        review_text: str,
        risk_types: list[str],
        candidates: list[PolicySearchResult],
    ) -> PolicyEvidenceBudgetPlan:
        requested = governed_risk_types(risk_types)
        demands = self.demands_for(review_text, requested)
        normalized_candidates = PolicyEvidenceCoverageSelector._dedupe(candidates)
        first_matching_rank = {
            demand.code: self._first_matching_rank(demand, normalized_candidates)
            for demand in demands
        }
        late_demands = [
            code
            for code, rank in first_matching_rank.items()
            if rank is not None and rank > self.minimum
        ]
        uncovered_demands = [code for code, rank in first_matching_rank.items() if rank is None]

        # Keep capacity for both required coverage and two competing candidates.
        limit = max(self.minimum, len(requested) + len(demands) + 2)
        # A relevant citation below the old Top-5 gets a bounded chance to be
        # reranked, rather than being discarded before the cross encoder sees it.
        if late_demands:
            limit = max(limit, self.minimum + min(3, len(late_demands) + 1))
        if self._has_redundant_top_candidates(normalized_candidates):
            limit += 1
        limit = min(self.maximum, limit)

        return PolicyEvidenceBudgetPlan(
            candidateLimit=limit,
            demands=demands,
            metadata={
                "mode": "adaptive_evidence_budget_v1",
                "minimumCandidateLimit": self.minimum,
                "maximumCandidateLimit": self.maximum,
                "requestedRiskTypes": requested,
                "demandCodes": [demand.code for demand in demands],
                "firstMatchingRanks": first_matching_rank,
                "lateDemandCodes": late_demands,
                "uncoveredDemandCodes": uncovered_demands,
                "redundantTopCandidates": self._has_redundant_top_candidates(normalized_candidates),
                "candidateLimit": limit,
            },
        )

    def demands_for(self, review_text: str, risk_types: list[str]) -> list[PolicyEvidenceDemand]:
        if "after_sales_risk" not in risk_types:
            return []
        normalized_review = _normalized_text(review_text)
        return [
            demand
            for demand in self._AFTER_SALES_PROFILES
            if any(_normalized_text(term) in normalized_review for term in demand.queryTerms)
        ]

    @staticmethod
    def demand_supports_evidence(demand: PolicyEvidenceDemand, evidence: PolicySearchResult) -> bool:
        if not evidence_supports_risk(demand.riskType, evidence):
            return False
        searchable = _normalized_text(
            " ".join([evidence.title, " ".join(evidence.sectionPath), evidence.snippet])
        )
        return any(_normalized_text(term) in searchable for term in demand.evidenceTerms)

    def _first_matching_rank(
        self,
        demand: PolicyEvidenceDemand,
        candidates: list[PolicySearchResult],
    ) -> int | None:
        for rank, candidate in enumerate(candidates, start=1):
            if self.demand_supports_evidence(demand, candidate):
                return rank
        return None

    @staticmethod
    def _has_redundant_top_candidates(candidates: list[PolicySearchResult]) -> bool:
        top = candidates[:5]
        if len(top) < 3:
            return False
        unique_clauses = {(item.sourceName, item.clauseId or item.chunkId) for item in top}
        return len(unique_clauses) / len(top) < 0.6


class PolicyEvidenceCoverageSelector:
    """Keep policy support for each detected risk visible to Reflection.

    The selector operates only on retrieved candidates. It is intentionally
    deterministic and does not infer new tags, create citations, or relax the
    Reflection support contract.
    """

    def select(
        self,
        candidates: list[PolicySearchResult],
        risk_types: list[str],
        *,
        limit: int = 5,
        demands: list[PolicyEvidenceDemand] | None = None,
        backfill: bool = True,
    ) -> PolicyEvidenceCoverageOutcome:
        ranked = self._dedupe(candidates)
        requested = governed_risk_types(risk_types)
        requested_demands = list(demands or [])
        bounded_limit = max(0, limit)
        if not ranked or bounded_limit == 0:
            return PolicyEvidenceCoverageOutcome(
                evidence=[],
                metadata={
                    "mode": "risk_coverage_then_rank",
                    "candidateCount": len(ranked),
                    "selectedCount": 0,
                    "selectionLimit": bounded_limit,
                    "requestedRiskTypes": requested,
                    "coveredRiskTypes": [],
                    "uncoveredRiskTypes": requested,
                    "requestedDemandCodes": [demand.code for demand in requested_demands],
                    "coveredDemandCodes": [],
                    "uncoveredDemandCodes": [demand.code for demand in requested_demands],
                    "coverageApplied": False,
                    "selectedChunkIds": [],
                },
            )

        support_by_index = []
        for candidate in ranked:
            support = {f"risk:{risk}" for risk in requested if evidence_supports_risk(risk, candidate)}
            support.update(
                f"demand:{demand.code}"
                for demand in requested_demands
                if PolicyAdaptiveEvidenceBudget.demand_supports_evidence(demand, candidate)
            )
            support_by_index.append(support)
        uncovered = {f"risk:{risk}" for risk in requested}
        uncovered.update(f"demand:{demand.code}" for demand in requested_demands)
        selected_indexes: list[int] = []

        # Greedy set coverage: prefer the candidate supporting the most still
        # uncovered risks; retain retrieval order to break ties.
        while uncovered and len(selected_indexes) < bounded_limit:
            best_index = -1
            best_gain = 0
            for index, supported in enumerate(support_by_index):
                if index in selected_indexes:
                    continue
                gain = len(supported.intersection(uncovered))
                if gain > best_gain:
                    best_index = index
                    best_gain = gain
            if best_index < 0 or best_gain == 0:
                break
            selected_indexes.append(best_index)
            uncovered.difference_update(support_by_index[best_index])

        # Search and final display have different jobs. Search may keep a
        # broader candidate pool, while a caller preparing the human-facing
        # bundle can stop as soon as every business demand is covered.
        if backfill:
            for index in range(len(ranked)):
                if len(selected_indexes) >= bounded_limit:
                    break
                if index not in selected_indexes:
                    selected_indexes.append(index)

        selected = [ranked[index] for index in selected_indexes]
        selected = self._renumber(selected)
        covered = [risk for risk in requested if any(evidence_supports_risk(risk, item) for item in selected)]
        covered_demands = [
            demand.code
            for demand in requested_demands
            if any(PolicyAdaptiveEvidenceBudget.demand_supports_evidence(demand, item) for item in selected)
        ]
        selected_chunk_ids = [item.chunkId for item in selected]
        original_chunk_ids = [item.chunkId for item in ranked[: len(selected)]]
        return PolicyEvidenceCoverageOutcome(
            evidence=selected,
            metadata={
                "mode": "risk_coverage_then_rank",
                "candidateCount": len(ranked),
                "selectedCount": len(selected),
                "selectionLimit": bounded_limit,
                "requestedRiskTypes": requested,
                "coveredRiskTypes": covered,
                "uncoveredRiskTypes": [risk for risk in requested if risk not in covered],
                "requestedDemandCodes": [demand.code for demand in requested_demands],
                "coveredDemandCodes": covered_demands,
                "uncoveredDemandCodes": [
                    demand.code for demand in requested_demands if demand.code not in covered_demands
                ],
                "coverageApplied": selected_chunk_ids != original_chunk_ids,
                "rankBackfillApplied": backfill,
                "selectedChunkIds": selected_chunk_ids,
            },
        )

    @staticmethod
    def _dedupe(candidates: list[PolicySearchResult]) -> list[PolicySearchResult]:
        seen: set[str] = set()
        unique: list[PolicySearchResult] = []
        for candidate in candidates:
            stable_id = candidate.chunkId or candidate.evidenceId
            if stable_id and stable_id not in seen:
                seen.add(stable_id)
                unique.append(candidate)
        return unique

    @staticmethod
    def _renumber(items: list[PolicySearchResult]) -> list[PolicySearchResult]:
        return [item.model_copy(update={"evidenceId": f"E{rank}"}) for rank, item in enumerate(items, start=1)]


def _normalized_text(value: str) -> str:
    """Normalize PDF-spaced CJK text before policy keyword matching."""
    return re.sub(r"\s+", "", value or "").lower()
