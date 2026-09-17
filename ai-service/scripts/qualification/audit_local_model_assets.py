#!/usr/bin/env python
"""Audit optional local model assets for the v2.1 qualification campaign.

The script is intentionally offline-only. It never downloads model files and it
does not write absolute local paths to its JSON output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_PARTS = {"cache", ".cache", "logs", "tmp", "temp", "__pycache__"}
IGNORED_SUFFIXES = {".lock", ".log", ".tmp", ".pyc"}
WEIGHT_SUFFIXES = {".bin", ".safetensors", ".pt", ".pth", ".gguf"}
TOKENIZER_NAMES = {
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "vocab.txt",
    "vocab.json",
    "merges.txt",
    "sentencepiece.bpe.model",
}


@dataclass(frozen=True)
class AssetSpec:
    asset_type: str
    env_name: str
    expected_kind: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_ignored(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & IGNORED_PARTS:
        return True
    return path.suffix.lower() in IGNORED_SUFFIXES


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(root: Path, files: list[Path]) -> str | None:
    if not files:
        return None
    digest = hashlib.sha256()
    for file_path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative_name = file_path.relative_to(root).as_posix()
        file_hash = _sha256_file(file_path)
        digest.update(relative_name.encode("utf-8"))
        digest.update(str(file_path.stat().st_size).encode("ascii"))
        digest.update(file_hash.encode("ascii"))
    return digest.hexdigest()


def _read_config(root: Path, blockers: list[str]) -> dict[str, Any] | None:
    config_path = root / "config.json"
    if not config_path.exists():
        blockers.append("MISSING_CONFIG_JSON")
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        blockers.append("INVALID_CONFIG_JSON")
        return None


def _safe_import_transformers(blockers: list[str]) -> Any | None:
    try:
        import transformers  # type: ignore

        return transformers
    except Exception as exc:  # pragma: no cover - depends on local env
        blockers.append(f"TRANSFORMERS_IMPORT_FAILED:{type(exc).__name__}")
        return None


def _auto_config(root: Path, blockers: list[str]) -> dict[str, Any]:
    details: dict[str, Any] = {
        "autoConfigLoadable": False,
        "autoTokenizerLoadable": False,
        "autoProcessorLoadable": False,
    }
    transformers = _safe_import_transformers(blockers)
    if transformers is None:
        return details

    previous_offline = {
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
    }
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        try:
            cfg = transformers.AutoConfig.from_pretrained(str(root), local_files_only=True, trust_remote_code=True)
            details["autoConfigLoadable"] = True
            details["autoConfigModelType"] = getattr(cfg, "model_type", None)
            details["autoConfigArchitectures"] = getattr(cfg, "architectures", None)
        except Exception as exc:  # pragma: no cover - depends on local assets
            blockers.append(f"AUTO_CONFIG_FAILED:{type(exc).__name__}")

        try:
            transformers.AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=True)
            details["autoTokenizerLoadable"] = True
        except Exception as exc:  # pragma: no cover - depends on local assets
            blockers.append(f"AUTO_TOKENIZER_FAILED:{type(exc).__name__}")

        try:
            transformers.AutoProcessor.from_pretrained(str(root), local_files_only=True, trust_remote_code=True)
            details["autoProcessorLoadable"] = True
        except Exception:
            details["autoProcessorLoadable"] = False
    finally:
        for key, value in previous_offline.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return details


def audit_asset(spec: AssetSpec) -> dict[str, Any]:
    raw_path = os.environ.get(spec.env_name, "").strip()
    blockers: list[str] = []
    result: dict[str, Any] = {
        "assetType": spec.asset_type,
        "envName": spec.env_name,
        "available": False,
        "fileCount": 0,
        "sizeBytes": 0,
        "architecture": [],
        "modelType": None,
        "weightFormat": [],
        "assetFingerprint": None,
        "blockerCodes": blockers,
    }

    if not raw_path:
        blockers.append("ENV_PATH_NOT_SET")
        return result

    root = Path(raw_path).expanduser()
    if not root.exists():
        blockers.append("MODEL_PATH_NOT_FOUND")
        return result
    if not root.is_dir():
        blockers.append("MODEL_PATH_NOT_DIRECTORY")
        return result

    config = _read_config(root, blockers)
    files = [path for path in root.rglob("*") if path.is_file() and not _is_ignored(path)]
    weight_files = [path for path in files if path.suffix.lower() in WEIGHT_SUFFIXES]
    tokenizer_files = [path for path in files if path.name in TOKENIZER_NAMES]

    if not weight_files:
        blockers.append("MISSING_WEIGHT_FILES")
    if not tokenizer_files:
        blockers.append("MISSING_TOKENIZER_FILES")

    if config:
        architectures = config.get("architectures") or []
        result["architecture"] = architectures if isinstance(architectures, list) else [str(architectures)]
        result["modelType"] = config.get("model_type")
        result["maxPositionEmbeddings"] = config.get("max_position_embeddings")
        result["maxSequenceLength"] = config.get("max_seq_len") or config.get("seq_length")
        result["quantizationConfigPresent"] = bool(config.get("quantization_config"))
        if spec.expected_kind == "causal_lm" and not any("CausalLM" in str(item) for item in result["architecture"]):
            blockers.append("ARCHITECTURE_NOT_DECLARED_CAUSAL_LM")

    result["fileCount"] = len(files)
    result["sizeBytes"] = sum(path.stat().st_size for path in files)
    result["weightFormat"] = sorted({path.suffix.lower().lstrip(".") for path in weight_files})
    result["assetFingerprint"] = _fingerprint(root, files)
    result.update(_auto_config(root, blockers))
    result["available"] = not blockers or all(code.startswith("AUTO_PROCESSOR_FAILED") for code in blockers)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="artifacts/qualification/model-assets-summary.json",
        help="JSON output path inside the qualification worktree.",
    )
    args = parser.parse_args()

    specs = [
        AssetSpec("reranker", "RAG_RERANKER_MODEL_PATH", "sequence_scorer"),
        AssetSpec("llm", "AGENT_LLM_MODEL_PATH", "causal_lm"),
    ]
    summary = {
        "schemaVersion": "v2.1-model-assets-audit",
        "generatedAt": _utc_now(),
        "offlineOnly": True,
        "absolutePathsRedacted": True,
        "assets": [audit_asset(spec) for spec in specs],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for asset in summary["assets"]:
        token = f"{asset['assetType'].upper()}_ASSET_AVAILABLE" if asset["available"] else f"{asset['assetType'].upper()}_ASSET_BLOCKED"
        print(token)
        if not asset["available"]:
            print(",".join(asset["blockerCodes"]))
    print(f"MODEL_ASSET_AUDIT_WRITTEN {output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
