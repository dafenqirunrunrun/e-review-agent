import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Dict, List

import httpx


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "eval" / "review_schema_eval.jsonl"
DEFAULT_REPORT = ROOT / "docs" / "100_v151_local_qwen_schema_eval_report.md"
COMPAT_REPORT = ROOT / "docs" / "99_v151_local_qwen_schema_eval_report.md"
REQUIRED_FIELDS = {
    "risk_type", "risk_level", "sentiment", "evidence", "reason", "suggestion",
    "need_human_review", "confidence", "missing_information",
}


def percentage(value: int, total: int) -> float:
    return round(value * 100.0 / total, 2) if total else 0.0


def percentile(values: List[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return round(ordered[index], 2)


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


def evidence_supported(evidence: List[str], row: Dict) -> bool:
    source = (row.get("comment_text") or "") + " " + (row.get("image_signal") or "")
    expected = row.get("expected_evidence_keywords") or []
    for item in evidence:
        if not item:
            continue
        if item in source:
            continue
        if any(keyword in item and keyword in source for keyword in expected):
            continue
        return False
    return True


def blocked_metrics(reason: str) -> Dict:
    return {
        "dataset_size": 100,
        "evaluated_count": 0,
        "schema_valid_rate": 0.0,
        "field_complete_rate": 0.0,
        "risk_type_accuracy": 0.0,
        "risk_level_accuracy": 0.0,
        "evidence_support_rate": 0.0,
        "unsupported_claim_rate": 0.0,
        "fallback_rate": 100.0,
        "local_qwen_success_rate": 0.0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "invalid_json_count": 0,
        "repair_used_rate": 0.0,
        "passed": False,
        "blocked": True,
        "blocked_reason": reason,
    }


def preflight(client: httpx.Client, base_url: str) -> Dict:
    status = client.get(f"{base_url.rstrip('/')}/api/v1/llm/provider/status")
    status.raise_for_status()
    provider_status = status.json()
    if provider_status.get("provider_name") != "local_qwen3_transformers":
        return {"blocked": True, "reason": "LOCAL_QWEN_PROVIDER_NOT_SELECTED", "status": provider_status}
    smoke = client.post(
        f"{base_url.rstrip('/')}/api/v1/llm/local-qwen/smoke-test",
        json={"comment_text": "刚收到就破损，客服一直不回复，要求退款", "rating": 1, "image_signal": "包装破损图片"},
    )
    smoke.raise_for_status()
    smoke_body = smoke.json()
    if smoke_body.get("provider") != "local_qwen3_transformers" or smoke_body.get("fallback_used"):
        reason = smoke_body.get("error_summary") or provider_status.get("load_error_summary") or "LOCAL_QWEN_MODEL_NOT_AVAILABLE"
        return {"blocked": True, "reason": reason, "status": provider_status, "smoke": smoke_body}
    return {"blocked": False, "status": provider_status, "smoke": smoke_body}


def evaluate(base_url: str, dataset: Path) -> Dict:
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    with httpx.Client(timeout=180.0, trust_env=False) as client:
        check = preflight(client, base_url)
        if check["blocked"]:
            return blocked_metrics(str(check["reason"]))
        for index, row in enumerate(rows, start=1):
            started = time.perf_counter()
            response = client.post(
                f"{base_url.rstrip('/')}/api/v1/llm/review/analyze",
                json={
                    "review_id": row["case_id"],
                    "product_id": "LOCAL-QWEN-EVAL",
                    "product_name": "本地 Qwen3 结构化输出评估商品",
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
            extra = body.get("extra") or {}
            local_success = body.get("llm_provider") == "local_qwen3_transformers" and not body.get("fallback_used")
            results.append({
                "schema_valid": body.get("schema_valid") is True and local_success,
                "field_complete": local_success and REQUIRED_FIELDS.issubset(structured) and all(structured[key] is not None for key in REQUIRED_FIELDS),
                "risk_type_correct": local_success and structured["risk_type"] == row["expected_risk_type"],
                "risk_level_correct": local_success and structured["risk_level"] == row["expected_risk_level"],
                "evidence_supported": local_success and evidence_supported(structured["evidence"], row),
                "evidence_keyword_hit": local_success and any(keyword in evidence_text for keyword in row["expected_evidence_keywords"]),
                "unsupported_claim": local_success and not evidence_supported(structured["evidence"], row),
                "fallback_used": bool(body.get("fallback_used")),
                "local_success": local_success,
                "repair_used": bool(body.get("repair_used")),
                "invalid_json": "invalid JSON" in str(extra.get("initial_schema_error") or ""),
                "latency_ms": body.get("latency_ms") if body.get("latency_ms") not in (None, 0) else elapsed,
            })
            if index % 10 == 0:
                print(f"PROGRESS={index}/{len(rows)}")

    total = len(results)
    local_total = sum(row["local_success"] for row in results)
    latencies = [float(row["latency_ms"]) for row in results]
    metrics = {
        "dataset_size": len(rows),
        "evaluated_count": total,
        "schema_valid_rate": percentage(sum(row["schema_valid"] for row in results), total),
        "field_complete_rate": percentage(sum(row["field_complete"] for row in results), total),
        "risk_type_accuracy": percentage(sum(row["risk_type_correct"] for row in results), local_total),
        "risk_level_accuracy": percentage(sum(row["risk_level_correct"] for row in results), local_total),
        "evidence_support_rate": percentage(sum(row["evidence_supported"] and row["evidence_keyword_hit"] for row in results), local_total),
        "unsupported_claim_rate": percentage(sum(row["unsupported_claim"] for row in results), local_total),
        "fallback_rate": percentage(sum(row["fallback_used"] for row in results), total),
        "local_qwen_success_rate": percentage(sum(row["local_success"] for row in results), total),
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "invalid_json_count": sum(row["invalid_json"] for row in results),
        "repair_used_rate": percentage(sum(row["repair_used"] for row in results), total),
        "blocked": False,
    }
    metrics["passed"] = (
        metrics["schema_valid_rate"] >= 90
        and metrics["field_complete_rate"] >= 90
        and metrics["unsupported_claim_rate"] <= 15
        and metrics["local_qwen_success_rate"] >= 80
    )
    return metrics


def report_text(metrics: Dict, base_url: str) -> str:
    if metrics.get("blocked"):
        marker = "LOCAL_QWEN_SCHEMA_EVAL_BLOCKED"
    else:
        marker = "LOCAL_QWEN_SCHEMA_EVAL_PASS" if metrics.get("passed") else "LOCAL_QWEN_SCHEMA_EVAL_FAIL"
    lines = [
        "# v1.5.1 本地 Qwen3 JSON Schema 评估报告",
        "",
        f"评估标记：`{marker}`",
        "",
        "本报告由实际脚本调用本地 FastAPI Provider 生成，不把 fallback 结果计入 Qwen3 成功率。",
        "",
        f"- 接口：`{base_url.rstrip('/')}/api/v1/llm/review/analyze`",
        "- 模型：`Qwen/Qwen3-1.7B`",
        f"- 测试集规模：{metrics['dataset_size']} 条",
        f"- 实际完成评估：{metrics['evaluated_count']} 条",
        f"- 阻塞原因：`{metrics.get('blocked_reason') or '无'}`",
        "- 风险、证据与无依据声明指标只以真实本地 Qwen 成功样本为分母；fallback 单独统计",
        "",
        "| 指标 | 结果 | 初始门槛 |",
        "| --- | ---: | ---: |",
        f"| schema_valid_rate | {metrics['schema_valid_rate']:.2f}% | >= 90% |",
        f"| field_complete_rate | {metrics['field_complete_rate']:.2f}% | >= 90% |",
        f"| risk_type_accuracy | {metrics['risk_type_accuracy']:.2f}% | 记录值 |",
        f"| risk_level_accuracy | {metrics['risk_level_accuracy']:.2f}% | 记录值 |",
        f"| evidence_support_rate | {metrics['evidence_support_rate']:.2f}% | 记录值 |",
        f"| unsupported_claim_rate | {metrics['unsupported_claim_rate']:.2f}% | <= 15% |",
        f"| fallback_rate | {metrics['fallback_rate']:.2f}% | 记录值 |",
        f"| local_qwen_success_rate | {metrics['local_qwen_success_rate']:.2f}% | >= 80% |",
        f"| avg_latency_ms | {metrics['avg_latency_ms']:.2f} ms | 记录值 |",
        f"| p95_latency_ms | {metrics['p95_latency_ms']:.2f} ms | 记录值 |",
        f"| invalid_json_count | {metrics['invalid_json_count']} | 记录值 |",
        f"| repair_used_rate | {metrics['repair_used_rate']:.2f}% | 记录值 |",
        "",
        "结果只代表本机、当前模型权重、Prompt 和 100 条测试集，不代表生产级模型质量。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        metrics = evaluate(args.base_url, args.dataset)
    except Exception as exc:
        metrics = blocked_metrics(f"LOCAL_QWEN_EVAL_REQUEST_FAILED:{type(exc).__name__}")
    text = report_text(metrics, args.base_url)
    args.report.write_text(text, encoding="utf-8", newline="\n")
    COMPAT_REPORT.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(metrics, ensure_ascii=False))
    if metrics.get("blocked"):
        print("LOCAL_QWEN_SCHEMA_EVAL_BLOCKED")
        return 2
    marker = "LOCAL_QWEN_SCHEMA_EVAL_PASS" if metrics.get("passed") else "LOCAL_QWEN_SCHEMA_EVAL_FAIL"
    print(marker)
    return 0 if metrics.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
