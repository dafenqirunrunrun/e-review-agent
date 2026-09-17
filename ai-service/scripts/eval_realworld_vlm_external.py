import json

from realworld_data_policy import REAL_MANIFEST_DIR, blocked_result, load_jsonl, write_json


OUT = REAL_MANIFEST_DIR / "eval" / "real_vlm_external_results.json"


def main() -> int:
    rows = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_multimodal_external_test.jsonl")
    result = blocked_result(
        "REALWORLD_VLM_EVAL_BLOCKED",
        "real multimodal external test requires at least 40 privacy-cleared image-text samples",
        sample_count=len(rows),
    )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
