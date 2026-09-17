from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.policy_rag.retriever import PolicyEvidenceRetriever


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a small local latency baseline for Step 13.")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    samples = max(2, min(args.samples, 20))
    retriever = PolicyEvidenceRetriever()
    client = TestClient(app)
    report = {
        "schemaVersion": "review-governance-latency-baseline-v1",
        "samples": samples,
        "bm25Ms": _measure(lambda: retriever.search("删除差评", risk_hints=["review_suppression"], top_k=3, mode="bm25"), samples),
        "hybridMs": _measure(lambda: retriever.search("好评返现 五星截图", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid"), samples),
        "cachedReuseMs": _measure(lambda: retriever.search("好评返现 五星截图", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid"), samples),
        "warmAnalyzeMs": _measure(
            lambda: client.post(
                "/api/v1/review/analyze",
                json={
                    "review_id": "latency-baseline",
                    "product_id": "P-LAT",
                    "product_name": "Latency product",
                    "review_text": "cashback for five star review screenshot",
                    "image_urls": [],
                    "rating": 5,
                },
            ),
            samples,
        ),
        "retrieverReadiness": retriever.readiness(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _measure(fn: Callable[[], object], samples: int) -> dict[str, float]:
    values = []
    for _ in range(samples):
        started = time.perf_counter()
        fn()
        values.append((time.perf_counter() - started) * 1000)
    ordered = sorted(values)
    return {
        "avg": round(statistics.mean(values), 2),
        "p50": round(statistics.median(values), 2),
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
        "max": round(max(values), 2),
    }


if __name__ == "__main__":
    raise SystemExit(main())
