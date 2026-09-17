from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "qualification" / "qualification-asset-verification.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redacted(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {"configured": False, "exists": False}
    path = Path(path_value)
    return {
        "configured": True,
        "exists": path.exists(),
        "name": path.name,
        "kind": "directory" if path.is_dir() else "file",
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "status": "ASSET_BLOCKED",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "bgeM3": {"status": "BLOCKED"},
        "denseIndex": {"status": "BLOCKED"},
        "reranker": {"status": "BLOCKED"},
        "llm": {"status": "BLOCKED"},
    }


def _write(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def verify(manifest_path: str | None) -> tuple[int, dict[str, Any]]:
    if not manifest_path:
        payload = _blocked("AGENT_RAG_QUALIFICATION_ASSET_MANIFEST_NOT_CONFIGURED")
        return 0, payload
    path = Path(manifest_path)
    if not path.exists():
        payload = _blocked("QUALIFICATION_ASSET_MANIFEST_FILE_NOT_FOUND")
        payload["manifest"] = _redacted(manifest_path)
        return 0, payload
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("schemaVersion") not in {"1.0.0", "1.1.0"}:
        errors.append("QUALIFICATION_ASSET_SCHEMA_VERSION_UNSUPPORTED")
    bge = manifest.get("bgeM3") or manifest.get("embedding", {})
    dense = manifest.get("denseIndex", {})
    reranker = manifest.get("reranker", {})
    llm = manifest.get("llm", {})

    bge_path = Path(bge["modelPath"]) if bge.get("modelPath") else None
    dense_index_path = Path(dense["indexPath"]) if dense.get("indexPath") else None
    dense_manifest_path = Path(dense["manifestPath"]) if dense.get("manifestPath") else None
    if not bge_path or not bge_path.exists():
        errors.append("QUALIFICATION_BGE_MODEL_PATH_NOT_FOUND")
    if not dense_index_path or not dense_index_path.exists():
        errors.append("QUALIFICATION_DENSE_INDEX_PATH_NOT_FOUND")
    if not dense_manifest_path or not dense_manifest_path.exists():
        errors.append("QUALIFICATION_DENSE_INDEX_MANIFEST_PATH_NOT_FOUND")
    if bge.get("assetFingerprint") and dense.get("effectiveEmbeddingFingerprint"):
        if bge["assetFingerprint"] != dense["effectiveEmbeddingFingerprint"]:
            errors.append("QUALIFICATION_EMBEDDING_FINGERPRINT_MISMATCH")

    hashes: dict[str, str] = {}
    if dense_index_path and dense_index_path.exists():
        hashes["indexSha256"] = _sha256(dense_index_path)
        if dense.get("indexSha256") and dense["indexSha256"] != hashes["indexSha256"]:
            errors.append("QUALIFICATION_DENSE_INDEX_SHA256_MISMATCH")
    if dense_manifest_path and dense_manifest_path.exists():
        hashes["manifestSha256"] = _sha256(dense_manifest_path)
        if dense.get("manifestSha256") and dense["manifestSha256"] != hashes["manifestSha256"]:
            errors.append("QUALIFICATION_DENSE_MANIFEST_SHA256_MISMATCH")

    payload = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if not errors else "ASSET_BLOCKED",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "manifest": _redacted(manifest_path),
        "bgeM3": {
            "status": "PASS" if bge_path and bge_path.exists() else "BLOCKED",
            "modelPath": _redacted(bge.get("modelPath")),
            "providerImpl": bge.get("providerImpl") or bge.get("provider"),
            "assetFingerprintConfigured": bool(bge.get("assetFingerprint")),
        },
        "denseIndex": {
            "status": "PASS" if dense_index_path and dense_index_path.exists() and dense_manifest_path and dense_manifest_path.exists() else "BLOCKED",
            "indexPath": _redacted(dense.get("indexPath")),
            "manifestPath": _redacted(dense.get("manifestPath")),
            "indexVersion": dense.get("indexVersion"),
            "effectiveEmbeddingFingerprintConfigured": bool(dense.get("effectiveEmbeddingFingerprint")),
            "hashes": hashes,
        },
        "reranker": {
            "status": "PASS" if reranker.get("modelPath") and Path(reranker["modelPath"]).exists() else "BLOCKED",
            "modelPath": _redacted(reranker.get("modelPath")),
        },
        "llm": {
            "status": "PASS" if llm.get("modelPath") and Path(llm["modelPath"]).exists() else "BLOCKED",
            "modelPath": _redacted(llm.get("modelPath")),
        },
        "errors": errors,
    }
    return 0, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=os.environ.get("AGENT_RAG_QUALIFICATION_ASSET_MANIFEST"))
    args = parser.parse_args()
    code, payload = verify(args.manifest)
    _write(payload)
    if payload["bgeM3"]["status"] == "PASS":
        print("QUALIFICATION_BGE_ASSET_PASS")
    else:
        print("QUALIFICATION_BGE_ASSET_BLOCKED")
    if payload["denseIndex"]["status"] == "PASS":
        print("QUALIFICATION_DENSE_INDEX_ASSET_PASS")
    else:
        print("QUALIFICATION_DENSE_INDEX_ASSET_BLOCKED")
    if payload["reranker"]["status"] == "PASS":
        print("QUALIFICATION_RERANKER_ASSET_PASS")
    else:
        print("QUALIFICATION_RERANKER_ASSET_BLOCKED")
    if payload["llm"]["status"] == "PASS":
        print("QUALIFICATION_LLM_ASSET_PASS")
    else:
        print("QUALIFICATION_LLM_ASSET_BLOCKED")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
