import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_v2_sampling_report.json"


def read_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def bucket_rating(value):
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "missing"


def main():
    rows = [row for row in read_jsonl(MANIFEST) if row.get("source_id") == "amazon_reviews_2023"]
    selected = rows[:150]
    multimodal = [row for row in selected if int(row.get("image_count") or 0) > 0]
    rating_distribution = Counter(bucket_rating(row.get("rating")) for row in selected)
    sampling_rule_counts = Counter()
    for row in selected:
        rating = bucket_rating(row.get("rating"))
        if rating in {"1", "2"}:
            sampling_rule_counts["low_star_risk_candidate"] += 1
        elif int(row.get("image_count") or 0) > 0:
            sampling_rule_counts["image_available_review"] += 1
        else:
            sampling_rule_counts["control_or_non_risk_candidate"] += 1
    sample_hashes = [
        hashlib.sha256((row.get("sample_id_hash", "") + "|v2").encode("utf-8")).hexdigest()[:24]
        for row in selected[:50]
    ]
    report = {
        "marker": "PILOT_TAXONOMY_PRELIMINARY_ONLY",
        "source_population_count": len(rows),
        "candidate_count": len(selected),
        "selected_count": len(selected),
        "rating_distribution": dict(sorted(rating_distribution.items())),
        "category_distribution": {"beauty_product_review": len(selected)},
        "image_available_count": len(multimodal),
        "multimodal_record_count": len(multimodal),
        "sampling_rule_counts": dict(sorted(sampling_rule_counts.items())),
        "positive_candidate_count": sum(count for rating, count in rating_distribution.items() if rating in {"4", "5"}),
        "control_candidate_count": sum(count for rating, count in rating_distribution.items() if rating in {"3", "4", "5"}),
        "sample_hashes": sample_hashes,
        "annotation_source": "heuristic_candidate_status",
        "annotation_reliability": "unverified",
        "not_gold_label": True,
        "not_external_test": True,
        "not_sft": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
