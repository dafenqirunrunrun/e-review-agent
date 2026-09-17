from __future__ import annotations

import sys
from types import SimpleNamespace

from app.policy_rag.embedding import QwenEmbeddingConfig
from app.policy_rag.retriever import PolicyEvidenceRetriever
from scripts.run_step233b_ranking_recovery import (
    candidate_embedding_config,
    case_query_language,
    detect_language,
    fusion_selection_key,
    load_reranker,
    no_subset_regression,
    promotion_gate,
    weighted_rrf,
)


def _chunk(chunk_id: str):
    return SimpleNamespace(chunkId=chunk_id)


def _evaluation(recall_at_1: float = 1.0, mrr: float = 1.0):
    subset = {"recallAt1": recall_at_1, "recallAt3": 1.0, "recallAt5": 1.0, "mrr": mrr}
    return {
        "metrics": dict(subset),
        "subsets": {"chinese": dict(subset), "cross_language": dict(subset)},
        "citationValid": True,
    }


def test_b0_weighted_rrf_matches_current_runtime_order():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    bm25 = [(9.0, a), (8.0, b), (7.0, c)]
    dense = [(0.9, b), (0.8, c), (0.7, a)]

    expected = PolicyEvidenceRetriever._fuse(bm25, dense, top_k=3, k=60)
    actual = weighted_rrf(bm25, dense, top_k=3, k=60)

    assert [chunk.chunkId for _, chunk in actual] == [chunk.chunkId for _, chunk in expected]


def test_fusion_grid_prefers_top1_before_secondary_metrics():
    better_top1 = {
        "metrics": {"recallAt1": 0.9, "mrr": 0.91, "recallAt3": 0.92, "recallAt5": 1.0},
        "bm25Weight": 0.5,
        "rrfK": 60,
    }
    better_recall5 = {
        "metrics": {"recallAt1": 0.8, "mrr": 0.99, "recallAt3": 1.0, "recallAt5": 1.0},
        "bm25Weight": 0.5,
        "rrfK": 60,
    }

    assert fusion_selection_key(better_top1) > fusion_selection_key(better_recall5)


def test_promotion_gate_requires_top1_mrr_and_language_stability():
    baseline = _evaluation()
    integrity = {"gold": True, "active": True}
    token_profile = {"overCandidateMaxLength": 0}

    passed = promotion_gate(_evaluation(), baseline, token_profile, integrity)
    failed = promotion_gate(_evaluation(recall_at_1=0.95, mrr=0.97), baseline, token_profile, integrity)

    assert passed["status"] == "PASS"
    assert failed["status"] == "HOLD"
    assert failed["checks"]["recallAt1"] is False
    assert failed["checks"]["chineseNoRegression"] is False


def test_subset_regression_and_language_direction_are_deterministic():
    baseline = _evaluation()
    candidate = _evaluation(recall_at_1=0.99, mrr=1.0)

    assert no_subset_regression(candidate, baseline, "chinese") is False
    assert detect_language("五星 cashback") == "mixed"
    assert detect_language("删除差评") == "zh"
    assert detect_language("paid review") == "en"
    assert case_query_language({"language": "cross_language", "reviewText": "五星 cashback"}) == "mixed"


def test_local_reranker_loader_does_not_import_sentence_transformers(monkeypatch, tmp_path):
    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

    class FakeModel:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

        def eval(self):
            return self

        def to(self, _device):
            return self

    for name in ("config.json", "tokenizer_config.json", "MODEL_PROVENANCE.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    monkeypatch.setattr("transformers.AutoTokenizer", FakeTokenizer)
    monkeypatch.setattr("transformers.AutoModelForSequenceClassification", FakeModel)

    reranker, metadata = load_reranker(tmp_path)

    assert metadata["provider"] == "transformers-sequence-classification"
    assert reranker.model is not None


def test_candidate_query_config_matches_candidate_index_semantics():
    current = QwenEmbeddingConfig(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        model_path="local-model",
        device="cpu",
        batch_size=4,
        max_length=96,
        normalize=True,
        allow_remote=False,
    )

    candidate = candidate_embedding_config(current, {"provider": {"maxLength": 512}})

    assert candidate.max_length == 512
    assert candidate.model_path == current.model_path
    assert candidate.batch_size == current.batch_size
