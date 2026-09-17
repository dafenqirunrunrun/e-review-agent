import json

from realworld_data_policy import REAL_DATA_DIR, blocked_result, ensure_private_dirs, write_json


OUT = REAL_DATA_DIR / "audit-cache" / "image_redaction_status.json"


def main() -> int:
    ensure_private_dirs()
    result = blocked_result(
        "REAL_IMAGE_REDACTION_MANUAL_REVIEW_REQUIRED",
        "automatic image redaction is not enabled; privacy-cleared or manually redacted images must be placed outside Git",
        private_processed_image_dir=str(REAL_DATA_DIR / "processed-images"),
    )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
