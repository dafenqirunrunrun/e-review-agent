from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.contracts.e_review_decision import (
    E_REVIEW_DECISION_SCHEMA_NAME,
    E_REVIEW_DECISION_SCHEMA_VERSION,
    EReviewDecision,
    RiskLevel,
    RiskType,
    canonical_contract_summary,
    validate_canonical_decision,
)

# Deprecated compatibility export. The source of truth is app.contracts.e_review_decision.
_SUMMARY = canonical_contract_summary()
E_REVIEW_DECISION_SCHEMA_CANONICAL = {
    "schema_name": E_REVIEW_DECISION_SCHEMA_NAME,
    "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
    "required_fields": _SUMMARY["required_fields"],
    "optional_fields": [],
    "field_types": {},
    "enum_values": {
        "risk_type": [item.value for item in RiskType],
        "risk_level": [item.value for item in RiskLevel],
    },
    "aliases": {
        "evidence": "text_evidence",
        "human_review_required": "need_human_review",
        "riskType": "risk_type",
        "riskLevel": "risk_level",
    },
    "nullable_fields": [],
    "extra_field_policy": "forbid",
    "evidence_item_shape": "see app.contracts.e_review_decision.RetrievedCaseEvidence",
}


FAILURE_REASONS = {
    "json_object_not_found",
    "json_syntax_error",
    "markdown_wrapper_present",
    "think_tag_present",
    "extra_text_before_json",
    "extra_text_after_json",
    "missing_required_field",
    "unknown_field",
    "wrong_field_alias",
    "enum_value_invalid",
    "enum_case_mismatch",
    "enum_language_mismatch",
    "wrong_scalar_type",
    "boolean_as_string",
    "number_as_string",
    "null_not_allowed",
    "list_expected",
    "object_expected",
    "evidence_item_shape_invalid",
    "nested_schema_mismatch",
    "empty_required_list",
    "unsupported_schema_version",
    "parser_bug",
    "evaluation_mapping_bug",
    "unknown_failure",
}


@dataclass(frozen=True)
class SchemaFailureAnalysis:
    parsed_json: bool
    raw_schema_valid: bool
    reasons: list[str]
    missing_fields: list[str]
    unknown_fields: list[str]
    invalid_enums: dict[str, Any]
    wrong_types: dict[str, str]
    alias_mismatches: dict[str, str]


def extract_json_object(raw_text: str) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    text = raw_text or ""
    stripped = text.strip()
    if re.search(r"```", stripped):
        reasons.append("markdown_wrapper_present")
    if re.search(r"<think>|</think>", stripped, flags=re.IGNORECASE):
        reasons.append("think_tag_present")
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        reasons.append("json_object_not_found")
        return None, reasons
    if stripped[:start].strip():
        reasons.append("extra_text_before_json")
    if stripped[end + 1 :].strip():
        reasons.append("extra_text_after_json")
    try:
        value = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        reasons.append("json_syntax_error")
        return None, reasons
    if not isinstance(value, dict):
        reasons.append("object_expected")
        return None, reasons
    return value, reasons


def analyze_schema_failure(raw: str | dict[str, Any]) -> SchemaFailureAnalysis:
    if isinstance(raw, str):
        obj, reasons = extract_json_object(raw)
    else:
        obj, reasons = raw, []
    if obj is None:
        return SchemaFailureAnalysis(False, False, sorted(set(reasons)), [], [], {}, {}, {})

    required = set(E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"])
    allowed = set(EReviewDecision.model_json_schema().get("properties", {}))
    aliases = E_REVIEW_DECISION_SCHEMA_CANONICAL["aliases"]
    enum_values = E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"]

    missing = sorted(required - set(obj))
    unknown = sorted(set(obj) - allowed)
    alias_mismatches = {key: aliases[key] for key in obj if key in aliases}
    invalid_enums: dict[str, Any] = {}
    wrong_types: dict[str, str] = {}

    for field, allowed_values in enum_values.items():
        if field in obj:
            value = obj[field]
            if not isinstance(value, str):
                wrong_types[field] = type(value).__name__
            elif value not in allowed_values:
                invalid_enums[field] = value
                if value.lower() in allowed_values:
                    reasons.append("enum_case_mismatch")
                elif re.search(r"[\u4e00-\u9fff]", value):
                    reasons.append("enum_language_mismatch")
                else:
                    reasons.append("enum_value_invalid")

    bool_value = obj.get("need_human_review")
    if "need_human_review" in obj and not isinstance(bool_value, bool):
        wrong_types["need_human_review"] = type(bool_value).__name__
        if isinstance(bool_value, str) and bool_value.lower() in {"true", "false"}:
            reasons.append("boolean_as_string")
        else:
            reasons.append("wrong_scalar_type")

    for field in ["text_evidence", "visual_evidence", "retrieved_case_evidence", "missing_information", "unsupported_claims"]:
        if field in obj:
            if obj[field] is None:
                reasons.append("null_not_allowed")
                wrong_types[field] = "NoneType"
            elif not isinstance(obj[field], list):
                reasons.append("list_expected")
                wrong_types[field] = type(obj[field]).__name__
            elif field in {"text_evidence", "visual_evidence", "missing_information", "unsupported_claims"} and any(not isinstance(item, str) for item in obj[field]):
                reasons.append("evidence_item_shape_invalid")
                wrong_types[field] = "list[non-string]"

    if "route_reason" in obj and not isinstance(obj["route_reason"], str):
        wrong_types["route_reason"] = type(obj["route_reason"]).__name__
        reasons.append("wrong_scalar_type")

    if missing:
        reasons.append("missing_required_field")
    if unknown:
        reasons.append("unknown_field")
    if alias_mismatches:
        reasons.append("wrong_field_alias")
    if not reasons and (missing or unknown or invalid_enums or wrong_types):
        reasons.append("unknown_failure")

    raw_valid = False
    if not missing and not unknown and not invalid_enums and not wrong_types and not alias_mismatches:
        try:
            validate_canonical_decision(obj)
            raw_valid = True
        except Exception:
            raw_valid = False
    return SchemaFailureAnalysis(
        parsed_json=True,
        raw_schema_valid=raw_valid,
        reasons=sorted(set(reasons)),
        missing_fields=missing,
        unknown_fields=unknown,
        invalid_enums=invalid_enums,
        wrong_types=wrong_types,
        alias_mismatches=alias_mismatches,
    )


def repair_to_canonical(raw: dict[str, Any] | None, parse_error: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.contracts.e_review_decision_migration import contract_normalization

    result = contract_normalization(raw or {})
    operations = {
        "field_overwrites": result.migration_operations,
        "default_injections": [],
        "risk_type_overwritten": False,
        "risk_level_overwritten": False,
        "need_human_review_overwritten": False,
        "evidence_overwritten": False,
        "semantic_field_changed": result.semantic_field_changed,
        "warnings": result.warnings,
    }
    return result.normalized_prediction or {}, operations
