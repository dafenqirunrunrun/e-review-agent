import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_dataset_role_freeze.json"
DOC = ROOT / "docs" / "166_v16111_pilot_dataset_role_freeze.md"


def main():
    roles = [
        {
            "source_id": "amazon_reviews_2023",
            "approved_role": "ecommerce compatibility corpus; risk candidate discovery only",
            "prohibited_role": "not a labeled risk benchmark; not formal external test; not training data; not redistributable",
            "taxonomy_fit": "ecommerce product-review source with unverified preliminary mapping",
            "label_reliability": "heuristic_candidate_status; unverified",
            "external_evaluation_allowed": False,
            "training_allowed": False,
            "redistribution_allowed": False,
        },
        {
            "source_id": "asap_chinese_reviews",
            "approved_role": "Chinese expression and sentiment auxiliary corpus",
            "prohibited_role": "excluded from ecommerce risk taxonomy denominator; not multimodal; not formal risk benchmark",
            "taxonomy_fit": "auxiliary language source only",
            "label_reliability": "unverified",
            "external_evaluation_allowed": False,
            "training_allowed": False,
            "redistribution_allowed": False,
        },
    ]
    report = {
        "marker": "PILOT_DATASET_ROLES_FROZEN",
        "sources": roles,
        "AUTHORIZED_REAL_DATA_REQUIRED_FOR_FORMAL_EVALUATION": True,
        "FORMAL_REALWORLD_DATA_RIGHTS_READY": False,
        "FORMAL_ANNOTATION_RELIABILITY_READY": False,
        "SFT_DATA_READY": False,
        "VLM_SFT_DATA_READY": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.1.11 Pilot Dataset Role Freeze\n\n"
        "Status: `PILOT_DATASET_ROLES_FROZEN`\n\n"
        "Amazon Reviews 2023 is frozen as an ecommerce compatibility corpus and risk-candidate discovery source only. It is not a labeled risk benchmark.\n\n"
        "ASAP Chinese Reviews is frozen as a Chinese expression and sentiment auxiliary corpus. It is excluded from the ecommerce risk taxonomy denominator, is not multimodal, and is not a formal risk benchmark.\n\n"
        "Formal evaluation still requires explicitly authorized and annotatable ecommerce review data.\n",
        encoding="utf-8",
    )
    print(report["marker"])


if __name__ == "__main__":
    main()
