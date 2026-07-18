from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[3]
PROJECT_MODE_CONFIG = ROOT / "data" / "governance" / "project_mode.yaml"


class ProjectMode(str, Enum):
    STRICT_AUTHORIZED_RESEARCH = "strict_authorized_research"
    PRIVATE_NONCOMMERCIAL_RESEARCH = "private_noncommercial_research"
    FORMAL_RELEASE = "formal_release"


@dataclass
class ProjectModePolicy:
    project_mode: ProjectMode
    local_machine_only: bool = True
    noncommercial_only: bool = True
    public_release_allowed: bool = False
    formal_external_benchmark_allowed: bool = False
    synthetic_training_allowed: bool = False
    public_pilot_local_read_only: bool = False
    restricted_data_training_allowed: bool = False


@dataclass
class ActivityDecision:
    allowed: bool
    decision: str
    reason_codes: List[str]
    policy_mode: str
    restrictions: List[str]
    evaluated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_config() -> Dict[str, Any]:
    if not PROJECT_MODE_CONFIG.exists() or yaml is None:
        return {}
    return yaml.safe_load(PROJECT_MODE_CONFIG.read_text(encoding="utf-8")) or {}


def load_project_mode_policy() -> ProjectModePolicy:
    config = _read_config()
    mode = os.getenv("E_REVIEW_PROJECT_MODE") or config.get("project_mode") or ProjectMode.STRICT_AUTHORIZED_RESEARCH.value
    scope = config.get("scope") or {}
    allowed = config.get("allowed_activities") or {}
    training = config.get("training_policy") or {}
    try:
        project_mode = ProjectMode(mode)
    except ValueError:
        project_mode = ProjectMode.STRICT_AUTHORIZED_RESEARCH
    return ProjectModePolicy(
        project_mode=project_mode,
        local_machine_only=_bool_env("E_REVIEW_LOCAL_ONLY", bool(scope.get("local_machine_only", True))),
        noncommercial_only=_bool_env("E_REVIEW_NONCOMMERCIAL_ONLY", bool(scope.get("noncommercial_only", True))),
        public_release_allowed=_bool_env("E_REVIEW_PUBLIC_RELEASE_ALLOWED", bool(scope.get("public_release_allowed", False))),
        formal_external_benchmark_allowed=_bool_env(
            "E_REVIEW_FORMAL_EXTERNAL_EVAL_ALLOWED",
            bool(scope.get("formal_external_benchmark_allowed", False)),
        ),
        synthetic_training_allowed=_bool_env(
            "E_REVIEW_SYNTHETIC_TRAINING_ALLOWED",
            bool(training.get("project_owned_synthetic_training_allowed", allowed.get("synthetic_data_training", False))),
        ),
        public_pilot_local_read_only=_bool_env(
            "E_REVIEW_PUBLIC_PILOT_LOCAL_READ_ONLY",
            bool(allowed.get("public_pilot_local_read_only", False)),
        ),
        restricted_data_training_allowed=_bool_env(
            "E_REVIEW_RESTRICTED_DATA_TRAINING_ALLOWED",
            bool(training.get("explicitly_authorized_real_training_allowed", False)),
        ),
    )


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def evaluate_project_activity(
    activity: str,
    source_type: str = "unknown_or_untracked",
    data_type: str = "text",
    intended_output: str = "local_result",
) -> ActivityDecision:
    policy = load_project_mode_policy()
    restrictions: List[str] = []
    if policy.project_mode != ProjectMode.PRIVATE_NONCOMMERCIAL_RESEARCH:
        return ActivityDecision(False, "requires_explicit_authorization", ["STRICT_MODE_REQUIRES_AUTHORIZATION"], policy.project_mode.value, restrictions, _now())

    blocked_activities = {
        "formal_external_evaluation": "FORMAL_RESEARCH_EVALUATION_BLOCKED",
        "restricted_data_training": "RESTRICTED_DATA_TRAINING_BLOCKED",
        "llm_sft": "RESTRICTED_DATA_TRAINING_BLOCKED",
        "vlm_sft": "RESTRICTED_DATA_TRAINING_BLOCKED",
        "dpo": "RESTRICTED_DATA_TRAINING_BLOCKED",
        "raw_data_redistribution": "RAW_DATA_REDISTRIBUTION_BLOCKED",
        "public_result_release": "FORMAL_RELEASE_BLOCKED",
        "model_weight_distribution": "MODEL_WEIGHT_DISTRIBUTION_BLOCKED",
    }
    if activity in blocked_activities:
        return ActivityDecision(False, "blocked", [blocked_activities[activity]], policy.project_mode.value, restrictions, _now())

    if source_type == "unknown_or_untracked":
        return ActivityDecision(False, "blocked", ["UNKNOWN_SOURCE_BLOCKED"], policy.project_mode.value, restrictions, _now())

    if source_type in {"amazon_reviews_2023", "asap_chinese_reviews"}:
        if activity in {"synthetic_training", "restricted_data_training", "llm_sft", "vlm_sft", "dpo"}:
            return ActivityDecision(False, "blocked", ["PUBLIC_PILOT_TRAINING_RIGHTS_UNVERIFIED"], policy.project_mode.value, restrictions, _now())
        if activity == "public_pilot_prompt_development":
            restrictions = [
                "private_exploratory_only",
                "not_external_test",
                "not_statistical_significance",
                "not_public_report",
                "not_release_gate_evidence",
            ]
            return ActivityDecision(True, "conditionally_allowed", ["PRIVATE_LOCAL_RESEARCH_SCOPE"], policy.project_mode.value, restrictions, _now())
        if activity in {"public_pilot_local_processing", "public_pilot_local_inference", "private_exploratory_evaluation", "private_rag_evaluation"}:
            return ActivityDecision(True, "conditionally_allowed", ["PRIVATE_LOCAL_RESEARCH_SCOPE"], policy.project_mode.value, ["local_read_only"], _now())

    if source_type == "synthetic_project_owned" and activity in {"synthetic_training", "synthetic_evaluation"}:
        return ActivityDecision(True, "allowed", ["PROJECT_OWNED_SYNTHETIC_TRAINING"], policy.project_mode.value, ["not_formal_realworld_claim"], _now())

    if activity in {"local_code_development", "local_model_inference", "private_exploratory_evaluation", "private_rag_evaluation"}:
        return ActivityDecision(True, "allowed", ["PRIVATE_NONCOMMERCIAL_LOCAL_ACTIVITY"], policy.project_mode.value, ["local_only", "noncommercial_only"], _now())

    return ActivityDecision(False, "configuration_error", ["UNMAPPED_ACTIVITY"], policy.project_mode.value, restrictions, _now())
