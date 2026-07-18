from __future__ import annotations

import json
from enum import Enum
from typing import Any, ClassVar, List

from pydantic import BaseModel, ConfigDict, Field, ValidationError


E_REVIEW_DECISION_SCHEMA_NAME = "e_review_decision"
E_REVIEW_DECISION_SCHEMA_VERSION = "v2.0.0"
E_REVIEW_DECISION_PROMPT_ID = "e_review_decision"
E_REVIEW_DECISION_PROMPT_VERSION = "v2.1.0"


class RiskType(str, Enum):
    normal_review = "normal_review"
    negative_review = "negative_review"
    after_sales_risk = "after_sales_risk"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RetrievedCaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: str = Field(default=E_REVIEW_DECISION_SCHEMA_VERSION)
    risk_type: RiskType
    risk_level: RiskLevel
    text_evidence: List[str]
    visual_evidence: List[str] = Field(default_factory=list)
    retrieved_case_evidence: List[RetrievedCaseEvidence] = Field(default_factory=list)
    need_human_review: bool
    route_reason: str = Field(min_length=1)
    missing_information: List[str]
    unsupported_claims: List[str]

    canonical_field_order: ClassVar[list[str]] = [
        "schema_version",
        "risk_type",
        "risk_level",
        "text_evidence",
        "visual_evidence",
        "retrieved_case_evidence",
        "need_human_review",
        "route_reason",
        "missing_information",
        "unsupported_claims",
    ]


def canonical_field_order() -> list[str]:
    return list(EReviewDecision.canonical_field_order)


def canonical_schema_dict() -> dict[str, Any]:
    schema = EReviewDecision.model_json_schema()
    schema["$id"] = f"{E_REVIEW_DECISION_SCHEMA_NAME}:{E_REVIEW_DECISION_SCHEMA_VERSION}"
    schema["x-schema-name"] = E_REVIEW_DECISION_SCHEMA_NAME
    schema["x-schema-version"] = E_REVIEW_DECISION_SCHEMA_VERSION
    schema["x-canonical-field-order"] = canonical_field_order()
    return schema


def canonical_schema_json() -> str:
    return json.dumps(canonical_schema_dict(), ensure_ascii=False, indent=2) + "\n"


def validate_canonical_decision(data: dict[str, Any]) -> EReviewDecision:
    return EReviewDecision.model_validate(data)


def is_canonical_decision(data: dict[str, Any]) -> bool:
    try:
        validate_canonical_decision(data)
        return True
    except ValidationError:
        return False


def canonical_serialize(decision: EReviewDecision | dict[str, Any]) -> str:
    if isinstance(decision, dict):
        decision = validate_canonical_decision(decision)
    payload = decision.model_dump(mode="json")
    ordered = {key: payload[key] for key in canonical_field_order()}
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def canonical_contract_summary() -> dict[str, Any]:
    schema = canonical_schema_dict()
    properties = schema.get("properties", {})
    return {
        "schema_name": E_REVIEW_DECISION_SCHEMA_NAME,
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "required_fields": list(schema.get("required", [])),
        "field_order": canonical_field_order(),
        "risk_type_enum": [item.value for item in RiskType],
        "risk_level_enum": [item.value for item in RiskLevel],
        "properties": sorted(properties),
    }


def empty_text_decision(risk_type: RiskType, risk_level: RiskLevel, need_human_review: bool, reason: str) -> EReviewDecision:
    return EReviewDecision(
        risk_type=risk_type,
        risk_level=risk_level,
        text_evidence=[],
        visual_evidence=[],
        retrieved_case_evidence=[],
        need_human_review=need_human_review,
        route_reason=reason,
        missing_information=[],
        unsupported_claims=[],
    )
