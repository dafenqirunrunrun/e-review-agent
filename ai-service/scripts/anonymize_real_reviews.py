import argparse
import json
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, load_jsonl, redact_text, write_json, write_jsonl


AUDIT = REAL_DATA_DIR / "audit-cache" / "real_review_anonymization_audit.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_normalized.jsonl")
    parser.add_argument("--output", type=Path, default=REAL_DATA_DIR / "processed-text" / "real_reviews_anonymized.jsonl")
    args = parser.parse_args()
    rows = load_jsonl(args.input)
    out = []
    pii_hit_count = 0
    for row in rows:
        item = dict(row)
        redacted, hits = redact_text(item.get("review_text_redacted") or item.get("review_text") or "")
        pii_hit_count += hits
        item["review_text_redacted"] = redacted
        item["privacy_status"] = "redacted" if hits else "cleared"
        out.append(item)
    write_jsonl(args.output, out)
    result = {"marker": "REAL_REVIEW_ANONYMIZATION_COMPLETE", "count": len(out), "pii_hit_count": pii_hit_count}
    write_json(AUDIT, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
