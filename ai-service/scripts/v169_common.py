from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE = ROOT / "ai-service"
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA_V21 = PRIVATE_ROOT / "synthetic-sft-v21"
DATA_V22 = PRIVATE_ROOT / "synthetic-sft-v22"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v22-v169"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
AUDIT = ROOT / "data/private_research/audit"
TRAINING = ROOT / "data/private_research/training"
EVAL = ROOT / "data/private_research/eval"
DOCS = ROOT / "docs"

if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256((row["system"] + row["user"] + row["assistant"]).encode("utf-8", errors="replace")).hexdigest()


def sample_identity(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {})
    return str(metadata.get("sample_hash") or hashlib.sha256(row["user"].encode("utf-8", errors="replace")).hexdigest())


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * q) - 1))]


def dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(target(row).get(key)) for row in rows))


def overlap_count(a: list[dict[str, Any]], b: list[dict[str, Any]], fn) -> int:
    return len({fn(row) for row in a} & {fn(row) for row in b})


def compact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def nvidia_smi() -> tuple[int | None, int | None]:
    import subprocess

    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, None
    parts = [part.strip() for part in proc.stdout.splitlines()[0].split(",")]
    return int(parts[0]), int(parts[1])
