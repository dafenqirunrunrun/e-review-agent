import json
from pathlib import Path

from realworld_data_policy import REAL_MANIFEST_DIR, load_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
SOURCE_CANDIDATES = REAL_MANIFEST_DIR / "source_manifest" / "source_candidates.jsonl"
APPROVED = REAL_MANIFEST_DIR / "source_manifest" / "approved_sources.jsonl"
OUT = REAL_MANIFEST_DIR / "audit" / "source_license_audit.json"
REPORT = ROOT / "docs" / "144_v1616_realworld_source_and_license_audit.md"


REQUIRED_FIELDS = {
    "source_id",
    "source_name",
    "official_publisher",
    "official_url",
    "license_name",
    "research_use_allowed",
    "redistribution_allowed",
    "contains_review_text",
    "contains_images",
    "contains_personal_information",
    "approval_status",
}


def approval_reason(row: dict) -> str | None:
    missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
    if missing:
        return f"missing required fields: {', '.join(missing)}"
    if row.get("approval_status") != "approved":
        return row.get("rejection_reason") or "source is not approved"
    if row.get("research_use_allowed") is not True:
        return "research use is not explicitly allowed"
    if row.get("redistribution_allowed") is not True and row.get("derived_data_redistribution_allowed") is not True:
        return "neither raw nor derived redistribution is allowed"
    if row.get("contains_personal_information") is True and not row.get("data_retention_restrictions"):
        return "personal information risk requires explicit retention/redaction notes"
    return None


def report(result: dict) -> str:
    rows = "\n".join(
        f"| `{row['source_id']}` | {row.get('source_name')} | {row.get('license_name')} | {row.get('approval_status')} | {row.get('audit_reason') or 'ok'} |"
        for row in result["sources"]
    ) or "| - | - | - | - | - |"
    return f"""# v1.6.1.6 Real-World Source And License Audit

## Conclusion

`{result['marker']}`

## Source Audit

| source_id | source_name | license | approval_status | audit_reason |
| --- | --- | --- | --- | --- |
{rows}

## Boundary

Only `approval_status=approved` sources with explicit research permission may
enter the downstream pipeline. If redistribution is restricted, Git stores only
hashes, manifests, statistics, scripts, and aggregate audit results.
"""


def main() -> int:
    candidates = load_jsonl(SOURCE_CANDIDATES)
    approved = []
    sources = []
    for row in candidates:
        item = dict(row)
        reason = approval_reason(item)
        item["audit_reason"] = reason
        if reason is None:
            approved.append(item)
        sources.append(item)
    marker = "REALWORLD_SOURCE_LICENSE_AUDIT_PASS" if approved else "REALWORLD_SOURCE_LICENSE_AUDIT_BLOCKED"
    result = {
        "marker": marker,
        "approved_text_source_count": sum(1 for row in approved if row.get("contains_review_text")),
        "approved_multimodal_source_count": sum(1 for row in approved if row.get("contains_review_text") and row.get("contains_images")),
        "sources": sources,
        "blocking_reasons": [] if approved else ["no compliant real-world source has been approved for downstream use"],
    }
    write_json(OUT, result)
    APPROVED.parent.mkdir(parents=True, exist_ok=True)
    with APPROVED.open("w", encoding="utf-8", newline="\n") as handle:
        for row in approved:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    REPORT.write_text(report(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
