import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_v2.corpus_loader import load_jsonl
from app.rag_v2.evaluator import evaluate_queries
from app.rag_v2.service import RagV2Service


ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = ROOT / "data/rag/eval/rag_eval_results.json"
FAILURE_PATH = ROOT / "data/rag/eval/rag_eval_failures.jsonl"
REPORT_PATH = ROOT / "docs/103_v16_hybrid_rag_eval_report.md"
REPORT_STRATEGIES = ["tfidf", "dense", "hybrid", "hybrid_rule", "hybrid_neural", "hybrid_rerank"]


def report_text(metrics: Dict[str, Dict], marker: str, status: Dict) -> str:
    lines = [
        "# v1.6 Hybrid RAG 检索评估报告", "", f"评估标记：`{marker}`", "",
        "本报告由 80 条黄金查询实际检索生成，检索指标与 Qwen 下游生成指标分开统计。", "",
        f"- 案例数：{status['corpus_size']}", f"- Embedding：`{status['embedding_model']}`",
        f"- bge-m3 本地可用：{status['embedding_model_available']}",
        f"- FAISS 索引可用：{status['index_available']}",
        f"- Neural reranker 本地可用：{status['reranker_model_available']}", "",
        "| 策略 | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | 空召回率 | 证据覆盖 | 平均延迟(ms) | P95(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in REPORT_STRATEGIES:
        if name not in metrics:
            continue
        row = metrics[name]
        lines.append(
            f"| {name} | {row['hit_at_1']:.4f} | {row['hit_at_3']:.4f} | {row['hit_at_5']:.4f} | "
            f"{row['mrr']:.4f} | {row['ndcg_at_5']:.4f} | {row['empty_retrieval_rate']:.4f} | "
            f"{row['evidence_keyword_coverage']:.4f} | {row['avg_latency_ms']:.2f} | {row['p95_latency_ms']:.2f} |"
        )
    lines.extend(["", "## 各风险类型 Hit@5", ""])
    for name in REPORT_STRATEGIES:
        if name not in metrics:
            continue
        values = ", ".join(f"{key}={value:.4f}" for key, value in metrics[name]["risk_type_hit_at_5"].items())
        lines.append(f"- `{name}`：{values}")
    lines.extend([
        "", "## 结论边界", "",
        "成功门槛为任一完整 Hybrid 策略 Hit@3 >= 0.80、Hit@5 >= 0.90 且空召回率 <= 0.10。",
        "数据为固定种子的合成实验集，结果不代表生产流量，也不能单独证明统计显著性。", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    service = RagV2Service()
    status = service.status()
    # Do not recursively embed a previous evaluation payload into the next result.
    status["evaluation_metrics"] = {}
    status["downstream_comparison"] = {}
    status["failure_queries"] = []
    if not status["embedding_model_available"] or not status["index_available"]:
        print("BGE_M3_NOT_AVAILABLE" if not status["embedding_model_available"] else "FAISS_INDEX_NOT_AVAILABLE")
        print("HYBRID_RAG_EVAL_BLOCKED")
        return 2
    queries = load_jsonl(service.config.query_path)
    metrics = {name: evaluate_queries(service.retriever, queries, name, service.config.top_k) for name in ["tfidf", "dense", "hybrid"]}
    neural = service.retriever.neural_reranker
    service.retriever.neural_reranker = None
    metrics["hybrid_rule"] = evaluate_queries(service.retriever, queries, "hybrid_rerank", service.config.top_k)
    metrics["hybrid_rule"]["strategy"] = "hybrid_rule"
    service.retriever.neural_reranker = neural
    if neural is not None and neural.available:
        metrics["hybrid_neural"] = evaluate_queries(service.retriever, queries, "hybrid_rerank", service.config.top_k)
        metrics["hybrid_neural"]["strategy"] = "hybrid_neural"
        metrics["hybrid_rerank"] = dict(metrics["hybrid_neural"])
        metrics["hybrid_rerank"]["strategy"] = "hybrid_rerank"
    else:
        metrics["hybrid_rerank"] = dict(metrics["hybrid_rule"])
        metrics["hybrid_rerank"]["strategy"] = "hybrid_rerank"
    passed = metrics["hybrid_rerank"]["hit_at_3"] >= 0.80 and metrics["hybrid_rerank"]["hit_at_5"] >= 0.90 and metrics["hybrid_rerank"]["empty_retrieval_rate"] <= 0.10
    marker = "HYBRID_RAG_EVAL_PASS" if passed else "HYBRID_RAG_EVAL_FAIL"
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps({"marker": marker, "status": status, "metrics": metrics}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    failures: List[Dict] = []
    for name, row in metrics.items():
        failures.extend(row.pop("failures", []))
    with FAILURE_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in failures:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    REPORT_PATH.write_text(report_text(metrics, marker, status), encoding="utf-8", newline="\n")
    print(json.dumps({name: {key: value for key, value in row.items() if key != "failures"} for name, row in metrics.items()}, ensure_ascii=False))
    print(marker)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
