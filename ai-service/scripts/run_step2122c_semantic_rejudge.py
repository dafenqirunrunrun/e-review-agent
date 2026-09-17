from __future__ import annotations

"""Materialize the Step 21.2.2C Codex single-judge review without model calls."""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_calibration.severity import RiskSeverityEvaluator


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"


# Explicit single-judge determinations. Unlisted queued cases pass semantic review.
RISK_REPAIRS: dict[str, list[str]] = {
    "boundary-e_review_expert_designed-72fe7685712ae2": ["paid_review"],
    "boundary-v2-e_review_candidate-29f3443b4bf2e0": ["paid_review", "rating_manipulation"],
    "boundary-v2-e_review_candidate-52ae143621f55d": ["paid_review", "review_suppression"],
    "boundary-v2-e_review_candidate-750d0d7cb30b23": ["paid_review", "rating_manipulation"],
    "cal-asap_chinese_reviews-05a721545ecd36": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-4196d918f2ba6d": ["harassment_or_abuse", "negative_review"],
    "cal-asap_chinese_reviews-4f46a48ba2f396": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-50a0cc058fe24a": ["paid_review"],
    "cal-asap_chinese_reviews-5b95d280a264af": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-a1336c6de4926f": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-aa2604a6a0f342": ["negative_review"],
    "cal-asap_chinese_reviews-c2e161f567c75b": ["fake_review", "negative_review"],
    "cal-asap_chinese_reviews-cd52c325c5f219": ["paid_review"],
    "cal-asap_chinese_reviews-d045b988d2a4d0": ["fake_review", "negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-d659b58c573b05": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-fa5e0dbf6c1732": ["fake_review"],
    "cal-figshare_chinese_negative_reviews-1f735153f91fc3": ["negative_review"],
    "cal-figshare_chinese_negative_reviews-6db7e1284bcbfc": ["after_sales_risk"],
    "cal-figshare_chinese_negative_reviews-7cc8b7cb071600": ["negative_review"],
    "cal-figshare_chinese_negative_reviews-87392fac7d8eb2": ["after_sales_risk", "safety_or_fraud_risk"],
    "cal-figshare_chinese_negative_reviews-8e6642d0b30b71": ["negative_review"],
    "cal-figshare_chinese_negative_reviews-d8ea8d298c0054": ["after_sales_risk", "harassment_or_abuse"],
    "cal-figshare_chinese_negative_reviews-f708c0f49c8dfa": ["after_sales_risk"],
    "cal-hf_fake_reviews_apache-4975117a3464a7": ["normal_review"],
    "cal-hf_fake_reviews_apache-68ea6312ebff19": ["normal_review"],
    "cal-hf_fake_reviews_apache-d5317bcfe9d01f": ["normal_review"],
    "cal-v2-moved-0e55d059034919": ["fake_review"],
}

UNCERTAIN = {"cal-asap_chinese_reviews-90b303a74db7b5"}
UNNATURAL = {
    "cal-asap_chinese_reviews-5b95d280a264af",
    "cal-asap_chinese_reviews-aa2604a6a0f342",
    "cal-v2-moved-0e55d059034919",
}
BOUNDARY_INVALID = {
    "boundary-figshare_chinese_negative_reviews-023a144527caeb",
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4",
    "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60",
}
BOUNDARY_MISSING_RISK = {
    "boundary-v2-e_review_candidate-29f3443b4bf2e0": ["paid_review"],
    "boundary-v2-e_review_candidate-52ae143621f55d": ["paid_review"],
    "boundary-v2-e_review_candidate-750d0d7cb30b23": ["paid_review"],
}
KEYWORD_SHORTCUT = {
    "boundary-figshare_chinese_negative_reviews-023a144527caeb",
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4",
    "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60",
    "boundary-v2-e_review_candidate-1388a989d12d1d",
    "boundary-v2-e_review_candidate-279c34136964c2",
    "boundary-v2-e_review_candidate-2ef6b69770ecf4",
    "boundary-v2-e_review_candidate-44917168ef8d3c",
    "boundary-v2-e_review_candidate-627fa8bda66c0a",
    "boundary-v2-e_review_candidate-89a2d3e266f916",
    "boundary-v2-e_review_candidate-96f2d8d0e32963",
    "boundary-v2-e_review_candidate-eaae3c40073782",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def semantic_result(row: dict[str, Any]) -> dict[str, Any]:
    case_id = row["caseId"]
    if row["evaluationTarget"] == "ABSTENTION":
        return {
            "caseId": case_id, "verdict": "PASS", "riskTypesAssessment": "CORRECT",
            "severityAssessment": "CORRECT", "expressionAssessment": "CORRECT",
            "multiRiskAssessment": "CORRECT", "abstentionAssessment": "CORRECT",
            "naturalChinese": True, "suggestedRiskTypes": [], "suggestedSeverity": None,
            "reasonCodes": ["ABSTENTION_EXPECTED"],
        }
    if case_id in UNCERTAIN:
        return {
            "caseId": case_id, "verdict": "UNCERTAIN", "riskTypesAssessment": "UNCERTAIN",
            "severityAssessment": "CORRECT", "expressionAssessment": "CORRECT",
            "multiRiskAssessment": "UNCERTAIN", "abstentionAssessment": "NOT_APPLICABLE",
            "naturalChinese": True, "suggestedRiskTypes": [], "suggestedSeverity": None,
            "reasonCodes": ["LABEL_AMBIGUOUS", "CONTEXT_INSUFFICIENT"],
        }
    suggested = RISK_REPAIRS.get(case_id)
    if suggested is None:
        return {
            "caseId": case_id, "verdict": "PASS", "riskTypesAssessment": "CORRECT",
            "severityAssessment": "CORRECT", "expressionAssessment": "CORRECT",
            "multiRiskAssessment": "CORRECT", "abstentionAssessment": "NOT_APPLICABLE",
            "naturalChinese": case_id not in UNNATURAL, "suggestedRiskTypes": [],
            "suggestedSeverity": None, "reasonCodes": [],
        }
    current = sorted(row["benchmarkRiskTypes"])
    proposed = sorted(suggested)
    current_multi, proposed_multi = len(current) > 1, len(proposed) > 1
    reasons = ["RISK_TYPE_MISMATCH"]
    if not current_multi and proposed_multi or set(current) < set(proposed):
        reasons.append("MISSED_MULTI_RISK")
    elif current_multi and not proposed_multi:
        reasons.append("FALSE_MULTI_RISK")
    proposed_severity = RiskSeverityEvaluator().evaluate(proposed, review_text=row["textZh"]).severity
    severity_assessment = "CORRECT"
    if proposed_severity != row["severity"]:
        severity_assessment = "INCORRECT"
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        reasons.append("SEVERITY_TOO_LOW" if order[row["severity"]] < order[proposed_severity] else "SEVERITY_TOO_HIGH")
    if case_id in UNNATURAL:
        reasons.append("UNNATURAL_CHINESE")
    return {
        "caseId": case_id, "verdict": "FAIL", "riskTypesAssessment": "INCORRECT",
        "severityAssessment": severity_assessment, "expressionAssessment": "CORRECT",
        "multiRiskAssessment": "INCORRECT" if current_multi != proposed_multi or set(current) < set(proposed) else "CORRECT",
        "abstentionAssessment": "NOT_APPLICABLE", "naturalChinese": case_id not in UNNATURAL,
        "suggestedRiskTypes": proposed, "suggestedSeverity": proposed_severity,
        "reasonCodes": list(dict.fromkeys(reasons)),
    }


def boundary_result(row: dict[str, Any]) -> dict[str, Any]:
    case_id = row["caseId"]
    abstention = row["evaluationTarget"] == "ABSTENTION"
    if case_id in BOUNDARY_INVALID:
        return {
            "caseId": case_id, "boundaryVerdict": "FAIL", "boundaryTypeAssessment": "INCORRECT",
            "challengeValue": "LOW", "keywordShortcutRisk": True, "abstentionBoundaryValid": False,
            "possibleMissingRiskTypes": [], "suggestedBoundaryType": None,
            "reasonCodes": ["NOT_REAL_BOUNDARY", "TOO_EASY"],
        }
    if case_id in BOUNDARY_MISSING_RISK:
        return {
            "caseId": case_id, "boundaryVerdict": "FAIL", "boundaryTypeAssessment": "CORRECT",
            "challengeValue": "MEDIUM", "keywordShortcutRisk": case_id in KEYWORD_SHORTCUT,
            "abstentionBoundaryValid": False, "possibleMissingRiskTypes": BOUNDARY_MISSING_RISK[case_id],
            "suggestedBoundaryType": None, "reasonCodes": ["MISSED_RISK"],
        }
    challenge = "MEDIUM" if row["boundaryType"] == "lexical_mismatch" else "HIGH"
    return {
        "caseId": case_id, "boundaryVerdict": "PASS", "boundaryTypeAssessment": "CORRECT",
        "challengeValue": challenge, "keywordShortcutRisk": case_id in KEYWORD_SHORTCUT,
        "abstentionBoundaryValid": abstention, "possibleMissingRiskTypes": [],
        "suggestedBoundaryType": None, "reasonCodes": ["ABSTENTION_EXPECTED"] if abstention else [],
    }


def rate(value: int, total: int) -> float:
    return round(value / total, 6) if total else 0.0


def main() -> int:
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() != FROZEN_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")
    calibration = load_jsonl(DATA / "router_calibration_candidate_demo_v2.jsonl")
    boundary = load_jsonl(DATA / "boundary_challenge_demo_v2.jsonl")
    queue = load_jsonl(DATA / "dataset_rejudge_queue_v1.jsonl")
    aggregation = {row["caseId"]: row for row in load_jsonl(DATA / "judge_aggregation_v1.jsonl")}
    queued = {row["caseId"]: row for row in queue}
    if len(queue) != 81 or sum(row["datasetType"] == "boundary" for row in queue) != 41:
        raise SystemExit("REJUDGE_QUEUE_COUNT_MISMATCH")

    semantic_results = [semantic_result(row) for row in queue]
    boundary_results = [boundary_result(row) for row in queue if row["datasetType"] == "boundary"]
    semantic_by = {row["caseId"]: row for row in semantic_results}
    boundary_by = {row["caseId"]: row for row in boundary_results}

    calibration_verdicts = []
    for row in calibration:
        calibration_verdicts.append(semantic_by[row["caseId"]]["verdict"] if row["caseId"] in queued else aggregation[row["caseId"]]["judgeAVerdict"])
    boundary_verdicts = []
    challenge_values, keyword_values = [], []
    for row in boundary:
        if row["caseId"] in boundary_by:
            result = boundary_by[row["caseId"]]
            boundary_verdicts.append(result["boundaryVerdict"])
            challenge_values.append(result["challengeValue"])
            keyword_values.append(result["keywordShortcutRisk"])
        else:
            prior = aggregation[row["caseId"]]
            boundary_verdicts.append(prior["judgeBVerdict"])
            challenge_values.append(prior["judgeBChallengeValue"])
            keyword_values.append(prior["judgeBKeywordShortcutRisk"])

    cal_counts = Counter(calibration_verdicts)
    boundary_counts = Counter(boundary_verdicts)
    challenge_counts = Counter(challenge_values)
    all_rows = calibration + boundary
    natural_false = {row["caseId"] for row in semantic_results if not row["naturalChinese"]}
    natural_count = len(all_rows) - len(natural_false)
    missed_multi = sum("MISSED_MULTI_RISK" in row["reasonCodes"] for row in semantic_results)
    risk_mismatch = sum("RISK_TYPE_MISMATCH" in row["reasonCodes"] for row in semantic_results)
    severity_mismatch = sum(row["severityAssessment"] == "INCORRECT" for row in semantic_results)
    abstention_results = [row for row in semantic_results if row["abstentionAssessment"] != "NOT_APPLICABLE"]
    abstention_counts = Counter(row["abstentionAssessment"] for row in abstention_results)
    shortcut_count = sum(keyword_values)
    high_medium = challenge_counts["HIGH"] + challenge_counts["MEDIUM"]

    metrics = {
        "semanticJudgeType": "CODEX_SINGLE_JUDGE",
        "singleJudgeLimitation": True,
        "calibration": {"total": 120, "pass": cal_counts["PASS"], "fail": cal_counts["FAIL"], "uncertain": cal_counts["UNCERTAIN"], "passRate": rate(cal_counts["PASS"], 120)},
        "boundary": {
            "total": 60, "pass": boundary_counts["PASS"], "fail": boundary_counts["FAIL"], "uncertain": boundary_counts["UNCERTAIN"], "passRate": rate(boundary_counts["PASS"], 60),
            "highChallengeCount": challenge_counts["HIGH"], "mediumChallengeCount": challenge_counts["MEDIUM"], "lowChallengeCount": challenge_counts["LOW"],
            "highMediumRatio": rate(high_medium, 60), "keywordShortcutCount": shortcut_count, "keywordShortcutRatio": rate(shortcut_count, 60),
        },
        "semantic": {
            "naturalChineseCount": natural_count, "naturalChineseRatio": rate(natural_count, len(all_rows)),
            "missedMultiRiskCount": missed_multi, "riskTypeMismatchCount": risk_mismatch,
            "severityMismatchCount": severity_mismatch,
        },
        "abstention": {
            "caseCount": len(abstention_results), "correctCount": abstention_counts["CORRECT"],
            "incorrectCount": abstention_counts["INCORRECT"], "uncertainCount": abstention_counts["UNCERTAIN"],
            "abstentionAccuracy": rate(abstention_counts["CORRECT"], len(abstention_results)),
        },
        "finalMinimalRepair": {"performed": False, "reason": "More than five semantic defects remain; a one-iteration minimal repair is not applicable."},
    }
    thresholds = {
        "calibrationSemanticPass": metrics["calibration"]["passRate"] >= 0.90,
        "boundaryValidityPass": metrics["boundary"]["passRate"] >= 0.85,
        "boundaryChallengePass": metrics["boundary"]["highMediumRatio"] >= 0.80,
        "keywordShortcutPass": metrics["boundary"]["keywordShortcutRatio"] <= 0.25,
        "naturalChinesePass": metrics["semantic"]["naturalChineseRatio"] >= 0.95,
        "multiRiskSystematicErrorPass": missed_multi < 3,
        "abstentionPass": metrics["abstention"]["correctCount"] >= 4,
    }
    metrics["thresholds"] = thresholds
    metrics["gate"] = "FAIL" if not all(thresholds.values()) else "PASS_WITH_SINGLE_JUDGE_LIMITATION"

    write_jsonl(DATA / "semantic_rejudge_results_v1.jsonl", semantic_results)
    write_jsonl(DATA / "boundary_rejudge_results_v1.jsonl", boundary_results)
    write_json(DATA / "semantic_gate_metrics_v1.json", metrics)
    calibration_hash = hashlib.sha256((DATA / "router_calibration_candidate_demo_v2.jsonl").read_bytes()).hexdigest().upper()
    boundary_hash = hashlib.sha256((DATA / "boundary_challenge_demo_v2.jsonl").read_bytes()).hexdigest().upper()
    freeze_manifest = {
        "datasetVersion": "evaluation-dataset-demo-v2.1",
        "calibrationHash": calibration_hash,
        "boundaryHash": boundary_hash,
        "frozenGoldSha": FROZEN_SHA,
        "semanticResultsHash": hashlib.sha256((DATA / "semantic_rejudge_results_v1.jsonl").read_bytes()).hexdigest().upper(),
        "boundaryResultsHash": hashlib.sha256((DATA / "boundary_rejudge_results_v1.jsonl").read_bytes()).hexdigest().upper(),
        "semanticJudgeType": "CODEX_SINGLE_JUDGE",
        "humanGold": False,
        "multiModelValidated": False,
        "independentJudge": False,
        "demoReady": metrics["gate"] != "FAIL",
        "freezeStatus": "NOT_FROZEN_GATE_FAILED" if metrics["gate"] == "FAIL" else "SEMANTICALLY_ACCEPTED_FOR_DEMO",
        "limitations": [
            "SINGLE_JUDGE_LIMITATION",
            "Calibration semantic pass rate is below the Demo threshold.",
            "Boundary keyword shortcut ratio is above the Demo threshold.",
            "Missed multi-risk errors remain systematic.",
        ] if metrics["gate"] == "FAIL" else ["SINGLE_JUDGE_LIMITATION"],
    }
    write_json(DATA / "dataset_final_freeze_manifest.json", freeze_manifest)
    print(json.dumps({"metrics": metrics, "freeze": freeze_manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
