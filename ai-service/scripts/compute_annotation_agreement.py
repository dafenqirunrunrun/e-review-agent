import argparse
import json
from collections import Counter
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, load_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "annotation_agreement.json"


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    total = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / total
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum((left[label] / total) * (right[label] / total) for label in set(left) | set(right))
    if expected == 1:
        return 1.0
    return round((observed - expected) / (1 - expected), 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, default=REAL_DATA_DIR / "annotations" / "dual_annotations.jsonl")
    args = parser.parse_args()
    rows = load_jsonl(args.annotations)
    if not rows:
        result = {
            "marker": "ANNOTATION_RELIABILITY_BLOCKED",
            "blocking_reasons": ["dual independent annotation file is missing"],
            "risk_type_kappa": None,
            "risk_level_kappa": None,
            "need_human_review_kappa": None,
            "text_image_consistency_kappa": None,
        }
        write_json(OUT, result)
        print(json.dumps(result, ensure_ascii=False))
        print(result["marker"])
        return 0
    def pairs(field: str):
        return [(str(row.get("annotator_a", {}).get(field)), str(row.get("annotator_b", {}).get(field))) for row in rows]
    result = {
        "marker": "ANNOTATION_RELIABILITY_COMPLETE",
        "sample_count": len(rows),
        "risk_type_kappa": cohen_kappa(pairs("risk_type")),
        "risk_level_kappa": cohen_kappa(pairs("risk_level")),
        "need_human_review_kappa": cohen_kappa(pairs("need_human_review")),
        "text_image_consistency_kappa": cohen_kappa(pairs("text_image_consistency")),
    }
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
