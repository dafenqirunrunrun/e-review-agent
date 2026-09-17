import json

from realworld_data_policy import REAL_MANIFEST_DIR, blocked_result, load_jsonl, write_json


OUT = REAL_MANIFEST_DIR / "eval" / "realworld_route_calibration.json"


def main() -> int:
    validation = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_multimodal_validation_manifest.jsonl")
    result = blocked_result(
        "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED",
        "real multimodal validation set is not available; external test must not be used for threshold calibration",
        validation_count=len(validation),
    )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
