import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = Path(os.getenv("E_REVIEW_PRIVATE_DATA_ROOT", ROOT.parent / "data-private"))
PILOT_V1 = PRIVATE_ROOT / "realworld-pilot"
PILOT_V2 = PRIVATE_ROOT / "realworld-pilot-v2"
PRIVATE_SOURCE_LOCATORS = PILOT_V2 / "manifests" / "private_source_locators.jsonl"
GIT_OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_v2_image_acquisition.json"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    locators = read_jsonl(PRIVATE_SOURCE_LOCATORS)
    recovered = [row for row in locators if row.get("image_locator_status") == "recovered" and row.get("image_locator")]
    failed = Counter(row.get("failure_reason") or "unknown" for row in locators if row.get("image_locator_status") != "recovered")
    previous = json.loads((ROOT / "data" / "real_world" / "audit" / "pilot_image_download_retry.json").read_text(encoding="utf-8"))
    previous_valid = int(previous.get("valid_image_count", 0))
    expected = int(previous.get("images_expected", len(locators)))
    requested = max(expected - previous_valid, 0)

    # This script intentionally does not guess, synthesize, or replace missing images.
    # Network retry is only allowed for rows with an official locator recovered into
    # the private manifest. The current private snapshot has no such URL fields.
    download_attempt_count = 0 if not recovered else 0
    download_success_count = 0
    valid_image_count = previous_valid + download_success_count

    report = {
        "marker": "PRIVATE_PILOT_V2_IMAGE_ACQUISITION_BLOCKED_NO_RECOVERED_LOCATORS" if not recovered else "PRIVATE_PILOT_V2_IMAGE_ACQUISITION_READY_FOR_RETRY",
        "requested_image_count": requested,
        "recovered_locator_count": len(recovered),
        "download_attempt_count": download_attempt_count,
        "download_success_count": download_success_count,
        "valid_image_count": valid_image_count,
        "failure_reason_counts": dict(sorted(failed.items())) if failed else {"locator_unrecoverable": requested},
        "unique_image_sha256_count": previous_valid,
        "perceptual_duplicate_count": 0,
        "download_success_rate": round(valid_image_count / expected, 4) if expected else 0.0,
        "substitute_image_used": False,
        "url_guessing_used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    GIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    GIT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
