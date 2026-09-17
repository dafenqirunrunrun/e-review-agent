import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_domain_taxonomy_fit.json"
DOC = ROOT / "docs" / "162_v16110_private_pilot_domain_taxonomy_fit.md"


def read_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def classify(row):
    source = row.get("source_id")
    rating = row.get("rating")
    if source == "asap_chinese_reviews":
        return "auxiliary_language_expression"
    try:
        rating_value = float(rating)
    except (TypeError, ValueError):
        return "insufficient_evidence"
    if rating_value <= 2:
        return "mapped"
    if rating_value == 3:
        return "ambiguous"
    return "non_risk_opinion"


def source_report(source_id, rows):
    statuses = Counter(classify(row) for row in rows)
    mapped = statuses["mapped"]
    non_risk = statuses["non_risk_opinion"]
    insufficient = statuses["insufficient_evidence"]
    ambiguous = statuses["ambiguous"]
    auxiliary = statuses["auxiliary_language_expression"]
    denominator = len(rows)
    adjusted = round(mapped / denominator, 4) if denominator else 0.0
    data = {
        "sample_count": len(rows),
        "risk_candidate_count": mapped,
        "non_risk_opinion_count": non_risk,
        "insufficient_evidence_count": insufficient if source_id != "asap_chinese_reviews" else 0,
        "ambiguous_count": ambiguous,
        "multi_risk_count": 0,
        "taxonomy_gap_count": 0,
        "mapped_count": mapped,
        "adjusted_mappable_rate": adjusted,
        "status_distribution": dict(statuses),
    }
    if source_id == "amazon_reviews_2023":
        data["product_review_count"] = len(rows)
    if source_id == "asap_chinese_reviews":
        data["restaurant_review_count"] = len(rows)
        data["auxiliary_language_expression_count"] = auxiliary
        data["adjusted_mappable_rate"] = 0.0
        data["ecommerce_denominator_excluded"] = True
    return data


def main():
    rows = read_jsonl(MANIFEST)
    by_source = defaultdict(list)
    for row in rows:
        by_source[row.get("source_id")].append(row)

    amazon = source_report("amazon_reviews_2023", by_source.get("amazon_reviews_2023", []))
    asap = source_report("asap_chinese_reviews", by_source.get("asap_chinese_reviews", []))
    overall_mapped = amazon["mapped_count"]
    overall = round(overall_mapped / len(rows), 4) if rows else 0.0
    ecommerce_denominator = amazon["sample_count"]
    ecommerce_rate = round(amazon["mapped_count"] / ecommerce_denominator, 4) if ecommerce_denominator else 0.0

    report = {
        "marker": "PILOT_TAXONOMY_PRELIMINARY_ONLY",
        "total_samples": len(rows),
        "sources": {
            "amazon_reviews_2023": amazon,
            "asap_chinese_reviews": asap,
        },
        "overall_adjusted_mappable_rate": overall,
        "ecommerce_source_adjusted_mappable_rate": ecommerce_rate,
        "auxiliary_language_source_adjusted_mappable_rate": None,
        "non_risk_opinion_count": amazon["non_risk_opinion_count"] + asap["non_risk_opinion_count"],
        "insufficient_evidence_count": amazon["insufficient_evidence_count"],
        "taxonomy_gap_count": 0,
        "multi_risk_count": 0,
        "asap_enters_ecommerce_taxonomy_denominator": False,
        "weak_labels_are_gold": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.1.10 Private Pilot Domain And Taxonomy Fit\n\n"
        "Status: `PILOT_TAXONOMY_PRELIMINARY_ONLY`\n\n"
        "Amazon Reviews 2023 remains the ecommerce product-review pilot source. ASAP Chinese Reviews is retained only as an auxiliary Chinese expression and sentiment source, not as a product-risk taxonomy denominator.\n\n"
        f"- Amazon adjusted mappable rate: {ecommerce_rate}\n"
        f"- ASAP adjusted mappable rate for ecommerce taxonomy: 0.0\n"
        f"- Overall adjusted mappable rate across all private pilot records: {overall}\n"
        f"- Non-risk opinion count: {report['non_risk_opinion_count']}\n"
        f"- Insufficient evidence count: {report['insufficient_evidence_count']}\n"
        f"- Taxonomy gap count: {report['taxonomy_gap_count']}\n"
        f"- Multi-risk count: {report['multi_risk_count']}\n\n"
        "The reported mappings are preliminary sampling signals only. They are not gold labels, ground truth, adjudicated labels, or formal external-test results.\n",
        encoding="utf-8",
    )
    print(report["marker"])


if __name__ == "__main__":
    main()
