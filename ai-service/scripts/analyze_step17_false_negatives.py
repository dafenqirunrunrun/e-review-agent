from __future__ import annotations

"""Capture the frozen Step 16 high-risk auto-pass baseline before router changes."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from scripts.run_step16_benchmark import load_jsonl, post_analyze
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    from run_step16_benchmark import load_jsonl, post_analyze


FROZEN_GOLD_SHA256 = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a read-only Step 17 false-negative root-cause report.")
    parser.add_argument("--dataset", type=Path, default=Path("data/benchmarks/review_governance_gold_v1.jsonl"))
    parser.add_argument("--service-url", default="http://127.0.0.1:8008")
    parser.add_argument("--output", type=Path, default=Path("artifacts/step17/baseline_fn_root_cause.json"))
    args = parser.parse_args()
    digest = sha256(args.dataset)
    if digest != FROZEN_GOLD_SHA256:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA256} actual={digest}")

    cases = [case for case in load_jsonl(args.dataset) if case["expectedHumanReview"]]
    rows = []
    for case in cases:
        actual, _, error = post_analyze(args.service_url, case)
        governance = actual.get("review_governance", {}) if actual else {}
        agentic = (actual.get("extra") or {}).get("agentic") or {}
        intent = agentic.get("intent") or {}
        decision = governance.get("decision", {}).get("code")
        risks = governance.get("riskTypes", [])
        if decision != "auto_pass":
            continue
        route = agentic.get("route", "unknown")
        failure_layer = (
            "ROUTER_FALSE_NEGATIVE" if route == "low_touch"
            else "DETECTOR_FALSE_NEGATIVE" if not set(risks).intersection(case["expectedRiskTypes"])
            else "DECISION_FALSE_NEGATIVE"
        )
        rows.append({
            "caseId": case["caseId"], "category": case["category"], "reviewText": case["reviewText"],
            "expectedRiskTypes": case["expectedRiskTypes"], "actualRiskTypes": risks,
            "actualRoute": route, "actualDecision": decision,
            "routerConfidence": intent.get("confidence"), "routerReasonCodes": intent.get("reason_codes") or intent.get("reasonCodes") or [],
            "failureLayer": failure_layer, "rootCause": root_cause(case, intent), "error": error,
        })
    report = {
        "schemaVersion": "step17-fn-root-cause-v1", "goldSha256": digest,
        "expectedHumanReviewCases": len(cases), "highRiskAutoPassCount": len(rows),
        "byFailureLayer": dict(Counter(row["failureLayer"] for row in rows)),
        "byRootCause": dict(Counter(row["rootCause"] for row in rows)), "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def root_cause(case: dict, intent: dict) -> str:
    if (intent.get("reason_codes") or intent.get("reasonCodes") or []) == ["NO_RISK_SIGNAL"]:
        return {
            "fake_review": "implicit_fake_review_language_not_covered",
            "paid_review": "incentive_review_phrase_not_covered",
            "rating_manipulation": "rating_manipulation_paraphrase_not_covered",
            "review_suppression": "review_suppression_paraphrase_not_covered",
            "multi_risk": "multi_risk_expression_not_covered",
            "privacy_risk": "privacy_expression_not_covered",
            "harassment_or_abuse": "harassment_expression_not_covered",
        }.get(case["category"], "no_risk_signal")
    return "strict_path_or_decision_analysis_required"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())
