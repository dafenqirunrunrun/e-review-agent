import json
from pathlib import Path

from realworld_data_policy import REAL_MANIFEST_DIR, write_json


ROOT = Path(__file__).resolve().parents[2]
OUT = REAL_MANIFEST_DIR / "audit" / "pilot_taxonomy_coverage.json"
REPORT = ROOT / "docs" / "157_v1617_realworld_pilot_taxonomy_report.md"


def main() -> int:
    result = {
        "marker": "REALWORLD_TAXONOMY_COVERAGE_BLOCKED",
        "coverage_ready": False,
        "pilot_sample_count": 0,
        "directly_mapped_ratio": None,
        "unmapped_ratio": None,
        "multi_risk_ratio": None,
        "insufficient_evidence_ratio": None,
        "emotion_only_ratio": None,
        "taxonomy_gap_categories": [],
        "language_distribution": {},
        "image_text_conflict_ratio": None,
        "irrelevant_image_ratio": None,
        "low_quality_image_ratio": None,
        "blocking_reasons": [
            "REALWORLD_SOURCE_APPROVAL_REQUIRED",
            "no manually approved source",
            "no pilot data may be acquired before user approval",
        ],
    }
    write_json(OUT, result)
    REPORT.write_text(
        """# v1.6.1.7 Real-World Pilot Taxonomy Report

## Conclusion

`REALWORLD_TAXONOMY_COVERAGE_BLOCKED`

No taxonomy coverage statistics were computed because no real-world source has
manual approval and no pilot data exists. This is intentional: pilot samples must
not be treated as external test data or SFT data, and no pilot can start until
`data/real_world/source_manifest/manual_source_approval.yaml` is explicitly
approved by the user.

## Required Next Step

After manual source approval, run the minimal pilot outside Git, store raw text
and images under `D:\\EReviewAgent\\data-private\\realworld-pilot\\`, and commit
only aggregate manifests and audit statistics.
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
