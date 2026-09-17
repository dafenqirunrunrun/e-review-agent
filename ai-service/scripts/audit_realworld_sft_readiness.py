import json

from realworld_data_policy import REAL_MANIFEST_DIR, blocked_result, load_jsonl, write_json


OUT = REAL_MANIFEST_DIR / "audit" / "sft_data_readiness.json"


def main() -> int:
    train = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_text_development_manifest.jsonl")
    external = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_text_external_manifest.jsonl")
    multimodal = load_jsonl(REAL_MANIFEST_DIR / "split_manifest" / "real_multimodal_development_manifest.jsonl")
    result = blocked_result(
        "SFT_DATA_NOT_READY",
        "compliant real-world train/dev data, annotation reliability, and external-test isolation are not complete",
        train_count=len(train),
        external_count=len(external),
        multimodal_train_count=len(multimodal),
        vlm_sft_status="VLM_SFT_DATA_NOT_READY",
    )
    write_json(OUT, result)
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    print(result["vlm_sft_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
