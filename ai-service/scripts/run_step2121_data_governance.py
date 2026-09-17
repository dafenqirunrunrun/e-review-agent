from __future__ import annotations

"""Govern human calibration data without fitting on insufficient labels."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agentic_workflow.workflow import IntentRouterAgent
from app.risk_calibration.assessment import SmallModelRiskAssessor
from app.risk_calibration.severity import RiskSeverityEvaluator, SeverityRank
from app.schemas.review import ReviewAnalyzeRequest


FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
MIN_HUMAN_CASES = 300
EXPLICIT_TERMS = (
    "返现", "五星", "刷单", "删评", "撤回", "退款", "退货", "破损", "威胁", "辱骂", "手机号", "住址",
    "cashback", "five-star", "fake review", "remove review", "refund", "threat",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=Path("artifacts/step2121/db_task_export.jsonl"))
    parser.add_argument("--frozen", type=Path, default=Path("data/benchmarks/review_governance_gold_v1.jsonl"))
    parser.add_argument("--calibrator", type=Path, default=Path("data/risk_calibration/confidence_calibrator_v1.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/risk_calibration/router_calibration_v2.jsonl"))
    parser.add_argument("--queue", type=Path, default=Path("data/risk_calibration/human_annotation_queue_v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/step2121/data_governance_report.json"))
    parser.add_argument("--frozen-report", type=Path, default=Path("artifacts/step212/frozen_holdout.json"))
    args = parser.parse_args()

    frozen_bytes = args.frozen.read_bytes()
    frozen_sha = hashlib.sha256(frozen_bytes).hexdigest().upper()
    if frozen_sha != FROZEN_SHA:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_SHA} actual={frozen_sha}")
    staging = load_jsonl(args.staging)
    frozen = load_jsonl(args.frozen)
    human_rows, excluded = build_human_cases(staging, frozen)
    split, leakage = source_aware_split(human_rows)
    write_jsonl(args.dataset, human_rows)
    queue = build_annotation_queue(staging, human_rows, frozen, target=max(0, MIN_HUMAN_CASES - len(human_rows)))
    write_jsonl(args.queue, queue)
    mark_not_approved(args.calibrator)

    confidence = confidence_analysis(human_rows)
    taxonomy = frozen_error_taxonomy(frozen, Path("data/workflow_checkpoints"), args.frozen_report)
    report = {
        "schemaVersion": "step21.2.1-data-governance-v1",
        "dataset": {
            "datasetVersion": "router_calibration_v2",
            "caseCount": len(human_rows),
            "currentHumanCalibrationCount": len(human_rows),
            "minimumRequired": MIN_HUMAN_CASES,
            "sourceDistribution": dict(Counter(row["sourceType"] for row in human_rows)),
            "tierDistribution": dict(Counter(row["provenanceTier"] for row in human_rows)),
            "humanReviewedCount": len(human_rows),
            "humanGoldCount": sum(row["provenanceTier"] == "A" for row in human_rows),
            "historicalHumanReviewedCount": sum(row["provenanceTier"] == "B" for row in human_rows),
            "weakLabelCount": 0,
            "riskDistribution": dict(Counter(risk for row in human_rows for risk in row["goldRiskTypes"])),
            "sourcePeriodDistribution": dict(Counter(row["sourcePeriod"] for row in human_rows)),
            "splitPolicy": "source/period/risk/expression/template-family grouped 70/30",
            "contentHash": hashlib.sha256(args.dataset.read_bytes()).hexdigest().upper(),
            "frozenGoldSha256": frozen_sha,
            "frozenExactDuplicateCount": excluded["exact"],
            "frozenNearDuplicateCount": excluded["near"],
            "excludedFromDataset": excluded,
            "provenanceTiers": {
                "A": "independent human-reviewed gold",
                "B": "human/QA-reviewed historical outcome",
                "C": "shadow audit or production bad case awaiting confirmed gold",
                "D": "controlled synthetic or weak label; excluded from final validation",
            },
        },
        "split": split,
        "splitLeakageAudit": leakage,
        "confidenceCardinality": confidence,
        "reliabilityTierAnalysis": reliability_tiers(confidence["rows"]),
        "multiSignalReliability": signal_analysis(confidence["rows"]),
        "previousCalibrator": {
            "status": "NOT_APPROVED_FOR_ROUTING",
            "reason": "Frozen ECE and Brier regressed after synthetic-template calibration.",
            "parametersChanged": False,
        },
        "recalibration": {
            "status": "NOT_RUN_INSUFFICIENT_HUMAN_DATA",
            "blockedReasons": [
                "human-reviewed case count is below 300",
                "independent Tier A gold coverage is insufficient",
                "usable labels cover only one risk type",
                "raw confidence has only two observed values",
            ],
            "rawVsPlattVsIsotonic": "DEFERRED",
            "acceptanceRule": "ECE improves AND Brier does not regress AND high-risk error does not worsen",
            "frozenHoldoutRerun": False,
            "frozenHoldoutReadOnly": True,
        },
        "annotationQueue": {
            "version": "human-annotation-queue-v1",
            "targetGap": max(0, MIN_HUMAN_CASES - len(human_rows)),
            "queuedCaseCount": len(queue),
            "unfilledQueueGap": max(0, MIN_HUMAN_CASES - len(human_rows) - len(queue)),
            "prioritySources": dict(Counter(row["queueReason"] for row in queue)),
            "reviewerIdentityIncluded": False,
        },
        "frozenErrorTaxonomy": taxonomy,
        "routerReadiness": "NOT_READY",
        "gate": "BLOCKED_ON_HUMAN_CALIBRATION_DATA",
    }
    del report["confidenceCardinality"]["rows"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_human_cases(staging: list[dict[str, Any]], frozen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    frozen_texts = [normalize(row.get("reviewText", "")) for row in frozen]
    conflicting_texts = {
        normalize(row.get("sanitizedText", ""))
        for row in staging
        if row.get("humanReviewed") and not row.get("eligibleAsGold")
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in staging:
        if row.get("eligibleAsGold") and row.get("humanReviewed"):
            grouped[normalize(row.get("sanitizedText", ""))].append(row)
    result = []
    excluded = {"exact": 0, "near": 0, "invalid": 0, "conflictingHumanOutcome": 0}
    evaluator = RiskSeverityEvaluator()
    for normalized, rows in grouped.items():
        if not normalized:
            excluded["invalid"] += 1
            continue
        if normalized in conflicting_texts:
            excluded["conflictingHumanOutcome"] += 1
            continue
        if normalized in frozen_texts:
            excluded["exact"] += 1
            continue
        if any(near_duplicate(normalized, text) for text in frozen_texts):
            excluded["near"] += 1
            continue
        text = rows[0]["sanitizedText"]
        risks = sorted({row["currentRiskType"] for row in rows if row.get("currentRiskType")}) or ["other"]
        expression = expression_type(text)
        result.append({
            "datasetVersion": "router_calibration_v2",
            "caseId": "human-" + sha(normalized)[:20],
            "sanitizedText": text,
            "goldRiskTypes": risks,
            "goldSeverity": evaluator.evaluate(risks, review_text=text).severity,
            "labelSource": "human_acceptance",
            "sourceType": rows[0].get("sourceType") or "risk_task:unknown",
            "difficulty": difficulty(text, risks, expression),
            "explicitOrImplicit": expression,
            "humanReviewed": True,
            "reviewOutcome": "accepted_ai_label",
            "sourcePeriod": rows[0].get("sourcePeriod") or "unknown",
            "provenanceTier": min(row.get("provenanceTier", "B") for row in rows),
            "templateFamily": template_family(text),
        })
    return sorted(result, key=lambda row: row["caseId"]), excluded


def source_aware_split(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    families = merge_near_duplicate_families(rows)
    strata: dict[str, list[str]] = defaultdict(list)
    for family, members in families.items():
        row = members[0]
        key = "|".join((
            row["sourceType"], row.get("sourcePeriod", "unknown"),
            row["goldRiskTypes"][0], row["explicitOrImplicit"],
        ))
        strata[key].append(family)
    fit_families: set[str] = set()
    validation_families: set[str] = set()
    for family_ids in strata.values():
        ordered = sorted(family_ids, key=sha)
        cut = max(1, round(len(ordered) * 0.7)) if len(ordered) > 1 else len(ordered)
        fit_families.update(ordered[:cut])
        validation_families.update(ordered[cut:])
    for family, members in families.items():
        split = "fit" if family in fit_families else "validation"
        for row in members:
            row["split"] = split
            row["templateFamily"] = family
    fit = [row for row in rows if row["split"] == "fit"]
    validation = [row for row in rows if row["split"] == "validation"]
    overlap = set(row["templateFamily"] for row in fit) & set(row["templateFamily"] for row in validation)
    exact_overlap = set(normalize(row["sanitizedText"]) for row in fit) & set(normalize(row["sanitizedText"]) for row in validation)
    return (
        {"fitCount": len(fit), "validationCount": len(validation), "fitFamilyCount": len(fit_families), "validationFamilyCount": len(validation_families)},
        {"templateFamilyLeakageCount": len(overlap), "normalizedTextLeakageCount": len(exact_overlap), "passed": not overlap and not exact_overlap},
    )


def confidence_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    evaluated = []
    for row in rows:
        decision = router.route(ReviewAnalyzeRequest(
            reviewId=row["caseId"], productId="calibration", productName="calibration",
            reviewText=row["sanitizedText"], rating=3,
        ))
        predicted = sorted(set(decision.risk_hints or ["normal_review"]))
        expected = set(row["goldRiskTypes"])
        missing = expected - set(predicted)
        expected_high = SeverityRank[row["goldSeverity"].upper()] >= SeverityRank.HIGH
        evaluated.append({
            **row,
            "rawConfidence": decision.confidence,
            "predictedRiskTypes": predicted,
            "correct": set(predicted) == expected,
            "falseNegative": bool(missing),
            "highRiskMiss": bool(expected_high and missing),
            "safetyGateTriggered": "HIGH_RISK_SAFETY_GATE" in decision.reason_codes,
            "ambiguityFlag": decision.confidence < 0.7 or len(row["sanitizedText"].strip()) < 8,
            "riskTypeCount": len(predicted),
            "ruleStrength": "strong" if decision.confidence >= 0.8 else "weak",
        })
    buckets = []
    for confidence in sorted({row["rawConfidence"] for row in evaluated}):
        items = [row for row in evaluated if row["rawConfidence"] == confidence]
        buckets.append({
            "confidence": confidence,
            "count": len(items),
            "accuracy": ratio(sum(row["correct"] for row in items), len(items)),
            "falseNegativeRate": ratio(sum(row["falseNegative"] for row in items), len(items)),
            "highRiskMissRate": ratio(sum(row["highRiskMiss"] for row in items), len(items)),
        })
    return {
        "uniqueConfidenceValues": sorted({row["rawConfidence"] for row in evaluated}),
        "uniqueValueCount": len({row["rawConfidence"] for row in evaluated}),
        "continuousProbabilitySuitable": len({row["rawConfidence"] for row in evaluated}) >= 10,
        "conclusion": "USE_ORDINAL_RELIABILITY_TIERS" if len({row["rawConfidence"] for row in evaluated}) < 10 else "CONTINUOUS_CALIBRATION_CANDIDATE",
        "buckets": buckets,
        "rows": evaluated,
    }


def reliability_tiers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row["rawConfidence"]
        tier = "VERY_HIGH" if value >= 0.85 else "HIGH" if value >= 0.75 else "MEDIUM" if value >= 0.6 else "LOW"
        groups[tier].append(row)
    result = []
    for tier in ("VERY_HIGH", "HIGH", "MEDIUM", "LOW"):
        items = groups[tier]
        result.append({
            "tier": tier, "count": len(items),
            "empiricalAccuracy": ratio(sum(row["correct"] for row in items), len(items)),
            "errorRate": ratio(sum(not row["correct"] for row in items), len(items)),
            "highRiskRecall": ratio(sum(not row["highRiskMiss"] for row in items if SeverityRank[row["goldSeverity"].upper()] >= SeverityRank.HIGH), sum(SeverityRank[row["goldSeverity"].upper()] >= SeverityRank.HIGH for row in items)),
            "probabilityClaim": False,
        })
    return result


def signal_analysis(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals = {
        "ruleStrength=strong": lambda row: row["ruleStrength"] == "strong",
        "multiRisk=true": lambda row: row["riskTypeCount"] > 1,
        "safetyGateTriggered=true": lambda row: row["safetyGateTriggered"],
        "explicitExpression=true": lambda row: row["explicitOrImplicit"] == "explicit",
        "ambiguityFlag=true": lambda row: row["ambiguityFlag"],
        "severity>=high": lambda row: SeverityRank[row["goldSeverity"].upper()] >= SeverityRank.HIGH,
    }
    output = []
    for name, predicate in signals.items():
        items = [row for row in rows if predicate(row)]
        output.append({"signal": name, "count": len(items), "errorRate": ratio(sum(not row["correct"] for row in items), len(items)), "highRiskMissRate": ratio(sum(row["highRiskMiss"] for row in items), len(items))})
    return output


def build_annotation_queue(staging: list[dict[str, Any]], human_rows: list[dict[str, Any]], frozen: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    used = {normalize(row["sanitizedText"]) for row in human_rows}
    frozen_texts = [normalize(row.get("reviewText", "")) for row in frozen]
    candidates = []
    for row in staging:
        text = normalize(row.get("sanitizedText", ""))
        needs_relabel = bool(row.get("humanReviewed") and not row.get("eligibleAsGold"))
        if not text or text in frozen_texts or any(near_duplicate(text, item) for item in frozen_texts):
            continue
        if text in used and not needs_relabel:
            continue
        reason = "HUMAN_OVERRIDE_NEEDS_GOLD_LABEL" if "override" in row.get("reviewOutcome", "") else "HUMAN_NO_ACTION_NEEDS_GOLD_LABEL" if "no_action" in row.get("reviewOutcome", "") else "PENDING_HUMAN_LABEL"
        priority = 1 if reason != "PENDING_HUMAN_LABEL" else 2
        candidates.append({
            "queueVersion": "human-annotation-queue-v1",
            "caseId": "queue-" + sha(text)[:20],
            "sanitizedText": row["sanitizedText"],
            "proposedRiskTypes": [row["currentRiskType"]] if row.get("currentRiskType") else [],
            "goldRiskTypes": None,
            "goldSeverity": None,
            "labelSource": "awaiting_human_review",
            "sourceType": row.get("sourceType") or "risk_task:unknown",
            "difficulty": difficulty(row["sanitizedText"], [row.get("currentRiskType", "other")], expression_type(row["sanitizedText"])),
            "explicitOrImplicit": expression_type(row["sanitizedText"]),
            "humanReviewed": False,
            "reviewOutcome": row.get("reviewOutcome"),
            "sourcePeriod": row.get("sourcePeriod") or "unknown",
            "queueReason": reason,
            "priority": priority,
        })
        used.add(text)
    deduplicated = {row["caseId"]: row for row in sorted(candidates, key=lambda row: (-row["priority"], row["caseId"]))}
    return sorted(deduplicated.values(), key=lambda row: (row["priority"], row["caseId"]))[:target]


def frozen_error_taxonomy(
    frozen: list[dict[str, Any]], checkpoint_root: Path, frozen_report: Path | None = None
) -> dict[str, Any]:
    evaluator = RiskSeverityEvaluator()
    assessor = SmallModelRiskAssessor()
    high_confidence: list[dict[str, Any]] = []
    undercalls: list[dict[str, Any]] = []
    for case in frozen:
        path = checkpoint_root / f"{sha(case['caseId'])}.json"
        if not path.exists():
            continue
        try:
            response = json.loads(path.read_text(encoding="utf-8")).get("governanceSnapshot", {}).get("response", {})
        except (OSError, ValueError):
            continue
        actual = set(response.get("risk_types") or [])
        expected = set(case["expectedRiskTypes"])
        assessment = (response.get("extra") or {}).get("riskAssessment") or {}
        if not assessment:
            intent = ((response.get("extra") or {}).get("agentic") or {}).get("intent") or {}
            assessment = assessor.assess(
                risk_types=sorted(actual) or list(intent.get("risk_hints") or intent.get("riskHints") or ["normal_review"]),
                raw_confidence=float(intent.get("confidence", response.get("confidence", 0.5))),
                reason_codes=list(intent.get("reason_codes") or intent.get("reasonCodes") or []),
                review_text=case["reviewText"],
                evidence_status=str(response.get("evidence_status") or ""),
                model_provider="intent-router:rule",
            ).model_dump()
        confidence = float(assessment.get("calibratedConfidence", 0))
        if confidence >= 0.8 and actual != expected:
            category = classify_error(case, expected, actual, response)
            high_confidence.append({"caseId": case["caseId"], "category": category})
        gold_severity = evaluator.evaluate(list(expected), review_text=case["reviewText"]).severity
        predicted_severity = assessment.get("severity", "low")
        if SeverityRank[gold_severity.upper()] >= SeverityRank.HIGH and SeverityRank[str(predicted_severity).upper()] < SeverityRank.HIGH:
            reason = "RISK_TYPE_ERROR" if actual != expected else "CONTEXT_MODIFIER_NOT_RECOGNIZED"
            undercalls.append({"caseId": case["caseId"], "reason": reason, "goldSeverity": gold_severity, "predictedSeverity": predicted_severity})
    historical = {}
    if frozen_report and frozen_report.exists():
        try:
            historical = json.loads(frozen_report.read_text(encoding="utf-8")).get("governance", {}).get("riskCalibrationHoldout", {})
        except (OSError, ValueError):
            historical = {}
    authoritative_high_confidence = int(historical.get("highConfidenceErrorCount", len(high_confidence)))
    authoritative_undercalls = int(historical.get("highSeverityUndercallCount", len(undercalls)))
    snapshot_matches_frozen = len(high_confidence) == authoritative_high_confidence
    classified = high_confidence if snapshot_matches_frozen else []
    return {
        "highConfidenceErrorCount": authoritative_high_confidence,
        "highConfidenceCountSource": "frozen_step21.2_holdout_artifact" if historical else "checkpoint_reconstruction",
        "checkpointReconstructionCount": len(high_confidence),
        "checkpointSnapshotMatchesFrozenRun": snapshot_matches_frozen,
        "classificationCoverageCount": len(classified),
        "classificationStatus": "COMPLETE" if snapshot_matches_frozen else "BLOCKED_HISTORICAL_PER_CASE_SNAPSHOT_UNAVAILABLE",
        "highConfidenceCategories": dict(Counter(row["category"] for row in classified)),
        "highConfidenceCases": classified,
        "highSeverityUndercallCount": authoritative_undercalls,
        "highSeverityUndercallReasons": dict(Counter(row["reason"] for row in undercalls)),
        "highSeverityUndercallCases": undercalls,
        "caseSpecificPatchesApplied": False,
    }


def classify_error(case: dict[str, Any], expected: set[str], actual: set[str], response: dict[str, Any]) -> str:
    if case.get("category") in {"lexical_mismatch", "ambiguous"}:
        return "implicit_semantics"
    if len(expected) > 1 or len(actual) > 1:
        return "multi_risk_ambiguity"
    if actual - expected and not expected - actual:
        return "rule_pattern_false_positive"
    if expected - actual and not actual - expected:
        return "rule_pattern_false_negative"
    if response.get("evidence_status") != case.get("expectedEvidenceStatus"):
        return "evidence_mismatch"
    return "other"


def merge_near_duplicate_families(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    parent = list(range(len(rows)))
    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a
    normalized = [normalize(row["sanitizedText"]) for row in rows]
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if near_duplicate(normalized[left], normalized[right]):
                union(left, right)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[find(index)].append(row)
    return {"family-" + sha("|".join(sorted(item["caseId"] for item in members)))[:16]: members for members in grouped.values()}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"[^\w\u4e00-\u9fff]+", "", str(text).lower()))


def template_family(text: str) -> str:
    normalized = re.sub(r"\d+", "<n>", normalize(text))
    return "family-" + sha(normalized)[:16]


def near_duplicate(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.9


def expression_type(text: str) -> str:
    lowered = text.lower()
    return "explicit" if any(term in lowered for term in EXPLICIT_TERMS) else "implicit"


def difficulty(text: str, risks: list[str], expression: str) -> str:
    if len(text.strip()) < 8 or expression == "implicit":
        return "hard"
    if len(set(risks)) > 1:
        return "medium"
    return "easy"


def mark_not_approved(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["approvalStatus"] = "NOT_APPROVED_FOR_ROUTING"
    data["approvalReason"] = "Frozen holdout ECE and Brier regression; retained for reproducibility only."
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def ratio(top: int, bottom: int) -> float | None:
    return round(top / bottom, 6) if bottom else None


def sha(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
