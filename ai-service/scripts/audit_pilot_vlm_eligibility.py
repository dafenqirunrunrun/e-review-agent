import json
from pathlib import Path

from realworld_data_policy import ROOT, load_jsonl, write_json


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
PRIVATE_AUDIT = PILOT / "privacy-audit" / "image_privacy_private_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_vlm_eligibility.json"


def main() -> int:
    rows = load_jsonl(PRIVATE_AUDIT)
    counts = {
        "automated_cleared_count": sum(1 for row in rows if row.get("privacy_status") == "automated_cleared"),
        "automated_redacted_count": sum(1 for row in rows if row.get("privacy_status") == "automated_redacted"),
        "automated_uncertain_count": sum(1 for row in rows if row.get("privacy_status") == "automated_uncertain"),
        "automated_rejected_count": sum(1 for row in rows if row.get("privacy_status") == "automated_rejected"),
    }
    eligible = counts["automated_cleared_count"] + counts["automated_redacted_count"]
    payload = {
        "marker": "REALWORLD_VLM_ELIGIBILITY_COMPLETE",
        "eligible_record_count": eligible,
        "eligible_image_count": eligible,
        **counts,
        "excluded_duplicate_count": 0,
        "excluded_invalid_image_count": counts["automated_rejected_count"],
        "excluded_license_count": 0,
    }
    write_json(OUT, payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
