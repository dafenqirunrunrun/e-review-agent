import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.agent_rag.metrics import dcg_at_k, ndcg_at_k, score_query, validate_metric_ranges

ROOT = Path(__file__).resolve().parents[2]


def test_v200_phase3a1_ndcg_perfect_order_is_one():
    assert ndcg_at_k([3, 2, 1], [3, 2, 1], 3) == pytest.approx(1.0, abs=1e-9)


def test_v200_phase3a1_ndcg_reverse_order_manual_value():
    value = ndcg_at_k([1, 2, 3], [3, 2, 1], 3)
    expected = dcg_at_k([1, 2, 3], 3) / dcg_at_k([3, 2, 1], 3)
    assert 0 < value < 1
    assert value == pytest.approx(expected, abs=1e-9)


def test_v200_phase3a1_ndcg_no_relevant_is_zero():
    assert ndcg_at_k([0, 0], [], 5) == 0.0


def test_v200_phase3a1_single_and_multiple_binary_relevance():
    one = score_query(retrieved_chunk_ids=["a", "b"], relevant_chunk_ids={"b"}, k_values=(1, 3, 5))
    assert one["hitRateAt1"] == 0.0
    assert one["hitRateAt3"] == 1.0
    assert one["recallAt3"] == 1.0
    multi = score_query(retrieved_chunk_ids=["a", "b", "c"], relevant_chunk_ids={"a", "c"}, k_values=(1, 3, 5))
    assert multi["hitRateAt1"] == 1.0
    assert multi["recallAt1"] == pytest.approx(0.5, abs=1e-9)
    assert multi["recallAt3"] == pytest.approx(1.0, abs=1e-9)


def test_v200_phase3a1_graded_relevance_specific_value():
    metrics = score_query(
        retrieved_chunk_ids=["partial", "best"],
        relevant_chunk_ids={"best", "partial"},
        relevance_grades={"best": 3, "partial": 1},
    )
    expected = dcg_at_k([1, 3], 5) / dcg_at_k([3, 1], 5)
    assert metrics["ndcgAt5"] == pytest.approx(expected, abs=1e-9)


def test_v200_phase3a1_result_shorter_and_longer_than_k():
    short = score_query(retrieved_chunk_ids=["rel"], relevant_chunk_ids={"rel", "missing"})
    assert short["recallAt5"] == pytest.approx(0.5, abs=1e-9)
    long = score_query(retrieved_chunk_ids=["x", "rel", "y", "z", "w", "late"], relevant_chunk_ids={"rel", "late"})
    assert long["hitRateAt5"] == 1.0
    assert long["recallAt5"] == pytest.approx(0.5, abs=1e-9)


def test_v200_phase3a1_duplicate_unknown_and_forbidden_chunks():
    metrics = score_query(
        retrieved_chunk_ids=["rel", "rel", "unknown", "forbidden"],
        relevant_chunk_ids={"rel", "forbidden"},
        forbidden_chunk_ids={"forbidden"},
    )
    assert metrics["duplicateCount"] == 1
    assert metrics["forbiddenHitCount"] == 1
    assert metrics["recallAt5"] == pytest.approx(0.5, abs=1e-9)


def test_v200_phase3a1_metric_range_validator_rejects_invalid_values():
    errors = validate_metric_ranges({"mode": {"hitRateAt1": 1.2, "hitRateAt3": 1, "hitRateAt5": 1, "recallAt1": 1, "recallAt3": 1, "recallAt5": 1, "mrr": 1, "ndcgAt5": math.inf, "citationCoverage": 1, "duplicateEvidenceRate": 0, "emptyRetrievalRate": 0}}, modes=["mode"])
    assert any("hitRateAt1" in error for error in errors)
    assert any("ndcgAt5" in error for error in errors)


def test_v200_phase3a1_phase3a_evaluation_metrics_are_in_range(monkeypatch):
    monkeypatch.delenv("RAG_BGE_M3_MODEL_PATH", raising=False)
    completed = subprocess.run([sys.executable, "ai-service/scripts/evaluation/run_agent_rag_phase3a_eval.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "agent-rag-phase3a-eval-v2" in completed.stdout


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a1_real_dense_gate_executes_coverage():
    if not os.getenv("RAG_BGE_M3_MODEL_PATH"):
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    completed = subprocess.run([sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase3a1_gate.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "AGENT_RAG_PHASE3A1_PASS" in completed.stdout
