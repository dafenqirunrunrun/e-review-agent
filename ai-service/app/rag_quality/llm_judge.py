from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


JUDGE_PROTOCOL_VERSION = "rag-quality-llm-judge-v1"
ALLOWED_RISK_TYPES = (
    "fake_review",
    "rating_manipulation",
    "review_suppression",
    "privacy_risk",
    "after_sales_risk",
    "safety_or_fraud_risk",
    "harassment_or_abuse",
)

RISK_GUIDE = {
    "fake_review": "并非真实消费体验、编造体验、组织员工或多账号伪装消费者评价",
    "rating_manipulation": "返现、奖励、指定星级、集中打分等方式影响评分真实性",
    "review_suppression": "删除、隐藏、屏蔽、威胁或以售后为条件干预负面评价",
    "privacy_risk": "未经同意公开姓名、电话、地址、身份信息或私人记录",
    "after_sales_risk": "退款、退货、维修、物流、售后记录或服务主体争议",
    "safety_or_fraud_risk": "商品危及人身财产安全、假货、欺诈或重大误导",
    "harassment_or_abuse": "持续辱骂、骚扰、人身威胁、煽动围攻或跟踪施压",
}


@dataclass(frozen=True)
class BlindJudgeCase:
    case_id: str
    review_text: str


def build_blind_prompt(cases: Iterable[BlindJudgeCase], *, pass_name: str) -> str:
    """Build a label-blind prompt: proposed labels and qrels are never included."""

    normalized = list(cases)
    guide = "\n".join(f"- {code}: {RISK_GUIDE[code]}" for code in ALLOWED_RISK_TYPES)
    payload = [{"caseId": item.case_id, "reviewText": item.review_text} for item in normalized]
    if pass_name == "recall_first":
        policy = (
            "先识别明确或语义等价的治理风险；否定、引用他人说法和已明确排除的风险不得误判。"
            "同一评论可以有多个风险，但不要添加仅有弱背景关联的类型。"
        )
    elif pass_name == "precision_challenge":
        policy = (
            "以反证视角复核：重点识别否定、正常售后、个人偏好和仅讨论规则的文本。"
            "只有评论陈述的实际事件满足定义时才标风险；明确风险不得因表达委婉而漏掉。"
        )
    else:
        raise ValueError(f"UNKNOWN_JUDGE_PASS:{pass_name}")
    return (
        "你是独立的电商评论治理数据审核员。不得猜测未写出的事实。\n"
        f"审核协议：{JUDGE_PROTOCOL_VERSION}\n"
        f"本轮规则：{policy}\n"
        "允许的风险类型只有：\n"
        f"{guide}\n"
        "riskTypes 为空表示该评论不需要上述政策证据。\n"
        "confidence 是 0 到 100 的整数，表示你对该标签的把握，不是风险严重度。\n"
        "只输出一个 JSON 对象。根对象只能有 cases 字段；cases 必须是数组。"
        "为减少输出，每个 case 只允许 caseId、riskTypes、confidence 三个字段。"
        "不要输出 noAnswer、reasonCodes 或解释。"
        "不要复制格式说明中的占位内容。"
        "必须逐条返回且不得增删 caseId。\n"
        f"待审核数据：{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def parse_blind_judge_output(raw_text: str, expected_case_ids: Iterable[str]) -> list[dict[str, Any]]:
    expected = list(expected_case_ids)
    payload = _extract_json_value(raw_text)
    rows = payload if isinstance(payload, list) else payload.get("cases")
    if not isinstance(rows, list):
        raise ValueError("LLM_JUDGE_CASES_ARRAY_MISSING")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if isinstance(raw, list) and len(raw) == 5:
            raw = {
                "caseId": raw[0],
                "riskTypes": raw[1],
                "noAnswer": raw[2],
                "confidence": float(raw[3]) / 100.0 if isinstance(raw[3], int) and not isinstance(raw[3], bool) else raw[3],
                "reasonCodes": raw[4],
            }
        if not isinstance(raw, dict):
            raise ValueError("LLM_JUDGE_CASE_NOT_OBJECT")
        case_id = str(raw.get("caseId") or "").strip()
        if not case_id or case_id in by_id:
            raise ValueError("LLM_JUDGE_CASE_ID_INVALID")
        risks = raw.get("riskTypes")
        if not isinstance(risks, list):
            raise ValueError(f"LLM_JUDGE_RISK_TYPES_INVALID:{case_id}")
        normalized_risks = sorted({str(item).strip() for item in risks if str(item).strip()})
        unknown = sorted(set(normalized_risks) - set(ALLOWED_RISK_TYPES))
        if unknown:
            raise ValueError(f"LLM_JUDGE_UNKNOWN_RISK_TYPE:{case_id}:{','.join(unknown)}")
        no_answer = raw.get("noAnswer", not normalized_risks)
        if not isinstance(no_answer, bool):
            raise ValueError(f"LLM_JUDGE_NO_ANSWER_INVALID:{case_id}")
        if no_answer != (not normalized_risks):
            raise ValueError(f"LLM_JUDGE_NO_ANSWER_CONTRADICTION:{case_id}")
        confidence = raw.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError(f"LLM_JUDGE_CONFIDENCE_INVALID:{case_id}")
        confidence = float(confidence)
        if confidence > 1.0 and confidence <= 100.0:
            confidence /= 100.0
        confidence = round(confidence, 4)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"LLM_JUDGE_CONFIDENCE_RANGE:{case_id}")
        reason_codes = raw.get("reasonCodes") or (["RISK_TYPES_PRESENT"] if normalized_risks else ["NO_POLICY_RISK"])
        if not isinstance(reason_codes, list):
            raise ValueError(f"LLM_JUDGE_REASON_CODES_INVALID:{case_id}")
        by_id[case_id] = {
            "caseId": case_id,
            "riskTypes": normalized_risks,
            "noAnswer": no_answer,
            "confidence": confidence,
            "reasonCodes": [str(item).strip()[:80] for item in reason_codes if str(item).strip()][:6],
        }
    if set(by_id) != set(expected):
        missing = sorted(set(expected) - set(by_id))
        extra = sorted(set(by_id) - set(expected))
        raise ValueError(f"LLM_JUDGE_CASE_SET_MISMATCH missing={missing} extra={extra}")
    return [by_id[case_id] for case_id in expected]


