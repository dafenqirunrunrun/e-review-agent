import argparse
import json
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, load_jsonl, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data" / "real_world" / "split_manifest" / "real_text_split_audit.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_deduplicated.jsonl")
    parser.add_argument("--dev-size", type=int, default=400)
    parser.add_argument("--validation-size", type=int, default=200)
    parser.add_argument("--external-size", type=int, default=200)
    args = parser.parse_args()
    rows = load_jsonl(args.input)
    required = args.dev_size + args.validation_size + args.external_size
    if len(rows) < required:
        result = {"marker": "REALWORLD_TEXT_SPLIT_BLOCKED", "input_count": len(rows), "required": required}
        write_json(AUDIT, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    ordered = sorted(rows, key=lambda row: stable_hash(row["sample_id"]))
    buckets = [
        ("development", ordered[: args.dev_size]),
        ("validation", ordered[args.dev_size : args.dev_size + args.validation_size]),
        ("external_test", ordered[args.dev_size + args.validation_size : required]),
    ]
    private_dir = REAL_DATA_DIR / "external-test"
    for split, split_rows in buckets:
        out_rows = []
        for row in split_rows:
            item = dict(row)
            item["split"] = split
            out_rows.append(item)
        write_jsonl(private_dir / f"real_reviews_{split}.jsonl", out_rows)
    result = {"marker": "REALWORLD_TEXT_SPLIT_COMPLETE", "development": args.dev_size, "validation": args.validation_size, "external_test": args.external_size}
    write_json(AUDIT, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
