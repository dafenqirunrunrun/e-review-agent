from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.contracts.e_review_decision import (
    E_REVIEW_DECISION_SCHEMA_VERSION,
    EReviewDecision,
    RiskLevel,
    RiskType,
    validate_canonical_decision,
)


FIELD_ALIASES = {
    "riskType": "risk_type",
    "riskLevel": "risk_level",
    "human_review_required": "need_human_review",
    "needHumanReview": "need_human_review",
    "evidence": "text_evidence",
}

SEMANTIC_FIELDS = {"risk_type", "risk_level", "need_human_review"}


@dataclass(frozen=True)
class RawJsonExtractionResult:
    extraction_success: bool
    extracted_json: dict[str, Any] | None
    syntax_operations: list[str] = field(default_factory=list)
    failure_reason: str | None = None


@dataclass(frozen=True)
class ContractNormalizationResult:
    normalization_success: bool
    normalized_prediction: dict[str, Any] | None
    migration_operations: list[str] = field(default_factory=list)
    semantic_field_changed: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OperationalFallbackResult:
    operational_result: dict[str, Any]
    prediction_source: str
    fallback_reason: str


def raw_json_extraction(raw_text: str) -> RawJsonExtractionResult:
    text = (raw_text or "").strip("\ufeff \t\r\n")
    operations: list[str] = []
    if re.search(r"<think>.*?</think>", text, flags=re.IGNORECASE | re.DOTALL):
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        operations.append("think_block_removed")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
        operations.append("markdown_fence_removed")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return RawJsonExtractionResult(False, None, operations, "json_object_not_found")
    if text[:start].strip():
        operations.append("extra_text_before_json_removed")
    if text[end + 1 :].strip():
        operations.append("extra_text_after_json_removed")
    candidate = text[start : end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        if cleaned != candidate:
            try:
                value = json.loads(cleaned)
                operations.append("trailing_comma_removed")
            except json.JSONDecodeError:
                return RawJsonExtractionResult(False, None, operations, f"json_syntax_error:{exc.msg}")
        else:
            return RawJsonExtractionResult(False, None, operations, f"json_syntax_error:{exc.msg}")
    if not isinstance(value, dict):
        return RawJsonExtractionResult(False, None, operations, "json_object_not_found")
    return RawJsonExtractionResult(True, value, operations)


def contract_normalization(data: dict[str, Any]) -> ContractNormalizationResult:
    operations: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = {}
    semantic_changed = False

    for key, value in data.items():
        target_key = FIELD_ALIASES.get(key, key)
        if target_key != key:
            operations.append(f"field_alias:{key}->{target_key}")
        normalized[target_key] = value

    if "schema_version" not in normalized:
        normalized["schema_version"] = E_REVIEW_DECISION_SCHEMA_VERSION
        operations.append("schema_version_added")

    for field, enum_cls in [("risk_type", RiskType), ("risk_level", RiskLevel)]:
        if field in normalized and isinstance(normalized[field], str):
            original = normalized[field]
            lowered = original.lower()
            allowed = {item.value for item in enum_cls}
            if original not in allowed and lowered in allowed:
                normalized[field] = lowered
                operations.append(f"enum_case_normalized:{field}")
                # Case-only enum normalization is not semantic drift.
            elif original not in allowed:
                warnings.append(f"invalid_enum:{field}:{original}")

    if "need_human_review" in normalized and isinstance(normalized["need_human_review"], str):
        original = normalized["need_human_review"]
        if original.lower() in {"true", "false"}:
            normalized["need_human_review"] = original.lower() == "true"
            operations.append("boolean_string_normalized:need_human_review")
        else:
            warnings.append(f"invalid_boolean:need_human_review:{original}")

    for field in ["text_evidence", "visual_evidence", "missing_information", "unsupported_claims"]:
        if field in normalized and isinstance(normalized[field], str):
            normalized[field] = [normalized[field]]
            operations.append(f"string_to_list:{field}")

    if "retrieved_case_evidence" in normalized:
        items = normalized["retrieved_case_evidence"]
        if isinstance(items, list):
            converted = []
            changed = False
            for item in items:
                if isinstance(item, str):
                    converted.append({"case_id": item, "reason": "legacy string case evidence"})
                    changed = True
                else:
                    converted.append(item)
            if changed:
                normalized["retrieved_case_evidence"] = converted
                operations.append("retrieved_case_string_to_object")

    try:
        validate_canonical_decision(normalized)
        success = True
    except ValidationError as exc:
        warnings.append(f"canonical_validation_failed:{len(exc.errors())}")
        success = False

    for field in SEMANTIC_FIELDS:
        if field in data and field in normalized and data[field] != normalized[field]:
            if not (isinstance(data[field], str) and isinstance(normalized[field], str) and data[field].lower() == normalized[field]):
                if not (
                    field == "need_human_review"
                    and isinstance(data[field], str)
                    and data[field].lower() in {"true", "false"}
                    and normalized[field] == (data[field].lower() == "true")
                ):
                    semantic_changed = True

    return ContractNormalizationResult(success, normalized if success else normalized, operations, semantic_changed, warnings)


def operational_safety_fallback(reason: str) -> OperationalFallbackResult:
    result = {
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "risk_type": "normal_review",
        "risk_level": "low",
        "text_evidence": [],
        "visual_evidence": [],
        "retrieved_case_evidence": [],
        "need_human_review": True,
        "route_reason": f"Model output could not be verified: {reason}",
        "missing_information": ["schema_validation_failed"],
        "unsupported_claims": [],
        "prediction_source": "operational_safety_fallback",
    }
    return OperationalFallbackResult(result, "operational_safety_fallback", reason)


def field_provenance_for(decision: dict[str, Any], source: str, operations: list[str]) -> dict[str, dict[str, Any]]:
    provenance = {}
    normalized_fields = {op.split(":", 1)[1].split("->")[-1] for op in operations if op.startswith("field_alias:")}
    for field in EReviewDecision.canonical_field_order:
        provenance[field] = {
            "source": source,
            "normalized": field in normalized_fields or any(op.endswith(f":{field}") for op in operations),
            "defaulted": False,
        }
    return provenance


def process_model_output(raw_output: str) -> dict[str, Any]:
    extraction = raw_json_extraction(raw_output)
    if not extraction.extraction_success or extraction.extracted_json is None:
        fallback = operational_safety_fallback(extraction.failure_reason or "raw_json_extraction_failed")
        return {
            "raw_json_extraction": extraction,
            "contract_normalization": None,
            "operational_result": fallback.operational_result,
            "prediction_eligible": False,
            "abstained": True,
            "field_provenance": field_provenance_for(fallback.operational_result, "operational_safety_fallback", []),
        }
    normalization = contract_normalization(extraction.extracted_json)
    if normalization.normalization_success and not normalization.semantic_field_changed:
        source = "contract_normalization" if normalization.migration_operations else "raw_model"
        return {
            "raw_json_extraction": extraction,
            "contract_normalization": normalization,
            "operational_result": normalization.normalized_prediction,
            "prediction_eligible": True,
            "abstained": False,
            "field_provenance": field_provenance_for(normalization.normalized_prediction or {}, source, normalization.migration_operations),
        }
    fallback = operational_safety_fallback(";".join(normalization.warnings) or "contract_normalization_failed")
    return {
        "raw_json_extraction": extraction,
        "contract_normalization": normalization,
        "operational_result": fallback.operational_result,
        "prediction_eligible": False,
        "abstained": True,
        "field_provenance": field_provenance_for(fallback.operational_result, "operational_safety_fallback", []),
    }
