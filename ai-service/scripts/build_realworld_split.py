import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/real_world/processed/real_reviews_staging_anonymized.jsonl"
DEV_OUT = ROOT / "data/real_world/processed/real_reviews_dev_400.jsonl"
TEST_OUT = ROOT / "data/real_world/external_test/real_reviews_external_test_200.jsonl"


def load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def text_hash(row: Dict) -> str:
    return hashlib.sha256((row.get("review_text") or "").strip().lower().encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dev-size", type=int, default=400)
    parser.add_argument("--test-size", type=int, default=200)
    args = parser.parse_args()
    rows = load_jsonl(args.input)
    if len(rows) < args.dev_size + args.test_size:
        print(json.dumps({
            "marker": "REALWORLD_SPLIT_BLOCKED",
            "input_count": len(rows),
            "required": args.dev_size + args.test_size,
        }, ensure_ascii=False))
        return 0
    seen = set()
    unique = []
    for row in rows:
        key = text_hash(row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    groups = defaultdict(list)
    for row in unique:
        groups[row.get("product_record_hash") or row["sample_id"]].append(row)
    dev, test = [], []
    for _, group in sorted(groups.items()):
        target = dev if len(dev) < args.dev_size else test
        for row in group:
            if target is dev and len(dev) >= args.dev_size:
                target = test
            if target is test and len(test) >= args.test_size:
                break
            item = dict(row)
            item["split"] = "dev" if target is dev else "external_test"
            target.append(item)
    if len(dev) < args.dev_size or len(test) < args.test_size:
        print(json.dumps({"marker": "REALWORLD_SPLIT_BLOCKED", "dev": len(dev), "external_test": len(test)}, ensure_ascii=False))
        return 0
    write_jsonl(DEV_OUT, dev)
    write_jsonl(TEST_OUT, test)
    print(json.dumps({"marker": "REALWORLD_SPLIT_COMPLETE", "dev": len(dev), "external_test": len(test)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
