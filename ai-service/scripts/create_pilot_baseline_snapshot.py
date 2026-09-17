import json
from datetime import datetime, timezone
from pathlib import Path

from realworld_data_policy import ROOT, load_jsonl, write_json


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_baseline_snapshot.json"


def main() -> int:
    status = json.loads((ROOT / "data" / "real_world" / "audit" / "private_pilot_status.json").read_text(encoding="utf-8"))
    manifest = load_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl")
    image_manifest = load_jsonl(PILOT / "manifests" / "image_private_manifest.jsonl")
    payload = {
        "marker": "PILOT_BASELINE_SNAPSHOT_COMPLETE",
        "source_ids": sorted({row.get("source_id") for row in manifest if row.get("source_id")}),
        "sample_id_hashes": [row.get("sample_id_hash") for row in manifest],
        "text_sample_count": status.get("text_pilot_count", len(manifest)),
        "multimodal_record_count": status.get("multimodal_pilot_count", 0),
        "expected_image_count": status.get("image_download_attempted", len(image_manifest)),
        "downloaded_image_count": status.get("image_download_success", 0),
        "failed_image_count": status.get("image_download_failed", 0),
        "skipped_image_count": status.get("image_download_skipped", 0),
        "text_privacy_statistics": status.get("privacy_counts", {}),
        "image_privacy_statistics": {
            "private_manifest_count": len(image_manifest),
            "downloaded": sum(1 for row in image_manifest if row.get("bytes")),
            "skipped": sum(1 for row in image_manifest if row.get("download_status") == "skipped_network_disabled"),
        },
        "taxonomy_statistics": {
            "raw_mappable_rate": status.get("taxonomy_mapped_ratio"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "processing_version": "v1.6.1.9",
    }
    write_json(OUT, payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
