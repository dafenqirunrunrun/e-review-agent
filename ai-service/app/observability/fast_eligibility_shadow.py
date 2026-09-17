from __future__ import annotations

"""Fail-open shadow evaluation for the frozen Step 21.3H eligibility policy."""

import hashlib
import json
import re
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse


FAST_SHORT_CHAIN = "FAST_SHORT_CHAIN"
LONG_ANALYSIS_CHAIN = "LONG_ANALYSIS_CHAIN"
EXPECTED_POLICY_HASH = "3F39478C3E834A27BC83BDE6D27FF57C5846FBC62CD8B6B4BDC572A0A5D6CD79"
HIGH_RISK_SIGNALS = {
    "fake_review",
    "rating_manipulation",
    "review_suppression",
    "safety_or_fraud_risk",
    "privacy_risk",
    "harassment_or_abuse",
    "rating_conflict",
}


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def shadow_gate(long_reduction: float, high_risk_fast: int, safety_fast: int) -> tuple[str, str]:
    if high_risk_fast or safety_fast:
        return "FAIL", "HIGH_OR_SAFETY_RISK_ROUTED_TO_SHADOW_FAST"
    if long_reduction >= 0.20:
        return "PASS", "SAFETY_CLEAR_AND_REDUCTION_AT_LEAST_20_PERCENT"
    if long_reduction >= 0.10:
        return "PASS_WITH_LIMITATIONS", "SAFETY_CLEAR_BUT_REDUCTION_BETWEEN_10_AND_20_PERCENT"
    return "FAIL", "ESTIMATED_LONG_REDUCTION_BELOW_10_PERCENT"


@dataclass(frozen=True)
class CurrentRouteSignal:
    route: str
    intent: str
    risk_hints: tuple[str, ...]
    reason_codes: tuple[str, ...]
    safety_gate_triggered: bool


class FrozenFastEligibilityPolicy:
    def __init__(self, artifact_path: str | Path):
        self.artifact_path = Path(artifact_path)
        artifact = json.loads(self.artifact_path.read_text(encoding="utf-8"))
        specification = {
            key: value
            for key, value in artifact.items()
            if key not in {"schemaVersion", "policyHash", "frozen"}
        }
        actual_hash = _stable_hash(specification)
        if not artifact.get("frozen") or actual_hash != EXPECTED_POLICY_HASH or artifact.get("policyHash") != actual_hash:
            raise RuntimeError("FAST_ELIGIBILITY_POLICY_INTEGRITY_FAILED")
        patterns = artifact["patterns"]
        self.policy_version = str(artifact["policyVersion"])
        self.policy_hash = actual_hash
        self.positive_or_ordinary = re.compile(patterns["positiveOrOrdinary"])
        self.negative_disqualifier = re.compile(patterns["negativeDisqualifier"])
        self.standard_issue = re.compile(patterns["standardIssue"])
        self.hard_long = re.compile(patterns["hardLong"], re.I)
        self.complex_issue = re.compile(patterns["complexIssue"])

    def evaluate(self, review_text: str, current: CurrentRouteSignal) -> tuple[str, str]:
        signals = set(current.risk_hints)
        if current.safety_gate_triggered:
            return LONG_ANALYSIS_CHAIN, "EXISTING_SAFETY_GATE"
        if self.hard_long.search(review_text):
            return LONG_ANALYSIS_CHAIN, "HARD_LONG_TEXT_SIGNAL"
        if signals - {"after_sales_risk"}:
            return LONG_ANALYSIS_CHAIN, "GOVERNANCE_RISK_SIGNAL"
        if self.standard_issue.search(review_text) and not self.complex_issue.search(review_text):
            return FAST_SHORT_CHAIN, "STANDARD_LOW_COMPLEXITY_ISSUE"
        if (
            current.intent == "normal_feedback"
            and not signals
            and current.route == "low_touch"
            and self.positive_or_ordinary.search(review_text)
            and not self.negative_disqualifier.search(review_text)
        ):
            return FAST_SHORT_CHAIN, "CLEAR_ORDINARY_REVIEW"
        return LONG_ANALYSIS_CHAIN, "FAST_ELIGIBILITY_NOT_PROVEN"


def current_route_signal(response: ReviewAnalyzeResponse) -> CurrentRouteSignal:
    extra = response.extra if isinstance(response.extra, dict) else {}
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    intent = agentic.get("intent") if isinstance(agentic.get("intent"), dict) else {}
    route = str(agentic.get("route") or intent.get("route") or response.route_decision or "unknown")
    route_candidate = {
        "auto_close": "low_touch",
        "auto_pass": "low_touch",
        "suggest_action": "governance_required",
        "human_review": "human_review_direct",
    }.get(route, route)
    risk_hints = intent.get("risk_hints") or intent.get("riskHints") or response.risk_types or []
    reason_codes = intent.get("reason_codes") or intent.get("reasonCodes") or []
    if not isinstance(risk_hints, list):
        risk_hints = [risk_hints]
    if not isinstance(reason_codes, list):
        reason_codes = [reason_codes]
    normalized_risks = tuple(sorted({str(value) for value in risk_hints if value and value != "normal_review"}))
    normalized_reasons = tuple(sorted({str(value) for value in reason_codes if value}))
    fallback_intent = "normal_feedback" if route_candidate == "low_touch" and not normalized_risks else "negative_feedback"
    return CurrentRouteSignal(
        route=route_candidate,
        intent=str(intent.get("intent") or fallback_intent),
        risk_hints=normalized_risks,
        reason_codes=normalized_reasons,
        safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in normalized_reasons,
    )


