import hashlib
import json
import threading
import time
from collections import deque
from pathlib import Path

import pytest

from app.document_ingestion.job_worker import (
    WorkerClient,
    atomic_json,
    parse_task,
    process_one,
    run_bounded_scheduler,
    worker_lock,
)


def task_at(tmp_path, suffix="md", content=b"# Policy\n\n## Reviews\n\nDo not buy fake reviews."):
    source = tmp_path / ("original." + suffix)
    source.write_bytes(content)
    return {"id": "test-document", "root": str(tmp_path), "inputPath": source.name,
            "fileHash": hashlib.sha256(content).hexdigest(), "sourceName": "Policy fixture",
            "sourceUrl": "https://example.org/policy", "usageType": "policy_candidate",
            "pipelineVersion": "document-parse-v1", "leaseToken": "test-lease"}


def test_markdown_real_parser_preserves_structure_and_unpublished_provenance(tmp_path):
    task = task_at(tmp_path)
    output = tmp_path / "normalized.json"
    parse_task(task, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["documentId"] == task["id"]
    assert result["sourceUri"] == task["sourceUrl"]
    assert result["sourceType"] == "uploaded_document"
    assert result["metadata"]["published"] is False
    assert any(node["sectionPath"] for node in result["nodes"])
    assert all(node["sourceRef"] for node in result["nodes"])


def test_csv_real_parser_preserves_table_reference(tmp_path):
    task = task_at(tmp_path, "csv", b"risk,rule\nfake_review,no incentives\n")
    output = tmp_path / "normalized.json"
    parse_task(task, output)
    result = json.loads(output.read_text())
    table = next(node for node in result["nodes"] if node["type"] == "table")
    assert table["sourceRef"]


def test_hash_mismatch_never_publishes_result(tmp_path):
    task = task_at(tmp_path)
    task["fileHash"] = "wrong"
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        parse_task(task, tmp_path / "normalized.json")
    assert not (tmp_path / "normalized.json").exists()


def test_path_traversal_rejected(tmp_path):
    task = task_at(tmp_path)
    task["inputPath"] = "../private.txt"
    with pytest.raises(ValueError, match="PATH_INVALID"):
        parse_task(task, tmp_path / "normalized.json")


class Client:
    def __init__(self):
        self.requests = []

    def post(self, path, data=None):
        self.requests.append((path, data))
        return {"accepted": True}


def test_independent_parse_process_finishes_real_task(tmp_path):
    client = Client()
    task = task_at(tmp_path)
    assert process_one(client, task, heartbeat_interval=0.1)
    assert client.requests[-1][1]["errorCode"] == ""
    assert any("heartbeat" in path for path, _ in client.requests)
    assert (tmp_path / task["id"] / task["leaseToken"] / "normalized.json").exists()


def test_parse_error_reported_as_failure_not_success(tmp_path):
    client = Client()
    task = task_at(tmp_path)
    task["fileHash"] = "invalid"
    assert process_one(client, task)
    assert client.requests[-1][1]["errorCode"] == "DOCUMENT_HASH_MISMATCH"


def test_timeout_terminates_child_and_records_failure(tmp_path):
    client = Client()
    assert process_one(client, task_at(tmp_path), timeout=0)
    assert client.requests[-1][1]["errorCode"] == "DOCUMENT_PARSE_TIMEOUT"


@pytest.mark.parametrize("url,token", [("https://example.org", "a" * 32), ("http://127.0.0.1:8083", "")])
def test_worker_auth_fails_closed(url, token):
    with pytest.raises(ValueError):
        WorkerClient(url, token)


def test_atomic_result_can_be_reopened_after_restart(tmp_path):
    path = tmp_path / "result.json"
    atomic_json(path, {"value": 1})
    atomic_json(path, {"value": 2})
    assert json.loads(Path(path).read_text()) == {"value": 2}


def test_worker_lock_releases_on_exit_and_prevents_second_supervisor(tmp_path):
    path = tmp_path / "queue.lock"
    with worker_lock(path):
        with pytest.raises(OSError):
            with worker_lock(path):
                pytest.fail("second worker must not enter")
    with worker_lock(path):
        pass


class ClassedQueueClient:
    def __init__(self, light=80, heavy=20):
        self.lock = threading.Lock()
        self.tasks = {
            "light": deque({"id": f"light-{index}", "executionClass": "light"} for index in range(light)),
            "heavy": deque({"id": f"heavy-{index}", "executionClass": "heavy"} for index in range(heavy)),
        }

    def post(self, path, data=None):
        assert path == "/claim"
        execution_class = data["executionClass"]
        with self.lock:
            return {"task": self.tasks[execution_class].popleft() if self.tasks[execution_class] else None}


def test_bounded_scheduler_drains_100_tasks_with_separate_cpu_and_gpu_caps():
    client = ClassedQueueClient()
    active = {"light": 0, "heavy": 0}
    maximum = {"light": 0, "heavy": 0}
    lock = threading.Lock()

    def handler(_client, task):
        execution_class = task["executionClass"]
        with lock:
            active[execution_class] += 1
            maximum[execution_class] = max(maximum[execution_class], active[execution_class])
        time.sleep(0.005)
        with lock:
            active[execution_class] -= 1
        return True

    summary = run_bounded_scheduler(
        client,
        light_workers=4,
        heavy_workers=1,
        stop_when_idle=True,
        poll_interval=0.001,
        handler=handler,
    )
    assert summary["completed"] == 100
    assert summary["failed"] == 0
    assert maximum == {"light": 4, "heavy": 1}
    assert summary["maxActive"] == maximum


def test_bounded_scheduler_rejects_unsafe_concurrency():
    with pytest.raises(ValueError, match="CONCURRENCY_INVALID"):
        run_bounded_scheduler(ClassedQueueClient(0, 0), light_workers=32, stop_when_idle=True)
