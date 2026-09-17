import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Dict, List

import httpx


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/eval/review_schema_eval.jsonl"
RESULT = ROOT / "data/rag/eval/qwen_rag_downstream_results.json"
REPORT = ROOT / "docs/104_v16_qwen_rag_downstream_eval_report.md"
ABLATION_REPORT = ROOT / "docs/107_v16_ablation_and_failure_analysis.md"
RAG_RESULT = ROOT / "data/rag/eval/rag_eval_results.json"
GROUPS = [
    ("prompt_only", False, None),
    ("qwen_tfidf", True, "tfidf"),
    ("qwen_dense", True, "dense"),
    ("qwen_hybrid_rerank", True, "hybrid_rerank"),
]
REQUIRED = {"risk_type", "risk_level", "sentiment", "evidence", "reason", "suggestion", "need_human_review", "confidence", "missing_information"}


def percentage(value: int, total: int) -> float:
    return round(100 * value / total, 2) if total else 0.0


def p95(values: List[float]) -> float:
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 2) if ordered else 0.0


def structured(body: Dict) -> Dict:
    extra = body.get("extra") or {}
    suggestion = body.get("agent_suggestion") or {}
    return {
        "risk_type": extra.get("risk_type"), "risk_level": body.get("risk_level"),
        "sentiment": body.get("sentiment_label"), "evidence": body.get("evidence") or [],
        "reason": extra.get("llm_reason") or suggestion.get("summary"),
        "suggestion": suggestion.get("operation_advice"), "need_human_review": body.get("need_human_review"),
        "confidence": body.get("confidence"), "missing_information": body.get("missing_information") or [],
    }


def evidence_supported(values: List[str], row: Dict) -> bool:
    source = f"{row.get('comment_text', '')} {row.get('image_signal', '')}"
    return all(value and value in source for value in values)


def evaluate_group(client: httpx.Client, base_url: str, rows: List[Dict], name: str,
                   rag_enabled: bool, strategy: str) -> Dict:
    samples = []
    for index, row in enumerate(rows, start=1):
        started = time.perf_counter()
        body = client.post(f"{base_url}/api/v1/llm/review/analyze", json={
            "review_id": f"{name}-{row['case_id']}", "product_id": "V16-DOWNSTREAM",
            "product_name": "Hybrid RAG 下游评估商品", "review_text": row["comment_text"],
            "image_urls": [row["image_signal"]] if row.get("image_signal") else [], "rating": row.get("rating"),
            "rag_enabled": rag_enabled, "rag_strategy": strategy,
        }).json()
        result = structured(body)
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        local_success = body.get("llm_provider") == "local_qwen3_transformers" and not body.get("fallback_used")
        samples.append({
            "case_id": row["case_id"], "risk_type_correct": result["risk_type"] == row["expected_risk_type"],
            "risk_level_correct": result["risk_level"] == row["expected_risk_level"],
            "human_review_correct": result["need_human_review"] == row["expected_need_human_review"],
            "schema_valid": body.get("schema_valid") is True, "field_complete": REQUIRED.issubset(result) and all(result[key] is not None for key in REQUIRED),
            "evidence_supported": evidence_supported(result["evidence"], row),
            "unsupported_claim": not evidence_supported(result["evidence"], row),
            "fallback_used": bool(body.get("fallback_used")), "local_success": local_success,
            "latency_ms": float(body.get("latency_ms") or elapsed),
            "rag_hit_count": int(body.get("retrieval_hit_count") or 0),
            "route_decision": body.get("route_decision"),
        })
        if index % 20 == 0:
            print(f"PROGRESS={name}:{index}/{len(rows)}", flush=True)
    total = len(samples)
    per_type = {}
    for risk_type in sorted({row["expected_risk_type"] for row in rows}):
        indexes = [index for index, row in enumerate(rows) if row["expected_risk_type"] == risk_type]
        per_type[risk_type] = {
            "count": len(indexes),
            "risk_type_accuracy": percentage(sum(samples[index]["risk_type_correct"] for index in indexes), len(indexes)),
            "risk_level_accuracy": percentage(sum(samples[index]["risk_level_correct"] for index in indexes), len(indexes)),
        }
    metrics = {
        "schema_valid_rate": percentage(sum(row["schema_valid"] for row in samples), total),
        "field_complete_rate": percentage(sum(row["field_complete"] for row in samples), total),
        "risk_type_accuracy": percentage(sum(row["risk_type_correct"] for row in samples), total),
        "risk_level_accuracy": percentage(sum(row["risk_level_correct"] for row in samples), total),
        "evidence_support_rate": percentage(sum(row["evidence_supported"] for row in samples), total),
        "unsupported_claim_rate": percentage(sum(row["unsupported_claim"] for row in samples), total),
        "need_human_review_accuracy": percentage(sum(row["human_review_correct"] for row in samples), total),
        "avg_latency_ms": round(statistics.mean(row["latency_ms"] for row in samples), 2),
        "p95_latency_ms": p95([row["latency_ms"] for row in samples]),
        "fallback_rate": percentage(sum(row["fallback_used"] for row in samples), total),
        "local_qwen_success_rate": percentage(sum(row["local_success"] for row in samples), total),
        "avg_retrieval_hit_count": round(statistics.mean(row["rag_hit_count"] for row in samples), 2),
        "by_expected_risk_type": per_type,
    }
    return {"metrics": metrics, "samples": samples}


