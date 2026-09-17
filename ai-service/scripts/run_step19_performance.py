from __future__ import annotations

import concurrent.futures
import ctypes
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.core.config import settings

INDEX = ROOT / "data/policy_rag_real/index/policy_chunks.jsonl"


def percentile(values, value):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * value))], 2)


def summary(rows):
    return {"avg": round(statistics.mean(rows), 2), "p50": percentile(rows, .5), "p95": percentile(rows, .95), "p99": percentile(rows, .99), "max": round(max(rows), 2)}


def memory_mb() -> float:
    if os.name != "nt":
        return 0.0

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return 0.0
    return round(counters.WorkingSetSize / (1024 * 1024), 2)


def run_workload(retriever, query, hints, workers, *, mode="hybrid", cache_enabled, repeats=4):
    settings.policy_rag.query_cache_enabled = cache_enabled
    if retriever.dense_store:
        retriever.dense_store.clear_query_cache()
    if cache_enabled and mode != "bm25":
        # Populate exactly this key before concurrent callers arrive. This measures
        # a genuine repeated-query hit rather than a cold-cache stampede.
        retriever.search(query, risk_hints=hints, top_k=3, mode=mode)

    def one(_):
        started = time.perf_counter()
        hits = retriever.search(query, risk_hints=hints, top_k=3, mode=mode)
        return (time.perf_counter() - started) * 1000, bool(hits)
    started = time.perf_counter()
    cpu_started = time.process_time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, range(workers * repeats)))
    elapsed = time.perf_counter() - started
    cpu_percent = round(((time.process_time() - cpu_started) / elapsed) * 100 / max(1, os.cpu_count() or 1), 2)
    return {
        "mode": mode,
        "cacheEnabled": cache_enabled,
        "requestCount": len(rows),
        "rps": round(len(rows) / elapsed, 3),
        "latencyMs": summary([row[0] for row in rows]),
        "errorRate": round(sum(not row[1] for row in rows) / len(rows), 4),
        "cpuPercent": cpu_percent,
        "workingSetMb": memory_mb(),
    }


def main():
    retriever = PolicyEvidenceRetriever.from_jsonl(INDEX, enable_dense=True)
    # Warm model/index, then collect workloads with explicit cache semantics.
    retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")
    workloads = {
        "light": ("物流很快，包装完整，商品和描述一致。", [], "bm25", False),
        "strict_uncached": ("五星截图返现，要求删除差评", ["rating_manipulation", "review_suppression"], "hybrid", False),
        "strict_cached": ("五星截图返现", ["rating_manipulation"], "hybrid", True),
        "mixed": ("退款后要求改成五星好评", ["after_sales_risk", "rating_manipulation"], "hybrid", False),
    }
    result = {"schemaVersion": "step19-performance-v1", "readiness": retriever.readiness(), "workloads": {}}
    for name, (query, hints, mode, cache_enabled) in workloads.items():
        result["workloads"][name] = {
            str(workers): run_workload(retriever, query, hints, workers, mode=mode, cache_enabled=cache_enabled)
            for workers in (1, 5, 10, 20)
        }
    settings.policy_rag.query_cache_enabled = True
    retriever.dense_store.clear_query_cache()
    retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")
    before = retriever.dense_store.cache_stats()
    retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")
    after = retriever.dense_store.cache_stats()
    retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=5, mode="hybrid")
    result["cache"] = {
        "before": before,
        "after": after,
        "afterTopKChange": retriever.dense_store.cache_stats(),
        "versionIsolation": "contentRootHash+modelIdentity+topK+normalizedQuery",
    }
    result["finalReadiness"] = retriever.readiness()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
