import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, TEXT_SCHEMA_REQUIRED, load_jsonl, source_by_id, stable_hash, write_jsonl


def normalize_row(row: dict, source_id: str) -> dict:
    record_id = str(row.get("source_record_id") or row.get("id") or row.get("review_id") or row.get("record_id") or "")
    text = str(row.get("review_text") or row.get("text") or row.get("review") or "")
    return {
        "sample_id": stable_hash(f"{source_id}:{record_id or text}")[:24],
        "source_id": source_id,
        "source_record_id_hash": stable_hash(record_id or text, source_id),
        "source_language": row.get("source_language") or row.get("language") or "other",
        "product_category": row.get("product_category") or row.get("category") or "unknown",
        "rating": row.get("rating"),
        "review_text": text,
        "review_text_redacted": text,
        "image_available": bool(row.get("image_available") or row.get("image_ids")),
        "image_ids": row.get("image_ids") or [],
        "source_type": "real_public",
        "privacy_status": "pending",
        "annotation_status": "unlabeled",
        "split": "unassigned",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processing_version": "v1.6.1.6",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_normalized.jsonl")
    args = parser.parse_args()
    if source_by_id(args.source_id) is None:
        print(json.dumps({"marker": "REAL_TEXT_DATA_SOURCE_NOT_AVAILABLE", "source_id": args.source_id}, ensure_ascii=False))
        return 0
    rows = [normalize_row(row, args.source_id) for row in load_jsonl(args.input)]
    invalid = [row["sample_id"] for row in rows if set(row) != TEXT_SCHEMA_REQUIRED]
    if invalid:
        print(json.dumps({"marker": "REAL_REVIEW_NORMALIZATION_BLOCKED", "invalid_count": len(invalid)}, ensure_ascii=False))
        return 0
    write_jsonl(args.output, rows)
    print(json.dumps({"marker": "REAL_REVIEW_NORMALIZATION_COMPLETE", "count": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
