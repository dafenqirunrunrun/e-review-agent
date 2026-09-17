from scripts.run_step242i_business_evidence_dev import VARIANT
from scripts.run_step242i_business_evidence_holdout import FIXED8_COVERAGE_AWARE, HOLDOUT, RETRIEVAL_WINDOW


def test_holdout_runner_uses_the_frozen_split_and_the_dev_selected_strategy() -> None:
    assert HOLDOUT.name == "holdout_bound_candidate_v2.jsonl"
    assert RETRIEVAL_WINDOW == 30
    assert FIXED8_COVERAGE_AWARE.name == VARIANT
    assert FIXED8_COVERAGE_AWARE.fixed_budget == 8
    assert FIXED8_COVERAGE_AWARE.demand_aware is True
