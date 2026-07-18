import json
import sys
from pathlib import Path

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.evaluation.schema_failure_analysis import (
    E_REVIEW_DECISION_SCHEMA_CANONICAL,
    analyze_schema_failure,
    repair_to_canonical,
)


def canonical_payload():
    return {
        "risk_type": "after_sales_risk",
        "risk_level": "high",
        "text_evidence": ["broken seal"],
        "retrieved_case_evidence": [],
        "need_human_review": True,
        "route_reason": "high risk after-sales issue",
        "missing_information": [],
        "unsupported_claims": [],
    }


def test_v165_canonical_schema_accepts_complete_payload():
    result = analyze_schema_failure(canonical_payload())
    assert result.parsed_json is True
    assert result.raw_schema_valid is True
    assert result.reasons == []


def test_v165_raw_schema_failure_reports_field_level_reasons():
    result = analyze_schema_failure({"riskType": "after_sales_risk", "risk_level": "HIGH", "evidence": "bad"})
    assert result.raw_schema_valid is False
    assert "missing_required_field" in result.reasons
    assert "wrong_field_alias" in result.reasons
    assert "enum_value_invalid" in result.reasons or "enum_case_mismatch" in result.reasons
    assert "risk_type" in result.missing_fields
    assert result.alias_mismatches["riskType"] == "risk_type"


def test_v165_raw_schema_distinguishes_json_parse_from_schema_validity():
    wrapped = "```json\n{\"synthetic_review_text\":\"copied input\"}\n```\nDone"
    result = analyze_schema_failure(wrapped)
    assert result.parsed_json is True
    assert result.raw_schema_valid is False
    assert "markdown_wrapper_present" in result.reasons
    assert "unknown_field" in result.reasons


def test_v165_compat_repair_no_longer_overwrites_risk_semantics():
    repaired, ops = repair_to_canonical({"risk_type": "product_review_risk", "risk_level": "critical"})
    assert repaired["risk_type"] == "product_review_risk"
    assert repaired["risk_level"] == "critical"
    assert ops["risk_type_overwritten"] is False
    assert ops["risk_level_overwritten"] is False
    assert ops["need_human_review_overwritten"] is False
    assert ops["warnings"]


def test_v165_canonical_schema_has_single_declared_name_and_version():
    assert E_REVIEW_DECISION_SCHEMA_CANONICAL["schema_name"] == "e_review_decision"
    assert E_REVIEW_DECISION_SCHEMA_CANONICAL["schema_version"] == "v2.0.0"
    assert "risk_type" in E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"]
    assert "risk_level" in E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"]


def test_v165_validation_diagnostic_does_not_rerun_or_read_holdout_if_artifact_exists():
    path = Path("data/private_research/audit/v165_validation_diagnostic.json")
    if not path.exists():
        return
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["holdout_read"] is False
    assert result["holdout_rerun_performed"] is False
    assert result["sample_count"] == len(set(result["sample_hashes"]))
