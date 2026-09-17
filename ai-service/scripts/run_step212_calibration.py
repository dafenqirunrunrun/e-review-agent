from __future__ import annotations

"""Build and evaluate the isolated Step 21.2 router calibration set."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agentic_workflow.workflow import IntentRouterAgent
from app.risk_calibration.assessment import SmallModelRiskAssessor
from app.risk_calibration.calibrator import (
    calibration_metrics,
    fit_isotonic,
    fit_platt,
    save_calibrator,
)
from app.risk_calibration.severity import RiskSeverityEvaluator, SeverityRank
from app.schemas.review import ReviewAnalyzeRequest


FROZEN_GOLD_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
DEFAULT_DATASET = Path("data/risk_calibration/router_calibration_v1.jsonl")
DEFAULT_CALIBRATOR = Path("data/risk_calibration/confidence_calibrator_v1.json")
DEFAULT_OUTPUT = Path("artifacts/step212/calibration_report.json")


SCENARIOS: list[tuple[str, str, list[str], int, str]] = [
    ("normal", "实际使用一周，包装和功能都符合预期，补充记录{n}。", ["normal_review"], 4, "easy"),
    ("after_sales", "配件出现破损，提交退货申请后仍在等待处理，订单情况{n}。", ["after_sales_risk"], 1, "medium"),
    ("fake", "运营让未购买的账号批量编写统一体验内容，本次线索{n}。", ["fake_review"], 5, "easy"),
    ("rating", "客服组织用户集中打五星来提高店铺评分，活动批次{n}。", ["rating_manipulation"], 5, "easy"),
    ("incentive", "完成五星评价并发送截图后可领取优惠券，活动编号{n}。", ["fake_review", "rating_manipulation"], 5, "easy"),
    ("suppression", "只有先撤回低分评价，商家才继续处理退款，沟通记录{n}。", ["review_suppression"], 1, "medium"),
    ("privacy", "公开回复中出现了买家的手机号和家庭住址，片段{n}。", ["privacy_risk"], 2, "easy"),
    ("harassment", "发布评价后持续收到辱骂和上门报复威胁，记录{n}。", ["harassment_or_abuse"], 1, "medium"),
    ("safety", "设备使用时起火并有人受伤，疑似存在商品安全问题，批次{n}。", ["safety_or_fraud_risk"], 1, "medium"),
    ("ambiguous", "这次体验有问题，希望平台帮忙确认具体情况，补充{n}。", ["after_sales_risk"], 2, "hard"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--frozen-dataset", type=Path, default=Path("data/benchmarks/review_governance_gold_v1.jsonl"))
    parser.add_argument("--calibrator", type=Path, default=DEFAULT_CALIBRATOR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    frozen_sha = hashlib.sha256(args.frozen_dataset.read_bytes()).hexdigest().upper()
    if frozen_sha != FROZEN_GOLD_SHA:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA} actual={frozen_sha}")
    cases = build_calibration_cases()
    assert_no_frozen_overlap(cases, load_jsonl(args.frozen_dataset))
    write_jsonl(args.dataset, cases)
    dataset_sha = hashlib.sha256(args.dataset.read_bytes()).hexdigest().upper()

    rows = assess_cases(cases)
    train, validation = split_rows(rows)
    train_conf = [row["rawConfidence"] for row in train]
    train_labels = [row["goldCorrect"] for row in train]
    candidates = [fit_platt(train_conf, train_labels), fit_isotonic(train_conf, train_labels)]
    comparisons = {}
    for candidate in candidates:
        predicted = [candidate.predict(row["rawConfidence"]) for row in validation]
        comparisons[candidate.method] = calibration_metrics(predicted, [row["goldCorrect"] for row in validation])
    selected = min(candidates, key=lambda item: (comparisons[item.method]["ece"], comparisons[item.method]["brier"], item.method))
    save_calibrator(selected, args.calibrator, {
        "datasetVersion": "router-calibration-v1",
        "datasetSha256": dataset_sha,
        "fitCaseCount": len(train),
        "validationCaseCount": len(validation),
        "frozenGoldExcluded": True,
        "frozenGoldSha256": FROZEN_GOLD_SHA,
    })

    assessor = SmallModelRiskAssessor(args.calibrator)
    for row in rows:
        calibrated = assessor.assess(
            risk_types=row["predictedRiskTypes"],
            raw_confidence=row["rawConfidence"],
            reason_codes=row["reasonCodes"],
            review_text=row["reviewText"],
            model_provider="intent-router:rule",
        )
        row.update(calibrated.model_dump())

    validation_ids = {row["caseId"] for row in validation}
    validation_rows = [row for row in rows if row["caseId"] in validation_ids]
    raw = calibration_metrics([row["rawConfidence"] for row in validation_rows], [row["goldCorrect"] for row in validation_rows])
    calibrated = calibration_metrics([row["calibratedConfidence"] for row in validation_rows], [row["goldCorrect"] for row in validation_rows])
    risk_metrics = multilabel_metrics(validation_rows)
    severity_metrics = evaluate_severity(validation_rows)
    simulations = escalation_simulations(validation_rows)
    report = {
        "schemaVersion": "step21.2-calibration-v1",
        "dataset": {
            "version": "router-calibration-v1",
            "caseCount": len(cases),
            "sourceCounts": dict(Counter(case["source"] for case in cases)),
            "labelSourceCounts": dict(Counter(case["labelSource"] for case in cases)),
            "difficultyCounts": dict(Counter(case["difficulty"] for case in cases)),
            "humanReviewedCount": sum(bool(case["humanReviewed"]) for case in cases),
            "sha256": dataset_sha,
            "frozenGoldOverlapCount": 0,
            "frozenGoldSha256": frozen_sha,
            "split": {"trainCalibration": len(train), "validation": len(validation), "method": "stable-sha256-stratified-70-30"},
        },
        "smallModel": {
            "evaluatedRuntime": "existing intent-router rule path",
            "optionalLocalModelAvailable": "Qwen3-1.7B",
            "optionalLocalModelUsedForFit": False,
            "reason": "The frozen runtime uses the rule router; the local generative model is not enabled as its production provider.",
            "outputSchema": "small-model-risk-assessment-v1",
        },
        "severityRegistry": RiskSeverityEvaluator.registry(),
        "riskClassification": risk_metrics,
        "severityClassification": severity_metrics,
        "rawConfidence": raw,
        "calibrationCandidates": comparisons,
        "selectedCalibrator": selected.to_dict(),
        "calibratedConfidence": calibrated,
        "highConfidenceErrorCount": sum(1 for row in validation_rows if not row["goldCorrect"] and row["calibratedConfidence"] >= 0.8),
        "lowConfidenceCorrectCount": sum(1 for row in validation_rows if row["goldCorrect"] and row["calibratedConfidence"] < 0.7),
        "safetyGateOverrideCount": sum(1 for row in validation_rows if row["safetyGateOverride"]),
        "escalationSimulation": simulations,
        "recommendedConfidenceThreshold": recommend_threshold(simulations),
        "routingMatrixCandidate": routing_matrix(),
        "ablation": {
            "A_risk_type_only": risk_metrics,
            "B_risk_type_plus_severity": severity_metrics,
            "C_raw_confidence": {"ece": raw["ece"], "brier": raw["brier"]},
            "D_calibrated_confidence": {"ece": calibrated["ece"], "brier": calibrated["brier"]},
        },
        "fitSafety": {"frozenDatasetUsedForFit": False, "thresholdChangesProductionRouting": False},
        "sampleErrors": [compact_error(row) for row in validation_rows if not row["goldCorrect"]][:20],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_calibration_cases() -> list[dict[str, Any]]:
    evaluator = RiskSeverityEvaluator()
    cases = []
    for category, template, risks, rating, difficulty in SCENARIOS:
        for index in range(1, 25):
            text = template.format(n=f"C{index:02d}")
            severity = evaluator.evaluate(risks, review_text=text).severity
            cases.append({
                "caseId": f"cal-{category}-{index:02d}",
                "text": text,
                "rating": rating,
                "goldRiskTypes": risks,
                "goldSeverity": severity,
                "source": "controlled_synthetic",
                "difficulty": difficulty,
                "humanReviewed": False,
                "labelSource": "synthetic_weak_label+deterministic_registry",
            })
    assert len(cases) == 240
    return cases


def assess_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    severity = RiskSeverityEvaluator()
    rows = []
    for case in cases:
        decision = router.route(ReviewAnalyzeRequest(
            reviewId=case["caseId"], productId="calibration", productName="calibration fixture",
            reviewText=case["text"], rating=case["rating"],
        ))
        predicted = sorted(set(decision.risk_hints or ["normal_review"]))
        predicted_severity = severity.evaluate(predicted, review_text=case["text"]).severity
        rows.append({
            **case,
            "reviewText": case["text"],
            "predictedRiskTypes": predicted,
            "predictedSeverity": predicted_severity,
            "rawConfidence": decision.confidence,
            "reasonCodes": decision.reason_codes,
            "goldCorrect": int(set(predicted) == set(case["goldRiskTypes"])),
        })
    return rows


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[row["caseId"].split("-")[1]].append(row)
    train, validation = [], []
    for category_rows in by_category.values():
        ordered = sorted(category_rows, key=lambda row: hashlib.sha256(row["caseId"].encode()).hexdigest())
        train.extend(ordered[:17])
        validation.extend(ordered[17:])
    return train, validation


def multilabel_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    tp = fp = fn = 0
    for row in rows:
        expected, actual = set(row["goldRiskTypes"]), set(row["predictedRiskTypes"])
        tp += len(expected & actual)
        fp += len(actual - expected)
        fn += len(expected - actual)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0}


def evaluate_severity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [item.name.lower() for item in SeverityRank]
    matrix = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    correct = 0
    undercalls = 0
    f1_values = []
    for row in rows:
        gold, predicted = row["goldSeverity"], row["predictedSeverity"]
        matrix[gold][predicted] += 1
        correct += int(gold == predicted)
        if SeverityRank[gold.upper()] >= SeverityRank.HIGH and SeverityRank[predicted.upper()] < SeverityRank.HIGH:
            undercalls += 1
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[gold][label] for gold in labels if gold != label)
        fn = sum(matrix[label][predicted] for predicted in labels if predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {"accuracy": round(correct / len(rows), 6), "macroF1": round(sum(f1_values) / len(labels), 6), "highSeverityUndercallCount": undercalls, "confusionMatrix": matrix}


def escalation_simulations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    high_rows = [row for row in rows if SeverityRank[row["goldSeverity"].upper()] >= SeverityRank.HIGH]
    normal_rows = [row for row in rows if row["goldSeverity"] == "low"]
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
        escalated = [row for row in rows if row["calibratedConfidence"] < threshold or row["goldSeverity"] == "critical"]
        escalated_ids = {row["caseId"] for row in escalated}
        results.append({
            "threshold": threshold,
            "escalationRate": round(len(escalated) / len(rows), 6),
            "highRiskEscalationRate": round(sum(row["caseId"] in escalated_ids for row in high_rows) / len(high_rows), 6) if high_rows else 0.0,
            "falseEscalationRate": round(sum(row["caseId"] in escalated_ids for row in normal_rows) / len(normal_rows), 6) if normal_rows else 0.0,
            "note": "Selection-only simulation; no downstream model correctness is assumed.",
        })
    return results


def recommend_threshold(simulations: list[dict[str, Any]]) -> float:
    eligible = [row for row in simulations if row["falseEscalationRate"] <= 0.35]
    return max(eligible, key=lambda row: (row["highRiskEscalationRate"], -row["escalationRate"]))["threshold"] if eligible else 0.7


def routing_matrix() -> dict[str, dict[str, str]]:
    return {
        "low": {"highConfidence": "LOCAL_OK", "lowConfidence": "ESCALATE_FLASH"},
        "medium": {"highConfidence": "LOCAL_OR_FLASH", "lowConfidence": "ESCALATE_FLASH"},
        "high": {"highConfidence": "STRICT_GOVERNANCE", "lowConfidence": "ESCALATE_PRO_CANDIDATE"},
        "critical": {"highConfidence": "HUMAN_REQUIRED_CANDIDATE", "lowConfidence": "HUMAN_REQUIRED_CANDIDATE"},
        "invariant": {"safetyGateTriggered": "STRICT_GOVERNANCE_OR_HIGHER"},
    }


def compact_error(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("caseId", "goldRiskTypes", "predictedRiskTypes", "rawConfidence", "calibratedConfidence", "goldSeverity", "predictedSeverity")}


def assert_no_frozen_overlap(cases: list[dict[str, Any]], frozen: list[dict[str, Any]]) -> None:
    def digest(value: str) -> str:
        return hashlib.sha256(" ".join(value.lower().split()).encode("utf-8")).hexdigest()
    frozen_hashes = {digest(str(case.get("reviewText", ""))) for case in frozen}
    overlaps = [case["caseId"] for case in cases if digest(case["text"]) in frozen_hashes]
    if overlaps:
        raise SystemExit(f"CALIBRATION_FROZEN_OVERLAP:{','.join(overlaps)}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
