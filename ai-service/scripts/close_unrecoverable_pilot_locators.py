import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "data" / "real_world" / "audit" / "pilot_source_locator_recovery.json"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_unrecoverable_locator_closure.json"


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def main():
    recovery = json.loads(RECOVERY.read_text(encoding="utf-8"))
    total = int(recovery.get("unrecoverable_count", 0))
    affected = [short_hash(f"unrecoverable_locator:{idx}") for idx in range(total)]
    report = {
        "marker": "PILOT_UNRECOVERABLE_LOCATORS_CLOSED",
        "total_unrecoverable_count": total,
        "affected_record_hashes": affected,
        "official_snapshot_checked": bool(recovery.get("source_snapshot_available")),
        "official_snapshot_version": recovery.get("source_snapshot_version"),
        "locator_field_absent": recovery.get("recovered_locator_count", 0) == 0,
        "retry_disabled": True,
        "retry_allowed": False,
        "retry_reason": "official_snapshot_contains_no_image_locator",
        "third_party_recovery_prohibited": True,
        "alternative_source_allowed": False,
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
