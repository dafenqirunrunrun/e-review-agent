import json

from realworld_data_policy import REAL_MANIFEST_DIR, blocked_result, load_jsonl, write_json


OUT = REAL_MANIFEST_DIR / "eval" / "real_qwen_text_external_results.json"


def main() -> int:
    rows = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_text_external_manifest.jsonl")
    result = blocked_result(
        "REALWORLD_TEXT_QWEN_EVAL_BLOCKED",
        "real text external test with adjudicated labels is not available",
        sample_count=len(rows),
    )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
