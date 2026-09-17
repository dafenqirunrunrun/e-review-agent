from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_WHEELS = {
    "transformers": "4.51.3",
    "tokenizers": "0.21.1",
    "huggingface_hub": "0.30.2",
    "safetensors": "0.5.3",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a transferred v2.2 offline bundle before import.")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--summary-output", default="artifacts/real-model-chain/offline-bundle-verification.json")
    args = parser.parse_args()

    root = Path(args.bundle_root)
    failures: list[str] = []
    tokens: list[str] = []

    bundle_manifest = _read_json(root / "bundle-manifest.json", failures, "BUNDLE_MANIFEST")
    wheel_manifest = _read_json(root / "metadata" / "wheelhouse-manifest.json", failures, "WHEELHOUSE_MANIFEST")
    asset_manifest = _read_json(root / "metadata" / "v22-real-model-assets.portable.json", failures, "PORTABLE_ASSET_MANIFEST")

    if bundle_manifest:
        _verify_bundle_hashes(root, bundle_manifest, failures)
    if not failures:
        tokens.append("E_REVIEW_V22_OFFLINE_BUNDLE_SCHEMA_PASS")
        tokens.append("E_REVIEW_V22_OFFLINE_BUNDLE_HASH_PASS")

    _verify_wheels(wheel_manifest, root, failures)
    if not any(item.startswith("WHEEL_") for item in failures):
        tokens.append("E_REVIEW_V22_WHEEL_COMPATIBILITY_PASS")

    _verify_model_provenance(asset_manifest, root, failures)
    if not any(item.startswith("MODEL_") or item.startswith("PORTABLE_") for item in failures):
        tokens.append("E_REVIEW_V22_MODEL_PROVENANCE_PASS")

    status = "PASS" if not failures else "BLOCKED"
    summary = {
        "status": status,
        "tokens": tokens if status == "PASS" else ["E_REVIEW_V22_OFFLINE_BUNDLE_BLOCKED"],
        "failures": sorted(set(failures)),
    }
    out = Path(args.summary_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for token in summary["tokens"]:
        print(token)
    for failure in summary["failures"]:
        print(failure)
    return 0 if status == "PASS" else 2


def _read_json(path: Path, failures: list[str], label: str) -> dict[str, Any]:
    if not path.is_file():
        failures.append(f"{label}_MISSING")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        failures.append(f"{label}_JSON_INVALID")
        return {}


def _verify_bundle_hashes(root: Path, manifest: dict[str, Any], failures: list[str]) -> None:
    files = manifest.get("files") or []
    if manifest.get("schemaVersion") != "1.0.0":
        failures.append("BUNDLE_SCHEMA_VERSION_INVALID")
    if not files:
        failures.append("BUNDLE_FILE_MANIFEST_EMPTY")
    seen: set[str] = set()
    total = 0
    for item in files:
        rel = str(item.get("relativePath", "")).replace("\\", "/")
        if _unsafe_rel(rel):
            failures.append("BUNDLE_UNSAFE_RELATIVE_PATH")
            continue
        seen.add(rel)
        path = root / rel
        if not path.is_file():
            failures.append(f"BUNDLE_FILE_MISSING:{rel}")
            continue
        size = path.stat().st_size
        total += size
        if size != item.get("sizeBytes"):
            failures.append(f"BUNDLE_FILE_SIZE_MISMATCH:{rel}")
        if _sha256(path) != str(item.get("sha256", "")).lower():
            failures.append(f"BUNDLE_FILE_HASH_MISMATCH:{rel}")
    if len(seen) != int(manifest.get("allFileCount", -1)):
        failures.append("BUNDLE_FILE_COUNT_MISMATCH")
    if total != int(manifest.get("allFileBytes", -1)):
        failures.append("BUNDLE_TOTAL_BYTES_MISMATCH")


def _verify_wheels(manifest: dict[str, Any], root: Path, failures: list[str]) -> None:
    entries = manifest.get("wheels") or []
    by_name = {str(item.get("packageName", "")).lower().replace("-", "_"): item for item in entries}
    for name, version in REQUIRED_WHEELS.items():
        item = by_name.get(name)
        if not item:
            failures.append(f"WHEEL_MISSING:{name}")
            continue
        if str(item.get("packageVersion")) != version:
            failures.append(f"WHEEL_VERSION_INVALID:{name}")
        filename = str(item.get("filename", ""))
        if not filename.endswith(".whl"):
            failures.append(f"WHEEL_FILENAME_INVALID:{name}")
        if any(token in filename for token in ["linux", "manylinux", "macosx", "win32", "cp313"]):
            failures.append(f"WHEEL_PLATFORM_INCOMPATIBLE:{filename}")
        path = root / "wheelhouse" / filename
        if not path.is_file():
            failures.append(f"WHEEL_FILE_MISSING:{filename}")
        elif _sha256(path) != str(item.get("sha256", "")).lower():
            failures.append(f"WHEEL_HASH_MISMATCH:{filename}")


def _verify_model_provenance(manifest: dict[str, Any], root: Path, failures: list[str]) -> None:
    for section in ["reranker", "llm"]:
        item = manifest.get(section) or {}
        rel = str(item.get("relativePath", "")).replace("\\", "/")
        if _unsafe_rel(rel):
            failures.append(f"PORTABLE_{section.upper()}_PATH_UNSAFE")
            continue
        if not item.get("revision") or str(item.get("revision")).lower() in {"main", "latest", "unknown"}:
            failures.append(f"MODEL_{section.upper()}_REVISION_INVALID")
        if item.get("license") != "Apache-2.0":
            failures.append(f"MODEL_{section.upper()}_LICENSE_INVALID")
        path = root / rel
        if not path.is_dir():
            failures.append(f"MODEL_{section.upper()}_DIRECTORY_MISSING")
            continue
        for required in ["config.json", "README.md", "MODEL_PROVENANCE.json", "SHA256SUMS"]:
            if not (path / required).is_file():
                failures.append(f"MODEL_{section.upper()}_{required.upper()}_MISSING")
        if not any(p.suffix in {".safetensors", ".bin"} for p in path.rglob("*") if p.is_file()):
            failures.append(f"MODEL_{section.upper()}_WEIGHTS_MISSING")


def _unsafe_rel(value: str) -> bool:
    return not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value) is not None or ".." in Path(value).parts


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
