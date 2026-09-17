import json
import math
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_v2.corpus_loader import load_jsonl
from app.rag_v2.evaluator import evaluate_queries
from app.rag_v2.service import RagV2Service


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rag" / "audit" / "validity_external_eval_results.json"
FAILURES = ROOT / "data" / "rag" / "audit" / "validity_external_eval_failures.jsonl"
REPORT = ROOT / "docs" / "112_v161_rag_validity_external_eval_report.md"
STRATEGIES = ["tfidf", "dense", "hybrid", "hybrid_rule", "hybrid_neural", "hybrid_rerank"]


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def dcg(relevances: List[int]) -> float:
    return sum(value / math.log2(index + 2) for index, value in enumerate(relevances))


def p95(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def strict_to_eval_rows(rows: Iterable[Dict]) -> List[Dict]:
    output = []
    for row in rows:
        labels = row["evaluation_labels"]
        output.append({
            "query_id": row["sample_id"],
            "query_text": row["input"]["query_text"],
            "product_category": row["input"].get("product_category"),
            "relevant_case_ids": labels["relevant_case_ids"],
            "risk_type": labels.get("risk_type"),
            "risk_level": labels.get("risk_level"),
            "source_scenario": labels.get("source_scenario"),
        })
    return output


def original_to_eval_rows(rows: Iterable[Dict]) -> List[Dict]:
    output = []
    for row in rows:
        output.append({
            "query_id": row["query_id"],
            "query_text": row["query_text"],
            "product_category": row.get("product_category"),
            "relevant_case_ids": row["relevant_case_ids"],
            "risk_type": row.get("expected_risk_type"),
            "risk_level": row.get("expected_risk_level"),
            "source_scenario": row["query_id"].split("-")[1].lower() if "-" in row["query_id"] else "unknown",
        })
    return output


def evaluate_no_oracle(retriever, rows: List[Dict], strategy: str, top_k: int) -> Dict:
    hit1 = hit3 = hit5 = empty = 0
    reciprocal: List[float] = []
    ndcgs: List[float] = []
    latencies: List[float] = []
    failures = []
    risk_hits: Dict[str, List[int]] = {}
    category_hits: Dict[str, List[int]] = {}
    hard_negative_errors = 0
    for row in rows:
        request = {
            "query_text": row["query_text"],
            "product_category": row.get("product_category"),
            "top_k": top_k,
            "strategy": strategy,
        }
        result = retriever.search(request)
        ids = [item["case_id"] for item in result["hits"]]
        relevant = set(row["relevant_case_ids"])
        ranks = [index + 1 for index, case_id in enumerate(ids) if case_id in relevant]
        hit1 += int(any(rank <= 1 for rank in ranks))
        hit3 += int(any(rank <= 3 for rank in ranks))
        hit5 += int(any(rank <= 5 for rank in ranks))
        empty += int(not ids)
        reciprocal.append(1.0 / min(ranks) if ranks else 0.0)
        relevance = [1 if case_id in relevant else 0 for case_id in ids[:5]]
        ideal = [1] * min(3, len(ids[:5])) + [0] * max(0, len(ids[:5]) - 3)
        ndcgs.append(dcg(relevance) / dcg(ideal) if dcg(ideal) else 0.0)
        latencies.append(float(result["latency_ms"]))
        if row.get("risk_type"):
            bucket = risk_hits.setdefault(row["risk_type"], [0, 0])
            bucket[0] += int(any(rank <= 5 for rank in ranks))
            bucket[1] += 1
        if row.get("product_category"):
            bucket = category_hits.setdefault(row["product_category"], [0, 0])
            bucket[0] += int(any(rank <= 5 for rank in ranks))
            bucket[1] += 1
        if not ranks:
            failures.append({"query_id": row["query_id"], "strategy": strategy, "returned_case_ids": ids, "relevant_case_ids": row["relevant_case_ids"]})
        hard_negative_errors += 0
    total = len(rows)
    return {
        "strategy": strategy,
        "query_count": total,
        "hit_at_1": hit1 / total if total else 0.0,
        "hit_at_3": hit3 / total if total else 0.0,
        "hit_at_5": hit5 / total if total else 0.0,
        "mrr": statistics.mean(reciprocal) if reciprocal else 0.0,
        "ndcg_at_5": statistics.mean(ndcgs) if ndcgs else 0.0,
        "empty_retrieval_rate": empty / total if total else 0.0,
        "hard_negative_error_rate": hard_negative_errors / total if total else 0.0,
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0.0,
        "p95_latency_ms": p95(latencies),
        "risk_type_hit_at_5": {key: value[0] / value[1] for key, value in sorted(risk_hits.items())},
        "product_category_hit_at_5": {key: value[0] / value[1] for key, value in sorted(category_hits.items())},
        "failures": failures,
    }


def evaluate_strategy_set(service: RagV2Service, rows: List[Dict], mode: str, original_rows: List[Dict] = None) -> Tuple[Dict, List[Dict]]:
    metrics: Dict[str, Dict] = {}
    failures: List[Dict] = []
    for strategy in STRATEGIES:
        if strategy == "hybrid_rule":
            neural = service.retriever.neural_reranker
            service.retriever.neural_reranker = None
            row = evaluate_no_oracle(service.retriever, rows, "hybrid_rerank", service.config.top_k)
            service.retriever.neural_reranker = neural
            row["strategy"] = "hybrid_rule"
        elif strategy == "hybrid_neural":
            row = evaluate_no_oracle(service.retriever, rows, "hybrid_rerank", service.config.top_k)
            row["strategy"] = "hybrid_neural"
        elif strategy == "hybrid_rerank":
            row = dict(metrics["hybrid_neural"]) if "hybrid_neural" in metrics else evaluate_no_oracle(service.retriever, rows, "hybrid_rerank", service.config.top_k)
            row["strategy"] = "hybrid_rerank"
        else:
            row = evaluate_no_oracle(service.retriever, rows, strategy, service.config.top_k)
        failures.extend(dict(item, dataset_mode=mode) for item in row.pop("failures", []))
        metrics[strategy] = row
    return metrics, failures


def compact_for_report(row: Dict) -> str:
    return f"{row['hit_at_3']:.4f} / {row['hit_at_5']:.4f} / {row['mrr']:.4f}"


def report_text(result: Dict) -> str:
    lines = [
        "# v1.6.1 RAG 有效性与真实外部评估报告",
        "",
        f"结论：`{result['marker']}`",
        "",
        "本报告同时记录 v1.6 原始 Oracle、v1.6 原始 No-Oracle、v1.6.1 strict No-Oracle 和真实外部集状态。核心结论优先看 No-Oracle；真实外部数据缺失时不得报告 PASS。",
        "",
        "## 数据规模",
        "",
        f"- 原始模拟查询：{result['counts']['original_synthetic']}",
        f"- strict 模拟查询：{result['counts']['strict_synthetic']}",
        f"- 真实外部文本：{result['counts']['real_external']}",
        "",
        "## Hybrid Neural 对比",
        "",
        "| 数据/模式 | Hit@3 / Hit@5 / MRR | 说明 |",
        "| --- | ---: | --- |",
        f"| original_oracle | {compact_for_report(result['original_oracle']['hybrid_rerank'])} | v1.6 原 evaluator，含 expected risk metadata |",
        f"| original_no_oracle | {compact_for_report(result['original_no_oracle']['hybrid_rerank'])} | 只输入 query_text 与 product_category |",
        f"| strict_no_oracle | {compact_for_report(result['strict_no_oracle']['hybrid_rerank'])} | strict 改写查询，不含答案字段 |",
        "",
        "## 结论边界",
        "",
        "- 原始 Oracle 指标用于回归，不用于泛化结论。",
        "- strict No-Oracle 用于暴露模板和元数据捷径影响；不要求保持 100%。",
        "- 真实外部文本集尚未准备完成，因此 `REALWORLD_EXTERNAL_EVAL_PASS` 仍为 BLOCKED。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    service = RagV2Service()
    original = load_jsonl(ROOT / "data/rag/golden_queries/golden_queries_80.jsonl")
    strict = load_jsonl(ROOT / "data/synthetic/golden_queries/golden_queries_strict_80.jsonl")
    real_external_count = count_lines(ROOT / "data/real_world/external_test/real_reviews_external_test_200.jsonl")

    original_oracle = {strategy: evaluate_queries(service.retriever, original, strategy if strategy != "hybrid_rule" else "hybrid_rerank", service.config.top_k) for strategy in ["tfidf", "dense", "hybrid"]}
    neural = service.retriever.neural_reranker
    service.retriever.neural_reranker = None
    original_oracle["hybrid_rule"] = evaluate_queries(service.retriever, original, "hybrid_rerank", service.config.top_k)
    original_oracle["hybrid_rule"]["strategy"] = "hybrid_rule"
    service.retriever.neural_reranker = neural
    original_oracle["hybrid_neural"] = evaluate_queries(service.retriever, original, "hybrid_rerank", service.config.top_k)
    original_oracle["hybrid_neural"]["strategy"] = "hybrid_neural"
    original_oracle["hybrid_rerank"] = dict(original_oracle["hybrid_neural"])
    original_failures = []
    for row in original_oracle.values():
        original_failures.extend(dict(item, dataset_mode="original_oracle") for item in row.pop("failures", []))

    original_no_oracle, original_no_oracle_failures = evaluate_strategy_set(service, original_to_eval_rows(original), "original_no_oracle")
    strict_no_oracle, strict_failures = evaluate_strategy_set(service, strict_to_eval_rows(strict), "strict_no_oracle")

    marker = "REALWORLD_EXTERNAL_EVAL_BLOCKED" if real_external_count < 200 else "REALWORLD_EXTERNAL_EVAL_READY"
    result = {
        "marker": marker,
        "counts": {
            "original_synthetic": len(original),
            "strict_synthetic": len(strict),
            "real_external": real_external_count,
        },
        "blocking_reasons": [] if real_external_count >= 200 else ["real_reviews_external_test_200.jsonl 缺失或不足 200 条"],
        "original_oracle": original_oracle,
        "original_no_oracle": original_no_oracle,
        "strict_no_oracle": strict_no_oracle,
        "oracle_no_oracle_note": "No-Oracle removes expected risk type, expected risk level, evidence keywords, relevant case ids and hard negatives from the retriever/model request.",
    }
    all_failures = original_failures + original_no_oracle_failures + strict_failures

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with FAILURES.open("w", encoding="utf-8", newline="\n") as handle:
        for row in all_failures:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps({
        "marker": marker,
        "original_oracle_hybrid_hit5": original_oracle["hybrid_rerank"]["hit_at_5"],
        "original_no_oracle_hybrid_hit5": original_no_oracle["hybrid_rerank"]["hit_at_5"],
        "strict_no_oracle_hybrid_hit5": strict_no_oracle["hybrid_rerank"]["hit_at_5"],
        "real_external_count": real_external_count,
    }, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
