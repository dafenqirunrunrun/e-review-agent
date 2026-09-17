from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class V22ModelAsset:
    model_id: str = ""
    provider: str = ""
    model_path: str = ""
    revision: str = ""
    fingerprint: str = ""
    license: str = ""
    architecture: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.model_id and self.model_path)


def load_v22_model_asset(section: str, env: dict[str, str] | None = None) -> V22ModelAsset:
    source = env or os.environ
    manifest_path = source.get("AGENT_RAG_V22_ASSET_MANIFEST", "").strip()
    if not manifest_path:
        return V22ModelAsset()
    path = Path(manifest_path)
    if not path.is_file():
        return V22ModelAsset()
    try:
        manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return V22ModelAsset()
    item = manifest.get(section) or {}
    if not isinstance(item, dict):
        return V22ModelAsset()
    return V22ModelAsset(
        model_id=str(item.get("modelId") or ""),
        provider=str(item.get("provider") or ""),
        model_path=str(item.get("modelPath") or ""),
        revision=str(item.get("revision") or ""),
        fingerprint=str(item.get("assetFingerprint") or ""),
        license=str(item.get("license") or ""),
        architecture=str(item.get("architecture") or ""),
    )
