from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402,F401
from app.document_ingestion.candidate_index import PolicyIndexReleaseStore, build_candidate  # noqa: E402
from app.document_ingestion.job_worker import WorkerClient, _kill_tree, atomic_json, worker_lock  # noqa: E402


def _process(client: WorkerClient, task: dict, *, timeout: float = 1800, heartbeat_interval: float = 20) -> bool:
    directory = Path(task["root"]) / "index-releases" / task["id"] / task["leaseToken"]
    directory.mkdir(parents=True, exist_ok=True)
    task_path = directory / "task.json"
    atomic_json(task_path, task)
    body = {"leaseToken": task["leaseToken"]}
    error = ""
    with (directory / "index.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--build-task", str(task_path)],
            stdout=log, stderr=log, start_new_session=os.name != "nt",
        )
        started = last_heartbeat = time.monotonic()
        while process.poll() is None:
            now = time.monotonic()
            if now - started >= timeout:
                _kill_tree(process)
                error = "INDEX_BUILD_TIMEOUT"
                break
            if now - last_heartbeat >= heartbeat_interval:
                if not client.post(f"/index/{task['id']}/heartbeat", body).get("accepted"):
                    _kill_tree(process)
                    return False
                last_heartbeat = now
            time.sleep(0.2)
    if process.returncode and not error:
        result_path = directory / "build-result.json"
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            if result.get("gate") == "FAIL":
                error = "INDEX_QUALITY_GATE_FAILED"
        error_path = directory / "error.json"
        if not error:
            error = "INDEX_BUILD_FAILED"
        if error_path.is_file() and error == "INDEX_BUILD_FAILED":
            error = str(json.loads(error_path.read_text(encoding="utf-8-sig")).get("errorCode") or error)
    return bool(client.post(f"/index/{task['id']}/finish", {**body, "errorCode": error}).get("accepted"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Durable candidate policy-index worker")
    parser.add_argument("--base-url", default="http://127.0.0.1:8083")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--build-task", type=Path)
    parser.add_argument("--publish", nargs=2, metavar=("INDEX_ROOT", "VERSION"))
    parser.add_argument("--rollback", nargs=2, metavar=("INDEX_ROOT", "VERSION"))
    parser.add_argument("--deactivate", nargs=2, metavar=("INDEX_ROOT", "VERSION"))
    args = parser.parse_args()
    if args.publish:
        result = PolicyIndexReleaseStore(args.publish[0]).publish(args.publish[1])
        print(json.dumps({"version": result["version"], "active": result["active"]}))
        return 0
    if args.rollback:
        result = PolicyIndexReleaseStore(args.rollback[0]).rollback(args.rollback[1])
        print(json.dumps({"version": result["version"], "active": result["active"]}))
        return 0
    if args.deactivate:
        print(json.dumps(PolicyIndexReleaseStore(args.deactivate[0]).deactivate(args.deactivate[1])))
        return 0
    if args.build_task:
        task = json.loads(args.build_task.read_text(encoding="utf-8-sig"))
        directory = args.build_task.parent
        try:
            manifest = build_candidate(Path(task["root"]) / task["requestPath"])
            atomic_json(directory / "build-result.json", manifest)
            return 0 if manifest["gate"] == "PASS" else 1
        except Exception as exc:
            code = str(exc)
            if not re.fullmatch(r"[A-Z0-9_]{1,100}", code):
                code = "INDEX_BUILD_FAILED"
            atomic_json(directory / "error.json", {"errorCode": code})
            return 1

    client = WorkerClient(args.base_url, os.getenv("DOCUMENT_WORKER_TOKEN", ""))
    lock = Path(__file__).resolve().parents[1] / "runtime" / "document-workers" / "index.lock"
    with worker_lock(lock):
        while True:
            try:
                task = client.post("/index/claim").get("task")
                if task:
                    _process(client, task)
                elif args.once:
                    return 0
                else:
                    time.sleep(3)
            except Exception as exc:
                print(json.dumps({"indexWorkerError": type(exc).__name__}), flush=True)
                if args.once:
                    return 1
                time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
