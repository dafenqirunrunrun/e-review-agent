from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.rag_v2.config import load_config
from app.rag_v2.dense_encoder import BgeM3Encoder


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/private_research/audit/v180_local_embedding_inventory.json"


def main() -> None:
    config = load_config()
    candidates = [
        {
            "name": "configured_bge_m3",
            "model_id": config.embedding_model,
            "path_label": "<repo-external>/models/bge-m3",
            "path": config.embedding_model_dir,
        }
    ]
    inventory = []
    selected = None
    for candidate in candidates:
        item = inspect_candidate(candidate)
        inventory.append(item)
        if item["status"] == "READY" and selected is None:
            selected = item
    status = "V180_REAL_LOCAL_EMBEDDING_AVAILABLE" if selected else "V180_REAL_LOCAL_EMBEDDING_BLOCKED"
    payload = {
        "status": status,
        "selected": selected,
        "candidates": inventory,
        "network_download_used": False,
        "hash_dense_allowed_for_enterprise": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(status)


def inspect_candidate(candidate: dict) -> dict:
    path = Path(candidate["path"])
    files = {item.name: item for item in path.glob("*") if item.is_file()} if path.exists() else {}
    required = ["config.json", "tokenizer.json", "model.safetensors"]
    missing = [name for name in required if name not in files]
    result = {
        "name": candidate["name"],
        "model_id": candidate["model_id"],
        "path_label": candidate["path_label"],
        "exists": path.exists(),
        "required_missing": missing,
        "file_count": len(files),
        "total_size_bytes": sum(item.stat().st_size for item in files.values()),
        "model_hash": sha256(files["model.safetensors"]) if "model.safetensors" in files else None,
        "torch_importable": importlib.util.find_spec("torch") is not None,
        "transformers_importable": importlib.util.find_spec("transformers") is not None,
        "numpy_importable": True,
        "status": "BLOCKED",
        "embedding_dimension": None,
        "probe": {},
    }
    if missing or not result["torch_importable"] or not result["transformers_importable"]:
        return result
    try:
        encoder = BgeM3Encoder(path, device="cpu", batch_size=2, normalize=True, max_length=128)
        started = time.perf_counter()
        docs = encoder.encode_documents(["good product quality", "bad after sales refund issue"])
        queries = encoder.encode_queries(["product quality is good"])
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        encoder.unload()
        if docs.dtype != np.float32 or queries.dtype != np.float32:
            result["probe"]["error"] = "NON_FLOAT32_OUTPUT"
            return result
        if not np.isfinite(docs).all() or not np.isfinite(queries).all():
            result["probe"]["error"] = "NAN_OR_INF_OUTPUT"
            return result
        norms = np.linalg.norm(docs, axis=1).round(5).tolist()
        if any(value == 0 for value in norms):
            result["probe"]["error"] = "ZERO_VECTOR_OUTPUT"
            return result
        result["status"] = "READY"
        result["embedding_dimension"] = int(docs.shape[1])
        result["probe"] = {
            "real_encode_executed": True,
            "document_count": int(docs.shape[0]),
            "query_count": int(queries.shape[0]),
            "dtype": str(docs.dtype),
            "l2_norms": norms,
            "latency_ms": latency_ms,
        }
        return result
    except Exception as exc:
        result["probe"] = {"real_encode_executed": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
        return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
