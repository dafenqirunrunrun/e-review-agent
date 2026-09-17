from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.rag.dense_retriever import HashDenseRetriever
from app.rag.embedding_provider import local_bge_m3_provider
from app.rag.sparse_retriever import BM25Retriever
from app.rag.versioned_faiss_index import VersionedFaissIndex


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data" / "private_research" / "enterprise_rag_v180"
CORPUS = DATA_ROOT / "difficult_corpus.jsonl"
QUERIES = DATA_ROOT / "difficult_queries.jsonl"
INDEX_ROOT = DATA_ROOT / "faiss_index"
RESULT = ROOT / "data" / "private_research" / "eval" / "v180_real_retrieval_eval.json"
DOC = ROOT / "docs" / "enterprise" / "v180_real_retrieval_eval.md"


def main() -> None:
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = evaluate()
    except Exception as exc:  # noqa: BLE001 - script must write a gate artifact on blocked runtime.
        result = {
            "status": "V180_REAL_RETRIEVAL_EVAL_BLOCKED",
            "blocked_reason": type(exc).__name__,
            "blocked_detail": str(exc),
            "real_bge_m3_used": False,
            "faiss_executed": False,
            "hash_dense_used_for_primary": False,
        }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    DOC.write_text(render_doc(result), encoding="utf-8", newline="\n")
    print(result["status"])
    if result["status"].endswith("_BLOCKED"):
        raise SystemExit(2)


def evaluate() -> dict[str, Any]:
    corpus_all = read_jsonl(CORPUS)
    queries = read_jsonl(QUERIES)
    active_corpus = [row for row in corpus_all if row.get("active", True) and not row.get("deleted", False)]
    provider = local_bge_m3_provider(device="cpu")
    started = time.perf_counter()
    doc_vectors = provider.encode_documents([row["content"] for row in active_corpus])
    query_vectors = provider.encode_queries([row["query_text"] for row in queries])
    encode_ms = round((time.perf_counter() - started) * 1000, 4)
    metadata = [metadata_row(row, position) for position, row in enumerate(active_corpus)]
    provider_meta = provider.metadata()
    provider.close()

    index_store = VersionedFaissIndex(INDEX_ROOT)
    index_store.cleanup_staging()
    manifest = index_store.build_staging(
        doc_vectors,
        metadata,
        embedding_model=provider_meta["model_id"],
        embedding_hash=provider_meta["model_hash"],
    )
    published = index_store.publish(manifest.index_version)
    index, loaded_metadata, loaded_manifest = index_store.load_active()
    restart_index_store = VersionedFaissIndex(INDEX_ROOT)
    restarted_index, restarted_metadata, restarted_manifest = restart_index_store.load_active()

    dense_results = dense_search(index, loaded_metadata, query_vectors, queries)
    restarted_results = dense_search(restarted_index, restarted_metadata, query_vectors, queries)
    sparse_results = sparse_search(active_corpus, queries)
    hybrid_results = rrf_fuse(dense_results, sparse_results)
    hash_negative = hash_dense_negative_control(active_corpus, queries)

    metrics = {
        "dense_bge_m3_faiss": compute_metrics(queries, dense_results),
        "sparse_bm25": compute_metrics(queries, sparse_results),
        "hybrid_bge_m3_bm25_rrf": compute_metrics(queries, hybrid_results),
        "hash_dense_negative_control": compute_metrics(queries, hash_negative),
    }
    status = "V180_REAL_RETRIEVAL_EVAL_PASS"
    blockers = []
    if loaded_manifest.index_version != restarted_manifest.index_version:
        blockers.append("restart version mismatch")
    if dense_results != restarted_results:
        blockers.append("restart search mismatch")
    if metrics["hybrid_bge_m3_bm25_rrf"]["recall_at_5"] < 0.50:
        blockers.append("hybrid recall below minimum evidence threshold")
    if blockers:
        status = "V180_REAL_RETRIEVAL_EVAL_BLOCKED"

    return {
        "status": status,
        "blockers": blockers,
        "corpus_count": len(corpus_all),
        "active_corpus_count": len(active_corpus),
        "query_count": len(queries),
        "real_bge_m3_used": True,
        "faiss_executed": True,
        "versioned_faiss_published": True,
        "persistent_restart_verified": dense_results == restarted_results,
        "hash_dense_used_for_primary": False,
        "hash_dense_negative_control_only": True,
        "encode_latency_ms": encode_ms,
        "index_version": published.index_version,
        "index_manifest": published.__dict__,
        "loaded_manifest": loaded_manifest.__dict__,
        "restarted_manifest": restarted_manifest.__dict__,
        "provider_metadata": provider_meta,
        "metrics": metrics,
    }


