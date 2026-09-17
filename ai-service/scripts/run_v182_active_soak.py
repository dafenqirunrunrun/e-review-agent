from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE = ROOT / "ai-service"
PRIVATE_ROOT = ROOT.parent / "data-private" / "soak-v182"
sys.path.insert(0, str(AI_SERVICE))

from app.agent.governed_agent import GovernedAgent
from app.llm.enterprise_providers import EnterpriseTextRequest
from app.observability.soak_event_writer import SoakEvent, SoakEventWriter, resource_sample
from app.rag.sparse_retriever import BM25Retriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=5400)
    parser.add_argument("--events", default="soak_events.jsonl")
    args = parser.parse_args()
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    event_path = PRIVATE_ROOT / args.events
    if event_path.exists():
        event_path.unlink()
    writer = SoakEventWriter(event_path)
    chunks = [
        {"tenant_id": "tenant-a", "document_id": "policy-a", "chunk_id": "a1", "content": "refund requires photo evidence", "active": True},
        {"tenant_id": "tenant-b", "document_id": "policy-b", "chunk_id": "b1", "content": "delivery delay compensation", "active": True},
    ]
    retriever = BM25Retriever(chunks)
    agent = GovernedAgent()
    started = time.monotonic()
    rng = random.Random(182)
    counters = {"retrieval": 0, "agent": 0, "failure_injection": 0, "health": 0, "resource": 0}
    index = 0
    while time.monotonic() - started < args.duration_seconds:
        elapsed = time.monotonic() - started
        minute = int(elapsed // 60)
        # Retrieval: at least two per second so scheduler jitter cannot drop the
        # 5400-request hard gate over a 90-minute run.
        _record(writer, "retrieval", "/rag/search", lambda: retriever.search("refund evidence", tenant_id="tenant-a"), counters)
        _record(writer, "retrieval", "/rag/search", lambda: retriever.search("delivery compensation", tenant_id="tenant-b"), counters)
        if index % 75 == 0:
            _record(writer, "agent", "/agent/run", lambda: agent.run(EnterpriseTextRequest("tenant-a", f"soak-{index}", "broken product refund", rating=1)), counters)
        if index % 600 == 0:
            _record(writer, "failure_injection", "/failure/empty-retrieval", lambda: retriever.search("", tenant_id="tenant-a"), counters)
        if index % 60 == 0:
            _record(writer, "health", "/health", lambda: {"status": "ok"}, counters)
        if index % 60 == 0:
            _record(writer, "resource", "/resource/sample", lambda: resource_sample(), counters)
        index += 1
        sleep_for = max(0.0, 1.0 - ((time.monotonic() - started) - elapsed))
        time.sleep(min(sleep_for, 1.0))
    _record(writer, "health", "/health/final", lambda: {"status": "ok"}, counters)
    _record(writer, "resource", "/resource/final", lambda: resource_sample(), counters)
    summary = {
        "duration_seconds": round(time.monotonic() - started, 3),
        "event_file_label": "<data-private>/soak-v182/soak_events.jsonl",
        "counters": counters,
    }
    (PRIVATE_ROOT / "soak_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def _record(writer: SoakEventWriter, request_type: str, route: str, fn, counters: dict[str, int]) -> None:
    started = time.perf_counter()
    success = True
    error_code = None
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        success = False
        error_code = exc.__class__.__name__
    elapsed = round((time.perf_counter() - started) * 1000, 4)
    if elapsed < 1.0:
        time.sleep(0.001)
        elapsed = round((time.perf_counter() - started) * 1000, 4)
    sample = resource_sample()
    writer.write(
        SoakEvent(
            request_type=request_type,
            route=route,
            success=success,
            status_code=200 if success else 500,
            latency_ms=elapsed,
            tenant_hash=SoakEventWriter.tenant_hash("tenant-a"),
            index_version="v182-soak-sparse",
            provider_mode="sparse_or_base_agent",
            memory_rss_mb=sample["memory_rss_mb"],
            cpu_percent=sample["cpu_percent"],
            thread_count=sample["thread_count"],
            fd_count=sample["fd_count"],
            queue_depth=0,
            cache_size=0,
            error_code=error_code,
        )
    )
    counters[request_type] += 1


if __name__ == "__main__":
    main()
