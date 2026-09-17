import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
RAG_ROOT = ROOT / "data" / "rag"
SEED = 20260711


SCENARIOS: List[Dict] = [
    {"key": "damaged", "label": "商品破损", "risk_type": "after_sales_risk", "risk_level": "high", "category": "家电", "rating": 1, "evidence": ["破损", "裂开", "外壳碎了并伴随漏液，客服也未响应"], "action": "核验签收与包装照片，转售后人工处理", "tags": ["破损", "签收", "售后", "多风险并存"], "hard": "quality_defect"},
    {"key": "leakage", "label": "漏液", "risk_type": "after_sales_risk", "risk_level": "high", "category": "个护", "rating": 1, "evidence": ["漏液", "瓶口渗出", "包装湿了"], "action": "核验批次与图片，隔离同批次并人工售后", "tags": ["漏液", "包装", "批次"], "hard": "damaged"},
    {"key": "missing_parts", "label": "缺件", "risk_type": "after_sales_risk", "risk_level": "high", "category": "家居", "rating": 1, "evidence": ["少了配件", "缺少螺丝", "清单不全"], "action": "比对装箱清单并安排补件", "tags": ["缺件", "配件", "补发"], "hard": "wrong_item"},
    {"key": "wrong_item", "label": "错发", "risk_type": "after_sales_risk", "risk_level": "high", "category": "服饰", "rating": 1, "evidence": ["发错型号", "颜色不对", "收到别的商品"], "action": "核对订单与拣货记录，人工处理换货", "tags": ["错发", "型号", "换货"], "hard": "missing_parts"},
    {"key": "delivery_delay", "label": "物流延迟", "risk_type": "after_sales_risk", "risk_level": "medium", "category": "日用", "rating": 2, "evidence": ["多天没到", "物流不更新", "超过承诺时间"], "action": "查询物流轨迹并主动告知预计时效", "tags": ["物流", "延迟", "时效"], "hard": "fake_shipping"},
    {"key": "fake_shipping", "label": "虚假发货", "risk_type": "after_sales_risk", "risk_level": "high", "category": "数码", "rating": 1, "evidence": ["只有单号", "一直未揽收", "显示发货但没物流"], "action": "核验揽收记录并转平台人工复核", "tags": ["虚假发货", "揽收", "物流"], "hard": "delivery_delay"},
    {"key": "refund_dispute", "label": "退款争议", "risk_type": "after_sales_risk", "risk_level": "high", "category": "数码", "rating": 1, "evidence": ["拒绝退款", "退款没到账", "申请被驳回"], "action": "核验退款单与支付流水，交由人工裁定", "tags": ["退款", "争议", "支付"], "hard": "return_dispute"},
    {"key": "return_dispute", "label": "退货争议", "risk_type": "after_sales_risk", "risk_level": "high", "category": "服饰", "rating": 1, "evidence": ["不让退货", "退回后拒收", "运费争议"], "action": "核验退货政策和签收记录，人工协商", "tags": ["退货", "拒收", "运费"], "hard": "refund_dispute"},
    {"key": "service_no_response", "label": "售后未响应", "risk_type": "after_sales_risk", "risk_level": "high", "category": "家电", "rating": 1, "evidence": ["客服不回复", "售后失联", "多次联系没人处理"], "action": "升级人工工单并设置响应时限", "tags": ["售后", "客服", "未响应"], "hard": "refund_dispute"},
    {"key": "counterfeit", "label": "假货质疑", "risk_type": "after_sales_risk", "risk_level": "high", "category": "美妆", "rating": 1, "evidence": ["怀疑是假货", "防伪码异常", "包装和专柜不同"], "action": "核验供应链和防伪信息，禁止自动定性", "tags": ["假货质疑", "防伪", "供应链"], "hard": "quality_defect"},
    {"key": "quality_defect", "label": "质量缺陷", "risk_type": "negative_review", "risk_level": "medium", "category": "家居", "rating": 2, "evidence": ["做工粗糙", "容易断", "使用后变形"], "action": "记录缺陷并汇总同款质量反馈", "tags": ["质量", "缺陷", "做工"], "hard": "damaged"},
    {"key": "food_safety", "label": "食品安全", "risk_type": "after_sales_risk", "risk_level": "high", "category": "食品", "rating": 1, "evidence": ["已经变质", "吃后不舒服", "发现异物"], "action": "立即人工复核批次与健康风险，不自动归责", "tags": ["食品安全", "变质", "批次"], "hard": "quality_defect"},
    {"key": "battery_safety", "label": "电池电器安全", "risk_type": "after_sales_risk", "risk_level": "high", "category": "数码", "rating": 1, "evidence": ["电池鼓包", "充电发烫", "出现焦味"], "action": "停止使用并升级安全复核，核验批次", "tags": ["电池", "发热", "安全"], "hard": "quality_defect"},
    {"key": "modality_conflict", "label": "图文冲突", "risk_type": "negative_review", "risk_level": "medium", "category": "家居", "rating": 3, "evidence": ["文字说完好", "图片显示破损", "图文不一致"], "action": "分离文本与图片证据并转人工复核", "tags": ["图文冲突", "多模态", "复核"], "hard": "rating_conflict"},
    {"key": "rating_conflict", "label": "评分文本矛盾", "risk_type": "negative_review", "risk_level": "medium", "category": "服饰", "rating": 5, "evidence": ["五星但说很差", "评分高却要求退货", "文字和星级相反"], "action": "降低置信度并人工确认真实意图", "tags": ["评分冲突", "文本", "置信度"], "hard": "modality_conflict"},
    {"key": "subjective_negative", "label": "主观差评", "risk_type": "negative_review", "risk_level": "medium", "category": "服饰", "rating": 2, "evidence": ["不喜欢款式", "手感一般", "颜色不合心意"], "action": "归纳主观偏好，不升级为高风险", "tags": ["主观", "差评", "偏好"], "hard": "malicious_review"},
    {"key": "malicious_review", "label": "恶意评价", "risk_type": "negative_review", "risk_level": "medium", "category": "日用", "rating": 1, "evidence": ["不给赔偿就差评", "要求返现删评", "威胁曝光"], "action": "保留沟通证据并交人工判断，禁止自动封禁", "tags": ["恶意评价", "威胁", "人工判断"], "hard": "subjective_negative"},
    {"key": "neutral", "label": "中性评价", "risk_type": "normal_review", "risk_level": "low", "category": "日用", "rating": 3, "evidence": ["整体一般", "符合描述", "暂时正常"], "action": "常规观察，无需主动干预", "tags": ["中性", "一般", "正常"], "hard": "insufficient_evidence"},
    {"key": "positive", "label": "正常好评", "risk_type": "normal_review", "risk_level": "low", "category": "家居", "rating": 5, "evidence": ["质量很好", "包装完好", "值得推荐"], "action": "记录正向反馈并常规观察", "tags": ["好评", "满意", "推荐"], "hard": "neutral"},
    {"key": "insufficient_evidence", "label": "证据不足", "risk_type": "normal_review", "risk_level": "low", "category": "数码", "rating": 3, "evidence": ["不好说", "感觉有问题", "没有具体描述"], "action": "请求补充图片、订单和故障细节", "tags": ["证据不足", "低置信度", "补充信息"], "hard": "neutral"},
]

