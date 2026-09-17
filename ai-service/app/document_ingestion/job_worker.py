"""Single-machine worker: durable queue ownership stays in the Java/MySQL service."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.request import Request, urlopen

from app.document_ingestion.router import DocumentParserRouter


LIGHT_EXECUTION_CLASS = "light"
HEAVY_EXECUTION_CLASS = "heavy"


@contextmanager
def worker_lock(path: Path):
    """One serial parser supervisor per local runtime; OS releases this lock on exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class WorkerClient:
    def __init__(self, base_url: str, token: str):
        from urllib.parse import urlparse

        url = urlparse(base_url)
        if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username:
            raise ValueError("WORKER_REQUIRES_LOOPBACK_URL")
        if len(token) < 32:
            raise ValueError("DOCUMENT_WORKER_TOKEN_REQUIRED")
        self.base_url = base_url.rstrip("/") + "/internal/document-jobs"
        self.token = token

    def post(self, path: str, data: dict | None = None) -> dict:
        request = Request(self.base_url + path, json.dumps(data or {}).encode(), method="POST", headers={
            "Content-Type": "application/json", "X-Document-Worker-Token": self.token,
        })
        with urlopen(request, timeout=15) as response:
            return json.load(response)


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def parse_task(task: dict, output: Path) -> None:
    root = Path(task["root"]).resolve()
    source = (root / task["inputPath"]).resolve()
    if not source.is_relative_to(root) or not output.resolve().is_relative_to(root):
        raise ValueError("DOCUMENT_PATH_INVALID")
    if hashlib.sha256(source.read_bytes()).hexdigest() != task["fileHash"]:
        raise ValueError("DOCUMENT_HASH_MISMATCH")
    if source.suffix.lower() in {".docx", ".pptx", ".xlsx"}:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(item.file_size for item in members) > 200 * 1024 * 1024:
                raise ValueError("DOCUMENT_ARCHIVE_LIMIT")
    result = DocumentParserRouter().parse(
        source, document_id=task["id"], source_name=task["sourceName"],
        source_type="uploaded_document", source_uri=task["sourceUrl"] or f"document:{task['id']}",
    )
    if not result.nodes:
        raise ValueError("DOCUMENT_EMPTY")
    result.metadata.update({"usageType": task["usageType"], "pipelineVersion": task["pipelineVersion"],
                            "fileHash": task["fileHash"], "published": False})
    atomic_json(output, result.model_dump(mode="json"))
    atomic_json(output.parent / "manifest.json", {
        "documentId": result.documentId, "sourceName": result.sourceName, "sourceUri": result.sourceUri,
        "fileHash": task["fileHash"], "contentHash": result.contentHash,
        "parser": result.parser, "parserVersion": result.parserVersion,
        "pipelineVersion": task["pipelineVersion"], "nodeCount": len(result.nodes),
        "assetCount": len(result.assets), "published": False,
        "attempts": [attempt.model_dump(mode="json") for attempt in result.attempts],
    })


def _kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=15)


def process_one(client: WorkerClient, task: dict, *, timeout: float = 600, heartbeat_interval: float = 20) -> bool:
    directory = Path(task["root"]) / task["id"] / task["leaseToken"]
    directory.mkdir(parents=True, exist_ok=True)
    task_path = directory / "task.json"
    atomic_json(task_path, task)
    script = Path(__file__).resolve().parents[2] / "scripts" / "document_job_worker.py"
    body = {"leaseToken": task["leaseToken"]}
    error = ""
    with (directory / "parser.log").open("wb") as log:
        process = subprocess.Popen([sys.executable, str(script), "--parse-task", str(task_path)],
                                   stdout=log, stderr=log, start_new_session=os.name != "nt")
        started = last_heartbeat = time.monotonic()
        try:
            while process.poll() is None:
                now = time.monotonic()
                if now - started >= timeout:
                    _kill_tree(process)
                    error = "DOCUMENT_PARSE_TIMEOUT"
                    break
                if now - last_heartbeat >= heartbeat_interval:
                    if not client.post(f"/{task['id']}/heartbeat", body).get("accepted"):
                        _kill_tree(process)
                        return False
                    last_heartbeat = now
                time.sleep(min(0.2, heartbeat_interval))
        except BaseException:
            if process.poll() is None:
                _kill_tree(process)
            raise
    if process.returncode and not error:
        error = "DOCUMENT_PARSE_FAILED"
        error_path = directory / "error.json"
        if error_path.exists():
            error = json.loads(error_path.read_text(encoding="utf-8"))["errorCode"]
    # Retry completion after a lost HTTP response is safe: lease fencing prevents double completion.
    return bool(client.post(f"/{task['id']}/finish", {**body, "errorCode": error}).get("accepted"))


def run_bounded_scheduler(
    client: WorkerClient,
    *,
    light_workers: int = 4,
    heavy_workers: int = 1,
    stop_when_idle: bool = False,
    poll_interval: float = 3.0,
    handler=process_one,
) -> dict[str, object]:
    """Drain classed durable work without allowing heavy jobs to crowd out light files."""
    if not 1 <= light_workers <= 16 or not 1 <= heavy_workers <= 2:
        raise ValueError("DOCUMENT_WORKER_CONCURRENCY_INVALID")
    pools = {
        LIGHT_EXECUTION_CLASS: ThreadPoolExecutor(max_workers=light_workers, thread_name_prefix="document-light"),
        HEAVY_EXECUTION_CLASS: ThreadPoolExecutor(max_workers=heavy_workers, thread_name_prefix="document-heavy"),
    }
    limits = {LIGHT_EXECUTION_CLASS: light_workers, HEAVY_EXECUTION_CLASS: heavy_workers}
    active: dict[Future, tuple[str, str]] = {}
    completed = failed = 0
    max_active = {LIGHT_EXECUTION_CLASS: 0, HEAVY_EXECUTION_CLASS: 0}

    def execute(task: dict) -> bool:
        accepted = bool(handler(client, task))
        print(json.dumps({"taskId": task["id"], "completionAccepted": accepted}), flush=True)
        return accepted

    try:
        while True:
            for future in [item for item in active if item.done()]:
                try:
                    accepted = bool(future.result())
                    completed += int(accepted)
                    failed += int(not accepted)
                except Exception as exc:
                    failed += 1
                    print(json.dumps({"workerError": type(exc).__name__}), flush=True)
                del active[future]

            claimed = 0
            for execution_class, pool in pools.items():
                class_active = sum(1 for current_class, _ in active.values() if current_class == execution_class)
                while class_active < limits[execution_class]:
                    try:
                        task = client.post("/claim", {"executionClass": execution_class}).get("task")
                    except Exception as exc:
                        print(json.dumps({"workerError": type(exc).__name__}), flush=True)
                        if stop_when_idle:
                            raise
                        break
                    if not task:
                        break
                    actual_class = task.get("executionClass", execution_class)
                    if actual_class != execution_class:
                        raise ValueError("DOCUMENT_EXECUTION_CLASS_MISMATCH")
                    future = pool.submit(execute, task)
                    active[future] = (execution_class, str(task["id"]))
                    class_active += 1
                    claimed += 1
                    max_active[execution_class] = max(max_active[execution_class], class_active)

            if stop_when_idle and not active and claimed == 0:
                break
            time.sleep(0.01 if active else poll_interval)
    finally:
        for pool in pools.values():
            pool.shutdown(wait=True, cancel_futures=False)
    return {
        "completed": completed,
        "failed": failed,
        "maxActive": max_active,
        "lightWorkers": light_workers,
        "heavyWorkers": heavy_workers,
    }
