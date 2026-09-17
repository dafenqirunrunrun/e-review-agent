from __future__ import annotations

from typing import Any


METRIC_CONTRACT_VERSION = "rag-quality-metric-contract-v1"


def metric_contract() -> dict[str, Any]:
    """Return the frozen Step 24.2A metric meanings and gate policy."""

    return {
        "schemaVersion": METRIC_CONTRACT_VERSION,
        "releaseSourceOfTruth": [
            "versioned_adjudicated_chinese_queries",
            "graded_qrels",
            "deterministic_ir_metrics",
            "policy_evidence_business_safety",
        ],
        "evaluationLayers": [
            "document_parsing",
            "retrieval_and_ranking",
            "workflow_business_safety",
            "runtime_and_capacity",
        ],
        "relevanceScale": {
            "0": "irrelevant",
            "1": "topically_related_but_insufficient",
            "2": "supporting_evidence",
            "3": "direct_preferred_policy_evidence",
        },
        "metrics": {
            "candidateEvidenceHitRateAt5": {
                "unit": "case",
                "denominator": "rankable_cases",
                "definition": "Fraction of cases with at least one relevance>=2 chunk in Top-5.",
            },
            "relevantChunkRecallAt5": {
                "unit": "qrel",
                "denominator": "all_relevance>=2_qrels",
                "aggregation": "micro",
                "definition": "Micro recall over all relevance>=2 supporting and direct evidence qrels.",
            },
            "irMeasuresRelevantChunkRecallAt5": {
                "unit": "case",
                "denominator": "rankable_cases",
                "aggregation": "macro",
                "definition": "Mean per-query Recall@5 from ir_measures using relevance>=2.",
            },
            "relevantChunkRecallAt10": {
                "unit": "case",
                "denominator": "rankable_cases",
                "aggregation": "macro",
                "definition": "Diagnostic mean per-query Recall@10 from ir_measures using relevance>=2.",
            },
            "mrrAt5": {
                "unit": "case",
                "denominator": "rankable_cases",
                "definition": "Mean reciprocal rank of the first relevance>=2 chunk, capped at rank 5.",
            },
            "pooledNdcgAt3": {
                "unit": "case",
                "denominator": "rankable_cases",
                "gain": "exponential_2^rel_minus_1",
                "definition": "nDCG@3 using exponential gain and graded pooled qrels; incomplete pools remain diagnostic.",
            },
            "pooledNdcgAt5": {
                "unit": "case",
                "denominator": "rankable_cases",
                "gain": "exponential_2^rel_minus_1",
                "definition": "nDCG@5 using exponential gain and graded pooled qrels; incomplete pools remain diagnostic.",
            },
            "irMeasuresNdcgAt3": {
                "unit": "case",
                "denominator": "rankable_cases",
                "aggregation": "macro",
                "definition": "Reference nDCG@3 calculated by ir_measures with its standard gain convention.",
            },
            "irMeasuresNdcgAt5": {
                "unit": "case",
                "denominator": "rankable_cases",
                "aggregation": "macro",
                "definition": "Reference nDCG@5 calculated by ir_measures with its standard gain convention.",
            },
            "riskCoverageAt3": {
                "unit": "case",
                "denominator": "risk_cases",
                "definition": "Fraction of risk cases whose expected risk types are all supported in Top-3 qrels.",
            },
            "highRiskEvidenceHitRateAt5": {
                "unit": "case",
                "denominator": "high_risk_cases",
                "definition": "Fraction of high-risk cases with at least one relevance>=2 chunk in Top-5.",
            },
            "citationValidCaseRate": {
                "unit": "case",
                "denominator": "non_abstained_cases_with_hits",
                "definition": "Fraction whose displayed Top-3 hits have sourceName, URL, sectionPath, and contentHash.",
            },
            "noAnswerAbstentionAccuracy": {
                "unit": "case",
                "denominator": "no_answer_cases",
                "definition": "Fraction of no-answer cases that expose no policy evidence.",
            },
            "unjudgedItemRateAt5": {
                "unit": "item",
                "denominator": "retrieved_top5_items",
                "definition": "Fraction of Top-5 hits absent from the current qrel pool.",
            },
            "duplicateItemRateAt5": {
                "unit": "item",
                "denominator": "retrieved_top5_items",
                "definition": "Fraction of duplicate chunk IDs in Top-5 results.",
            },
        },
        "hardSafetyGates": {
            "citationValidCaseRate": 1.0,
            "highRiskAutoPassCount": 0,
            "highRiskEvidenceHitRateAt5": 1.0,
            "noAnswerAbstentionAccuracy": 1.0,
            "silentParserLossCount": 0,
            "frozenWorkflowGoldUnchanged": True,
        },
        "qualityThresholdPolicy": {
            "status": "PENDING_TRUSTWORTHY_BASELINE",
            "rule": "Freeze absolute quality thresholds from Dev only after a release-approved adjudication protocol; never tune on Holdout.",
            "aggregateCannotHideCriticalSliceRegression": True,
        },
        "judgePolicy": {
            "syntheticQueries": "candidate_only_until_human_review",
            "llmJudgeScores": "release_eligible_only_when_label_blind_versioned_conflict_resolved_and_explicitly_provenanced",
            "singleLlmJudge": "personal_demo_only_with_explicit_limitation_not_human_gold",
            "langfuse": "experiment_and_observability_surface_not_release_truth",
        },
    }
