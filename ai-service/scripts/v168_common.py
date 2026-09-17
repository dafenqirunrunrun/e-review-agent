from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE = ROOT / "ai-service"
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA = PRIVATE_ROOT / "synthetic-sft-v21"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v21-v168"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
AUDIT = ROOT / "data/private_research/audit"
TRAINING = ROOT / "data/private_research/training"
EVAL = ROOT / "data/private_research/eval"
DOCS = ROOT / "docs"
BASE_HEAD = "da2e0399"

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


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256((row["system"] + row["user"] + row["assistant"]).encode("utf-8", errors="replace")).hexdigest()


def normalized_user_hash(row: dict[str, Any]) -> str:
    user = json.loads(row["user"])
    return hashlib.sha256(json.dumps(user, ensure_ascii=False, sort_keys=True).lower().encode("utf-8")).hexdigest()


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def target_dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(target(row).get(key)) for row in rows))


def overlap_count(a: list[dict[str, Any]], b: list[dict[str, Any]], fn) -> int:
    return len({fn(row) for row in a} & {fn(row) for row in b})


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


def finite(value: float | None) -> bool:
    return value is not None and not math.isnan(value) and not math.isinf(value)


def macro_f1(labels: list[Any], preds: list[Any]) -> float:
    classes = sorted(set(labels) | set(preds), key=str)
    if not classes:
        return 0.0
    scores = []
    for cls in classes:
        tp = sum(1 for y, p in zip(labels, preds) if y == cls and p == cls)
        fp = sum(1 for y, p in zip(labels, preds) if y != cls and p == cls)
        fn = sum(1 for y, p in zip(labels, preds) if y == cls and p != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append((2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * q) - 1))]
