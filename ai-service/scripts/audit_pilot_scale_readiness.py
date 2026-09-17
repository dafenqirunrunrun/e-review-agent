import json

from realworld_data_policy import ROOT, write_json


OUT = ROOT / "data" / "real_world" / "audit" / "pilot_scale_readiness.json"
REPORT = ROOT / "docs" / "161_v1619_pilot_scale_readiness.md"


def load(name: str) -> dict:
    return json.loads((ROOT / "data" / "real_world" / "audit" / name).read_text(encoding="utf-8"))


def main() -> int:
    pilot = load("private_pilot_status.json")
    retry = load("pilot_image_download_retry.json")
    privacy = load("pilot_image_privacy_audit.json")
    eligibility = load("pilot_vlm_eligibility.json")
    vlm = load("realworld_vlm_private_pilot.json")
    taxonomy = load("pilot_taxonomy_mapping_quality.json")
    duplicate = load("pilot_duplicate_audit.json")
    isolation = json.loads((ROOT / "data" / "multimodal" / "audit" / "external_test_isolation_audit.json").read_text(encoding="utf-8"))
    checks = {
        "text_pilot_count>=300": pilot.get("text_pilot_count", 0) >= 300,
        "valid_multimodal_records>=20": pilot.get("multimodal_pilot_count", 0) >= 20,
        "valid_images>=20": retry.get("valid_image_count", 0) >= 20,
        "image_success_rate>=0.80": retry.get("final_download_success_rate", 0) >= 0.80,
        "vlm_inference_count>=5": vlm.get("real_vlm_inference_count", 0) >= 5,
        "REALWORLD_VLM_PILOT_PASS": vlm.get("marker") == "REALWORLD_VLM_PILOT_PASS",
        "automated_uncertain_ratio<=0.30": (privacy.get("automated_uncertain", 0) / max(privacy.get("image_count", 1), 1)) <= 0.30,
        "privacy_text_leak_count=0": vlm.get("privacy_text_leak_count", 0) == 0,
        "exact_duplicate_audit_complete": duplicate.get("marker") == "PILOT_DUPLICATE_AUDIT_COMPLETE",
        "perceptual_duplicate_audit_complete": duplicate.get("marker") == "PILOT_DUPLICATE_AUDIT_COMPLETE",
        "adjusted_mappable_rate>=0.70": taxonomy.get("adjusted_mappable_rate", 0) >= 0.70,
        "forced_mapping_count=0": taxonomy.get("forced_mapping_count") == 0,
        "default_mapping_count=0": taxonomy.get("default_mapping_count") == 0,
        "EXTERNAL_TEST_ISOLATION_AUDIT_PASS": isolation.get("marker") == "EXTERNAL_TEST_ISOLATION_AUDIT_PASS",
        "pilot_not_external_or_sft": not pilot.get("external_test") and not pilot.get("sft"),
    }
    unmet = [name for name, ok in checks.items() if not ok]
    marker = "REALWORLD_PILOT_READY_FOR_SCALE" if not unmet else "REALWORLD_PILOT_NOT_READY_FOR_SCALE"
    payload = {
        "marker": marker,
        "checks": checks,
        "unmet_requirements": unmet,
        "scope": "private_pilot_scale_only_not_external_test_not_training",
    }
    write_json(OUT, payload)
    REPORT.write_text(
        f"""# v1.6.1.9 Pilot Scale Readiness

## Conclusion

`{marker}`

READY would only mean permission to expand private Pilot scale. It would not
authorize formal external test, model training, public release, or a release tag.

## Unmet Requirements

{chr(10).join(f'- {item}' for item in unmet) if unmet else '- none'}
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
