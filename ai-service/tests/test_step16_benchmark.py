from pathlib import Path

from scripts.run_step16_benchmark import build_gold_cases, evaluate_faults, ranking_metrics, subset_for


def test_step16_gold_dataset_has_fixed_coverage():
    cases = build_gold_cases()

    assert len(cases) == 120
    assert {case["category"] for case in cases} >= {
        "normal_review", "fake_review", "paid_review", "rating_manipulation",
        "review_suppression", "after_sales_risk", "multi_risk", "lexical_mismatch",
    }
    assert all({"reviewText", "expectedRiskTypes", "expectedRoute", "expectedDecision", "expectedEvidenceStatus", "expectedHumanReview", "expectedEvidenceTags"} <= set(case) for case in cases)
    assert any("chinese" in case["subset"] for case in cases)
    assert any("english" in case["subset"] for case in cases)
    assert any("cross_language" in case["subset"] for case in cases)


def test_ranking_metrics_treat_missing_rank_as_miss():
    metrics = ranking_metrics([{"rank": 1}, {"rank": None}, {"rank": 3}])

    assert metrics == {"recallAt1": 0.3333, "recallAt3": 0.6667, "recallAt5": 0.6667, "mrr": 0.4444}
    assert subset_for("lexical_mismatch", "cross_language") == ["governance", "cross_language", "lexical_mismatch"]


def test_fault_injection_retrievers_preserve_observability_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("E_REVIEW_AGENTIC_CHECKPOINT_ENABLED", "true")
    default_checkpoint_dir = tmp_path / "default-checkpoints"
    monkeypatch.setenv("E_REVIEW_AGENTIC_CHECKPOINT_DIR", str(default_checkpoint_dir))

    scenarios = evaluate_faults(Path("data/policy_rag_real/index/policy_chunks.jsonl"))

    assert len(scenarios) == 9
    assert all(scenario["status"] == "PASS" for scenario in scenarios)
    assert not default_checkpoint_dir.exists()
