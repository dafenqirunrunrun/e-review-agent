from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.document_ingestion.job_worker import run_bounded_scheduler


class VerificationQueue:
    def __init__(self, tasks: list[dict[str, Any]]) -> None:
        self._lock = threading.Lock()
        self._queues = {
            "light": deque(task for task in tasks if task["executionClass"] == "light"),
            "heavy": deque(task for task in tasks if task["executionClass"] == "heavy"),
        }
        self.claimed_at: dict[str, float] = {}
        self.completed_at: dict[str, float] = {}
        self.errors: dict[str, str] = {}

    def post(self, path: str, data: dict | None = None) -> dict:
        with self._lock:
            if path == "/claim":
                execution_class = str((data or {}).get("executionClass"))
                task = self._queues[execution_class].popleft() if self._queues[execution_class] else None
                if task:
                    self.claimed_at[task["id"]] = time.perf_counter()
                return {"task": task}
            if path.endswith("/heartbeat"):
                return {"accepted": True}
            if path.endswith("/finish"):
                task_id = path.split("/")[1]
                self.completed_at[task_id] = time.perf_counter()
                error = str((data or {}).get("errorCode") or "")
                if error:
                    self.errors[task_id] = error
                return {"accepted": True}
        raise ValueError("UNEXPECTED_VERIFICATION_REQUEST")


def _write_fixture(path: Path, index: int) -> None:
    suffix = path.suffix.lower()
    if suffix == ".md":
        path.write_text(f"# Policy {index}\n\n## Reviews\n\nDo not suppress genuine review {index}.\n", encoding="utf-8")
    elif suffix == ".txt":
        path.write_text(f"Policy record {index}\n\nRefund complaints require review.\n", encoding="utf-8")
    elif suffix == ".html":
        path.write_text(f"<html><body><h1>Policy {index}</h1><p>Disclose incentives.</p></body></html>", encoding="utf-8")
    elif suffix == ".csv":
        path.write_text(f"risk,rule\nfake_review_{index},no paid reviews\n", encoding="utf-8")
    elif suffix == ".xlsx":
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Review Policy"
        sheet.append(["risk", "rule"])
        sheet.append([f"rating_manipulation_{index}", "No incentive for positive reviews"])
        workbook.save(path)
        workbook.close()
    elif suffix == ".pdf":
        scan = ROOT / "artifacts" / "step24_multiformat_quality" / "raw" / "ocrmypdf_multipage_scan.pdf"
        if not scan.is_file():
            raise FileNotFoundError("STEP24_COMPLEX_SCAN_FIXTURE_MISSING")
        shutil.copyfile(scan, path)
    else:
        raise ValueError("FIXTURE_FORMAT_UNSUPPORTED")


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction) - 1))]


def main() -> int:
    output = ROOT / "artifacts" / "step243" / "batch_ingestion_verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    formats = ["md"] * 20 + ["txt"] * 20 + ["html"] * 20 + ["csv"] * 20 + ["xlsx"] * 19 + ["pdf"]
    with tempfile.TemporaryDirectory(prefix="e-review-step243-") as temporary:
        root = Path(temporary)
        inputs = root / "inputs"
        inputs.mkdir()
        tasks = []
        for index, suffix in enumerate(formats):
            task_id = f"batch-{index:03d}"
            path = inputs / f"{task_id}.{suffix}"
            _write_fixture(path, index)
            content = path.read_bytes()
            tasks.append(
                {
                    "id": task_id,
                    "root": str(root),
                    "inputPath": path.relative_to(root).as_posix(),
                    "fileHash": hashlib.sha256(content).hexdigest(),
                    "sourceName": f"Batch fixture {index}",
                    "sourceUrl": "",
                    "usageType": "reference",
                    "pipelineVersion": "step24.3-verification-v1",
                    "leaseToken": f"lease-{index:03d}",
                    "executionClass": "heavy" if suffix == "pdf" else "light",
                }
            )
        queue = VerificationQueue(tasks)
        started = time.perf_counter()
        scheduler = run_bounded_scheduler(
            queue,
            light_workers=4,
            heavy_workers=1,
            stop_when_idle=True,
            poll_interval=0.01,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        parsed = 0
        traceable = 0
        parser_counts: dict[str, int] = {}
        for task in tasks:
            artifact = root / task["id"] / task["leaseToken"] / "normalized.json"
            if not artifact.is_file():
                continue
            document = json.loads(artifact.read_text(encoding="utf-8"))
            if document.get("nodes"):
                parsed += 1
            if document.get("nodes") and all(node.get("sourceRef") for node in document["nodes"]):
                traceable += 1
            parser = str(document.get("parser", "unknown"))
            parser_counts[parser] = parser_counts.get(parser, 0) + 1
        durations = [
            (queue.completed_at[task_id] - claimed) * 1000
            for task_id, claimed in queue.claimed_at.items()
            if task_id in queue.completed_at
        ]
        checks = {
            "taskCount": len(tasks) == 100,
            "allCompleted": scheduler["completed"] == 100 and not scheduler["failed"],
            "allParsed": parsed == 100,
            "allTraceable": traceable == 100,
            "lightConcurrencyBounded": scheduler["maxActive"]["light"] <= 4,
            "heavyConcurrencyBounded": scheduler["maxActive"]["heavy"] <= 1,
            "noWorkerErrors": not queue.errors,
        }
        report = {
            "schemaVersion": "step24.3-batch-ingestion-verification-v1",
            "gate": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "batch": {
                "fileCount": len(tasks),
                "formatCounts": {suffix: formats.count(suffix) for suffix in sorted(set(formats))},
                "parserCounts": parser_counts,
                "elapsedMs": round(elapsed_ms, 3),
                "throughputFilesPerSecond": round(len(tasks) / (elapsed_ms / 1000), 3),
                "taskLatencyP50Ms": round(statistics.median(durations), 3),
                "taskLatencyP95Ms": round(_percentile(durations, 0.95), 3),
                "parsedCount": parsed,
                "traceableCount": traceable,
                "workerErrors": queue.errors,
            },
            "scheduler": scheduler,
            "safety": {
                "published": False,
                "productionIndexModified": False,
                "temporaryArtifactsDeletedAfterRun": True,
            },
        }
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
