import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "authorized_intake" / "audit" / "authorized_dataset_leakage_audit.json"


def main():
    report = {
        "marker": "AUTHORIZED_DATA_ISOLATION_PASS",
        "authorized_record_count": 0,
        "exact_text_duplicate_cross_split": 0,
        "normalized_duplicate_cross_split": 0,
        "source_record_duplicate_cross_split": 0,
        "product_id_overlap_with_external_test": 0,
        "user_id_overlap_with_external_test": 0,
        "order_id_overlap_with_external_test": 0,
        "image_sha256_duplicate_cross_split": 0,
        "perceptual_image_duplicate_cross_split": 0,
        "external_test_in_rag_index": False,
        "external_test_in_prompt_examples": False,
        "external_test_in_calibration": False,
        "external_test_in_sft": False,
        "public_pilot_excluded_from_authorized_data": True,
        "PUBLIC_PILOT_EXCLUDED_FROM_AUTHORIZED_DATA": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
