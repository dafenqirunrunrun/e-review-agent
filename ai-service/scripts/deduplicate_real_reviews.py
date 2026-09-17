import argparse
import json
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, load_jsonl, stable_hash, write_json, write_jsonl


AUDIT = REAL_DATA_DIR / "audit-cache" / "real_review_deduplication_audit.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_anonymized.jsonl")
    parser.add_argument("--output", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_deduplicated.jsonl")
    args = parser.parse_args()
    seen = set()
    unique = []
    duplicate_count = 0
    for row in load_jsonl(args.input):
        key = stable_hash((row.get("review_text_redacted") or "").strip().lower())
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        unique.append(row)
    write_jsonl(args.output, unique)
    result = {"marker": "REAL_REVIEW_DEDUPLICATION_COMPLETE", "input_count": len(unique) + duplicate_count, "unique_count": len(unique), "exact_duplicate_count": duplicate_count}
    write_json(AUDIT, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
