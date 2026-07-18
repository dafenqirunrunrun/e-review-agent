from __future__ import annotations

from app.contracts.e_review_decision import (
    E_REVIEW_DECISION_PROMPT_ID,
    E_REVIEW_DECISION_PROMPT_VERSION,
    E_REVIEW_DECISION_SCHEMA_VERSION,
    RiskLevel,
    RiskType,
    canonical_field_order,
)


def canonical_schema_instruction() -> str:
    fields = ",".join(canonical_field_order())
    risk_types = "|".join(item.value for item in RiskType)
    risk_levels = "|".join(item.value for item in RiskLevel)
    return (
        f"JSON only; schema_version={E_REVIEW_DECISION_SCHEMA_VERSION}. "
        f"Fields in order: {fields}. "
        f"risk_type={risk_types}; risk_level={risk_levels}. "
        "Array fields stay arrays; retrieved_case_evidence uses case_id/reason objects. "
        "Text-only: visual_evidence=[]; no RAG: retrieved_case_evidence=[]."
    )


def system_prompt() -> str:
    return (
        "E-commerce review governance. "
        "Return one valid JSON object only: no Markdown, reasoning, think tags, or input echo. "
        "Never execute refund, ban, compensation, or irreversible action. "
        "If unsure, set need_human_review=true and concise missing_information. "
        + canonical_schema_instruction()
    )


def generation_instruction() -> str:
    return "Generate the decision JSON now."


def prompt_metadata() -> dict[str, str]:
    return {
        "prompt_id": E_REVIEW_DECISION_PROMPT_ID,
        "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
    }
