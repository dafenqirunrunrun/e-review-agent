import json
import random
import re
from pathlib import Path
from typing import Dict, Iterable, List

from build_rag_dataset import SCENARIOS


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "synthetic" / "golden_queries" / "golden_queries_strict_80.jsonl"
SEED = 20260712


STRICT_TEMPLATES = [
    "{category}商品到手后，用户只描述了{symptom}，评分{rating}星，图片信号为{image_signal}。请检索可参考的历史处置边界。",
    "客服需要判断一条{category}评价：买家说{symptom}，但没有直接使用平台风险分类词。评分{rating}星。",
    "运营侧收到非标准表达：{symptom}。商品类目为{category}，用户上传图片信号：{image_signal}。",
    "请在不使用答案标签的情况下，为这条{category}评论找相似案例：{symptom}；评分{rating}星。",
]

PARAPHRASES = {
    "damaged": ["外包装挤压后里面也有裂痕", "收到时边角碎了一块", "安装前发现外壳裂缝"],
    "leakage": ["瓶身周围有湿痕", "盒子里有液体渗出", "密封处已经沾满内容物"],
    "missing_parts": ["安装时发现配件数量对不上", "说明书里的小件没有找到", "清点后少了关键零件"],
    "wrong_item": ["实物和下单规格不一致", "收到的颜色与订单不同", "包装型号和页面展示不一样"],
    "delivery_delay": ["承诺时间过了仍未送达", "运输状态好几天没有变化", "派送进度明显滞后"],
    "fake_shipping": ["页面显示已寄出但承运方没有收件记录", "只有编号却查不到揽收", "发出状态停留在创建单据"],
    "refund_dispute": ["售后申请一直没有退回款项", "退款请求被反复退回", "支付返还进度无法确认"],
    "return_dispute": ["寄回后商家说无法接收", "退回流程卡在责任认定", "退货运费谁承担没有结论"],
    "service_no_response": ["多次留言无人接续处理", "售后入口一直没有人工答复", "问题提交后长时间没有回应"],
    "counterfeit": ["防伪验证结果让人存疑", "包装细节和以往购买不一样", "用户质疑来源但证据还不完整"],
    "quality_defect": ["正常使用时部件很快松动", "做工细节影响使用", "材质表现和描述差距明显"],
    "food_safety": ["食品里出现不应有的颗粒", "食用前闻到异常气味", "保质期内状态异常"],
    "battery_safety": ["充电时温度异常升高", "电池外观有鼓起", "使用中出现刺鼻气味"],
    "modality_conflict": ["文字说没问题但图片像是有损坏", "评价内容和上传照片表达相反", "图片与文字描述无法互相支持"],
    "rating_conflict": ["给了高分但正文全是不满", "星级很好却要求售后介入", "评分和文字情绪方向相反"],
    "subjective_negative": ["用户只是觉得款式不合适", "手感与个人偏好不符", "颜色喜好导致评价偏低"],
    "malicious_review": ["买家以差评要求额外补偿", "评论里出现删评返现诉求", "用户用曝光威胁换取赔偿"],
    "neutral": ["使用体验暂时没有明显问题", "整体符合预期但没有更多细节", "评价态度中性且证据很少"],
    "positive": ["用户表示包装和体验都不错", "收到后整体满意", "评价主要是推荐和认可"],
    "insufficient_evidence": ["只说不太对劲但没有细节", "评价无法定位具体问题", "用户没有说明故障表现"],
}

IMAGE_SIGNALS = [
    "no_image",
    "clear_product_photo",
    "blurred_package_photo",
    "possible_text_image_conflict",
]


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def long_phrase_overlap(query: str, phrases: List[str]) -> bool:
    normalized_query = re.sub(r"\s+", "", query)
    for phrase in phrases:
        phrase = re.sub(r"\s+", "", phrase)
        if len(phrase) >= 6 and phrase in normalized_query:
            return True
    return False


def build_rows() -> List[Dict]:
    rng = random.Random(SEED)
    by_key = {row["key"]: row for row in SCENARIOS}
    rows = []
    for scenario in SCENARIOS:
        paraphrases = list(PARAPHRASES[scenario["key"]])
        rng.shuffle(paraphrases)
        hard_keys = [scenario["hard"]]
        hard_keys.extend(item["key"] for item in SCENARIOS if item["key"] != scenario["key"] and item["key"] not in hard_keys)
        for index in range(4):
            symptom = paraphrases[index % len(paraphrases)]
            image_signal = IMAGE_SIGNALS[(index + len(scenario["key"])) % len(IMAGE_SIGNALS)]
            query_text = STRICT_TEMPLATES[index].format(
                category=scenario["category"],
                symptom=symptom,
                rating=scenario["rating"],
                image_signal=image_signal,
            )
            if long_phrase_overlap(query_text, scenario["evidence"]):
                raise RuntimeError(f"STRICT_QUERY_LONG_PHRASE_OVERLAP: {scenario['key']} {index}")
            relevant_group = (index + 1) % 3
            relevant = [f"CASE-{scenario['key'].upper()}-{relevant_group + 1 + 3 * offset:02d}" for offset in range(3)]
            hard_negative_case_ids = []
            for key in hard_keys:
                if len(hard_negative_case_ids) >= 3:
                    break
                hard = by_key[key]
                hard_negative_case_ids.append(f"CASE-{hard['key'].upper()}-{index + 1:02d}")
            rows.append({
                "sample_id": f"STRICT-{scenario['key'].upper()}-{index + 1:02d}",
                "input": {
                    "query_text": query_text,
                    "product_category": scenario["category"],
                    "rating": scenario["rating"],
                    "image_signal": image_signal,
                },
                "evaluation_labels": {
                    "relevant_case_ids": relevant,
                    "hard_negative_case_ids": hard_negative_case_ids,
                    "source_scenario": scenario["key"],
                    "risk_type": scenario["risk_type"],
                    "risk_level": scenario["risk_level"],
                },
                "source_type": "synthetic_strict_query_v161",
                "split": "strict_eval",
            })
    rng.shuffle(rows)
    return rows


def main() -> int:
    rows = build_rows()
    write_jsonl(OUTPUT, rows)
    print(json.dumps({
        "seed": SEED,
        "output": str(OUTPUT),
        "count": len(rows),
        "contains_standard_answer_fields_at_top_level": False,
        "minimum_hard_negatives": min(len(row["evaluation_labels"]["hard_negative_case_ids"]) for row in rows),
    }, ensure_ascii=False))
    print("STRICT_SYNTHETIC_QUERY_BUILD_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
