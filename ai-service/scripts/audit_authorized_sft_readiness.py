import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "authorized_intake" / "audit" / "authorized_sft_readiness.json"


def main():
    report = {
        "marker": "AUTHORIZED_SFT_DATA_NOT_READY",
        "AUTHORIZED_SFT_DATA_READY": False,
        "AUTHORIZED_VLM_SFT_DATA_READY": False,
        "llm_requirements": {
            "allowed_model_training": False,
            "llm_sft": False,
            "trainable_samples_at_least_1000": False,
            "external_test_overlap_zero": True,
            "annotation_reliability_pass": False,
        },
        "vlm_requirements": {
            "image_model_training_allowed": False,
            "vlm_sft": False,
            "real_multimodal_training_samples_at_least_500": False,
            "image_privacy_review_complete": False,
            "visual_labels_reliable": False,
            "external_test_isolation_pass": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("AUTHORIZED_SFT_DATA_NOT_READY")
    print("AUTHORIZED_VLM_SFT_DATA_NOT_READY")


if __name__ == "__main__":
    main()
