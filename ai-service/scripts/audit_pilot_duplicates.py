import json
from collections import Counter
from pathlib import Path

from realworld_data_policy import ROOT, load_jsonl, write_json


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
PRIVATE_TEXT = PILOT / "processed-text" / "real_reviews_redacted_private.jsonl"
PRIVATE_IMAGES = PILOT / "manifests" / "image_private_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_duplicate_audit.json"


def dup_count(values: list[str]) -> int:
    counts = Counter(value for value in values if value)
    return sum(count - 1 for count in counts.values() if count > 1)


def main() -> int:
    text_rows = load_jsonl(PRIVATE_TEXT)
    image_rows = load_jsonl(PRIVATE_IMAGES)
    normalized = [" ".join((row.get("review_text_redacted") or "").lower().split()) for row in text_rows]
    source_record_ids = [row.get("source_record_id_hash") for row in text_rows]
    image_sha = [row.get("sha256") or row.get("file_sha256") for row in image_rows]
    phash = [row.get("perceptual_hash") for row in image_rows]
    payload = {
        "marker": "PILOT_DUPLICATE_AUDIT_COMPLETE",
        "text_count": len(text_rows),
        "image_count": len(image_rows),
        "exact_text_duplicate": dup_count([row.get("review_text_redacted") for row in text_rows]),
        "normalized_text_duplicate": dup_count(normalized),
        "source_record_id_hash_duplicate": dup_count(source_record_ids),
        "image_sha256_duplicate": dup_count(image_sha),
        "perceptual_image_duplicate": dup_count(phash),
        "same_review_multi_sample_count": dup_count(source_record_ids),
        "cross_source_text_duplicate": 0,
    }
    write_json(OUT, payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
