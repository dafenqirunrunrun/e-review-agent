import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = Path(os.getenv("E_REVIEW_PRIVATE_DATA_ROOT", ROOT.parent / "data-private"))
PILOT_V1 = PRIVATE_ROOT / "realworld-pilot"
PILOT_V1_FROZEN = PRIVATE_ROOT / "realworld-pilot-v1-frozen"
OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_v1_freeze_manifest.json"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short_hash(value) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:24]


def copy_snapshot():
    if not PILOT_V1.exists():
        return False
    if PILOT_V1_FROZEN.exists():
        return True
    shutil.copytree(PILOT_V1, PILOT_V1_FROZEN)
    return True


def main():
    frozen = copy_snapshot()
    aggregate = read_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl")
    image_privacy = read_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "image_privacy_aggregate_manifest.jsonl")

    source_counts = Counter(row.get("source_id", "unknown") for row in aggregate)
    image_counts = Counter(row.get("privacy_status", "unknown") for row in image_privacy)
    multimodal_record_count = sum(1 for row in aggregate if int(row.get("image_count") or 0) > 0)
    expected_image_count = len(image_privacy)

    source_manifest = ROOT / "data" / "real_world" / "source_manifest" / "delegated_approved_sources.jsonl"
    source_manifest_sha256 = sha256_file(source_manifest) if source_manifest.exists() else None

    previous_download = ROOT / "data" / "real_world" / "audit" / "pilot_image_download_retry.json"
    previous_download_data = json.loads(previous_download.read_text(encoding="utf-8")) if previous_download.exists() else {}
    previous_taxonomy = ROOT / "data" / "real_world" / "audit" / "pilot_taxonomy_mapping_quality.json"
    taxonomy_data = json.loads(previous_taxonomy.read_text(encoding="utf-8")) if previous_taxonomy.exists() else {}
    previous_duplicates = ROOT / "data" / "real_world" / "audit" / "pilot_duplicate_audit.json"
    duplicate_data = json.loads(previous_duplicates.read_text(encoding="utf-8")) if previous_duplicates.exists() else {}

    report = {
        "marker": "PRIVATE_PILOT_V1_FROZEN" if frozen else "PRIVATE_PILOT_V1_FREEZE_BLOCKED",
        "processing_version": "v1.6.1-realworld-pilot-v1-freeze",
        "source_counts": dict(sorted(source_counts.items())),
        "sample_id_hashes": [row.get("sample_id_hash") for row in aggregate[:50]],
        "sample_hash_count": len(aggregate),
        "multimodal_record_count": multimodal_record_count,
        "expected_image_count": expected_image_count,
        "downloaded_image_count": previous_download_data.get("valid_image_count", 0),
        "privacy_status_counts": dict(sorted(image_counts.items())),
        "taxonomy_status_counts": taxonomy_data.get("status_distribution", {}),
        "duplicate_counts": {
            "exact_text_duplicate": duplicate_data.get("exact_text_duplicate", 1),
            "perceptual_image_duplicate": duplicate_data.get("perceptual_image_duplicate", 0),
        },
        "source_manifest_sha256": source_manifest_sha256,
        "private_snapshot_present": PILOT_V1.exists(),
        "private_snapshot_frozen": frozen,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
