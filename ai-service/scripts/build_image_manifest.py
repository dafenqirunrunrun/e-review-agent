import argparse
import hashlib
import json
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "split_manifest" / "real_image_manifest.jsonl"
AUDIT = ROOT / "data" / "real_world" / "audit" / "real_image_manifest_audit.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", type=Path, default=REAL_DATA_DIR / "processed-images")
    parser.add_argument("--source-id", default="unknown")
    args = parser.parse_args()
    files = [path for path in args.image_dir.rglob("*") if path.is_file()]
    rows = []
    for path in files:
        digest = sha256_file(path)
        rows.append(
            {
                "image_id": stable_hash(f"{args.source_id}:{digest}")[:24],
                "source_id": args.source_id,
                "image_sha256": digest,
                "perceptual_hash": None,
                "width": None,
                "height": None,
                "mime_type": path.suffix.lower().lstrip("."),
                "license": None,
                "privacy_status": "pending",
                "redaction_status": "pending",
                "local_private_relative_path_hash": stable_hash(str(path.relative_to(REAL_DATA_DIR))),
                "split": "unassigned",
            }
        )
    write_jsonl(OUT, rows)
    result = {"marker": "REAL_IMAGE_MANIFEST_COMPLETE" if rows else "REAL_IMAGE_MANIFEST_BLOCKED", "image_count": len(rows)}
    write_json(AUDIT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