def report_text(results: Dict) -> str:
    base = results["groups"]["prompt_only"]["metrics"]
    hybrid = results["groups"]["qwen_hybrid_rerank"]["metrics"]
    lines = [
        "# v1.6 Qwen3 + Hybrid RAG 下游评估报告", "",
        "本报告使用 v1.5.1 固定 100 条测试集，四组均完整披露，不以检索 Hit@K 替代下游生成质量。", "",
        "| 组别 | Schema | 字段完整 | 风险类型准确率 | 风险等级准确率 | 证据支持率 | 无依据声明率 | 人工复核准确率 | 平均延迟(ms) | P95(ms) | fallback |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, _, _ in GROUPS:
        row = results["groups"][name]["metrics"]
        lines.append(f"| {name} | {row['schema_valid_rate']:.2f}% | {row['field_complete_rate']:.2f}% | {row['risk_type_accuracy']:.2f}% | {row['risk_level_accuracy']:.2f}% | {row['evidence_support_rate']:.2f}% | {row['unsupported_claim_rate']:.2f}% | {row['need_human_review_accuracy']:.2f}% | {row['avg_latency_ms']:.2f} | {row['p95_latency_ms']:.2f} | {row['fallback_rate']:.2f}% |")
    lines.extend([
        "", "## 对比结论", "",
        f"- v1.5.1 封版基线：风险类型/等级准确率均为 84%，平均延迟 2825.88 ms。",
        f"- 本次 Prompt-only：风险类型 {base['risk_type_accuracy']:.2f}%，风险等级 {base['risk_level_accuracy']:.2f}%。",
        f"- 本次 Hybrid：风险类型 {hybrid['risk_type_accuracy']:.2f}%，风险等级 {hybrid['risk_level_accuracy']:.2f}%。",
        f"- Hybrid 相对本次 Prompt-only 风险类型变化 {hybrid['risk_type_accuracy'] - base['risk_type_accuracy']:+.2f} 个百分点，平均延迟变化 {hybrid['avg_latency_ms'] - base['avg_latency_ms']:+.2f} ms。",
        "- 是否默认启用必须同时考虑准确率、无依据声明和延迟；合成测试集不构成生产级统计显著性证明。", "",
        "## 各风险类别变化", "",
    ])
    for risk_type, base_row in base["by_expected_risk_type"].items():
        hybrid_row = hybrid["by_expected_risk_type"][risk_type]
        lines.append(
            f"- `{risk_type}`：风险类型准确率 {base_row['risk_type_accuracy']:.2f}% -> "
            f"{hybrid_row['risk_type_accuracy']:.2f}%，风险等级准确率 {base_row['risk_level_accuracy']:.2f}% -> "
            f"{hybrid_row['risk_level_accuracy']:.2f}% 。"
        )
    lines.append("")
    return "\n".join(lines)


def ablation_text(results: Dict) -> str:
    retrieval = json.loads(RAG_RESULT.read_text(encoding="utf-8")) if RAG_RESULT.exists() else {"metrics": {}, "status": {}}
    metrics = retrieval.get("metrics") or {}
    group_names = [
        ("tfidf", "TF-IDF only"), ("dense", "bge-m3 only"), ("hybrid", "TF-IDF + bge-m3"),
        ("hybrid_rule", "TF-IDF + bge-m3 + RuleReranker"),
        ("hybrid_neural", "TF-IDF + bge-m3 + NeuralReranker"),
    ]
    lines = [
        "# v1.6 消融实验与失败分析", "", "## 1. 检索消融", "",
        "| 方法 | Hit@3 | Hit@5 | MRR | nDCG@5 | 空召回率 | 平均延迟(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in group_names:
        row = metrics.get(key)
        if not row:
            lines.append(f"| {label} | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 |")
            continue
        lines.append(f"| {label} | {row['hit_at_3']:.4f} | {row['hit_at_5']:.4f} | {row['mrr']:.4f} | {row['ndcg_at_5']:.4f} | {row['empty_retrieval_rate']:.4f} | {row['avg_latency_ms']:.2f} |")
    lines.extend([
        "", "## 2. Qwen3 下游消融", "",
        "| 方法 | 风险类型准确率 | 风险等级准确率 | 证据支持率 | 无依据声明率 | 平均延迟(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    labels = {"prompt_only": "Prompt-only", "qwen_tfidf": "Qwen + TF-IDF", "qwen_dense": "Qwen + bge-m3", "qwen_hybrid_rerank": "Qwen + Hybrid + reranker"}
    for key, label in labels.items():
        row = results["groups"][key]["metrics"]
        lines.append(f"| {label} | {row['risk_type_accuracy']:.2f}% | {row['risk_level_accuracy']:.2f}% | {row['evidence_support_rate']:.2f}% | {row['unsupported_claim_rate']:.2f}% | {row['avg_latency_ms']:.2f} |")
    failures = {key: len(value.get("failures") or []) for key, value in metrics.items()}
    lines.extend([
        "", "## 3. 失败样本", "",
        "失败文件只记录 query_id、策略和案例 ID，不保存完整查询。各策略未命中数量：" +
        "，".join(f"{key}={value}" for key, value in sorted(failures.items())) + "。", "",
        "主要风险包括同场景内部排序、语义相邻困难负样本、元数据先验偏置、证据同义表达和多风险并存。",
        "具体失败样本见 `data/rag/eval/rag_eval_failures.jsonl`。", "",
        "## 4. 结论边界", "",
        f"实际 neural reranker 可用：{bool((retrieval.get('status') or {}).get('reranker_model_available'))}。规则与神经重排分别报告，不相互冒充。",
        "固定合成数据集可用于工程消融，但没有重复随机采样、置信区间或真实线上对照，因此不宣称生产级统计显著性。", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = {"dataset_size": len(rows), "v151_baseline": {"risk_type_accuracy": 84.0, "risk_level_accuracy": 84.0, "avg_latency_ms": 2825.88}, "groups": {}}
    with httpx.Client(timeout=240.0, trust_env=False) as client:
        for name, enabled, strategy in GROUPS:
            results["groups"][name] = evaluate_group(client, base_url, rows, name, enabled, strategy)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(results), encoding="utf-8", newline="\n")
    ABLATION_REPORT.write_text(ablation_text(results), encoding="utf-8", newline="\n")
    print(json.dumps({name: value["metrics"] for name, value in results["groups"].items()}, ensure_ascii=False))
    print("QWEN_RAG_DOWNSTREAM_EVAL_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
