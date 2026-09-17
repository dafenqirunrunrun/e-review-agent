from __future__ import annotations

import concurrent.futures
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.policy_rag.retriever import PolicyEvidenceRetriever


def stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "avg": round(statistics.mean(values), 2),
        "p50": round(ordered[len(ordered) // 2], 2),
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
        "max": round(max(values), 2),
    }


def main() -> None:
    settings.policy_rag.query_cache_enabled = False
    retriever = PolicyEvidenceRetriever.from_jsonl(ROOT / "data/policy_rag_real/index/policy_chunks.jsonl", enable_dense=True)
    query = "五星截图返现，要求删除差评"
    hints = ["rating_manipulation", "review_suppression"]
    retriever.search(query, risk_hints=hints, top_k=3, mode="hybrid")
    serial: list[float] = []
    parallel: list[float] = []
    for _ in range(6):
        retriever.dense_store.clear_query_cache()
        started = time.perf_counter()
        retriever.search(query, risk_hints=hints, top_k=3, mode="hybrid")
        serial.append((time.perf_counter() - started) * 1000)
    expanded = " ".join([query, retriever._expand_risk_hints(hints)]).strip()
    for _ in range(6):
        retriever.dense_store.clear_query_cache()
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            bm25_future = executor.submit(retriever._bm25_search, expanded, hints, top_k=12)
            dense_future = executor.submit(retriever._dense_search, expanded, top_k=12)
            bm25 = bm25_future.result()
            dense = dense_future.result()
        retriever._fuse(bm25, dense, top_k=3)
        parallel.append((time.perf_counter() - started) * 1000)
    print(json.dumps({"sampleCount": 6, "serial": stats(serial), "parallel": stats(parallel), "p95DeltaMs": round(stats(serial)["p95"] - stats(parallel)["p95"], 2)}, indent=2))


if __name__ == "__main__":
    main()
