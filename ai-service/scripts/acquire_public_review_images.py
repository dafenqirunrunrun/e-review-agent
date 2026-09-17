import argparse
import json

from realworld_data_policy import REAL_DATA_DIR, blocked_result, ensure_private_dirs, source_by_id, write_json


OUT = REAL_DATA_DIR / "audit-cache" / "real_review_image_acquisition_status.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()
    ensure_private_dirs()
    source = source_by_id(args.source_id)
    if source is None or source.get("contains_images") is not True:
        result = blocked_result("REAL_MULTIMODAL_DATA_SOURCE_NOT_AVAILABLE", "approved multimodal source is not available", source_id=args.source_id)
    elif source.get("image_download_allowed") is not True:
        result = blocked_result("REAL_IMAGE_DOWNLOAD_NOT_ALLOWED", "source does not explicitly allow image download", source_id=args.source_id)
    else:
        result = blocked_result(
            "REAL_IMAGE_ACQUISITION_MANUAL_STEP_REQUIRED",
            "automatic image download is disabled until source terms and redaction workflow are confirmed",
            source_id=args.source_id,
            private_raw_image_dir=str(REAL_DATA_DIR / "raw-images"),
        )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