def dense_search(index: Any, metadata: list[dict[str, Any]], query_vectors: np.ndarray, queries: list[dict[str, Any]]) -> dict[str, list[str]]:
    matrix = np.asarray(query_vectors, dtype="float32")
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
    faiss.normalize_L2(matrix)
    scores, indexes = index.search(matrix, min(50, len(metadata)))
    results: dict[str, list[str]] = {}
    for row, score_row, index_row in zip(queries, scores, indexes):
        hits = []
        seen = set()
        for score, idx in zip(score_row, index_row):
            if idx < 0:
                continue
            candidate = metadata[int(idx)]
            if candidate["tenant_id"] != row["tenant_id"]:
                continue
            if candidate["chunk_id"] in seen:
                continue
            if float(score) <= 0:
                continue
            seen.add(candidate["chunk_id"])
            hits.append(candidate["chunk_id"])
            if len(hits) >= 10:
                break
        results[row["query_id"]] = hits
    return results


def sparse_search(active_corpus: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, list[str]]:
    retriever = BM25Retriever(active_corpus)
    return {
        row["query_id"]: [hit.chunk_id for hit in retriever.search(row["query_text"], top_k=10, tenant_id=row["tenant_id"])]
        for row in queries
    }


def rrf_fuse(dense_results: dict[str, list[str]], sparse_results: dict[str, list[str]], rrf_k: int = 60) -> dict[str, list[str]]:
    fused = {}
    for query_id in sorted(set(dense_results) | set(sparse_results)):
        scores: dict[str, float] = {}
        for source in (dense_results.get(query_id, []), sparse_results.get(query_id, [])):
            for rank, chunk_id in enumerate(source, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (rrf_k + rank)
        fused[query_id] = [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:10]]
    return fused


def hash_dense_negative_control(active_corpus: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, list[str]]:
    retriever = HashDenseRetriever(active_corpus)
    return {
        row["query_id"]: [hit.chunk_id for hit in retriever.search(row["query_text"], top_k=10, tenant_id=row["tenant_id"])]
        for row in queries
    }


def compute_metrics(queries: list[dict[str, Any]], results: dict[str, list[str]]) -> dict[str, Any]:
    scored_queries = [row for row in queries if row["gold_chunk_ids"]]
    negatives = [row for row in queries if not row["gold_chunk_ids"]]
    hit1 = hit3 = hit5 = 0
    reciprocal = 0.0
    ndcg = 0.0
    empty = 0
    forbidden_hits = 0
    for row in scored_queries:
        hits = results.get(row["query_id"], [])
        if not hits:
            empty += 1
        gold = set(row["gold_chunk_ids"])
        forbidden_hits += len(set(hits[:5]) & set(row["forbidden_chunk_ids"]))
        rank = next((index for index, chunk_id in enumerate(hits, start=1) if chunk_id in gold), None)
        if rank and rank <= 5:
            hit5 += 1
            reciprocal += 1 / rank
            ndcg += 1 / math.log2(rank + 1)
            if rank <= 3:
                hit3 += 1
            if rank == 1:
                hit1 += 1
    false_positive_negatives = sum(1 for row in negatives if results.get(row["query_id"]))
    total = max(1, len(scored_queries))
    return {
        "evaluated_positive_queries": len(scored_queries),
        "evaluated_negative_queries": len(negatives),
        "hit_at_1": round(hit1 / total, 4),
        "hit_at_3": round(hit3 / total, 4),
        "hit_at_5": round(hit5 / total, 4),
        "recall_at_5": round(hit5 / total, 4),
        "mrr": round(reciprocal / total, 4),
        "ndcg_at_5": round(ndcg / total, 4),
        "empty_retrieval_rate": round(empty / total, 4),
        "forbidden_top5_hit_count": forbidden_hits,
        "negative_control_false_positive_count": false_positive_negatives,
    }


def metadata_row(row: dict[str, Any], position: int) -> dict[str, Any]:
    return {
        "position": position,
        "tenant_id": row["tenant_id"],
        "document_id": row["document_id"],
        "document_version": row["document_version"],
        "chunk_id": row["chunk_id"],
        "trust_level": row["trust_level"],
        "topic": row["metadata"]["topic"],
        "role": row["metadata"]["role"],
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def render_doc(result: dict[str, Any]) -> str:
    metrics = result.get("metrics", {})
    lines = [
        "# v1.8.0 Real Retrieval Evaluation",
        "",
        f"Status: `{result['status']}`",
        "",
        "## Evidence Boundary",
        "",
        f"- Real BGE-M3 used: `{result.get('real_bge_m3_used')}`",
        f"- FAISS executed: `{result.get('faiss_executed')}`",
        f"- Persistent restart verified: `{result.get('persistent_restart_verified')}`",
        f"- Hash dense primary path: `{result.get('hash_dense_used_for_primary')}`",
        "",
        "## Metrics",
        "",
    ]
    for name, values in metrics.items():
        lines.append(f"### {name}")
        lines.append("")
        for key in ["hit_at_1", "hit_at_3", "hit_at_5", "recall_at_5", "mrr", "ndcg_at_5", "empty_retrieval_rate", "forbidden_top5_hit_count", "negative_control_false_positive_count"]:
            lines.append(f"- {key}: `{values.get(key)}`")
        lines.append("")
    if result.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in result["blockers"])
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
