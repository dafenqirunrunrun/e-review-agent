import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = Path(os.getenv("E_REVIEW_PRIVATE_DATA_ROOT", ROOT.parent / "data-private"))
PILOT_V1 = PRIVATE_ROOT / "realworld-pilot"
PILOT_V2 = PRIVATE_ROOT / "realworld-pilot-v2"
PRIVATE_OUT = PILOT_V2 / "manifests" / "private_source_locators.jsonl"
GIT_OUT = ROOT / "data" / "real_world" / "audit" / "pilot_source_locator_recovery.json"


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def short_hash(value) -> str:
    return sha256_text(str(value))[:24]


def is_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def host_of(value):
    if not is_url(value):
        return None
    return urlparse(value).netloc.lower()


def walk_urls(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if is_url(value):
                yield key, value
            else:
                yield from walk_urls(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_urls(value)


def find_private_rows():
    candidates = []
    for path in [
        PILOT_V1 / "raw" / "amazon_all_beauty_selected_private.jsonl",
        PILOT_V1 / "manifests" / "image_private_manifest.jsonl",
    ]:
        candidates.extend((path, row) for row in read_jsonl(path))
    return candidates


def main():
    private_rows = find_private_rows()
    source_snapshot_available = any(path.exists() for path, _ in private_rows)
    image_ids = set()
    image_to_record = defaultdict(list)
    recovered = {}
    recovery_methods = Counter()
    host_distribution = Counter()

    for path, row in private_rows:
        ids = []
        for key in ("image_id", "image_private_ids", "image_ids"):
            value = row.get(key)
            if isinstance(value, list):
                ids.extend(str(item) for item in value)
            elif value:
                ids.append(str(value))
        for image_id in ids:
            image_ids.add(image_id)
            source_record_id = row.get("source_record_id") or row.get("review_id") or row.get("sample_id_hash")
            image_to_record[image_id].append({
                "source_record_id": source_record_id,
                "source_record_id_hash": short_hash(source_record_id) if source_record_id else None,
                "dataset_version": row.get("dataset_version") or row.get("source_id") or "amazon_reviews_2023_private_snapshot",
                "source_file_role": path.name,
            })
        for field, url in walk_urls(row):
            for image_id in ids:
                recovered[image_id] = {"field": field, "url": url}
                recovery_methods["official_snapshot_url_field"] += 1
                host_distribution[host_of(url) or "unknown"] += 1

    previous = json.loads((ROOT / "data" / "real_world" / "audit" / "pilot_image_download_retry.json").read_text(encoding="utf-8"))
    total_expected = int(previous.get("images_expected", len(image_ids)))
    downloaded = int(previous.get("valid_image_count", 0))
    total_missing_images = max(total_expected - downloaded, 0)

    PRIVATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    manifest_lines = []
    for image_id in sorted(image_ids):
        locator = recovered.get(image_id)
        record_links = image_to_record.get(image_id) or [{}]
        private_record = {
            "source_id": "amazon_reviews_2023",
            "dataset_version": record_links[0].get("dataset_version", "amazon_reviews_2023_private_snapshot"),
            "source_record_id": record_links[0].get("source_record_id"),
            "source_record_id_hash": record_links[0].get("source_record_id_hash"),
            "image_id": image_id,
            "image_locator": locator.get("url") if locator else None,
            "image_locator_type": "official_snapshot_url" if locator else None,
            "image_locator_acquired_at": datetime.now(timezone.utc).isoformat() if locator else None,
            "image_locator_status": "recovered" if locator else "unrecoverable_source_locator_missing",
            "image_locator_host": host_of(locator.get("url")) if locator else None,
            "image_locator_sha256": sha256_text(locator.get("url")) if locator else None,
            "download_status": "pending_retry" if locator else "blocked_no_locator",
            "failure_reason": None if locator else "locator_unrecoverable",
            "recovery_method": "official_snapshot_url_field" if locator else "no_official_locator_in_private_snapshot",
        }
        manifest_lines.append(json.dumps(private_record, ensure_ascii=False))
    PRIVATE_OUT.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")

    private_sha = hashlib.sha256(PRIVATE_OUT.read_bytes()).hexdigest() if PRIVATE_OUT.exists() else None
    exact_record_match_count = sum(1 for image_id in image_ids if image_to_record.get(image_id))
    report = {
        "marker": "PILOT_SOURCE_LOCATOR_RECOVERY_COMPLETE" if recovered else "PILOT_SOURCE_LOCATOR_RECOVERY_BLOCKED",
        "total_private_image_ids": len(image_ids),
        "total_missing_images": total_missing_images,
        "exact_record_match_count": exact_record_match_count,
        "recovered_locator_count": len(recovered),
        "unrecoverable_count": total_missing_images if not recovered else max(total_missing_images - len(recovered), 0),
        "source_snapshot_available": source_snapshot_available,
        "source_snapshot_version": "private_v1_selected_records_without_url" if source_snapshot_available else None,
        "locator_host_distribution": dict(sorted(host_distribution.items())),
        "signed_url_count": 0,
        "expired_locator_count": 0,
        "recovery_method_counts": dict(recovery_methods) if recovered else {"no_official_locator_in_private_snapshot": len(image_ids)},
        "private_manifest_sha256": private_sha,
        "git_report_url_redacted": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    GIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    GIT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