def judge_agreement(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_risks = set(first["riskTypes"])
    second_risks = set(second["riskTypes"])
    exact = first_risks == second_risks and first["noAnswer"] == second["noAnswer"]
    union = first_risks | second_risks
    intersection = first_risks & second_risks
    return {
        "exact": exact,
        "riskJaccard": round(len(intersection) / len(union), 6) if union else 1.0,
        "agreedRiskTypes": sorted(intersection),
        "disputedRiskTypes": sorted(first_risks ^ second_risks),
        "minimumConfidence": min(float(first["confidence"]), float(second["confidence"])),
    }


def model_fingerprint(model_dir: Path) -> str:
    paths = [
        model_dir / "config.json",
        model_dir / "tokenizer_config.json",
        model_dir / "model.safetensors.index.json",
    ]
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"LLM_JUDGE_MODEL_FILE_MISSING:{path.name}")
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest().upper()


def protocol_hash() -> str:
    probes = [BlindJudgeCase("probe-normal", "商品使用正常，只是颜色略浅。")]
    content = "\n".join(
        build_blind_prompt(probes, pass_name=name)
        for name in ("recall_first", "precision_challenge")
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest().upper()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _extract_json_value(raw_text: str) -> dict[str, Any] | list[Any]:
    text = re.sub(r"<think>.*?</think>", "", raw_text or "", flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    object_start = text.find("{")
    array_start = text.find("[")
    starts = [item for item in (object_start, array_start) if item >= 0]
    start = min(starts) if starts else -1
    if start < 0:
        raise ValueError("LLM_JUDGE_JSON_VALUE_MISSING")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM_JUDGE_JSON_INVALID:{exc.msg}") from exc
    if not isinstance(payload, (dict, list)):
        raise ValueError("LLM_JUDGE_JSON_NOT_CONTAINER")
    return payload
