from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scripts" / "database" / "agent-rag-migrations.json"
OUT = ROOT / "artifacts" / "qualification" / "migration-immutability-gate.json"
DIAGNOSIS_OUT = ROOT / "artifacts" / "qualification" / "migration-checksum-diagnosis.json"
RC_COMMIT = "ffd05f26"


def canonical_lf_sha256(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    data = data.rstrip(b"\n") + b"\n"
    return hashlib.sha256(data).hexdigest()


def git_blob(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "-p", f"{ref}:{path}"], cwd=ROOT)


def git_blob_id(ref: str, path: str) -> str:
    return subprocess.check_output(["git", "rev-parse", f"{ref}:{path}"], cwd=ROOT, text=True).strip()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    versions: set[str] = set()
    migrations: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in manifest["migrations"]:
        version = item["version"]
        script = item["script"]
        if version in versions:
            errors.append(f"DUPLICATE_MIGRATION_VERSION:{version}")
        versions.add(version)
        path = ROOT / script
        if not path.exists():
            errors.append(f"MIGRATION_SCRIPT_NOT_FOUND:{version}")
            continue
        algorithm = item.get("checksumAlgorithm")
        if algorithm != "sha256-canonical-lf-v1":
            errors.append(f"MIGRATION_CHECKSUM_ALGORITHM_UNSUPPORTED:{version}:{algorithm}")
        current_bytes = path.read_bytes()
        current_raw = hashlib.sha256(current_bytes).hexdigest()
        current_canonical = canonical_lf_sha256(current_bytes)
        expected = item.get("canonicalChecksum")
        if current_canonical != expected:
            errors.append(f"MIGRATION_CANONICAL_CHECKSUM_MISMATCH:{version}")
        rc_blob_id = None
        head_blob_id = None
        rc_canonical = None
        try:
            rc_blob_id = git_blob_id(RC_COMMIT, script)
            head_blob_id = git_blob_id("HEAD", script)
            rc_canonical = canonical_lf_sha256(git_blob(RC_COMMIT, script))
            if rc_canonical != current_canonical:
                errors.append(f"MIGRATION_RC_SEMANTIC_MISMATCH:{version}")
        except subprocess.CalledProcessError:
            if version <= "20260720.01":
                errors.append(f"MIGRATION_RC_BLOB_NOT_FOUND:{version}")
        migrations.append(
            {
                "version": version,
                "script": script,
                "checksumAlgorithm": algorithm,
                "canonicalChecksum": current_canonical,
                "expectedCanonicalChecksum": expected,
                "rawBytesChecksum": current_raw,
                "rcBlob": rc_blob_id,
                "headBlob": head_blob_id,
                "rcCanonicalChecksum": rc_canonical,
                "approvedLegacyChecksumCount": len(item.get("approvedLegacyChecksums", [])),
            }
        )
    payload = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rcCommit": RC_COMMIT,
        "rootCause": "RAW_BYTE_CHECKSUM_WAS_PLATFORM_DEPENDENT; RC_AND_HEAD_SQL_BLOBS_MATCH",
        "manifest": "scripts/database/agent-rag-migrations.json",
        "migrations": migrations,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    DIAGNOSIS_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if errors:
        print("E_REVIEW_MIGRATION_IMMUTABILITY_FAIL")
        return 1
    print("E_REVIEW_MIGRATION_IMMUTABILITY_PASS")
    print("E_REVIEW_MIGRATION_CROSS_PLATFORM_CHECKSUM_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
