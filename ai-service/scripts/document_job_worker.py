from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402,F401 -- shared local env loader
from app.document_ingestion.job_worker import (  # noqa: E402
    WorkerClient,
    atomic_json,
    parse_task,
    process_one,
    run_bounded_scheduler,
    worker_lock,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial, lease-fenced document ingestion worker")
    parser.add_argument("--base-url", default="http://127.0.0.1:8083")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true")
    parser.add_argument("--light-workers", type=int, default=int(os.getenv("E_REVIEW_DOCUMENT_LIGHT_WORKERS", "4")))
    parser.add_argument("--heavy-workers", type=int, default=int(os.getenv("E_REVIEW_DOCUMENT_HEAVY_WORKERS", "1")))
    parser.add_argument("--parse-task", type=Path)
    args = parser.parse_args()
    if args.parse_task:
        task = json.loads(args.parse_task.read_text(encoding="utf-8"))
        try:
            parse_task(task, args.parse_task.parent / "normalized.json")
            return 0
        except Exception as exc:
            code = getattr(exc, "reason_code", str(exc))
            if not re.fullmatch(r"[A-Z0-9_]{1,100}", code):
                code = "DOCUMENT_PARSE_FAILED"
            atomic_json(args.parse_task.parent / "error.json", {"errorCode": code})
            return 1
    client = WorkerClient(args.base_url, os.getenv("DOCUMENT_WORKER_TOKEN", ""))
    lock_path = Path(__file__).resolve().parents[1] / "runtime" / "document-workers" / "queue.lock"
    if args.once and args.drain:
        parser.error("--once and --drain are mutually exclusive")
    with worker_lock(lock_path):
        return run(
            client,
            once=args.once,
            drain=args.drain,
            light_workers=args.light_workers,
            heavy_workers=args.heavy_workers,
        )


def run(client: WorkerClient, *, once: bool, drain: bool = False, light_workers: int = 4, heavy_workers: int = 1) -> int:
    if once:
        try:
            task = client.post("/claim", {"executionClass": "any"}).get("task")
            return 0 if not task or process_one(client, task) else 1
        except Exception as exc:
            print(json.dumps({"workerError": type(exc).__name__}), flush=True)
            return 1
    try:
        summary = run_bounded_scheduler(
            client,
            light_workers=light_workers,
            heavy_workers=heavy_workers,
            stop_when_idle=drain,
        )
        return 0 if not summary["failed"] else 1
    except Exception as exc:
        print(json.dumps({"workerError": type(exc).__name__}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
