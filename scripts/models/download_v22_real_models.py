from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any


MODEL_SPECS = {
    "reranker": {
        "modelId": "BAAI/bge-reranker-v2-m3",
        "targetName": "bge-reranker-v2-m3",
        "license": "Apache-2.0",
        "architectureHint": "XLMRobertaForSequenceClassification",
    },
    "llm": {
        "modelId": "Qwen/Qwen3-1.7B",
        "targetName": "qwen3-1.7b",
        "license": "Apache-2.0",
        "architectureHint": "Qwen3ForCausalLM",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision official v2.2 real model assets outside Git.")
    parser.add_argument("--model", choices=["reranker", "llm"], action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args()

    selected = list(MODEL_SPECS) if args.all else (args.model or [])
    if not selected:
        parser.error("Select --model reranker, --model llm, or --all.")

    target_root = Path(args.target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []

    for key in selected:
        spec = MODEL_SPECS[key]
        target = target_root / spec["targetName"]
        resolved_revision = ""
        if not (args.verify_only or args.verify) and not args.offline:
            resolved_revision = _download_to_target(spec["modelId"], target, max_workers=max(1, min(args.max_workers, 4)))
        summary = _summarize_model(spec, target)
        if resolved_revision:
            summary["resolvedRevision"] = resolved_revision
        else:
            existing = _read_existing_provenance(target)
            if existing.get("resolvedRevision"):
                summary["resolvedRevision"] = existing["resolvedRevision"]
        summaries.append(summary)
        if summary["status"] != "PASS":
            print(f"V22_{key.upper()}_ASSET_BLOCKED")
            print(json.dumps(_safe_summary(summary), ensure_ascii=False))
            return 2
        if not (args.verify_only or args.verify):
            _write_external_provenance(target, spec, summary)

    print("E_REVIEW_V22_REAL_MODEL_ASSETS_PASS")
    print(json.dumps([_safe_summary(item) for item in summaries], ensure_ascii=False, indent=2))
    return 0


def _download_to_target(model_id: str, target: Path, *, max_workers: int) -> str:
    from huggingface_hub import HfApi, snapshot_download

    partial = target.with_name(target.name + ".partial")
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(repo_id=model_id)
    revision = info.sha
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            snapshot_download(
                repo_id=model_id,
                revision=revision,
                local_dir=str(partial),
                local_dir_use_symlinks=False,
                max_workers=max_workers,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt >= 3:
                raise
            time.sleep(2**attempt)
    if target.exists():
        shutil.rmtree(target)
    partial.rename(target)
    return revision


def _summarize_model(spec: dict[str, str], target: Path) -> dict[str, Any]:
    files = [p for p in target.rglob("*") if p.is_file()] if target.is_dir() else []
    config_path = target / "config.json"
    config: dict[str, Any] = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    weights = [p for p in files if p.suffix in {".safetensors", ".bin"}]
    tokenizer = any((target / name).is_file() for name in ["tokenizer.json", "tokenizer_config.json", "sentencepiece.bpe.model"])
    license_file = any(p.name.lower().startswith("license") for p in files)
    status = "PASS"
    reasons: list[str] = []
    if not target.is_dir():
        status = "BLOCKED"
        reasons.append("MODEL_DIRECTORY_MISSING")
    if not config:
        status = "BLOCKED"
        reasons.append("CONFIG_MISSING")
    if not tokenizer:
        status = "BLOCKED"
        reasons.append("TOKENIZER_MISSING")
    if not weights:
        status = "BLOCKED"
        reasons.append("WEIGHTS_MISSING")
    architecture = ",".join(config.get("architectures") or [])
    fingerprint, sha_path = _fingerprint(target) if target.is_dir() else ("", [])
    return {
        "modelId": spec["modelId"],
        "targetName": target.name,
        "status": status,
        "blockedReasons": reasons,
        "architecture": architecture,
        "architectureHint": spec["architectureHint"],
        "license": spec["license"],
        "licenseFilePresent": license_file,
        "fileCount": len(files),
        "totalBytes": sum(p.stat().st_size for p in files),
        "assetFingerprint": fingerprint,
        "controlledFiles": sha_path,
    }


def _fingerprint(root: Path) -> tuple[str, list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        if ".cache/" in rel or rel.endswith(".lock") or rel.endswith(".tmp"):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"relativePath": rel, "sizeBytes": path.stat().st_size, "sha256": digest})
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), entries


def _write_external_provenance(target: Path, spec: dict[str, str], summary: dict[str, Any]) -> None:
    provenance = {
        "modelId": spec["modelId"],
        "resolvedRevision": summary.get("resolvedRevision") or os.getenv("E_REVIEW_V22_MODEL_REVISION", ""),
        "source": "Hugging Face official repository",
        "downloadedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "license": spec["license"],
        "architecture": summary["architecture"],
        "fileCount": summary["fileCount"],
        "totalBytes": summary["totalBytes"],
        "assetFingerprint": summary["assetFingerprint"],
    }
    (target / "MODEL_PROVENANCE.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{entry['sha256']}  {entry['relativePath']}" for entry in summary["controlledFiles"]]
    (target / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_existing_provenance(target: Path) -> dict[str, Any]:
    path = target / "MODEL_PROVENANCE.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _safe_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "controlledFiles"}


if __name__ == "__main__":
    raise SystemExit(main())
