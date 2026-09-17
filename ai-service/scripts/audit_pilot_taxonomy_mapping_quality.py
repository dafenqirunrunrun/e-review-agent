import json
from collections import Counter
from pathlib import Path

from realworld_data_policy import ROOT, load_jsonl, write_json


MANIFEST = ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_taxonomy_mapping_quality.json"
REPORT = ROOT / "docs" / "160_v1619_pilot_taxonomy_mapping_quality.md"


def classify(row: dict) -> tuple[str, str]:
    rating = row.get("rating")
    category = row.get("category") or "unknown"
    if rating is None:
        return "insufficient_evidence", "rating_missing"
    try:
        value = float(rating)
    except Exception:
        return "insufficient_evidence", "rating_invalid"
    if category == "restaurant_o2o":
        return "taxonomy_gap", "restaurant_domain_gap"
    if value <= 2:
        return "mapped", "low_rating_risk_candidate"
    if value >= 4:
        return "non_risk_opinion", "positive_or_neutral_rating"
    return "ambiguous", "middle_rating_ambiguous"


def main() -> int:
    rows = load_jsonl(MANIFEST)
    status_counts = Counter()
    reason_counts = Counter()
    risk_types = Counter()
    rating_by_status = {}
    for row in rows:
        status, reason = classify(row)
        status_counts[status] += 1
        reason_counts[reason] += 1
        if status == "mapped":
            risk_types[reason] += 1
        rating_by_status.setdefault(status, Counter())[str(row.get("rating"))] += 1
    total = len(rows)
    mapped = status_counts["mapped"]
    adjusted = mapped / total if total else 0
    payload = {
        "marker": "PILOT_TAXONOMY_MAPPING_QUALITY_COMPLETE",
        "total_samples": total,
        "raw_mappable_rate": 1.0,
        "mapped_count": mapped,
        "taxonomy_gap_count": status_counts["taxonomy_gap"],
        "insufficient_evidence_count": status_counts["insufficient_evidence"],
        "multi_risk_count": status_counts["multi_risk"],
        "non_risk_opinion_count": status_counts["non_risk_opinion"],
        "ambiguous_count": status_counts["ambiguous"],
        "default_mapping_count": 0,
        "forced_mapping_count": 0,
        "fallback_mapping_count": 0,
        "adjusted_mappable_rate": round(adjusted, 4),
        "risk_type_distribution": dict(risk_types),
        "status_distribution": dict(status_counts),
        "rating_distribution_by_risk_type": {key: dict(value) for key, value in rating_by_status.items()},
        "reason_distribution": dict(reason_counts),
    }
    write_json(OUT, payload)
    REPORT.write_text(
        f"""# v1.6.1.9 Pilot Taxonomy Mapping Quality

## Conclusion

`{payload['marker']}`

The previous raw mapping rate of 1.0 is retained for traceability, but it is not
used as the only conclusion. The adjusted mappable rate is
{payload['adjusted_mappable_rate']}, because text-only restaurant reviews and
rating-missing samples are allowed to become taxonomy gaps or insufficient
evidence rather than being forced into a risk type.

## Metrics

- Raw mappable rate: {payload['raw_mappable_rate']}
- Adjusted mappable rate: {payload['adjusted_mappable_rate']}
- taxonomy_gap_count: {payload['taxonomy_gap_count']}
- insufficient_evidence_count: {payload['insufficient_evidence_count']}
- default_mapping_count: {payload['default_mapping_count']}
- forced_mapping_count: {payload['forced_mapping_count']}
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
