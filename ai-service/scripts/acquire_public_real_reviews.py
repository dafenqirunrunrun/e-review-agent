import argparse
import json
from pathlib import Path

from realworld_data_policy import REAL_DATA_DIR, blocked_result, ensure_private_dirs, source_by_id, write_json


OUT = REAL_DATA_DIR / "audit-cache" / "real_review_acquisition_status.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()
    ensure_private_dirs()
    source = source_by_id(args.source_id)
    if source is None:
        result = blocked_result("REAL_TEXT_DATA_SOURCE_NOT_AVAILABLE", "source is not approved", source_id=args.source_id)
    else:
        result = blocked_result(
            "REAL_TEXT_ACQUISITION_MANUAL_STEP_REQUIRED",
            "automatic download is disabled until the approved source terms and local storage path are confirmed",
            source_id=args.source_id,
            private_raw_text_dir=str(REAL_DATA_DIR / "raw-text"),
        )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
