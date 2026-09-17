import json
from pathlib import Path

from realworld_data_policy import ROOT, write_json


ELIGIBILITY = ROOT / "data" / "real_world" / "audit" / "pilot_vlm_eligibility.json"
OUT = ROOT / "data" / "real_world" / "audit" / "realworld_vlm_private_pilot.json"
REPORT = ROOT / "docs" / "159_v1619_realworld_vlm_private_pilot.md"


def main() -> int:
    eligibility = json.loads(ELIGIBILITY.read_text(encoding="utf-8"))
    eligible = eligibility.get("eligible_record_count", 0)
    if eligible < 5:
        payload = {
            "marker": "REALWORLD_VLM_PILOT_BLOCKED_INSUFFICIENT_SAFE_IMAGES",
            "eligible_record_count": eligible,
            "eligible_image_count": eligibility.get("eligible_image_count", 0),
            "real_vlm_inference_count": 0,
            "real_vlm_success_rate": 0.0,
            "raw_schema_valid_rate": 0.0,
            "final_schema_valid_rate": 0.0,
            "fallback_rate": 0.0,
            "oom_count": 0,
            "privacy_text_leak_count": 0,
            "unsupported_business_action_count": 0,
            "obvious_invalid_visual_claim_count": 0,
            "avg_generate_ms": None,
            "p95_generate_ms": None,
            "consistency_distribution": {},
            "reason": "automated privacy screening did not produce at least five safe images",
        }
    else:
        payload = {
            "marker": "REALWORLD_VLM_PILOT_BLOCKED",
            "eligible_record_count": eligible,
            "real_vlm_inference_count": 0,
            "reason": "real VLM execution not started by this conservative script",
        }
    write_json(OUT, payload)
    REPORT.write_text(
        f"""# v1.6.1.9 Real-World VLM Private Pilot

## Conclusion

`{payload['marker']}`

No VLM inference was executed because fewer than five images passed automated
privacy eligibility. Automated privacy screening is not human review, and
`automated_uncertain` images are excluded from VLM Pilot.
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
