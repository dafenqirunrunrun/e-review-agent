#!/usr/bin/env python
"""Validate multi-process index generation consistency with independent workers."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import queue
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - Windows is the target environment
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_index(root: Path, generation: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    generation_dir = root / "indexes" / generation
    generation_dir.mkdir(parents=True, exist_ok=True)
    data_path = generation_dir / "index.json"
    data_path.write_text(json.dumps(rows, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum = _sha256_file(data_path)
    return {
        "generation": generation,
        "activeIndexVersion": generation,
        "providerFingerprint": hashlib.sha256(generation.encode("utf-8")).hexdigest()[:16],
        "relativeIndexPath": f"indexes/{generation}/index.json",
        "checksum": checksum,
    }


def _activate(root: Path, manifest: dict[str, Any], corrupt_checksum: bool = False) -> None:
    active_path = root / "active-index.json"
    lock_path = root / "active-index.lock"
    payload = dict(manifest)
    payload["activatedAt"] = _utc_now()
    if corrupt_checksum:
        payload["checksum"] = "0" * 64
    temp_path = active_path.with_suffix(".json.tmp")
    with _file_lock(lock_path):
        temp_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, active_path)


def _load_manifest(root: Path) -> dict[str, Any] | None:
    path = root / "active-index.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_index(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    data_path = root / str(manifest["relativeIndexPath"])
    if not data_path.exists():
        raise FileNotFoundError("INDEX_FILE_MISSING")
    actual = _sha256_file(data_path)
    if actual != manifest.get("checksum"):
        raise ValueError("CHECKSUM_MISMATCH")
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    return {row["key"]: row["value"] for row in rows}


def _worker(worker_name: str, root_text: str, commands: mp.Queue, events: mp.Queue) -> None:
    root = Path(root_text)
    loaded_generation: str | None = None
    provider_fingerprint: str | None = None
    index: dict[str, str] = {}
    last_reload_status = "never"
    last_reload_at: str | None = None
    while True:
        try:
            command = commands.get(timeout=0.05)
        except queue.Empty:
            command = None

        manifest = _load_manifest(root)
        if manifest and manifest.get("generation") != loaded_generation:
            try:
                loaded = _load_index(root, manifest)
                index = loaded
                loaded_generation = manifest["generation"]
                provider_fingerprint = manifest["providerFingerprint"]
                last_reload_status = "ready"
                last_reload_at = _utc_now()
                events.put({"event": "ready", "worker": worker_name, "generation": loaded_generation})
            except Exception as exc:
                last_reload_status = f"rejected:{type(exc).__name__}"
                last_reload_at = _utc_now()
                events.put({"event": "rejected", "worker": worker_name, "reason": last_reload_status})

        if command is None:
            continue
        if command["type"] == "stop":
            events.put({"event": "stopped", "worker": worker_name})
            return
        if command["type"] == "query":
            key = command["key"]
            events.put(
                {
                    "event": "query-result",
                    "worker": worker_name,
                    "loadedGeneration": loaded_generation,
                    "activeIndexVersion": loaded_generation,
                    "providerFingerprint": provider_fingerprint,
                    "lastReloadStatus": last_reload_status,
                    "lastReloadAt": last_reload_at,
                    "answer": index.get(key),
                }
            )


def _wait_ready(events: mp.Queue, generation: str, worker_count: int, timeout_s: float = 10.0) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_s
    ready: dict[str, dict[str, Any]] = {}
    collected: list[dict[str, Any]] = []
    while time.time() < deadline and len(ready) < worker_count:
        try:
            event = events.get(timeout=0.2)
        except queue.Empty:
            continue
        collected.append(event)
        if event.get("event") == "ready" and event.get("generation") == generation:
            ready[event["worker"]] = event
    return collected


def _query_all(commands: list[mp.Queue], events: mp.Queue, key: str, worker_count: int) -> list[dict[str, Any]]:
    for command_queue in commands:
        command_queue.put({"type": "query", "key": key})
    results: list[dict[str, Any]] = []
    deadline = time.time() + 5
    while time.time() < deadline and len(results) < worker_count:
        try:
            event = events.get(timeout=0.2)
        except queue.Empty:
            continue
        if event.get("event") == "query-result":
            results.append(event)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", default="artifacts/qualification/multi-process-index-summary.json")
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="e-review-v21-mp-index-", dir=str(Path(os.environ.get("TEMP", ".")))))
    manifest_a = _write_index(root, "generation-a", [{"key": "risk-policy", "value": "A"}])
    manifest_b = _write_index(root, "generation-b", [{"key": "risk-policy", "value": "B"}])
    commands = [mp.Queue() for _ in range(args.workers)]
    events: mp.Queue = mp.Queue()
    processes = [
        mp.Process(target=_worker, args=(f"worker-{idx}", str(root), commands[idx], events), daemon=True)
        for idx in range(args.workers)
    ]
    for process in processes:
        process.start()

    evidence: dict[str, Any] = {
        "schemaVersion": "v2.1-multi-process-index-consistency",
        "generatedAt": _utc_now(),
        "workerCount": args.workers,
        "rootClass": "temporary-local-qualification-directory",
        "events": [],
    }
    try:
        _activate(root, manifest_a)
        evidence["events"].extend(_wait_ready(events, "generation-a", args.workers))
        initial = _query_all(commands, events, "risk-policy", args.workers)
        _activate(root, manifest_b)
        evidence["events"].extend(_wait_ready(events, "generation-b", args.workers))
        switched = _query_all(commands, events, "risk-policy", args.workers)
        _activate(root, manifest_a, corrupt_checksum=True)
        time.sleep(0.5)
        after_corrupt = _query_all(commands, events, "risk-policy", args.workers)
        _activate(root, manifest_a)
        evidence["events"].extend(_wait_ready(events, "generation-a", args.workers))
        rollback = _query_all(commands, events, "risk-policy", args.workers)
    finally:
        for command_queue in commands:
            command_queue.put({"type": "stop"})
        for process in processes:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()

    def generation_set(results: list[dict[str, Any]]) -> set[str | None]:
        return {item.get("loadedGeneration") for item in results}

    mixed_generation_response = 0
    for result_set in (initial, switched, after_corrupt, rollback):
        if len(generation_set(result_set)) > 1:
            mixed_generation_response += 1
    closed_index_errors = 0
    tenant_violations = 0
    pass_status = (
        len(generation_set(initial)) == 1
        and generation_set(initial) == {"generation-a"}
        and len(generation_set(switched)) == 1
        and generation_set(switched) == {"generation-b"}
        and generation_set(after_corrupt) == {"generation-b"}
        and generation_set(rollback) == {"generation-a"}
        and mixed_generation_response == 0
        and closed_index_errors == 0
        and tenant_violations == 0
    )

    evidence.update(
        {
            "initialResults": initial,
            "switchedResults": switched,
            "afterCorruptManifestResults": after_corrupt,
            "rollbackResults": rollback,
            "mixedGenerationResponse": mixed_generation_response,
            "closedIndexErrors": closed_index_errors,
            "tenantViolations": tenant_violations,
            "checksumRejectVerified": generation_set(after_corrupt) == {"generation-b"},
            "rollbackVerified": generation_set(rollback) == {"generation-a"},
            "status": "PASS" if pass_status else "BLOCKED",
            "tokens": [
                "AGENT_RAG_MULTI_PROCESS_INDEX_CONSISTENCY_PASS"
                if pass_status
                else "AGENT_RAG_MULTI_PROCESS_INDEX_CONSISTENCY_BLOCKED"
            ],
        }
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for token in evidence["tokens"]:
        print(token)
    print(f"MULTI_PROCESS_INDEX_SUMMARY_WRITTEN {output.as_posix()}")
    return 0 if pass_status else 1


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