PREFIXES = ["刚签收时发现", "使用两天后注意到", "拆开包装以后", "这次购买让我遇到", "家人试用后反馈", "今天检查商品时发现"]
SUFFIXES = ["希望尽快核实。", "订单和照片都可以补充。", "请给出明确处理方案。", "目前先保留商品等待回复。", "这不是我预期的体验。"]
PRODUCTS = ["便携设备", "家用套装", "日常用品", "精选单品", "新款商品", "基础款产品"]


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def build_cases() -> List[Dict]:
    rows = []
    for scenario in SCENARIOS:
        for index in range(12):
            evidence = scenario["evidence"][index % len(scenario["evidence"])]
            rows.append({
                "case_id": f"CASE-{scenario['key'].upper()}-{index + 1:02d}",
                "title": f"{scenario['label']}处置案例 {index + 1:02d}",
                "product_category": scenario["category"],
                "risk_type": scenario["risk_type"],
                "risk_level": scenario["risk_level"],
                "scenario": f"历史工单核验到“{evidence}”，场景归类为{scenario['label']}，第{index + 1}种处理条件。",
                "evidence": [evidence, scenario["tags"][index % len(scenario["tags"])]],
                "operation_suggestion": scenario["action"],
                "human_review_reason": "涉及高风险或证据边界时由人工确认最终处置" if scenario["risk_level"] != "low" else "低风险案例用于相似场景参考",
                "tags": scenario["tags"] + [scenario["category"]],
                "source_type": "synthetic_case_v16",
            })
    return rows


