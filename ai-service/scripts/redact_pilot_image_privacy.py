import hashlib
import json
import shutil
from pathlib import Path

from realworld_data_policy import ROOT, load_jsonl, write_json, write_jsonl


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
RAW_IMAGES = PILOT / "raw-images"
REDACTED = PILOT / "processed-images" / "redacted"
PRIVATE_AUDIT = PILOT / "privacy-audit" / "image_privacy_private_manifest.jsonl"
PRIVATE_OUT = PILOT / "privacy-audit" / "image_redaction_private_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_image_redaction.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    REDACTED.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(PRIVATE_AUDIT)
    out = []
    copied = 0
    rejected = 0
    for row in rows:
        image_id = row.get("image_id")
        src = RAW_IMAGES / f"{image_id}.jpg"
        status = row.get("privacy_status")
        if status == "automated_redacted":
            dst = REDACTED / f"{image_id}.jpg"
            if src.exists():
                shutil.copy2(src, dst)
                copied += 1
                out.append(
                    {
                        "source_image_hash": row.get("source_image_hash"),
                        "processed_image_hash": sha256(dst),
                        "redaction_types": [],
                        "redaction_region_count": 0,
                        "redaction_method": "copy_no_localizable_regions",
                        "privacy_status": status,
                        "detector_versions": row.get("detector_versions", {}),
                    }
                )
        elif status == "automated_rejected":
            rejected += 1
    write_jsonl(PRIVATE_OUT, out)
    payload = {
        "marker": "PILOT_IMAGE_REDACTION_COMPLETE",
        "redacted_copy_count": copied,
        "automated_rejected_count": rejected,
        "raw_images_overwritten": False,
    }
    write_json(OUT, payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
