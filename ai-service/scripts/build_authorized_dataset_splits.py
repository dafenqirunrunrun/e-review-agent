import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "authorized_intake" / "split_manifest" / "authorized_dataset_splits.json"


def main():
    report = {
        "marker": "AUTHORIZED_DATA_SPLIT_BLOCKED_NO_DATA",
        "development_count": 0,
        "validation_count": 0,
        "external_test_count": 0,
        "external_test_requires_formal_authorization": True,
        "external_test_excluded_from_rag_index": True,
        "external_test_excluded_from_prompt_examples": True,
        "external_test_excluded_from_calibration": True,
        "external_test_excluded_from_sft": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