def build_comments(rng: random.Random) -> List[Dict]:
    rows = []
    for scenario in SCENARIOS:
        combinations = [(a, b, c, d) for a in PREFIXES for b in scenario["evidence"] for c in SUFFIXES for d in PRODUCTS]
        rng.shuffle(combinations)
        for index, (prefix, evidence, suffix, product) in enumerate(combinations[:60]):
            split = "train" if index < 42 else "validation" if index < 51 else "test"
            image_signal = "未提供图片" if index % 4 == 0 else f"合成图片信号：{scenario['label']}细节-{index + 1:02d}"
            rows.append({
                "review_id": f"REV-{scenario['key'].upper()}-{index + 1:03d}",
                "product_name": f"{scenario['category']}{product}",
                "product_category": scenario["category"],
                "rating": scenario["rating"],
                "review_text": f"这款{product}{prefix}{evidence}，{suffix}",
                "image_signal": image_signal,
                "risk_type": scenario["risk_type"],
                "risk_level": scenario["risk_level"],
                "expected_action": scenario["action"],
                "evidence_keywords": [evidence] + scenario["tags"][:2],
                "source_type": "synthetic_review_v16",
                "split": split,
            })
    rng.shuffle(rows)
    return rows


def build_queries(rng: random.Random) -> List[Dict]:
    by_key = {row["key"]: row for row in SCENARIOS}
    rows = []
    query_openers = ["用户反馈", "一条新评论提到", "需要检索相似处置案例：", "运营收到反馈称"]
    for scenario in SCENARIOS:
        for index in range(4):
            evidence = scenario["evidence"][(index + 1) % len(scenario["evidence"])]
            evidence_group = (index + 1) % len(scenario["evidence"])
            relevant_indexes = [evidence_group + 1 + 3 * offset for offset in range(3)]
            relevant = [f"CASE-{scenario['key'].upper()}-{value:02d}" for value in relevant_indexes]
            hard = by_key[scenario["hard"]]
            hard_ids = [f"CASE-{hard['key'].upper()}-{value:02d}" for value in (index + 2, index + 6)]
            rows.append({
                "query_id": f"QUERY-{scenario['key'].upper()}-{index + 1:02d}",
                "query_text": f"{query_openers[index]}{evidence}，想知道应如何核验和处理。",
                "product_category": scenario["category"],
                "expected_risk_type": scenario["risk_type"],
                "expected_risk_level": scenario["risk_level"],
                "relevant_case_ids": relevant,
                "evidence_keywords": [evidence] + scenario["tags"][:2],
                "hard_negative_case_ids": hard_ids,
            })
    rng.shuffle(rows)
    return rows


def stats(comments: List[Dict], cases: List[Dict], queries: List[Dict]) -> Dict:
    return {
        "seed": SEED,
        "comments": len(comments),
        "cases": len(cases),
        "golden_queries": len(queries),
        "comment_risk_types": dict(Counter(row["risk_type"] for row in comments)),
        "comment_splits": dict(Counter(row["split"] for row in comments)),
        "case_risk_types": dict(Counter(row["risk_type"] for row in cases)),
        "query_risk_types": dict(Counter(row["expected_risk_type"] for row in queries)),
        "scenario_count": len(SCENARIOS),
        "contains_personal_data": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=RAG_ROOT)
    args = parser.parse_args()
    rng = random.Random(SEED)
    comments = build_comments(rng)
    cases = build_cases()
    queries = build_queries(rng)
    write_jsonl(args.output_root / "comments" / "review_samples_1200.jsonl", comments)
    write_jsonl(args.output_root / "cases" / "risk_cases_240.jsonl", cases)
    write_jsonl(args.output_root / "golden_queries" / "golden_queries_80.jsonl", queries)
    (args.output_root / "index").mkdir(parents=True, exist_ok=True)
    (args.output_root / "eval").mkdir(parents=True, exist_ok=True)
    result = stats(comments, cases, queries)
    (args.output_root / "dataset_stats.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, ensure_ascii=False))
    print("RAG_DATASET_BUILD_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
