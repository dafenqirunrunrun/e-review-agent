from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED = {
    "embedding": ("BAAI/bge-m3", "flagembedding"),
    "reranker": ("BAAI/bge-reranker-v2-m3", "flagembedding"),
    "llm": ("Qwen/Qwen3-1.7B", "local_qwen3_transformers"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify v2.2 real model asset manifest without committing assets.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--summary-output", default="artifacts/real-model-chain/model-assets-summary.json")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        return _blocked(args.summary_output, ["MANIFEST_NOT_FOUND"])
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _blocked(args.summary_output, ["MANIFEST_JSON_INVALID"])

    reasons: list[str] = []
    assets: dict[str, Any] = {}
    if manifest.get("schemaVersion") != "2.0.0":
        reasons.append("SCHEMA_VERSION_INVALID")
    for section, (model_id, provider) in EXPECTED.items():
        item = manifest.get(section) or {}
        section_reasons = _verify_section(section, item, model_id, provider)
        if section_reasons:
            reasons.extend(section_reasons)
        assets[section] = _safe_asset_summary(section, item, section_reasons)

    status = "PASS" if not reasons else "BLOCKED"
    pass_tokens = []
    if status == "PASS":
        pass_tokens = [
            "E_REVIEW_V22_EMBEDDING_ASSET_PASS",
            "E_REVIEW_V22_RERANKER_ASSET_PASS",
            "E_REVIEW_V22_LLM_ASSET_PASS",
            "E_REVIEW_V22_REAL_MODEL_ASSETS_PASS",
        ]
    summary = {
        "status": status,
        "tokens": pass_tokens if status == "PASS" else ["E_REVIEW_V22_REAL_MODEL_ASSETS_BLOCKED"],
        "blockedReasons": reasons,
        "sourceCommit": manifest.get("sourceCommit", ""),
        "assets": assets,
    }
    _write_summary(args.summary_output, summary)
    if status == "PASS":
        for token in pass_tokens:
            print(token)
        return 0
    print("E_REVIEW_V22_REAL_MODEL_ASSETS_BLOCKED")
    for reason in reasons:
        print(reason)
    return 2


def _verify_section(section: str, item: dict[str, Any], model_id: str, provider: str) -> list[str]:
    reasons: list[str] = []
    if item.get("modelId") != model_id:
        reasons.append(f"{section.upper()}_MODEL_ID_INVALID")
    if item.get("provider") != provider:
        reasons.append(f"{section.upper()}_PROVIDER_INVALID")
    if not item.get("assetFingerprint"):
        reasons.append(f"{section.upper()}_FINGERPRINT_MISSING")
    if section != "embedding" and not item.get("revision"):
        reasons.append(f"{section.upper()}_REVISION_MISSING")
    model_path = item.get("modelPath")
    if not model_path:
        reasons.append(f"{section.upper()}_PATH_MISSING")
        return reasons
    root = Path(model_path)
    if not root.is_dir():
        reasons.append(f"{section.upper()}_PATH_NOT_FOUND")
        return reasons
    if not (root / "config.json").is_file():
        reasons.append(f"{section.upper()}_CONFIG_MISSING")
    if not any((root / name).is_file() for name in ["tokenizer.json", "tokenizer_config.json", "sentencepiece.bpe.model"]):
        reasons.append(f"{section.upper()}_TOKENIZER_MISSING")
    if not any(p.suffix in {".safetensors", ".bin"} for p in root.rglob("*") if p.is_file()):
        reasons.append(f"{section.upper()}_WEIGHTS_MISSING")
    if section in {"reranker", "llm"} and item.get("license") != "Apache-2.0":
        reasons.append(f"{section.upper()}_LICENSE_INVALID")
    return reasons


def _safe_asset_summary(section: str, item: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    root = Path(item.get("modelPath", "")) if item.get("modelPath") else None
    files = [p for p in root.rglob("*") if p.is_file()] if root and root.is_dir() else []
    return {
        "section": section,
        "modelId": item.get("modelId", ""),
        "provider": item.get("provider", ""),
        "pathLabel": root.name if root else "",
        "revision": item.get("revision", ""),
        "assetFingerprint": item.get("assetFingerprint", ""),
        "license": item.get("license", ""),
        "fileCount": len(files),
        "totalBytes": sum(p.stat().st_size for p in files),
        "status": "PASS" if not reasons else "BLOCKED",
        "blockedReasons": reasons,
    }


def _blocked(output: str, reasons: list[str]) -> int:
    _write_summary(output, {"status": "BLOCKED", "tokens": ["E_REVIEW_V22_REAL_MODEL_ASSETS_BLOCKED"], "blockedReasons": reasons})
    print("E_REVIEW_V22_REAL_MODEL_ASSETS_BLOCKED")
    for reason in reasons:
        print(reason)
    return 2


def _write_summary(output: str, summary: dict[str, Any]) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
