from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a3_common import PROVIDER_IMPLS, make_provider, provider_config, write_phase3a3_json


def run() -> dict:
    texts = ["refund broken after-sales policy", "unsafe smoke fire battery", "商品坏了想退货", "物流延迟太慢"] * 3
    providers = {}
    for impl in PROVIDER_IMPLS:
        cfg = provider_config(impl)
        rss_before = _rss_mb()
        provider = make_provider(impl)
        try:
            started = time.perf_counter_ns()
            provider.embed_query("resource benchmark cold start")
            cold_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
            rss_after = _rss_mb()
            latencies = []
            for _ in range(5):
                tick = time.perf_counter_ns()
                provider.embed_documents(texts)
                latencies.append((time.perf_counter_ns() - tick) / 1_000_000)
            providers[impl] = {
                "status": "PASS",
                "providerImpl": impl,
                "device": provider.metadata().get("device", cfg["device"]),
                "dtype": provider.metadata().get("dtype", ""),
                "batchSize": cfg["batchSize"],
                "maxLength": cfg["maxLength"],
                "sampleCount": len(texts) * len(latencies),
                "coldStartMs": cold_ms,
                "warmP50Ms": _pct(latencies, 0.5),
                "warmP95Ms": _pct(latencies, 0.95),
                "warmP99Ms": _pct(latencies, 0.99),
                "throughputPerSecond": round((len(texts) * len(latencies)) / max(0.001, sum(latencies) / 1000), 3),
                "rssBeforeMb": rss_before,
                "rssAfterModelMb": rss_after,
                **_cuda_memory(),
            }
        except Exception as exc:
            providers[impl] = {"status": "BLOCKED", "providerImpl": impl, "reason": str(exc)[:240], "rssBeforeMb": rss_before}
        finally:
            provider.close()
    output = {"schemaVersion": "1.0.0", "providers": providers}
    write_phase3a3_json("provider-resource-summary.json", output)
    return output


def _rss_mb() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024)
    except Exception:
        return 0


def _cuda_memory() -> dict[str, int]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"cudaPeakAllocatedMb": 0, "cudaPeakReservedMb": 0}
        return {
            "cudaPeakAllocatedMb": int(torch.cuda.max_memory_allocated() / 1024 / 1024),
            "cudaPeakReservedMb": int(torch.cuda.max_memory_reserved() / 1024 / 1024),
        }
    except Exception:
        return {"cudaPeakAllocatedMb": 0, "cudaPeakReservedMb": 0}


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))], 3)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
