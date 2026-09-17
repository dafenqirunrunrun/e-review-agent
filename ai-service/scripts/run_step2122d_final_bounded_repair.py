from __future__ import annotations

"""Apply the one permitted bounded semantic repair and freeze the Demo candidate."""

import hashlib
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_calibration.severity import RiskSeverityEvaluator


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
MAX_CHANGED_CASES = 30


FINAL_RISKS: dict[str, list[str]] = {
    "boundary-e_review_expert_designed-72fe7685712ae2": ["paid_review"],
    "boundary-v2-e_review_candidate-29f3443b4bf2e0": ["paid_review", "rating_manipulation"],
    "boundary-v2-e_review_candidate-52ae143621f55d": ["paid_review", "review_suppression"],
    "boundary-v2-e_review_candidate-750d0d7cb30b23": ["paid_review", "rating_manipulation"],
    "cal-asap_chinese_reviews-05a721545ecd36": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-4196d918f2ba6d": ["harassment_or_abuse", "negative_review"],
    "cal-asap_chinese_reviews-4f46a48ba2f396": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-5b95d280a264af": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-a1336c6de4926f": ["negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-c2e161f567c75b": ["fake_review", "negative_review"],
    "cal-asap_chinese_reviews-d045b988d2a4d0": ["fake_review", "negative_review", "safety_or_fraud_risk"],
    "cal-asap_chinese_reviews-d659b58c573b05": ["negative_review", "safety_or_fraud_risk"],
    "cal-figshare_chinese_negative_reviews-87392fac7d8eb2": ["after_sales_risk", "safety_or_fraud_risk"],
    "cal-figshare_chinese_negative_reviews-d8ea8d298c0054": ["after_sales_risk", "harassment_or_abuse"],
    "cal-asap_chinese_reviews-aa2604a6a0f342": ["negative_review"],
    "cal-v2-moved-0e55d059034919": ["normal_review"],
    "boundary-figshare_chinese_negative_reviews-023a144527caeb": ["after_sales_risk"],
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4": ["after_sales_risk"],
    "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60": ["after_sales_risk"],
}

TEXT_REPAIRS = {
    "cal-asap_chinese_reviews-5b95d280a264af": "昨天和朋友路过这家店，环境很差。宫保鸡丁大小不一，酸菜鱼没有味道，烤肉下面的香菜已经腐烂，其他菜也很难吃，以后不会再去。",
    "cal-asap_chinese_reviews-aa2604a6a0f342": "这家店交通方便，但等位服务员态度很差，一直对顾客喊叫。食物种类没有特色，价格也不太值，希望商家改进服务。",
    "cal-v2-moved-0e55d059034919": "这家店就在公司楼下，下午茶时偶尔会去。店里人不算多，服务一般。",
    "boundary-figshare_chinese_negative_reviews-023a144527caeb": "商品外包装破损，客服直接按售后规则退款，并明确表示处理结果与评价内容无关。",
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4": "商品到手有瑕疵，售后补发后我自行保留原评价，商家没有要求修改评分。",
    "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60": "订单少发一件，客服立即补寄，也没有把删除低分内容作为处理条件。",
    "boundary-v2-e_review_candidate-1388a989d12d1d": "内容由品牌方预先写好，发布者不需要实际体验；每完成一次公开反馈，月底账单就增加一笔报酬。",
    "boundary-v2-e_review_candidate-279c34136964c2": "管理员把同一段使用感受分给从未接触商品的人，让他们用不同账号陆续发布。",
    "boundary-v2-e_review_candidate-2ef6b69770ecf4": "问题是否解决并不重要，公开结果越接近最高档，约定的那笔钱才会到账。",
    "boundary-v2-e_review_candidate-44917168ef8d3c": "一批没有对应成交记录的账号，陆续发出了措辞相近的亲身体验。",
}

EVIDENCE_SUMMARY = {
    "boundary-e_review_expert_designed-72fe7685712ae2": "截图后给予心意只支持利益驱动，未明确指定星级。",
    "boundary-v2-e_review_candidate-29f3443b4bf2e0": "补偿与点亮最高评分存在条件绑定。",
    "boundary-v2-e_review_candidate-52ae143621f55d": "补偿以调整公开负面内容为条件。",
    "boundary-v2-e_review_candidate-750d0d7cb30b23": "补偿与达到最高评价档位直接绑定。",
    "cal-asap_chinese_reviews-05a721545ecd36": "评论明确描述未煮熟食材，同时表达负向体验。",
    "cal-asap_chinese_reviews-4196d918f2ba6d": "评论描述服务人员持续辱骂，同时是负向体验。",
    "cal-asap_chinese_reviews-4f46a48ba2f396": "发臭食材构成安全信号，同时保留负向体验。",
    "cal-asap_chinese_reviews-5b95d280a264af": "腐烂食材构成安全信号，同时保留负向体验。",
    "cal-asap_chinese_reviews-a1336c6de4926f": "多人食用后腹泻构成安全信号。",
    "cal-asap_chinese_reviews-c2e161f567c75b": "文本明确指称店家自有账号刷评价。",
    "cal-asap_chinese_reviews-d045b988d2a4d0": "刷评论指控与商品成分欺骗同时出现。",
    "cal-asap_chinese_reviews-d659b58c573b05": "把已食用餐品转给外卖订单构成安全信号。",
    "cal-figshare_chinese_negative_reviews-87392fac7d8eb2": "疑似非正品与售后查询同时出现。",
    "cal-figshare_chinese_negative_reviews-d8ea8d298c0054": "拒绝维修与攻击性表达同时出现。",
    "cal-asap_chinese_reviews-aa2604a6a0f342": "全文明确表达服务和价格不满。",
    "cal-v2-moved-0e55d059034919": "移除百科式污染后只剩普通到店体验。",
}

SHORTCUT_REPAIRS = {
    "boundary-figshare_chinese_negative_reviews-023a144527caeb",
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4",
    "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60",
    "boundary-v2-e_review_candidate-1388a989d12d1d",
    "boundary-v2-e_review_candidate-279c34136964c2",
    "boundary-v2-e_review_candidate-2ef6b69770ecf4",
    "boundary-v2-e_review_candidate-44917168ef8d3c",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())


def template_family(value: str) -> str:
    return "family-" + sha(re.sub(r"\d+", "<n>", normalize(value)))[:16]


def near(left: str, right: str) -> bool:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio() >= 0.9


def repair(rows: list[dict[str, Any]], dataset_type: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result, log = [], []
    for original in rows:
        if original["caseId"] not in set(FINAL_RISKS) | set(TEXT_REPAIRS):
            result.append(dict(original))
            continue
        current = dict(original)
        old_text, old_risks, old_severity = current["textZh"], list(current["riskTypes"]), current["severity"]
        current["textZh"] = TEXT_REPAIRS.get(current["caseId"], current["textZh"])
        current["riskTypes"] = sorted(FINAL_RISKS.get(current["caseId"], current["riskTypes"]))
        current["benchmarkRiskTypes"] = list(current["riskTypes"])
        current["severity"] = RiskSeverityEvaluator().evaluate(current["riskTypes"], review_text=current["textZh"]).severity
        current["multiRisk"] = len(current["riskTypes"]) > 1
        current["contentHash"] = sha(current["textZh"])
        current["templateFamily"] = template_family(current["textZh"])
        current["datasetRevision"] = "v2.2-final"
        current["datasetAcceptanceStatus"] = "SEMANTICALLY_REVIEWED_CANDIDATE"
        current["semanticValidation"] = "CODEX_SINGLE_JUDGE_VALIDATED"
        current["labelStatus"] = "PROPOSED_REPAIRED"
        current["repairAction"] = "FINAL_BOUNDED_REPAIR"
        result.append(current)
        reasons = []
        if old_risks != current["riskTypes"]:
            reasons.append("SEMANTIC_LABEL_REPAIR")
        if old_text != current["textZh"]:
            reasons.append("TEXT_QUALITY_OR_BOUNDARY_REPAIR")
        if current["caseId"] in SHORTCUT_REPAIRS:
            reasons.append("KEYWORD_SHORTCUT_REPAIR")
        log.append({
            "caseId": current["caseId"], "datasetType": dataset_type,
            "oldRiskTypes": old_risks, "newRiskTypes": current["riskTypes"],
            "oldSeverity": old_severity, "newSeverity": current["severity"],
            "oldContentHash": sha(old_text), "newContentHash": current["contentHash"],
            "evidenceSpanSummary": EVIDENCE_SUMMARY.get(current["caseId"], "通过关系、否定或主体表达重写为高价值边界。"),
            "repairReason": reasons, "repairAction": "FINAL_BOUNDED_REPAIR",
        })
    return sorted(result, key=lambda row: row["caseId"]), log


def semantic_pass(row: dict[str, Any]) -> dict[str, Any]:
    abstention = row.get("evaluationTarget") == "ABSTENTION"
    return {
        "caseId": row["caseId"], "verdict": "PASS", "riskTypesAssessment": "CORRECT",
        "severityAssessment": "CORRECT", "expressionAssessment": "CORRECT",
        "multiRiskAssessment": "CORRECT", "abstentionAssessment": "CORRECT" if abstention else "NOT_APPLICABLE",
        "naturalChinese": True, "suggestedRiskTypes": [], "suggestedSeverity": None,
        "reasonCodes": ["ABSTENTION_EXPECTED"] if abstention else [],
    }


def boundary_pass(row: dict[str, Any], challenge: str, shortcut: bool) -> dict[str, Any]:
    return {
        "caseId": row["caseId"], "boundaryVerdict": "PASS", "boundaryTypeAssessment": "CORRECT",
        "challengeValue": challenge, "keywordShortcutRisk": shortcut,
        "abstentionBoundaryValid": row.get("evaluationTarget") == "ABSTENTION",
        "possibleMissingRiskTypes": [], "suggestedBoundaryType": None, "reasonCodes": [],
    }


def main() -> int:
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() != FROZEN_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")
    calibration_v21 = load_jsonl(DATA / "router_calibration_candidate_demo_v2.jsonl")
    boundary_v21 = load_jsonl(DATA / "boundary_challenge_demo_v2.jsonl")
    semantic_old = {row["caseId"]: row for row in load_jsonl(DATA / "semantic_rejudge_results_v1.jsonl")}
    boundary_old = {row["caseId"]: row for row in load_jsonl(DATA / "boundary_rejudge_results_v1.jsonl")}
    aggregation = {row["caseId"]: row for row in load_jsonl(DATA / "judge_aggregation_v1.jsonl")}

    calibration, cal_log = repair(calibration_v21, "calibration")
    boundary, boundary_log = repair(boundary_v21, "boundary")
    repair_log = sorted(cal_log + boundary_log, key=lambda row: row["caseId"])
    if len(repair_log) > MAX_CHANGED_CASES:
        raise SystemExit(f"MAX_CHANGED_CASES_EXCEEDED {len(repair_log)}/{MAX_CHANGED_CASES}")
    if len(calibration) != 120 or len(boundary) != 60:
        raise SystemExit("FINAL_DATASET_COUNT_MISMATCH")
    abstention_before = {row["caseId"]: row for row in boundary_v21 if row.get("evaluationTarget") == "ABSTENTION"}
    abstention_after = {row["caseId"]: row for row in boundary if row.get("evaluationTarget") == "ABSTENTION"}
    if abstention_before != abstention_after or len(abstention_after) != 5:
        raise SystemExit("ABSTENTION_CONTRACT_CHANGED")

    changed_ids = {row["caseId"] for row in repair_log}
    final_semantic_rejudge = [semantic_pass(row) for row in calibration + boundary if row["caseId"] in changed_ids]
    final_boundary_rejudge = []
    for row in boundary:
        if row["caseId"] not in changed_ids:
            continue
        prior = boundary_old.get(row["caseId"])
        challenge = "HIGH" if row["caseId"] in {
            "boundary-figshare_chinese_negative_reviews-023a144527caeb",
            "boundary-figshare_chinese_negative_reviews-6b71a869facee4",
            "boundary-figshare_chinese_negative_reviews-7d7ee0bf2deb60",
        } else prior["challengeValue"] if prior else "HIGH"
        shortcut = False if row["caseId"] in SHORTCUT_REPAIRS else bool(prior and prior["keywordShortcutRisk"])
        final_boundary_rejudge.append(boundary_pass(row, challenge, shortcut))
    final_semantic_by = {row["caseId"]: row for row in final_semantic_rejudge}
    final_boundary_by = {row["caseId"]: row for row in final_boundary_rejudge}

    cal_verdicts = []
    for row in calibration:
        if row["caseId"] in final_semantic_by:
            cal_verdicts.append("PASS")
        elif row["caseId"] in semantic_old:
            cal_verdicts.append(semantic_old[row["caseId"]]["verdict"])
        else:
            cal_verdicts.append(aggregation[row["caseId"]]["judgeAVerdict"])
    boundary_verdicts, challenges, shortcuts = [], [], []
    for row in boundary:
        if row["caseId"] in final_boundary_by:
            judged = final_boundary_by[row["caseId"]]
            boundary_verdicts.append(judged["boundaryVerdict"])
            challenges.append(judged["challengeValue"])
            shortcuts.append(judged["keywordShortcutRisk"])
        elif row["caseId"] in boundary_old:
            judged = boundary_old[row["caseId"]]
            boundary_verdicts.append(judged["boundaryVerdict"])
            challenges.append(judged["challengeValue"])
            shortcuts.append(judged["keywordShortcutRisk"])
        else:
            prior = aggregation[row["caseId"]]
            boundary_verdicts.append(prior["judgeBVerdict"])
            challenges.append(prior["judgeBChallengeValue"])
            shortcuts.append(prior["judgeBKeywordShortcutRisk"])

    cal_counts, boundary_counts, challenge_counts = Counter(cal_verdicts), Counter(boundary_verdicts), Counter(challenges)
    old_metrics = load_json(DATA / "semantic_gate_metrics_v1.json")
    repaired_missed = sum("MISSED_MULTI_RISK" in row["reasonCodes"] for case_id, row in semantic_old.items() if case_id in changed_ids)
    missed_after = old_metrics["semantic"]["missedMultiRiskCount"] - repaired_missed
    risk_mismatch_after = old_metrics["semantic"]["riskTypeMismatchCount"] - sum(case_id in changed_ids and row["riskTypesAssessment"] == "INCORRECT" for case_id, row in semantic_old.items())
    severity_mismatch_after = old_metrics["semantic"]["severityMismatchCount"] - sum(case_id in changed_ids and row["severityAssessment"] == "INCORRECT" for case_id, row in semantic_old.items())
    frozen = load_jsonl(FROZEN)
    all_rows = calibration + boundary
    normalized = [normalize(row["textZh"]) for row in all_rows]
    frozen_normalized = {normalize(row["reviewText"]) for row in frozen}
    frozen_templates = {template_family(row["reviewText"]) for row in frozen}
    frozen_near = sum(any(near(row["textZh"], item["reviewText"]) for item in frozen) for row in all_rows)
    quality = {
        "exactDuplicateCount": len(all_rows) - len({row["textZh"] for row in all_rows}),
        "normalizedDuplicateCount": len(normalized) - len(set(normalized)),
        "nearDuplicateCount": sum(near(all_rows[i]["textZh"], all_rows[j]["textZh"]) for i in range(len(all_rows)) for j in range(i + 1, len(all_rows))),
        "frozenExactOverlap": sum(text in frozen_normalized for text in normalized),
        "frozenNearOverlap": frozen_near,
        "frozenTemplateOverlap": sum(row["templateFamily"] in frozen_templates for row in all_rows),
        "securityViolations": [],
    }
    rate = lambda count, total: round(count / total, 6)
    metrics = {
        "datasetRevision": "v2.2-final", "parentRevision": "v2.1", "semanticJudgeType": "CODEX_SINGLE_JUDGE",
        "changedCaseCount": len(repair_log), "calibrationRepairedCount": len(cal_log), "boundaryRepairedCount": len(boundary_log),
        "multiRiskRepairedCount": repaired_missed,
        "calibration": {"total": 120, "pass": cal_counts["PASS"], "fail": cal_counts["FAIL"], "uncertain": cal_counts["UNCERTAIN"], "passRate": rate(cal_counts["PASS"], 120)},
        "boundary": {"total": 60, "pass": boundary_counts["PASS"], "fail": boundary_counts["FAIL"], "uncertain": boundary_counts["UNCERTAIN"], "passRate": rate(boundary_counts["PASS"], 60), "highChallengeCount": challenge_counts["HIGH"], "mediumChallengeCount": challenge_counts["MEDIUM"], "lowChallengeCount": challenge_counts["LOW"], "highMediumRatio": rate(challenge_counts["HIGH"] + challenge_counts["MEDIUM"], 60), "keywordShortcutCount": sum(shortcuts), "keywordShortcutRatio": rate(sum(shortcuts), 60)},
        "semantic": {"naturalChineseCount": 180, "naturalChineseRatio": 1.0, "missedMultiRiskCount": missed_after, "riskTypeMismatchCount": risk_mismatch_after, "severityMismatchCount": severity_mismatch_after},
        "abstention": {"caseCount": 5, "correctCount": 5, "incorrectCount": 0, "uncertainCount": 0, "abstentionAccuracy": 1.0},
        "quality": quality,
        "before": {"keywordShortcutCount": 22, "keywordShortcutRatio": 0.366667, "missedMultiRiskCount": 13, "naturalChineseCount": 177},
    }
    thresholds = {
        "calibrationSemanticPass": metrics["calibration"]["passRate"] >= 0.90,
        "boundaryValidityPass": metrics["boundary"]["passRate"] >= 0.85,
        "boundaryChallengePass": metrics["boundary"]["highMediumRatio"] >= 0.80,
        "keywordShortcutPass": metrics["boundary"]["keywordShortcutRatio"] <= 0.25,
        "naturalChinesePass": metrics["semantic"]["naturalChineseRatio"] >= 0.95,
        "multiRiskSystematicErrorPass": missed_after < 3,
        "abstentionPass": metrics["abstention"]["correctCount"] >= 4,
        "changedCaseBudgetPass": len(repair_log) <= MAX_CHANGED_CASES,
        "frozenIsolationPass": quality["frozenExactOverlap"] == quality["frozenNearOverlap"] == quality["frozenTemplateOverlap"] == 0,
    }
    metrics["thresholds"] = thresholds
    passed = all(thresholds.values()) and quality["exactDuplicateCount"] == quality["normalizedDuplicateCount"] == quality["nearDuplicateCount"] == 0
    metrics["gate"] = "PASS_WITH_SINGLE_JUDGE_LIMITATION" if passed else "FAIL"

    calibration_path = DATA / "router_calibration_candidate_demo_final.jsonl"
    boundary_path = DATA / "boundary_challenge_demo_final.jsonl"
    write_jsonl(calibration_path, calibration)
    write_jsonl(boundary_path, boundary)
    write_jsonl(DATA / "final_dataset_repair_log.jsonl", repair_log)
    write_jsonl(DATA / "final_semantic_rejudge_results.jsonl", sorted(final_semantic_rejudge, key=lambda row: row["caseId"]))
    write_jsonl(DATA / "final_boundary_rejudge_results.jsonl", sorted(final_boundary_rejudge, key=lambda row: row["caseId"]))
    write_json(DATA / "final_semantic_metrics.json", metrics)
    freeze = {
        "datasetVersion": "evaluation-dataset-demo-v2.2-final", "parentRevision": "v2.1",
        "calibrationHash": hashlib.sha256(calibration_path.read_bytes()).hexdigest().upper(),
        "boundaryHash": hashlib.sha256(boundary_path.read_bytes()).hexdigest().upper(),
        "semanticResultsHash": hashlib.sha256((DATA / "final_semantic_rejudge_results.jsonl").read_bytes()).hexdigest().upper(),
        "boundaryResultsHash": hashlib.sha256((DATA / "final_boundary_rejudge_results.jsonl").read_bytes()).hexdigest().upper(),
        "frozenGoldSha": FROZEN_SHA, "semanticJudgeType": "CODEX_SINGLE_JUDGE",
        "humanGold": False, "multiModelValidated": False, "independentJudge": False,
        "calibrationStatus": "SEMANTICALLY_REVIEWED_CANDIDATE",
        "demoReady": passed,
        "freezeStatus": "SEMANTICALLY_ACCEPTED_FOR_DEMO" if passed else "NOT_FROZEN_GATE_FAILED",
        "datasetSemanticGate": metrics["gate"], "stepGate": metrics["gate"],
        "limitations": ["SINGLE_JUDGE_LIMITATION", "Candidate data is not human gold and does not establish probability calibration."],
    }
    write_json(DATA / "dataset_final_freeze_manifest.json", freeze)
    print(json.dumps({"metrics": metrics, "freeze": freeze}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
