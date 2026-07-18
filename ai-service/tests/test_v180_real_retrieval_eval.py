import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v180_real_retrieval_eval_uses_real_bge_and_faiss():
    result = json.loads((ROOT / "data/private_research/eval/v180_real_retrieval_eval.json").read_text(encoding="utf-8"))
    assert result["status"] == "V180_REAL_RETRIEVAL_EVAL_PASS"
    assert result["real_bge_m3_used"] is True
    assert result["faiss_executed"] is True
    assert result["versioned_faiss_published"] is True
    assert result["persistent_restart_verified"] is True
    assert result["hash_dense_used_for_primary"] is False
    assert result["hash_dense_negative_control_only"] is True
    assert result["provider_metadata"]["provider"] == "bge_m3"
    assert result["index_manifest"]["dimension"] == 1024


def test_v180_real_retrieval_eval_records_hard_benchmark_metrics():
    result = json.loads((ROOT / "data/private_research/eval/v180_real_retrieval_eval.json").read_text(encoding="utf-8"))
    metrics = result["metrics"]
    assert metrics["hybrid_bge_m3_bm25_rrf"]["evaluated_positive_queries"] == 48
    assert metrics["hybrid_bge_m3_bm25_rrf"]["recall_at_5"] >= 0.5
    assert metrics["dense_bge_m3_faiss"]["recall_at_5"] >= metrics["hash_dense_negative_control"]["recall_at_5"]
    assert metrics["sparse_bm25"]["empty_retrieval_rate"] > 0


def test_v180_real_retrieval_eval_persistent_index_files_exist():
    result = json.loads((ROOT / "data/private_research/eval/v180_real_retrieval_eval.json").read_text(encoding="utf-8"))
    index_root = ROOT / "data/private_research/enterprise_rag_v180/faiss_index"
    version = result["index_version"]
    assert (index_root / "ACTIVE").read_text(encoding="utf-8").strip() == version
    version_dir = index_root / "versions" / version
    assert (version_dir / "index.faiss").exists()
    assert (version_dir / "metadata.jsonl").exists()
    assert (version_dir / "manifest.json").exists()
