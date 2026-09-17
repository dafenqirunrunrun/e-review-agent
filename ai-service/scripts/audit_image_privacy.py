import json
from pathlib import Path

from realworld_data_policy import REAL_MANIFEST_DIR, load_jsonl, write_json


MANIFEST = REAL_MANIFEST_DIR / "split_manifest" / "real_image_manifest.jsonl"
OUT = REAL_MANIFEST_DIR / "audit" / "image_privacy_audit.json"


def main() -> int:
    rows = load_jsonl(MANIFEST)
    cleared = sum(1 for row in rows if row.get("privacy_status") == "cleared")
    rejected = sum(1 for row in rows if row.get("privacy_status") == "rejected")
    uncertain = sum(1 for row in rows if row.get("privacy_status") in {None, "pending", "uncertain"})
    marker = "REAL_IMAGE_PRIVACY_AUDIT_PASS" if rows and uncertain == 0 else "REAL_IMAGE_PRIVACY_AUDIT_BLOCKED"
    result = {
        "marker": marker,
        "image_count": len(rows),
        "privacy_cleared_count": cleared,
        "privacy_rejected_count": rejected,
        "privacy_uncertain_count": uncertain,
        "blocking_reasons": [] if marker.endswith("_PASS") else ["image manifest is missing or contains privacy-pending images"],
    }
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
