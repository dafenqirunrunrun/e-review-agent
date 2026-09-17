from app.policy_rag.models import PolicySearchResult
from scripts.run_step242h_adaptive_evidence_budget_dev import (
    EVIDENCE_LIMIT,
    EXPERIMENT_VARIANTS,
    RETRIEVAL_WINDOW,
    final_evidence_bundle,
)
from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector


def test_adaptive_budget_experiment_has_isolated_fixed_and_dynamic_variants() -> None:
    variants = {variant.name: variant for variant in EXPERIMENT_VARIANTS}

    assert RETRIEVAL_WINDOW == 50
    assert EVIDENCE_LIMIT == 3
    assert variants["fixed5_legacy"].retrieval_k == 20
    assert variants["fixed5_legacy"].fixed_budget == 5
    assert variants["fixed8_rank_only"].fixed_budget == 8
    assert variants["fixed8_coverage_aware"].demand_aware is True
    assert variants["adaptive5to10_coverage_aware"].fixed_budget is None
    assert variants["adaptive5to10_coverage_aware"].retrieval_k == 50
    assert variants["adaptive5to10_coverage_aware"].demand_aware is True


def test_final_bundle_keeps_ranked_options_when_there_is_no_specific_business_demand() -> None:
    result = final_evidence_bundle(
        PolicyEvidenceCoverageSelector(),
        [_evidence("one"), _evidence("two"), _evidence("three"), _evidence("four")],
        ["after_sales_risk"],
        [],
    )

    assert [item.chunkId for item in result.evidence] == ["one", "two", "three"]
    assert result.metadata["rankBackfillApplied"] is True


def _evidence(chunk_id: str) -> PolicySearchResult:
    return PolicySearchResult(
        evidenceId="E0",
        chunkId=chunk_id,
        sourceType="regulation",
        sourceName="Test policy",
        sourceUrl=f"https://example.test/{chunk_id}",
        title=chunk_id,
        snippet="A valid after-sales policy citation.",
        riskTypes=["after_sales_risk"],
        evidenceTags=["after_sales"],
        score=1.0,
        contentHash=f"hash-{chunk_id}",
        sectionPath=["Test", chunk_id],
        clauseId=chunk_id,
    )
