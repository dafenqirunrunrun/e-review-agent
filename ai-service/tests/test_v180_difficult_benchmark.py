import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_v180_difficult_benchmark_generation_and_audit_pass():
    result = subprocess.run(
        [PYTHON, "ai-service/scripts/build_v180_difficult_rag_benchmark.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "V180_DIFFICULT_BENCHMARK_PASS" in result.stdout
    audit = json.loads((ROOT / "data/private_research/audit/v180_difficult_benchmark_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "V180_DIFFICULT_BENCHMARK_PASS"
    assert audit["closed_holdout_accessed"] is False
    assert audit["external_test_accessed"] is False
    assert audit["real_user_text_used"] is False
    assert audit["hash_dense_used"] is False


def test_v180_difficult_benchmark_has_tenant_and_topic_coverage():
    corpus = read_jsonl(ROOT / "data/private_research/enterprise_rag_v180/difficult_corpus.jsonl")
    queries = read_jsonl(ROOT / "data/private_research/enterprise_rag_v180/difficult_queries.jsonl")
    assert len(corpus) == 192
    assert len(queries) == 52
    assert len({row["tenant_id"] for row in corpus}) == 4
    assert len({row["topic"] for row in queries}) == 13
    assert all(row["metadata"]["generated_project_owned_synthetic"] is True for row in corpus)


def test_v180_difficult_benchmark_gold_is_active_and_tenant_scoped():
    corpus = read_jsonl(ROOT / "data/private_research/enterprise_rag_v180/difficult_corpus.jsonl")
    queries = read_jsonl(ROOT / "data/private_research/enterprise_rag_v180/difficult_queries.jsonl")
    by_chunk = {row["chunk_id"]: row for row in corpus}
    for query in queries:
        for chunk_id in query["gold_chunk_ids"]:
            gold = by_chunk[chunk_id]
            assert gold["tenant_id"] == query["tenant_id"]
            assert gold["active"] is True
            assert gold["deleted"] is False
            assert chunk_id not in query["forbidden_chunk_ids"]


def test_v180_difficult_benchmark_includes_hard_negative_controls():
    queries = read_jsonl(ROOT / "data/private_research/enterprise_rag_v180/difficult_queries.jsonl")
    negatives = [row for row in queries if "negative_control" in row["difficulty_tags"]]
    assert len(negatives) == 4
    assert all(row["gold_chunk_ids"] == [] for row in negatives)
    assert all(row["expected_human_review"] is False for row in negatives)
