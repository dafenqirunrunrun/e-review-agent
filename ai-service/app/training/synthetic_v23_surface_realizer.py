from __future__ import annotations

from dataclasses import dataclass


SYNTHETIC_V23_SURFACE_REALIZER_VERSION = "synthetic_v23_surface_realizer_v1.0.0"

REALIZER_IDS = [
    "concise",
    "colloquial",
    "narrative",
    "contrastive",
    "negation_heavy",
    "temporal",
    "causal",
    "comparative",
    "uncertain",
    "multi_clause",
    "customer_service_context",
    "typo_light",
]


@dataclass(frozen=True)
class ScenarioSpec:
    product: str
    base_signal: str
    boundary_signal: str
    severity_signal: str
    evidence_signal: str
    risk_type: str
    risk_level: str
    need_human_review: bool


def render_surface(spec: ScenarioSpec, realizer_id: str, sample_index: int) -> str:
    if realizer_id == "concise":
        return f"{spec.product}: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "colloquial":
        return f"Used {spec.product}; {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "narrative":
        return f"Opened {spec.product}: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "contrastive":
        return f"Not mood alone: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "negation_heavy":
        return f"This is not a random complaint. {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "temporal":
        return f"Delivery: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "causal":
        return f"Because {spec.evidence_signal}; {spec.base_signal}."
    if realizer_id == "comparative":
        return f"Compared page: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "uncertain":
        return f"May need staff: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "multi_clause":
        return f"{spec.product}; {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "customer_service_context":
        return f"Support: {spec.base_signal}; {spec.evidence_signal}."
    if realizer_id == "typo_light":
        return f"Short: {spec.base_signal}; Evdence: {spec.evidence_signal}."
    return f"{spec.product}: {spec.base_signal}. {spec.boundary_signal}. {spec.evidence_signal}. sample {sample_index}"
