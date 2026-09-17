from __future__ import annotations

"""Controlled runtime activation for the frozen Fast Eligibility policy."""

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings
from app.observability.fast_eligibility_shadow import (
    FAST_SHORT_CHAIN,
    HIGH_RISK_SIGNALS,
    LONG_ANALYSIS_CHAIN,
    CurrentRouteSignal,
    FrozenFastEligibilityPolicy,
)
from app.schemas.review import ReviewAnalyzeRequest


BASELINE_CHAIN = "BASELINE_CHAIN"
NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class FastEligibilityRuntimeDecision:
    enabled: bool
    canarySelected: bool
    canaryBucket: int
    policyDecision: str
    executedChain: str
    reasonCode: str
    policyVersion: str = ""
    policyHash: str = ""
    failClosed: bool = False

    @property
    def fast_executed(self) -> bool:
        return self.executedChain == FAST_SHORT_CHAIN

    def metadata(self) -> dict:
        return asdict(self)


class FastEligibilityRuntimeController:
    """Select the fast chain without changing the frozen policy itself.

    The policy is an admission signal, while the runtime guards preserve the
    current Router and Safety Gate as hard authorities. Any uncertainty keeps
    the existing baseline chain.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        canary_percent: int | None = None,
        policy_path: str | Path | None = None,
    ):
        self._enabled = enabled
        self._canary_percent = canary_percent
        self._policy_path = Path(policy_path) if policy_path is not None else None
        self._policy: FrozenFastEligibilityPolicy | None = None
        self._loaded_path: Path | None = None

    def decide(
        self,
        payload: ReviewAnalyzeRequest,
        current: CurrentRouteSignal,
    ) -> FastEligibilityRuntimeDecision:
        enabled = settings.fast_eligibility_runtime_enabled if self._enabled is None else self._enabled
        bucket = self._canary_bucket(payload)
        if not enabled:
            return self._baseline(False, False, bucket, "FAST_RUNTIME_DISABLED")
        if payload.audit_mode:
            return self._baseline(True, False, bucket, "AUDIT_MODE_BASELINE_ONLY")

        percent = (
            settings.fast_eligibility_runtime_canary_percent
            if self._canary_percent is None
            else max(0, min(100, self._canary_percent))
        )
        selected = bucket < percent
        if not selected:
            return self._baseline(True, False, bucket, "CANARY_NOT_SELECTED")

        try:
            policy = self._load_policy()
            policy_decision, policy_reason = policy.evaluate(payload.review_text, current)
        except Exception:
            return self._baseline(
                True,
                True,
                bucket,
                "FAST_POLICY_UNAVAILABLE",
                fail_closed=True,
            )

        common = {
            "enabled": True,
            "canarySelected": True,
            "canaryBucket": bucket,
            "policyDecision": policy_decision,
            "policyVersion": policy.policy_version,
            "policyHash": policy.policy_hash,
        }
        if policy_decision != FAST_SHORT_CHAIN:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=BASELINE_CHAIN,
                reasonCode=policy_reason,
            )

        risks = set(current.risk_hints)
        if current.safety_gate_triggered or risks.intersection(HIGH_RISK_SIGNALS):
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=BASELINE_CHAIN,
                reasonCode="RUNTIME_SAFETY_OVERRIDE",
                failClosed=True,
            )
        if current.route != "low_touch" or risks:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=BASELINE_CHAIN,
                reasonCode="CURRENT_GOVERNANCE_ROUTE_OVERRIDE",
                failClosed=True,
            )
        if payload.image_urls:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=BASELINE_CHAIN,
                reasonCode="IMAGE_REVIEW_BASELINE_OVERRIDE",
                failClosed=True,
            )
        return FastEligibilityRuntimeDecision(
            **common,
            executedChain=FAST_SHORT_CHAIN,
            reasonCode=policy_reason,
        )

    def decide_admission(
        self,
        payload: ReviewAnalyzeRequest,
        current: CurrentRouteSignal,
    ) -> FastEligibilityRuntimeDecision:
        """Make the authoritative short-chain admission decision.

        Unlike the historical canary controller, this gate is evaluated for
        every business request. Only an explicit policy approval may enter the
        short chain; unavailable policy state and every non-fast result fail
        closed to the long analysis chain.
        """

        bucket = self._canary_bucket(payload)
        try:
            policy = self._load_policy()
            policy_decision, policy_reason = policy.evaluate(payload.review_text, current)
        except Exception:
            return FastEligibilityRuntimeDecision(
                enabled=True,
                canarySelected=True,
                canaryBucket=bucket,
                policyDecision=NOT_EVALUATED,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode="FAST_POLICY_UNAVAILABLE",
                failClosed=True,
            )

        common = {
            "enabled": True,
            "canarySelected": True,
            "canaryBucket": bucket,
            "policyDecision": policy_decision,
            "policyVersion": policy.policy_version,
            "policyHash": policy.policy_hash,
        }
        if payload.audit_mode:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode="AUDIT_MODE_LONG_ANALYSIS",
            )
        if policy_decision != FAST_SHORT_CHAIN:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode=policy_reason,
            )

        risks = set(current.risk_hints)
        if current.safety_gate_triggered or risks.intersection(HIGH_RISK_SIGNALS):
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode="RUNTIME_SAFETY_OVERRIDE",
                failClosed=True,
            )
        if current.route != "low_touch" or risks:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode="CURRENT_GOVERNANCE_ROUTE_OVERRIDE",
                failClosed=True,
            )
        if payload.image_urls:
            return FastEligibilityRuntimeDecision(
                **common,
                executedChain=LONG_ANALYSIS_CHAIN,
                reasonCode="IMAGE_REVIEW_LONG_ANALYSIS",
                failClosed=True,
            )
        return FastEligibilityRuntimeDecision(
            **common,
            executedChain=FAST_SHORT_CHAIN,
            reasonCode=policy_reason,
        )

    def status(self) -> dict:
        path = self._resolved_policy_path()
        status = {
            "enabled": settings.fast_eligibility_runtime_enabled if self._enabled is None else self._enabled,
            "canaryPercent": (
                settings.fast_eligibility_runtime_canary_percent
                if self._canary_percent is None
                else max(0, min(100, self._canary_percent))
            ),
            "policyConfigured": bool(path),
            "policyAvailable": path.exists(),
            "policyIntegrity": "unavailable",
            "failureMode": "baseline_chain",
        }
        try:
            policy = self._load_policy()
            status.update({
                "policyIntegrity": "ready",
                "policyVersion": policy.policy_version,
                "policyHash": policy.policy_hash,
            })
        except Exception:
            status["policyIntegrity"] = "failed"
        return status

    def _load_policy(self) -> FrozenFastEligibilityPolicy:
        path = self._resolved_policy_path()
        if self._policy is None or self._loaded_path != path:
            self._policy = FrozenFastEligibilityPolicy(path)
            self._loaded_path = path
        return self._policy

    def _resolved_policy_path(self) -> Path:
        configured = self._policy_path or Path(settings.fast_eligibility_runtime_policy_path)
        if configured.is_absolute():
            return configured
        return Path(__file__).resolve().parents[2] / configured

    @staticmethod
    def _canary_bucket(payload: ReviewAnalyzeRequest) -> int:
        identity = payload.review_id or hashlib.sha256(
            f"{payload.product_id}|{payload.review_text}|{payload.rating}|{payload.rating_source}".encode("utf-8")
        ).hexdigest()
        return int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16) % 100

    @staticmethod
    def _baseline(
        enabled: bool,
        selected: bool,
        bucket: int,
        reason: str,
        *,
        fail_closed: bool = False,
    ) -> FastEligibilityRuntimeDecision:
        return FastEligibilityRuntimeDecision(
            enabled=enabled,
            canarySelected=selected,
            canaryBucket=bucket,
            policyDecision=NOT_EVALUATED,
            executedChain=BASELINE_CHAIN,
            reasonCode=reason,
            failClosed=fail_closed,
        )