class FastEligibilityShadowEvaluator:
    def __init__(self, *, policy_path: str | Path, output_dir: str | Path, report_path: str | Path):
        self.policy = FrozenFastEligibilityPolicy(policy_path)
        self.output_dir = Path(output_dir)
        self.report_path = Path(report_path)
        self.decisions_path = self.output_dir / "fast_shadow_decisions.jsonl"
        self.metrics_path = self.output_dir / "fast_shadow_metrics.json"
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] | None = None
        self._metadata: dict[str, Any] = {}

    def reset(self) -> None:
        with self._lock:
            for path in (self.decisions_path, self.metrics_path, self.report_path):
                if path.exists():
                    path.unlink()
            self._records = []

    def observe(self, payload: ReviewAnalyzeRequest, current: CurrentRouteSignal) -> dict[str, Any]:
        shadow_route, reason_code = self.policy.evaluate(payload.review_text, current)
        high_risk = bool(set(current.risk_hints).intersection(HIGH_RISK_SIGNALS))
        request_hash = hashlib.sha256(
            f"{payload.review_id}|{payload.product_id}|{payload.review_text}|"
            f"{payload.rating}|{payload.rating_source}".encode("utf-8")
        ).hexdigest()[:24]
        record = {
            "schemaVersion": "fast-eligibility-shadow-decision-v1",
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "reviewId": payload.review_id or f"anonymous-{request_hash[:12]}",
            "requestHash": request_hash,
            "currentDecision": current.route,
            "shadowDecision": shadow_route,
            "reasonCodes": [reason_code],
            "estimatedCostSaving": 1.0 if shadow_route == FAST_SHORT_CHAIN else 0.0,
            "riskSignalSummary": {
                "intentType": current.intent,
                "matchedRiskSignals": list(current.risk_hints),
                "currentReasonCodes": list(current.reason_codes),
                "highRiskSignal": high_risk,
                "safetyGateTriggered": current.safety_gate_triggered,
            },
            "policyVersion": self.policy.policy_version,
            "policyHash": self.policy.policy_hash,
            "shadowOnly": True,
            "chainExecuted": False,
        }
        with self._lock:
            records = self._load_records()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with self.decisions_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            records.append(record)
            metrics = self._metrics(records)
            if self._metadata:
                metrics["observation"] = self._metadata
            self._write_json_atomic(self.metrics_path, metrics)
            self._write_text_atomic(self.report_path, self._report(metrics))
        return record

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return self._metrics(self._load_records())

    def finalize(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            metrics = self._metrics(self._load_records())
            if metadata:
                self._metadata = dict(metadata)
            if self._metadata:
                metrics["observation"] = self._metadata
            self._write_json_atomic(self.metrics_path, metrics)
            self._write_text_atomic(self.report_path, self._report(metrics))
            return metrics

    def _load_records(self) -> list[dict[str, Any]]:
        if self._records is None:
            self._records = []
            if self.decisions_path.exists():
                self._records = [
                json.loads(line)
                for line in self.decisions_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
                ]
        return self._records

    def _metrics(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(records)
        fast = sum(row["shadowDecision"] == FAST_SHORT_CHAIN for row in records)
        long_count = total - fast
        high_fast = sum(
            row["shadowDecision"] == FAST_SHORT_CHAIN and row["riskSignalSummary"]["highRiskSignal"]
            for row in records
        )
        safety_fast = sum(
            row["shadowDecision"] == FAST_SHORT_CHAIN and row["riskSignalSummary"]["safetyGateTriggered"]
            for row in records
        )
        reduction = round(fast / total, 6) if total else 0.0
        gate, gate_reason = shadow_gate(reduction, high_fast, safety_fast)
        return {
            "schemaVersion": "fast-eligibility-shadow-metrics-v1",
            "sampleCount": total,
            "longAnalysisReduction": reduction,
            "potentialCostSaving": reduction,
            "shadowFastCount": fast,
            "shadowLongCount": long_count,
            "highRiskShadowFast": high_fast,
            "safetyShadowFast": safety_fast,
            "currentDecisionCounts": dict(sorted(Counter(row["currentDecision"] for row in records).items())),
            "shadowReasonCounts": dict(sorted(Counter(row["reasonCodes"][0] for row in records).items())),
            "policyVersion": self.policy.policy_version,
            "policyHash": self.policy.policy_hash,
            "step21_4Gate": gate,
            "gateReason": gate_reason,
            "frozenBenchmarkExecuted": False,
            "shortChainExecuted": False,
            "longAnalysisExecuted": False,
            "productionRouterModified": False,
        }

    def _report(self, metrics: dict[str, Any]) -> str:
        observation = metrics.get("observation") or {}
        limitations = []
        if metrics["gateReason"] == "ESTIMATED_LONG_REDUCTION_BELOW_10_PERCENT":
            limitations.append(
                "The observed traffic did not meet the minimum reduction threshold. Inputs were preserved as received; no rating normalization or Router tuning was applied."
            )
        if observation.get("skippedInvalidRequestCount"):
            limitations.append(
                f"`{observation['skippedInvalidRequestCount']}` source rows were not valid ReviewAnalyzeRequest payloads and were excluded."
            )
        rating_source_counts = observation.get("ratingSourceCounts") or {}
        if rating_source_counts.get("UNKNOWN"):
            limitations.append(
                f"`{rating_source_counts['UNKNOWN']}` legacy records have unknown rating provenance. Their stored star values were excluded from LOW_RATING under the v2 rating contract."
            )
        return "\n".join(
            [
                "# Fast Eligibility Shadow Report",
                "",
                "## Scope",
                "",
                "The frozen Step 21.3H policy is evaluated after the current route is known. The evaluator records metadata only and never executes either candidate chain or changes the review response.",
                "",
                "## Metrics",
                "",
                f"- Observed requests: `{metrics['sampleCount']}`",
                f"- Long Analysis Reduction: `{metrics['longAnalysisReduction']:.2%}`",
                f"- Potential Cost Saving: `{metrics['potentialCostSaving']:.2%}` (unit-cost estimate)",
                f"- Shadow Fast / Long: `{metrics['shadowFastCount']} / {metrics['shadowLongCount']}`",
                f"- High-risk Shadow Fast: `{metrics['highRiskShadowFast']}`",
                f"- Safety Shadow Fast: `{metrics['safetyShadowFast']}`",
                f"- Current route distribution: `{json.dumps(metrics['currentDecisionCounts'], sort_keys=True)}`",
                f"- Shadow reason distribution: `{json.dumps(metrics['shadowReasonCounts'], sort_keys=True)}`",
                "",
                "## Observation Source",
                "",
                f"`{json.dumps(observation, ensure_ascii=False, sort_keys=True)}`",
                "",
                "## Gate",
                "",
                f"`STEP21_4_GATE = {metrics['step21_4Gate']}`",
                f"Reason: `{metrics['gateReason']}`",
                "",
                "## Isolation",
                "",
                "- Production Router modified: `false`",
                "- Short Chain executed by shadow: `false`",
                "- Long Analysis executed by shadow: `false`",
                "- Frozen benchmark executed: `false`",
                "- Raw review text persisted: `false`",
                "",
                "## Limitations",
                "",
                *(f"- {item}" for item in limitations),
                "- The file sink targets the project's local single-process demo runtime; a multi-worker deployment would require a transactional metrics sink.",
                "",
            ]
        )

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        FastEligibilityShadowEvaluator._write_text_atomic(
            path,
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        )

    @staticmethod
    def _write_text_atomic(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(value, encoding="utf-8", newline="\n")
        temporary.replace(path)


_default_evaluator: FastEligibilityShadowEvaluator | None = None
_default_lock = threading.Lock()


def observe_fast_eligibility_shadow(payload: ReviewAnalyzeRequest, response: ReviewAnalyzeResponse) -> None:
    """Observe a completed request and swallow every shadow-side failure."""
    if payload.audit_mode or not _shadow_enabled():
        return
    extra = response.extra if isinstance(response.extra, dict) else {}
    runtime = extra.get("fastEligibilityRuntime") if isinstance(extra.get("fastEligibilityRuntime"), dict) else {}
    if runtime.get("canarySelected"):
        # Runtime already persists this decision in the workflow trace. Avoid
        # evaluating and synchronously writing the same observation twice.
        return
    try:
        evaluator = _get_default_evaluator()
        evaluator.observe(payload, current_route_signal(response))
    except Exception:
        return


def _shadow_enabled() -> bool:
    from app.core.config import settings

    return settings.fast_eligibility_shadow_enabled


def _get_default_evaluator() -> FastEligibilityShadowEvaluator:
    from app.core.config import settings

    global _default_evaluator
    with _default_lock:
        if _default_evaluator is None:
            service_root = Path(__file__).resolve().parents[2]

            def resolved(value: str) -> Path:
                path = Path(value)
                return path if path.is_absolute() else (service_root / path).resolve()

            _default_evaluator = FastEligibilityShadowEvaluator(
                policy_path=resolved(settings.fast_eligibility_shadow_policy_path),
                output_dir=resolved(settings.fast_eligibility_shadow_output_dir),
                report_path=resolved(settings.fast_eligibility_shadow_report_path),
            )
        return _default_evaluator
