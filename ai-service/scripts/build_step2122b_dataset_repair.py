from __future__ import annotations

"""Aggregate independent audits and build the candidate-only Step 21.2.2B v2 datasets."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts.review_semantics import RISK_TYPE_REGISTRY
from app.risk_calibration.severity import RiskSeverityEvaluator


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
SEED = "step21.2.2b-demo-v2-fixed-seed-2122"
BOUNDARY_TARGET = {
    "implicit_or_paraphrase": 15,
    "lexical_mismatch": 10,
    "hard_negative": 15,
    "multi_risk_or_conflict": 10,
    "ambiguous_context": 5,
    "noisy_or_adversarial": 5,
}


# These are candidate boundary probes, not gold. Each is sent to independent rejudge.
BOUNDARY_REPLACEMENTS = [
    ("implicit-06", "售后说公开页面调整妥当，他们就把原本扣着的补偿打过来。", ["review_suppression"], "implicit_or_paraphrase", "implicit"),
    ("implicit-07", "对方暗示把店铺形象维护得漂亮些，答应的心意才会到账。", ["paid_review", "rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-08", "群管理员让没用过商品的人按统一说法分享体验，完成后逐条登记。", ["fake_review"], "implicit_or_paraphrase", "implicit"),
    ("implicit-09", "客服没有直接说改几分，只说页面达到最高档才能申请补偿。", ["rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-10", "先让那段影响店铺形象的内容消失，退货申请才继续往下走。", ["review_suppression", "after_sales_risk"], "implicit_or_paraphrase", "implicit"),
    ("implicit-11", "任务群要求换不同账号写成亲身体验的口吻，结算时只看发布数量。", ["fake_review", "paid_review"], "implicit_or_paraphrase", "implicit"),
    ("implicit-12", "商家说把评价结果再提一档，之前谈好的费用就能报销。", ["paid_review", "rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-13", "对方反复提醒公开记录会影响售后速度，希望我先自行处理掉。", ["review_suppression", "after_sales_risk"], "implicit_or_paraphrase", "implicit"),
    ("implicit-14", "同事收到一批没有真实订单的体验文案，让大家分账号陆续发出。", ["fake_review"], "implicit_or_paraphrase", "implicit"),
    ("implicit-15", "补贴是否发放不看问题是否解决，只看最终展示出来的评价等级。", ["paid_review", "rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-16", "客服说先把公开抱怨收起来，仓库才会确认退货。", ["review_suppression", "after_sales_risk"], "implicit_or_paraphrase", "implicit"),
    ("implicit-17", "没有买过的人照着商家给的体验要点发布，月底统一结算报酬。", ["fake_review", "paid_review"], "implicit_or_paraphrase", "implicit"),
    ("implicit-18", "对方只说把结果做得好看一点，再把页面发给他核对奖励。", ["paid_review", "rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("lexical-06", "把最后一格也点亮，之前谈的补偿才能提交。", ["rating_manipulation"], "lexical_mismatch", "implicit"),
    ("lexical-07", "先让那条不太友好的声音从页面上退场，售后再继续。", ["review_suppression", "after_sales_risk"], "lexical_mismatch", "implicit"),
    ("lexical-08", "店铺找了一批陌生账号照稿描述从未发生过的使用体验。", ["fake_review"], "lexical_mismatch", "implicit"),
    ("lexical-09", "公开反馈每完成一条就记一笔劳务费，内容由品牌方统一提供。", ["fake_review", "paid_review"], "lexical_mismatch", "implicit"),
    ("lexical-10", "客服把补偿分成五档，页面上的亮星越多到账越多。", ["paid_review", "rating_manipulation"], "lexical_mismatch", "implicit"),
    ("hardneg-04", "五星是我按真实体验自己打的，商家从未要求，也没有任何奖励。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-05", "退款到账后我主动更新了评价，客服没有把改分作为退款条件。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-06", "客服同意正常退货，没有提删除差评，也没有要求发送截图。", ["after_sales_risk"], "hard_negative", "mixed"),
    ("hardneg-07", "我看到群里有人说好评返现，但我没有参加，只按真实感受评价。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-08", "订单里的赠品下单时就已注明，与是否评价、打几星都无关。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-09", "截图是为了证明商品破损，不是评价截图，售后已按规则退款。", ["after_sales_risk"], "hard_negative", "mixed"),
    ("hardneg-10", "评论里引用了客服说的‘删差评才退款’，但商家随后否认并直接完成退款。", ["after_sales_risk"], "hard_negative", "mixed"),
    ("hardneg-11", "返现指银行卡重复扣款后的原路退回，与发布评价没有关系。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-12", "朋友推荐我购买，但评论是我实际使用一个月后独立写的。", ["normal_review"], "hard_negative", "implicit"),
    ("hardneg-13", "客服请我如实反馈问题，没有指定正面内容，也没有要求修改星级。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-14", "我自己删掉旧评价重新补充细节，过程中商家没有联系或施压。", ["normal_review"], "hard_negative", "mixed"),
    ("hardneg-15", "页面写着评价后抽奖，但所有评价都能参加，不要求好评或固定分数。", ["paid_review"], "hard_negative", "mixed"),
    ("ambiguous-01", "客服说‘评价处理好以后再联系’，不清楚是指问题处理还是修改评价。", ["low_confidence"], "ambiguous_context", "implicit"),
    ("ambiguous-02", "对方提到会安排一点补偿，但没有说明是否与发布内容或评分有关。", ["low_confidence"], "ambiguous_context", "implicit"),
    ("ambiguous-03", "群里说需要几个人帮店铺，但没有说明是正常试用还是虚构体验。", ["fake_review_suspected"], "ambiguous_context", "implicit"),
    ("ambiguous-04", "客服让我把页面截图发过去，现有上下文无法判断截图是订单还是评价。", ["low_confidence"], "ambiguous_context", "implicit"),
    ("ambiguous-05", "商家说处理完公开内容就退款，但聊天记录缺失，条件关系无法确认。", ["low_confidence"], "ambiguous_context", "implicit"),
    ("noise-06", "评jia到顶→截tu→领h包；旧差P先撤，售hou才走。", ["paid_review", "rating_manipulation", "review_suppression", "after_sales_risk"], "noisy_or_adversarial", "mixed"),
]


TEXT_ROUTER_SCOPE = {
    "normal_review": (True, "RISK_CLASSIFICATION", "文本 Router 的低触达基线类别。"),
    "negative_review": (True, "RISK_CLASSIFICATION", "纯文本可识别的一般负向体验。"),
    "after_sales_risk": (True, "RISK_CLASSIFICATION", "退款、退货、破损和客服争议可由文本表达。"),
    "fake_review": (True, "RISK_CLASSIFICATION", "虚构体验、未购买账号和组织化发布可由文本表达。"),
    "paid_review": (True, "RISK_CLASSIFICATION", "报酬、返利或赠品驱动评价可由文本表达。"),
    "rating_manipulation": (True, "RISK_CLASSIFICATION", "指定星级或集中打分可由文本表达。"),
    "review_suppression": (True, "RISK_CLASSIFICATION", "删除、隐藏或撤回负面评价可由文本表达。"),
    "safety_or_fraud_risk": (True, "RISK_CLASSIFICATION", "文本中的假货、安全或欺诈陈述属于 Router 范围。"),
    "privacy_risk": (True, "RISK_CLASSIFICATION", "文本可直接包含泄露个人信息的陈述；仅做定性 slice。"),
    "harassment_or_abuse": (True, "RISK_CLASSIFICATION", "文本威胁、辱骂和骚扰属于 Router 范围；仅做定性 slice。"),
    "rating_conflict": (False, "OUT_OF_SCOPE_INPUT_REQUIREMENT", "需要 rating 与文本联合输入，不属于 text-only benchmark。"),
    "modality_conflict": (False, "OUT_OF_SCOPE_INPUT_REQUIREMENT", "需要图片等多模态信息。"),
    "low_confidence": (False, "ABSTENTION_SIGNAL", "属于运行时置信状态，不是稳定业务风险类别。"),
    "fake_review_suspected": (False, "ABSTENTION_OR_EVIDENCE_STATE", "属于证据强度不足的中间状态，不作为确定性 text Router 标签计分。"),
    "other": (False, "FALLBACK_ONLY", "迁移与未知风险 fallback，不要求独立类别覆盖。"),
}

OUT_OF_SCOPE_CODES = {code for code, value in TEXT_ROUTER_SCOPE.items() if not value[0]}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def consensus(a: str | None, b: str | None) -> str:
    if a == "UNCERTAIN":
        return "UNCERTAIN"
    if b is None:
        return a or "UNCERTAIN"
    return "PASS" if a == b == "PASS" else "FAIL" if a == b == "FAIL" else "DISAGREEMENT"


def aggregate(v1_rows: list[dict[str, Any]], judge_a: list[dict[str, Any]], judge_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_a = {row["caseId"]: row for row in judge_a}
    by_b = {row["caseId"]: row for row in judge_b}
    if set(by_a) != {row["caseId"] for row in v1_rows}:
        raise SystemExit("JUDGE_A_CASE_COVERAGE_MISMATCH")
    boundary_ids = {row["caseId"] for row in v1_rows if row["boundaryType"]}
    if set(by_b) != boundary_ids:
        raise SystemExit("JUDGE_B_CASE_COVERAGE_MISMATCH")
    result = []
    for row in v1_rows:
        a = by_a[row["caseId"]]
        b = by_b.get(row["caseId"])
        result.append({
            "caseId": row["caseId"],
            "datasetType": "boundary" if row["boundaryType"] else "calibration",
            "originalText": row["textZh"],
            "originalRiskTypes": row["riskTypes"],
            "originalSeverity": row["severity"],
            "originalBoundaryType": row["boundaryType"],
            "sourceDataset": row["sourceDataset"],
            "judgeAVerdict": a["verdict"],
            "judgeARiskAssessment": a["riskTypesAssessment"],
            "judgeASeverityAssessment": a["severityAssessment"],
            "judgeASuggestedRiskTypes": a["suggestedRiskTypes"],
            "judgeASuggestedSeverity": a["suggestedSeverity"],
            "judgeAReasonCodes": a["reasonCodes"],
            "judgeBVerdict": b["boundaryVerdict"] if b else None,
            "judgeBBoundaryAssessment": b["boundaryTypeAssessment"] if b else None,
            "judgeBChallengeValue": b["challengeValue"] if b else None,
            "judgeBKeywordShortcutRisk": b["keywordShortcutRisk"] if b else None,
            "judgeBMissingRiskTypes": b["possibleMissingRiskTypes"] if b else [],
            "judgeBSuggestedBoundaryType": b["suggestedBoundaryType"] if b else None,
            "judgeBReasonCodes": b["reasonCodes"] if b else [],
            "judgeConsensusStatus": consensus(a["verdict"], b["boundaryVerdict"] if b else None),
        })
    return sorted(result, key=lambda row: row["caseId"])


def with_status(row: dict[str, Any], status: str, consensus_status: str, action: str) -> dict[str, Any]:
    value = dict(row)
    value.update({
        "parentVersion": "evaluation-dataset-demo-v1",
        "originalCaseId": row["caseId"],
        "labelStatus": status,
        "judgeConsensusStatus": consensus_status,
        "proposedRiskTypes": None,
        "proposedSeverity": None,
        "repairAction": action,
    })
    cleaned = re.sub(r"\s+", " ", value["textZh"].replace("\\r\\n", " ").replace("&hellip;", "…")).strip()
    if cleaned != value["textZh"]:
        value["textZh"] = cleaned
        value["labelStatus"] = "NEEDS_ADJUDICATION"
        value["repairAction"] = "NORMALIZE_TEXT_ARTIFACT"
        value["proposedRiskTypes"] = list(value["riskTypes"])
        recompute(value)
        value["proposedSeverity"] = value["severity"]
    return value


def recompute(row: dict[str, Any]) -> None:
    row["riskTypes"] = sorted(set(row["riskTypes"]))
    row["multiRisk"] = len(row["riskTypes"]) > 1
    row["severity"] = RiskSeverityEvaluator().evaluate(row["riskTypes"], review_text=row["textZh"]).severity
    row["contentHash"] = sha(row["textZh"])
    row["templateFamily"] = template_family(row["textZh"])


def replacement_case(spec: tuple[str, str, list[str], str, str]) -> dict[str, Any]:
    row_id, text, risks, boundary_type, expression = spec
    row = {
        "caseId": f"boundary-v2-e_review_candidate-{sha(row_id)[:14]}",
        "textZh": text,
        "sourceDataset": "e_review_v2_replacement",
        "sourceRowId": row_id,
        "sourceLanguage": "zh",
        "translationStatus": "native",
        "adaptationStatus": "none",
        "riskTypes": risks,
        "severity": "low",
        "expressionType": expression,
        "difficulty": "hard",
        "multiRisk": len(risks) > 1,
        "ambiguity": boundary_type == "ambiguous_context",
        "boundaryType": boundary_type,
        "labelSource": "llm_assisted_candidate",
        "sourceTier": "project_candidate",
        "externalLabel": None,
        "calibrationStatus": None,
        "contentHash": sha(text),
        "templateFamily": template_family(text),
        "parentVersion": "evaluation-dataset-demo-v1",
        "originalCaseId": None,
        "labelStatus": "NEEDS_ADJUDICATION",
        "judgeConsensusStatus": "UNCERTAIN",
        "proposedRiskTypes": sorted(risks),
        "proposedSeverity": None,
        "repairAction": "NEW_BOUNDARY_REPLACEMENT",
    }
    recompute(row)
    row["proposedSeverity"] = row["severity"]
    return row


def apply_judge_a_repair(row: dict[str, Any], audit: dict[str, Any]) -> bool:
    suggested = sorted(set(audit["judgeASuggestedRiskTypes"]))
    if not suggested or not set(suggested).issubset(RISK_TYPE_REGISTRY):
        return False
    # Only project-authored cases with explicit missed multi-risk semantics are auto-proposed.
    if row["sourceDataset"] != "e_review_expert_designed" or "MISSED_MULTI_RISK" not in audit["judgeAReasonCodes"]:
        return False
    row["riskTypes"] = suggested
    recompute(row)
    row["proposedRiskTypes"] = suggested
    row["proposedSeverity"] = row["severity"]
    row["labelStatus"] = "PROPOSED_REPAIRED"
    row["repairAction"] = "PROPOSE_MULTI_RISK_REPAIR"
    return True


def build_calibration(v1: list[dict[str, Any]], audits: dict[str, dict[str, Any]], boundary_v1: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, log = [], []
    drift = []
    for original in v1:
        audit = audits[original["caseId"]]
        if "TRANSLATION_DRIFT" in audit["judgeAReasonCodes"]:
            drift.append(original)
            continue
        if audit["judgeAVerdict"] == "PASS":
            current = with_status(original, "ORIGINAL_ACCEPTED", "PASS", "KEEP")
        elif audit["judgeAVerdict"] == "UNCERTAIN":
            current = with_status(original, "NEEDS_ADJUDICATION", "UNCERTAIN", "HUMAN_OR_REJUDGE")
            current["proposedRiskTypes"] = audit["judgeASuggestedRiskTypes"] or None
            current["proposedSeverity"] = audit["judgeASuggestedSeverity"]
        else:
            current = with_status(original, "NEEDS_ADJUDICATION", "FAIL", "LABEL_REPAIR_REQUIRED")
            current["proposedRiskTypes"] = audit["judgeASuggestedRiskTypes"] or None
            current["proposedSeverity"] = audit["judgeASuggestedSeverity"]
            apply_judge_a_repair(current, audit)
        rows.append(current)
        if current["repairAction"] != "KEEP":
            log.append(repair_record(original, current, audit))

    move_candidates = [row for row in boundary_v1 if audits[row["caseId"]]["judgeAVerdict"] == "PASS" and audits[row["caseId"]]["judgeBVerdict"] == "FAIL" and row["translationStatus"] == "native"]
    if len(move_candidates) < len(drift):
        raise SystemExit("CALIBRATION_NATIVE_REPLACEMENT_SHORTFALL")
    for original, moved_source in zip(drift, sorted(move_candidates, key=lambda row: row["caseId"])):
        moved = with_status(moved_source, "ORIGINAL_ACCEPTED", "PASS", "MOVE_TO_CALIBRATION_CANDIDATE")
        moved["caseId"] = f"cal-v2-moved-{sha(moved_source['caseId'])[:14]}"
        moved["originalCaseId"] = moved_source["caseId"]
        moved["boundaryType"] = None
        moved["ambiguity"] = False
        moved["calibrationStatus"] = "CANDIDATE_ONLY"
        moved["difficulty"] = "hard"
        recompute(moved)
        rows.append(moved)
        drift_audit = audits[original["caseId"]]
        log.append(repair_record(original, moved, drift_audit, action="REPLACE_TRANSLATION_DRIFT_WITH_NATIVE"))
    return sorted(rows, key=lambda row: row["caseId"]), log


def build_boundary(v1: list[dict[str, Any]], audits: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept, replaced, log = [], [], []
    for original in v1:
        audit = audits[original["caseId"]]
        if audit["judgeBVerdict"] != "PASS":
            replaced.append(original)
            continue
        if audit["judgeAVerdict"] == "PASS":
            current = with_status(original, "ORIGINAL_ACCEPTED", "PASS", "KEEP")
        elif audit["judgeAVerdict"] == "UNCERTAIN":
            current = with_status(original, "NEEDS_ADJUDICATION", "UNCERTAIN", "HUMAN_OR_REJUDGE")
            current["proposedRiskTypes"] = audit["judgeASuggestedRiskTypes"] or None
            current["proposedSeverity"] = audit["judgeASuggestedSeverity"]
        else:
            current = with_status(original, "NEEDS_ADJUDICATION", "DISAGREEMENT", "LABEL_REPAIR_REQUIRED")
            current["proposedRiskTypes"] = audit["judgeASuggestedRiskTypes"] or None
            current["proposedSeverity"] = audit["judgeASuggestedSeverity"]
            apply_judge_a_repair(current, audit)
        kept.append(current)
        if current["repairAction"] != "KEEP":
            log.append(repair_record(original, current, audit))

    new_rows = [replacement_case(spec) for spec in BOUNDARY_REPLACEMENTS]
    if len(replaced) != len(new_rows):
        raise SystemExit(f"BOUNDARY_REPLACEMENT_COUNT_MISMATCH old={len(replaced)} new={len(new_rows)}")
    for original, new in zip(sorted(replaced, key=lambda row: row["caseId"]), sorted(new_rows, key=lambda row: row["caseId"])):
        audit = audits[original["caseId"]]
        log.append(repair_record(original, new, audit, action="REPLACE_LOW_QUALITY_BOUNDARY"))
    return sorted(kept + new_rows, key=lambda row: row["caseId"]), log


def apply_scope_consistency_patch(rows: list[dict[str, Any]]) -> list[str]:
    patched = []
    for row in rows:
        out_of_scope = sorted(set(row["riskTypes"]) & OUT_OF_SCOPE_CODES)
        if not out_of_scope:
            continue
        if row["boundaryType"] != "ambiguous_context":
            raise SystemExit(f"OUT_OF_SCOPE_CLASSIFICATION_GOLD {row['caseId']}")
        row["provenanceRiskTypes"] = list(row["riskTypes"])
        row["riskTypes"] = []
        row["benchmarkRiskTypes"] = []
        row["evaluationTarget"] = "ABSTENTION"
        row["expectedDisposition"] = "ESCALATE_OR_ABSTAIN"
        row["excludeFromRiskTypeMetrics"] = True
        row["multiRisk"] = False
        row["proposedRiskTypes"] = []
        # Medium here describes escalation priority, not a classified business risk.
        row["severity"] = "medium"
        row["proposedSeverity"] = "medium"
        row["scopePatchAction"] = "CLASSIFICATION_TO_ABSTENTION"
        row["contentHash"] = sha(row["textZh"])
        patched.append(row["caseId"])
    return patched


def repair_record(original: dict[str, Any], new: dict[str, Any], audit: dict[str, Any], action: str | None = None) -> dict[str, Any]:
    return {
        "originalCaseId": original["caseId"],
        "newCaseId": new["caseId"],
        "originalRiskTypes": original["riskTypes"],
        "newProposedRiskTypes": new.get("proposedRiskTypes") or new["riskTypes"],
        "originalSeverity": original["severity"],
        "newProposedSeverity": new.get("proposedSeverity") or new["severity"],
        "originalBoundaryType": original["boundaryType"],
        "newBoundaryType": new["boundaryType"],
        "judgeAReasons": audit["judgeAReasonCodes"],
        "judgeBReasons": audit["judgeBReasonCodes"],
        "repairAction": action or new["repairAction"],
        "labelStatus": new["labelStatus"],
    }


def distributions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sourceDistribution": dict(Counter(row["sourceDataset"] for row in rows)),
        "riskDistribution": dict(Counter(risk for row in rows for risk in row["riskTypes"])),
        "severityDistribution": dict(Counter(row["severity"] for row in rows)),
        "expressionDistribution": dict(Counter(row["expressionType"] for row in rows)),
        "difficultyDistribution": dict(Counter(row["difficulty"] for row in rows)),
        "boundaryDistribution": dict(Counter(row["boundaryType"] for row in rows if row["boundaryType"])),
        "labelStatusDistribution": dict(Counter(row["labelStatus"] for row in rows)),
        "judgeConsensusDistribution": dict(Counter(row["judgeConsensusStatus"] for row in rows)),
        "multiRiskCount": sum(row["multiRisk"] for row in rows),
        "ambiguityCount": sum(row["ambiguity"] for row in rows),
        "nativeChineseCount": sum(row["translationStatus"] == "native" for row in rows),
        "translatedCount": sum(row["translationStatus"] == "translated" for row in rows),
        "businessAdaptedCount": sum(row["adaptationStatus"] == "business_adapted" for row in rows),
        "templateFamilyCount": len({row["templateFamily"] for row in rows}),
    }


def keyword_shortcut_estimate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = ("返现", "红包", "五星", "好评", "删差评", "删除评价", "刷单", "虚假评价", "统一模板", "威胁", "身份证", "手机号")
    vulnerable = 0
    counter_signal = 0
    for row in rows:
        has_keyword = any(term in row["textZh"] for term in canonical)
        governance_risk = any(risk not in {"normal_review", "negative_review", "after_sales_risk", "low_confidence", "fake_review_suspected"} for risk in row["riskTypes"])
        vulnerable += int(has_keyword and governance_risk and row["expressionType"] == "explicit")
        counter_signal += int(has_keyword and not governance_risk)
    return {"estimatedShortcutVulnerableCount": vulnerable, "keywordCounterSignalCount": counter_signal, "method": "deterministic lexical estimate; not a model score"}


def quality(calibration: list[dict[str, Any]], boundary: list[dict[str, Any]], frozen: list[dict[str, Any]]) -> dict[str, Any]:
    rows = calibration + boundary
    required = {"caseId", "textZh", "riskTypes", "severity", "boundaryType", "labelStatus", "judgeConsensusStatus", "contentHash"}
    schema_errors = [row["caseId"] for row in rows if not required.issubset(row)]
    risk_errors = [row["caseId"] for row in rows if not set(row["riskTypes"]).issubset(RISK_TYPE_REGISTRY)]
    severity_errors = [row["caseId"] for row in rows if row.get("evaluationTarget", "RISK_CLASSIFICATION") == "RISK_CLASSIFICATION" and row["severity"] != RiskSeverityEvaluator().evaluate(row["riskTypes"], review_text=row["textZh"]).severity]
    normalized = [normalize(row["textZh"]) for row in rows]
    near_duplicates = sum(near(rows[i]["textZh"], rows[j]["textZh"]) for i in range(len(rows)) for j in range(i + 1, len(rows)))
    frozen_normalized = {normalize(row["reviewText"]) for row in frozen}
    frozen_templates = {template_family(row["reviewText"]) for row in frozen}
    frozen_near = sum(any(near(row["textZh"], item["reviewText"]) for item in frozen) for row in rows)
    bad_naturalness = [row["caseId"] for row in rows if len(re.findall(r"[\u4e00-\u9fff]", row["textZh"])) < 4 or "\\r\\n" in row["textZh"] or "&hellip;" in row["textZh"]]
    boundary_actual = Counter(row["boundaryType"] for row in boundary)
    security_payload = json.dumps(rows, ensure_ascii=False).lower()
    security_violations = []
    for pattern, name in ((r"[a-z]:\\", "private_absolute_path"), (r"authorization\s*[=:]", "authorization"), (r"api[_-]?key\s*[=:]", "api_key"), (r"chain.of.thought", "chain_of_thought"), (r"reviewer(identity|id|name)", "reviewer_identity")):
        if re.search(pattern, security_payload, re.I):
            security_violations.append(name)
    return {
        "schemaValid": not schema_errors,
        "schemaErrors": schema_errors,
        "riskTypeValid": not risk_errors,
        "riskTypeErrors": risk_errors,
        "severityRegistryValid": not severity_errors,
        "severityErrors": severity_errors,
        "exactDuplicateCount": len(rows) - len({row["textZh"] for row in rows}),
        "normalizedDuplicateCount": len(normalized) - len(set(normalized)),
        "nearDuplicateCount": near_duplicates,
        "templateFamilyCount": len({row["templateFamily"] for row in rows}),
        "frozenExactOverlap": sum(item in frozen_normalized for item in normalized),
        "frozenNearOverlap": frozen_near,
        "frozenTemplateOverlap": sum(row["templateFamily"] in frozen_templates for row in rows),
        "chineseNaturalnessHeuristicFailures": bad_naturalness,
        "boundaryExpected": BOUNDARY_TARGET,
        "boundaryActual": dict(boundary_actual),
        "keywordShortcutEstimate": keyword_shortcut_estimate(boundary),
        "securityViolations": security_violations,
    }


def frozen_aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "caseCount": len(rows),
        "riskDistribution": dict(Counter(risk for row in rows for risk in row.get("expectedRiskTypes", []))),
        "routeDistribution": dict(Counter(row.get("expectedRoute") for row in rows)),
        "decisionDistribution": dict(Counter(row.get("expectedDecision") for row in rows)),
        "languageDistribution": dict(Counter(row.get("language") for row in rows)),
        "multiRiskCount": sum(len(row.get("expectedRiskTypes", [])) > 1 for row in rows),
        "auditMode": "read_only_aggregate",
    }


def build_queue(calibration: list[dict[str, Any]], boundary: list[dict[str, Any]], repair_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    log_by_new = {row["newCaseId"]: row for row in repair_log}
    queue = []
    for row in calibration + boundary:
        reasons = []
        if row["labelStatus"] != "ORIGINAL_ACCEPTED":
            reasons.append(row["labelStatus"])
        if row["judgeConsensusStatus"] in {"UNCERTAIN", "DISAGREEMENT"}:
            reasons.append(row["judgeConsensusStatus"])
        if row["repairAction"] == "NEW_BOUNDARY_REPLACEMENT":
            reasons.append("NEW_BOUNDARY")
        repair = log_by_new.get(row["caseId"])
        if repair and (repair["originalRiskTypes"] != repair["newProposedRiskTypes"] or repair["originalSeverity"] != repair["newProposedSeverity"]):
            reasons.append("LABEL_OR_SEVERITY_REPAIR")
        if row["translationStatus"] == "translated" and row["labelStatus"] != "ORIGINAL_ACCEPTED":
            reasons.append("TRANSLATED_CASE")
        if reasons:
            queue.append({
                "caseId": row["caseId"],
                "datasetType": "boundary" if row["boundaryType"] else "calibration",
                "textZh": row["textZh"],
                "riskTypes": row["riskTypes"],
                "severity": row["severity"],
                "expressionType": row["expressionType"],
                "ambiguity": row["ambiguity"],
                "boundaryType": row["boundaryType"],
                "evaluationTarget": row.get("evaluationTarget", "RISK_CLASSIFICATION"),
                "expectedDisposition": row.get("expectedDisposition", "CLASSIFY_RISK"),
                "benchmarkRiskTypes": row.get("benchmarkRiskTypes", row["riskTypes"]),
                "excludeFromRiskTypeMetrics": row.get("excludeFromRiskTypeMetrics", False),
                "labelStatus": row["labelStatus"],
                "queueReasons": sorted(set(reasons)),
            })
    return sorted(queue, key=lambda row: row["caseId"])


def write_batches(queue: list[dict[str, Any]]) -> dict[str, Any]:
    batch_dir = DATA / "rejudge_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for path in batch_dir.glob("*.json"):
        path.unlink()
    judge_a = [{
        "caseId": row["caseId"],
        "datasetType": row["datasetType"],
        "textZh": row["textZh"],
        "evaluationTarget": row.get("evaluationTarget", "RISK_CLASSIFICATION"),
        "expectedDisposition": row.get("expectedDisposition", "CLASSIFY_RISK"),
        "benchmarkRiskTypes": row.get("benchmarkRiskTypes", row["riskTypes"]),
        "severity": row["severity"],
        "expressionType": row["expressionType"],
        "ambiguity": row["ambiguity"],
        "boundaryType": row["boundaryType"],
    } for row in queue]
    judge_b = [{
        "caseId": row["caseId"],
        "textZh": row["textZh"],
        "evaluationTarget": row.get("evaluationTarget", "RISK_CLASSIFICATION"),
        "expectedDisposition": row.get("expectedDisposition", "CLASSIFY_RISK"),
        "benchmarkRiskTypes": row.get("benchmarkRiskTypes", row["riskTypes"]),
        "severity": row["severity"],
        "expressionType": row["expressionType"],
        "ambiguity": row["ambiguity"],
        "boundaryType": row["boundaryType"],
    } for row in queue if row["datasetType"] == "boundary"]
    counts = {}
    for name, rows in (("judge_a_recheck", judge_a), ("judge_b_boundary_recheck", judge_b)):
        chunks = [rows[i:i + 20] for i in range(0, len(rows), 20)]
        for index, chunk in enumerate(chunks, 1):
            write_json(batch_dir / f"{name}_{index:02d}.json", {"batchType": name, "items": chunk})
        counts[name] = {"itemCount": len(rows), "batchCount": len(chunks)}
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-a", required=True, type=Path)
    parser.add_argument("--judge-b", required=True, type=Path)
    parser.add_argument("--judge-c", required=True, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() != FROZEN_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")

    calibration_v1 = load_jsonl(DATA / "router_calibration_candidate_demo_v1.jsonl")
    boundary_v1 = load_jsonl(DATA / "boundary_challenge_demo_v1.jsonl")
    frozen = load_jsonl(FROZEN)
    judge_a, judge_b, judge_c = load_json(args.judge_a), load_json(args.judge_b), load_json(args.judge_c)
    aggregation = aggregate(calibration_v1 + boundary_v1, judge_a, judge_b)
    audits = {row["caseId"]: row for row in aggregation}
    calibration_v2, cal_log = build_calibration(calibration_v1, audits, boundary_v1)
    boundary_v2, boundary_log = build_boundary(boundary_v1, audits)
    abstention_case_ids = apply_scope_consistency_patch(boundary_v2)
    if len(calibration_v2) != 120 or len(boundary_v2) != 60:
        raise SystemExit(f"V2_COUNT_MISMATCH calibration={len(calibration_v2)} boundary={len(boundary_v2)}")

    repair_log = sorted(cal_log + boundary_log, key=lambda row: (row["originalCaseId"], row["newCaseId"]))
    for record in repair_log:
        if record["newCaseId"] in abstention_case_ids:
            record["newProposedRiskTypes"] = []
            record["newProposedSeverity"] = "medium"
            record["scopePatchAction"] = "CLASSIFICATION_TO_ABSTENTION"
    quality_report = quality(calibration_v2, boundary_v2, frozen)
    queue = build_queue(calibration_v2, boundary_v2, repair_log)
    batch_counts = write_batches(queue)
    scope = {
        "scopeVersion": "text-router-benchmark-scope-v1",
        "scopePatchVersion": "step21.2.2b.1",
        "risks": [{"riskCode": code, "inScope": value[0], "benchmarkRole": value[1], "reason": value[2]} for code, value in sorted(TEXT_ROUTER_SCOPE.items())],
    }
    if {row["riskCode"] for row in scope["risks"]} != set(RISK_TYPE_REGISTRY):
        raise SystemExit("TEXT_ROUTER_SCOPE_REGISTRY_MISMATCH")

    c_resolution = {
        "sourceAuditSha256": hashlib.sha256(args.judge_c.read_bytes()).hexdigest().upper(),
        "sourceOverallVerdict": judge_c.get("overallVerdict"),
        "findings": [
            {"finding": "Boundary quality", "status": "PARTIAL", "resolution": "36 Judge-B-failed rows replaced; all new rows remain pending independent rejudge."},
            {"finding": "Semantic label quality", "status": "PARTIAL", "resolution": "Judge aggregation and proposed repair provenance added; no proposal is human gold."},
            {"finding": "Text Router scope", "status": "RESOLVED", "resolution": "All 15 registry codes explicitly classified in or out of text-only benchmark scope."},
            {"finding": "Frozen aggregate audit", "status": "RESOLVED", "resolution": "Read-only aggregate distribution recorded without case-driven repair."},
            {"finding": "Frozen isolation", "status": "RESOLVED", "resolution": "Exact, near, and template overlap gates rerun against unchanged SHA."},
            {"finding": "Multi-risk labeling", "status": "PARTIAL", "resolution": "Clear project-authored missed labels proposed and queued for rejudge."},
            {"finding": "Translation drift", "status": "PARTIAL", "resolution": "Calibration drift rows replaced with native Chinese; retained translated candidates still require rejudge when modified."},
        ],
    }

    write_jsonl(DATA / "judge_aggregation_v1.jsonl", aggregation)
    write_jsonl(DATA / "router_calibration_candidate_demo_v2.jsonl", calibration_v2)
    write_jsonl(DATA / "boundary_challenge_demo_v2.jsonl", boundary_v2)
    write_jsonl(DATA / "dataset_repair_log_v1.jsonl", repair_log)
    write_jsonl(DATA / "dataset_rejudge_queue_v1.jsonl", queue)
    write_json(DATA / "text_router_benchmark_scope_v1.json", scope)
    write_json(DATA / "text_router_metric_contract_v1.json", {
        "contractVersion": "text-router-metrics-v1",
        "scopePatchVersion": "step21.2.2b.1",
        "defaultEvaluationTarget": "RISK_CLASSIFICATION",
        "riskClassificationEligibility": "evaluationTarget == RISK_CLASSIFICATION",
        "abstentionEligibility": "evaluationTarget == ABSTENTION",
        "riskMetrics": ["precision", "recall", "f1", "accuracy"],
        "abstentionMetrics": {
            "abstentionAccuracy": "correct abstain/escalate/needs-more-context outcomes divided by ABSTENTION cases",
            "escalationAccuracy": "correct escalate or needs-more-context outcomes divided by ABSTENTION cases",
            "falseConfidentClassificationCount": "ABSTENTION cases receiving a confident business risk classification",
        },
    })
    write_json(DATA / "judge_c_findings_resolution.json", c_resolution)

    repair_counts = Counter(row["repairAction"] for row in repair_log)
    gates = {
        "JUDGE_AGGREGATION_GATE": "PASS" if len(aggregation) == 180 else "FAIL",
        "CALIBRATION_REPAIR_GATE": "PASS" if len(calibration_v2) == 120 and all(row["labelStatus"] in {"ORIGINAL_ACCEPTED", "PROPOSED_REPAIRED", "NEEDS_ADJUDICATION"} for row in calibration_v2) else "FAIL",
        "BOUNDARY_REPAIR_GATE": "PASS" if len(boundary_v2) == 60 and dict(Counter(row["boundaryType"] for row in boundary_v2)) == BOUNDARY_TARGET else "FAIL",
        "TEXT_ROUTER_SCOPE_GATE": "PASS" if len(scope["risks"]) == len(RISK_TYPE_REGISTRY) else "FAIL",
        "FROZEN_ISOLATION_GATE": "PASS" if quality_report["frozenExactOverlap"] == quality_report["frozenNearOverlap"] == quality_report["frozenTemplateOverlap"] == 0 else "FAIL",
        "REJUDGE_BATCH_GATE": "PASS" if queue and all(info["itemCount"] <= info["batchCount"] * 20 for info in batch_counts.values()) else "FAIL",
        "TEXT_ROUTER_SCOPE_CONSISTENCY_GATE": "PASS" if len(abstention_case_ids) == 5 and not any(set(row.get("benchmarkRiskTypes", row["riskTypes"])) & OUT_OF_SCOPE_CODES for row in calibration_v2 + boundary_v2 if row.get("evaluationTarget", "RISK_CLASSIFICATION") == "RISK_CLASSIFICATION") else "FAIL",
        "ABSTENTION_EVALUATION_GATE": "PASS" if len(abstention_case_ids) == 5 and all(row.get("excludeFromRiskTypeMetrics") for row in boundary_v2 if row["caseId"] in abstention_case_ids) else "FAIL",
        "BOUNDARY_COUNT_GATE": "PASS" if len(boundary_v2) == 60 else "FAIL",
        "REJUDGE_BATCH_SCOPE_GATE": "PASS" if all(row["caseId"] in {item["caseId"] for item in queue} for row in boundary_v2 if row.get("evaluationTarget") == "ABSTENTION") else "FAIL",
        "SECURITY_GATE": "PASS" if not quality_report["securityViolations"] else "FAIL",
    }
    deterministic_gate = (
        not quality_report["schemaErrors"] and not quality_report["riskTypeErrors"] and not quality_report["severityErrors"]
        and quality_report["exactDuplicateCount"] == quality_report["normalizedDuplicateCount"] == quality_report["nearDuplicateCount"] == 0
        and not quality_report["chineseNaturalnessHeuristicFailures"] and not quality_report["securityViolations"]
    )
    manifest = {
        "datasetVersion": "evaluation-dataset-demo-v2",
        "datasetRevision": "v2.1",
        "scopePatchVersion": "step21.2.2b.1",
        "parentVersion": "evaluation-dataset-demo-v1",
        "repairSource": "multi_prompt_judge",
        "fixedSeed": SEED,
        "frozenGoldSha256": FROZEN_SHA,
        "calibrationCount": len(calibration_v2),
        "boundaryCount": len(boundary_v2),
        "frozenCount": len(frozen),
        "judgeSummary": {
            "judgeA": dict(Counter(row["judgeAVerdict"] for row in aggregation)),
            "judgeB": dict(Counter(row["judgeBVerdict"] for row in aggregation if row["judgeBVerdict"])),
            "consensus": dict(Counter(row["judgeConsensusStatus"] for row in aggregation)),
        },
        "repairSummary": {
            "keptCount": sum(row["repairAction"] == "KEEP" for row in calibration_v2 + boundary_v2),
            "relabelCandidateCount": sum(row["repairAction"] in {"PROPOSE_MULTI_RISK_REPAIR", "LABEL_REPAIR_REQUIRED"} for row in calibration_v2 + boundary_v2),
            "movedCount": sum(row["repairAction"] == "MOVE_TO_CALIBRATION_CANDIDATE" for row in calibration_v2),
            "replacedCount": repair_counts["REPLACE_LOW_QUALITY_BOUNDARY"] + repair_counts["REPLACE_TRANSLATION_DRIFT_WITH_NATIVE"],
            "retranslatedCount": 0,
            "newCaseCount": sum(row["repairAction"] == "NEW_BOUNDARY_REPLACEMENT" for row in boundary_v2),
        },
        "calibration": distributions(calibration_v2),
        "boundary": distributions(boundary_v2),
        "frozenAggregateAudit": frozen_aggregate(frozen),
        "quality": quality_report,
        "rejudge": {"queueCount": len(queue), "batches": batch_counts},
        "benchmarkScopeSummary": {
            "riskClassificationCaseCount": sum(row.get("evaluationTarget", "RISK_CLASSIFICATION") == "RISK_CLASSIFICATION" for row in calibration_v2 + boundary_v2),
            "abstentionCaseCount": len(abstention_case_ids),
            "outOfScopeRiskCodeAsClassificationGoldCount": sum(bool(set(row.get("benchmarkRiskTypes", row["riskTypes"])) & OUT_OF_SCOPE_CODES) for row in calibration_v2 + boundary_v2 if row.get("evaluationTarget", "RISK_CLASSIFICATION") == "RISK_CLASSIFICATION"),
            "abstentionCaseIds": sorted(abstention_case_ids),
        },
        "gates": gates,
        "deterministicValidationGate": "PASS" if deterministic_gate else "FAIL",
        "datasetHashes": {},
        "datasetSemanticGate": "PENDING_INDEPENDENT_REJUDGE",
    }
    all_pass = all(value == "PASS" for value in gates.values()) and deterministic_gate
    manifest["gate"] = "PASS" if all_pass else "FAIL"
    write_json(DATA / "dataset_manifest_demo_v2.json", manifest)
    manifest["datasetHashes"] = {
        "calibration": hashlib.sha256((DATA / "router_calibration_candidate_demo_v2.jsonl").read_bytes()).hexdigest().upper(),
        "boundary": hashlib.sha256((DATA / "boundary_challenge_demo_v2.jsonl").read_bytes()).hexdigest().upper(),
        "aggregation": hashlib.sha256((DATA / "judge_aggregation_v1.jsonl").read_bytes()).hexdigest().upper(),
        "repairLog": hashlib.sha256((DATA / "dataset_repair_log_v1.jsonl").read_bytes()).hexdigest().upper(),
        "rejudgeQueue": hashlib.sha256((DATA / "dataset_rejudge_queue_v1.jsonl").read_bytes()).hexdigest().upper(),
    }
    write_json(DATA / "dataset_manifest_demo_v2.json", manifest)
    print(json.dumps({"gate": manifest["gate"], "counts": [len(calibration_v2), len(boundary_v2)], "repair": manifest["repairSummary"], "queue": manifest["rejudge"], "quality": quality_report, "gates": gates}, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
