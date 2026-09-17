import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Dict, List

import httpx


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "eval" / "review_schema_eval.jsonl"
DEFAULT_REPORT = ROOT / "docs" / "96_v15_llm_json_schema_eval_report.md"
REQUIRED_FIELDS = {
    "risk_type", "risk_level", "sentiment", "evidence", "reason", "suggestion",
    "need_human_review", "confidence", "missing_information",
}
KNOWN_IMAGE_EVIDENCE = ("未提供图片", "商品外观信息", "非 HTTP 图片 URL")


def percentage(value: int, total: int) -> float:
    return round(value * 100.0 / total, 2) if total else 0.0


def structured_result(body: Dict) -> Dict:
    extra = body.get("extra") or {}
    suggestion = body.get("agent_suggestion") or {}
    return {
        "risk_type": extra.get("risk_type") or "unknown",
        "risk_level": body.get("risk_level"),
        "sentiment": body.get("sentiment_label"),
        "evidence": body.get("evidence") or [],
        "reason": extra.get("llm_reason") or suggestion.get("summary") or suggestion.get("operation_advice"),
        "suggestion": suggestion.get("operation_advice"),
        "need_human_review": body.get("need_human_review"),
        "confidence": body.get("confidence"),
        "missing_information": body.get("missing_information") or [],
    }


def evidence_supported(evidence: List[str], comment: str) -> bool:
    for item in evidence:
        if item and item not in comment and not any(signal in item for signal in KNOWN_IMAGE_EVIDENCE):
            return False
    return True


def evaluate(base_url: str, dataset: Path) -> Dict:
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        for index, row in enumerate(rows, start=1):
            started = time.perf_counter()
            response = client.post(
                f"{base_url.rstrip('/')}/api/v1/llm/review/analyze",
                json={
                    "review_id": row["case_id"],
                    "product_id": "EVAL-PRODUCT",
                    "product_name": "结构化输出评估商品",
                    "review_text": row["comment_text"],
                    "image_urls": [row["image_signal"]] if row.get("image_signal") else [],
                    "rating": row.get("rating"),
                },
            )
            response.raise_for_status()
            body = response.json()
            structured = structured_result(body)
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            evidence_text = " ".join(structured["evidence"])
            results.append({
                "case_id": row["case_id"],
                "schema_valid": body.get("schema_valid") is True,
                "field_complete": REQUIRED_FIELDS.issubset(structured.keys()) and all(structured[key] is not None for key in REQUIRED_FIELDS),
                "risk_type_correct": structured["risk_type"] == row["expected_risk_type"],
                "risk_level_correct": structured["risk_level"] == row["expected_risk_level"],
                "human_review_correct": structured["need_human_review"] == row["expected_need_human_review"],
                "evidence_supported": evidence_supported(structured["evidence"], row["comment_text"]),
                "evidence_keyword_hit": any(keyword in evidence_text for keyword in row["expected_evidence_keywords"]),
                "unsupported_claim": not evidence_supported(structured["evidence"], row["comment_text"]),
                "fallback_used": bool(body.get("fallback_used")),
                "latency_ms": body.get("latency_ms") if body.get("latency_ms") not in (None, 0) else elapsed,
            })
            if index % 20 == 0:
                print(f"PROGRESS={index}/{len(rows)}")
    total = len(results)
    metrics = {
        "dataset_size": total,
        "schema_valid_rate": percentage(sum(row["schema_valid"] for row in results), total),
        "field_complete_rate": percentage(sum(row["field_complete"] for row in results), total),
        "risk_type_accuracy": percentage(sum(row["risk_type_correct"] for row in results), total),
        "risk_level_accuracy": percentage(sum(row["risk_level_correct"] for row in results), total),
        "need_human_review_accuracy": percentage(sum(row["human_review_correct"] for row in results), total),
        "evidence_support_rate": percentage(sum(row["evidence_supported"] and row["evidence_keyword_hit"] for row in results), total),
        "unsupported_claim_rate": percentage(sum(row["unsupported_claim"] for row in results), total),
        "fallback_rate": percentage(sum(row["fallback_used"] for row in results), total),
        "avg_latency_ms": round(statistics.mean(row["latency_ms"] for row in results), 2),
    }
    metrics["passed"] = (
        metrics["schema_valid_rate"] >= 95
        and metrics["field_complete_rate"] >= 95
        and metrics["unsupported_claim_rate"] <= 10
    )
    return metrics


def write_report(path: Path, metrics: Dict, base_url: str) -> None:
    marker = "LLM_SCHEMA_EVAL_PASS" if metrics["passed"] else "LLM_SCHEMA_EVAL_FAIL"
    lines = [
        "# v1.5 LLM JSON Schema 评估报告",
        "",
        f"评估标记：`{marker}`",
        "",
        "本报告由 `ai-service/scripts/eval_llm_schema.py` 对实际运行中的 FastAPI 接口生成，不包含人工填写或伪造指标。",
        "",
        f"- 接口：`{base_url.rstrip('/')}/api/v1/llm/review/analyze`",
        f"- 测试集：`data/eval/review_schema_eval.jsonl`（{metrics['dataset_size']} 条）",
        "- 当前评估模式：未配置真实 API Key 时自动使用 `local_rule_fallback`",
        "",
        "| 指标 | 结果 | 初始门槛 |",
        "| --- | ---: | ---: |",
        f"| schema_valid_rate | {metrics['schema_valid_rate']:.2f}% | >= 95% |",
        f"| field_complete_rate | {metrics['field_complete_rate']:.2f}% | >= 95% |",
        f"| risk_type_accuracy | {metrics['risk_type_accuracy']:.2f}% | 记录值 |",
        f"| risk_level_accuracy | {metrics['risk_level_accuracy']:.2f}% | 记录值 |",
        f"| evidence_support_rate | {metrics['evidence_support_rate']:.2f}% | 记录值 |",
        f"| unsupported_claim_rate | {metrics['unsupported_claim_rate']:.2f}% | <= 10% |",
        f"| fallback_rate | {metrics['fallback_rate']:.2f}% | 记录值 |",
        f"| avg_latency_ms | {metrics['avg_latency_ms']:.2f} ms | 记录值 |",
        "",
        "说明：该结果只反映当前 100 条小型测试集及当前 Provider 配置，不代表生产级模型效果。Qwen/DeepSeek 未配置 Key 时，不报告其真实模型质量。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    metrics = evaluate(args.base_url, args.dataset)
    write_report(args.report, metrics, args.base_url)
    print(json.dumps(metrics, ensure_ascii=False))
    print("LLM_SCHEMA_EVAL_PASS" if metrics["passed"] else "LLM_SCHEMA_EVAL_FAIL")
    return 0 if metrics["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
