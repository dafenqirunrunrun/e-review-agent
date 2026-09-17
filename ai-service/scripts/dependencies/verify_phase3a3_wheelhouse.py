from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_SOURCE_HASHES = {
    "FlagEmbedding-1.3.5.tar.gz": "a0714cb8dd03f38e74b84530684c47ad8e0442ab1f4cbb7b0bcd4017dafb9f9c",
    "sentence_transformers-3.0.1-py3-none-any.whl": "01050cc4053c49b9f5b78f6980b5a72db3fd3a0abb9169b1792ac83875505ee6",
}
TOP_LEVEL_REQUIREMENTS = ("FlagEmbedding==1.3.5", "sentence-transformers==3.0.1")
FORBIDDEN_PATTERNS = ("torch-*", "torchvision-*", "torchaudio-*", "nvidia-*", "faiss-*", "faiss_cpu-*")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_wheelhouse(wheelhouse: Path, sources: Path | None = None) -> dict[str, Any]:
    files = []
    forbidden = []
    missing_required = []

    wheelhouse_files = sorted([path for path in wheelhouse.glob("*") if path.is_file()]) if wheelhouse.exists() else []
    for path in wheelhouse_files:
        entry = {
            "filename": path.name,
            "sha256": sha256(path),
            "sizeBytes": path.stat().st_size,
            "sourceType": "pypi-wheel-or-locally-built-wheel",
        }
        files.append(entry)
        if any(fnmatch.fnmatch(path.name.lower(), pattern.lower()) for pattern in FORBIDDEN_PATTERNS):
            forbidden.append(path.name)

    lower_names = {path.name.lower() for path in wheelhouse_files}
    if not any(name.startswith("flagembedding-1.3.5") and name.endswith(".whl") for name in lower_names):
        missing_required.append("FlagEmbedding==1.3.5 wheel")
    if "sentence_transformers-3.0.1-py3-none-any.whl" not in lower_names:
        missing_required.append("sentence-transformers==3.0.1 wheel")

    source_hashes = []
    source_mismatches = []
    source_missing = []
    if sources is not None:
        for filename, expected in EXPECTED_SOURCE_HASHES.items():
            path = sources / filename
            if not path.exists():
                source_missing.append(filename)
                continue
            actual = sha256(path)
            source_hashes.append({"filename": filename, "sha256": actual, "expectedSha256": expected, "match": actual == expected})
            if actual != expected:
                source_mismatches.append({"filename": filename, "actual": actual, "expected": expected})

    status = "PASS" if not forbidden and not missing_required and not source_mismatches else "BLOCKED"
    return {
        "schemaVersion": "1.0.0",
        "status": status,
        "target": {"os": "windows", "architecture": "amd64", "python": "3.10", "implementation": "CPython"},
        "topLevelRequirements": list(TOP_LEVEL_REQUIREMENTS),
        "files": files,
        "wheelCount": len(files),
        "missingRequired": missing_required,
        "forbiddenFiles": forbidden,
        "sourceHashes": source_hashes,
        "sourceMissing": source_missing,
        "sourceMismatches": source_mismatches,
        "excludedPackages": list(FORBIDDEN_PATTERNS),
        "torchWheelPresent": any(name.lower().startswith("torch-") for name in lower_names),
        "cudaWheelPresent": any(name.lower().startswith("nvidia-") for name in lower_names),
        "networkUsed": False,
    }


def write_manifest(manifest_path: Path, sha_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    sha_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"{entry['sha256']}  {entry['filename']}" for entry in payload["files"]]
    sha_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Phase 3A.3 offline wheelhouse integrity without installing packages.")
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256sums", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = verify_wheelhouse(args.wheelhouse, args.sources)
    write_manifest(args.manifest, args.sha256sums, payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
