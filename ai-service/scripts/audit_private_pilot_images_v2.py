import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = Path(os.getenv("E_REVIEW_PRIVATE_DATA_ROOT", ROOT.parent / "data-private"))
PILOT_V2 = PRIVATE_ROOT / "realworld-pilot-v2"
PRIVATE_OUT = PILOT_V2 / "manifests" / "private_image_privacy_v2.jsonl"
GIT_OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_v2_image_privacy.json"
CAPABILITIES = ROOT / "data" / "real_world" / "audit" / "image_privacy_detector_capabilities.json"


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
    capability = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    missing = capability.get("missing_mandatory_detectors", [])
    prior_rows = read_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "image_privacy_aggregate_manifest.jsonl")
    reason = "automated_uncertain_detector_unavailable" if missing else "automated_uncertain_detector_error"

    PRIVATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for row in prior_rows:
        image_hash = row.get("image_id_hash")
        lines.append(json.dumps({
            "image_hash": image_hash,
            "privacy_status": reason,
            "reason_codes": missing or ["detector_error"],
            "detector_result_summary": {
                "mandatory_missing_count": len(missing),
                "full_ocr_text_retained": False,
                "human_review_performed": False,
            },
            "detection_count": 0,
            "masked_excerpt": None,
            "processed_image_hash": hashlib.sha256(str(image_hash).encode("utf-8")).hexdigest()[:24],
        }, ensure_ascii=False))
    PRIVATE_OUT.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    status_counts = Counter([reason for _ in prior_rows])
    report = {
        "marker": "PRIVATE_PILOT_V2_IMAGE_PRIVACY_BLOCKED_DETECTOR_UNAVAILABLE" if missing else "PRIVATE_PILOT_V2_IMAGE_PRIVACY_COMPLETE",
        "image_count": len(prior_rows),
        "automated_cleared": 0 if missing else len(prior_rows),
        "automated_redacted": 0,
        "automated_uncertain": len(prior_rows) if missing else 0,
        "automated_uncertain_reason_distribution": dict(status_counts),
        "automated_rejected": 0,
        "missing_mandatory_detectors": missing,
        "qwen3_vl_used_for_clearance": False,
        "human_review_performed": False,
        "private_manifest_sha256": hashlib.sha256(PRIVATE_OUT.read_bytes()).hexdigest() if PRIVATE_OUT.exists() else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    GIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    GIT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
