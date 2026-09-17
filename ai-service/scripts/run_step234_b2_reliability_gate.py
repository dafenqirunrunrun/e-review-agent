from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "step234" / "b2_runtime_reliability.json"
AUTO_PASS_DECISIONS = {"allow", "auto_close", "auto_pass", "operation_advice"}
RISK_CASES = [
    ("cashback", "五星好评截图返现，晒图后联系客服领取现金奖励。", 5),
    ("paid", "商家承诺给二十元红包，要求我先发布五星评价。", 5),
    ("suppression", "客服要求删除差评才同意退款，否则不处理售后。", 1),
    ("safety", "充电时电池冒烟发烫，有起火危险，商家拒绝处理。", 1),
    ("fake", "这条评价不是买家真实体验，是商家安排账号批量发布的。", 5),
    ("mixed", "返现换五星，还威胁不删差评就不给退款。", 1),
    ("incentive", "收到赠品的条件是晒图并把评分改成满分。", 5),
    ("fraud", "疑似假货并存在欺诈，使用后还有漏电风险。", 1),
]


def dense_cache_misses(readiness: dict[str, Any]) -> int:
    policy = readiness.get("policyRag") if isinstance(readiness.get("policyRag"), dict) else {}
    dense = policy.get("dense") if isinstance(policy.get("dense"), dict) else {}
    cache = dense.get("cache") if isinstance(dense.get("cache"), dict) else {}
    return int(cache.get("misses", 0) or 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 23.4 live B2 reliability gate")
    parser.add_argument("--ai-url", default="http://127.0.0.1:8008")
    parser.add_argument("--requests-per-level", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[dict, float]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result, round((time.perf_counter() - started) * 1000, 2)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile))))
    return round(ordered[index], 2)


def latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"meanMs": 0.0, "p50Ms": 0.0, "p95Ms": 0.0, "maxMs": 0.0}
    return {
        "meanMs": round(statistics.mean(values), 2),
        "p50Ms": percentile(values, 0.50),
        "p95Ms": percentile(values, 0.95),
        "maxMs": round(max(values), 2),
    }


def citation_valid(citation: dict[str, Any]) -> bool:
    return bool(
        citation.get("sourceName")
        and str(citation.get("sourceUrl", "")).startswith(("http://", "https://"))
        and citation.get("sectionPath")
        and citation.get("contentHash")
        and len(str(citation.get("snippet", ""))) <= 220
    )


def summarize_response(case_name: str, response: dict[str, Any], wall_ms: float) -> dict[str, Any]:
    extra = response.get("extra") if isinstance(response.get("extra"), dict) else {}
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    latency = extra.get("latencyBreakdown") if isinstance(extra.get("latencyBreakdown"), dict) else {}
    citations = (
        (agentic.get("evidenceBundle") or {}).get("citations")
        if isinstance(agentic.get("evidenceBundle"), dict)
        else []
    ) or []
    rerank_traces = [
        item
        for item in response.get("workflow_trace") or []
        if isinstance(item, dict) and item.get("node") == "policy_evidence_rerank"
    ]
    fallback_count = sum(
        bool((item.get("output") or {}).get("fallbackUsed"))
        for item in rerank_traces
        if isinstance(item.get("output"), dict)
    )
    decision = str(response.get("route_decision") or "")
    return {
        "case": case_name,
        "reviewId": response.get("review_id"),
        "route": agentic.get("route"),
        "decision": decision,
        "riskTypes": list(response.get("risk_types") or []),
        "evidenceStatus": response.get("evidence_status"),
        "requiresHumanReview": bool(response.get("requires_human_review")),
        "citationCount": len(citations),
        "citationValid": bool(citations) and all(citation_valid(item) for item in citations),
        "rerankerRuns": len(rerank_traces),
        "rerankerFallbacks": fallback_count,
        "rerankerModes": [
            str((item.get("output") or {}).get("effectiveMode") or "")
            for item in rerank_traces
            if isinstance(item.get("output"), dict)
        ],
        "safeFromAutoPass": decision not in AUTO_PASS_DECISIONS,
        "wallMs": wall_ms,
        "workflowMs": float(latency.get("totalMs", 0.0) or 0.0),
        "embeddingComputeMs": float(latency.get("embeddingComputeMs", 0.0) or 0.0),
        "rerankerMs": float(latency.get("policyRerankerMs", 0.0) or 0.0),
    }


def analyze_case(ai_url: str, case_name: str, text: str, rating: int, suffix: str) -> dict[str, Any]:
    payload = {
        "review_id": f"step234-{case_name}-{suffix}",
        "product_id": "P-STEP234",
        "product_name": "Step 23.4 reliability fixture",
        "review_text": text,
        "image_urls": [],
        "rating": rating,
        "rating_source": "USER_PROVIDED",
    }
    response, wall_ms = request_json("POST", f"{ai_url}/api/v1/review/analyze", payload)
    return summarize_response(case_name, response, wall_ms)


def run_concurrency_level(ai_url: str, concurrency: int, request_count: int, suffix: str) -> dict[str, Any]:
    readiness_before, _ = request_json("GET", f"{ai_url}/api/v1/system/readiness")
    misses_before = dense_cache_misses(readiness_before)
    cases = [RISK_CASES[index % len(RISK_CASES)] for index in range(request_count)]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                analyze_case,
                ai_url,
                name,
                f"{text} 补充说明：这是第{concurrency}组第{index + 1}个独立审核样本。",
                rating,
                f"{suffix}-{concurrency}-{index}",
            ): name
            for index, (name, text, rating) in enumerate(cases)
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(type(exc).__name__)
    rows.sort(key=lambda item: str(item.get("reviewId", "")))
    wall_values = [float(item["wallMs"]) for item in rows]
    workflow_values = [float(item["workflowMs"]) for item in rows]
    fallback_total = sum(int(item["rerankerFallbacks"]) for item in rows)
    fallback_rows = [item for item in rows if item["rerankerFallbacks"]]
    readiness_after, _ = request_json("GET", f"{ai_url}/api/v1/system/readiness")
    misses_after = dense_cache_misses(readiness_after)
    return {
        "concurrency": concurrency,
        "requestCount": request_count,
        "apiErrors": len(errors),
        "errorTypes": sorted(set(errors)),
        "wallLatency": latency_summary(wall_values),
        "workflowLatency": latency_summary(workflow_values),
        "rerankerRuns": sum(int(item["rerankerRuns"]) for item in rows),
        "rerankerFallbacks": fallback_total,
        "denseCacheMissDelta": max(0, misses_after - misses_before),
        "highRiskAutoPass": sum(not bool(item["safeFromAutoPass"]) for item in rows),
        "citationInvalid": sum(not bool(item["citationValid"]) for item in rows),
        "fallbackSafe": all(bool(item["safeFromAutoPass"]) and bool(item["citationValid"]) for item in fallback_rows),
        "rows": rows,
    }


def evaluate_gate(readiness: dict[str, Any], normal: dict[str, Any], levels: list[dict[str, Any]]) -> dict[str, bool]:
    policy = readiness.get("policyRag") if isinstance(readiness.get("policyRag"), dict) else {}
    reranker = policy.get("reranker") if isinstance(policy.get("reranker"), dict) else {}
    checks = {
        "serviceReady": readiness.get("status") == "ready",
        "hybridReady": policy.get("retrievalMode") == "hybrid",
        "rerankerReadyAndLoaded": reranker.get("status") == "ready" and reranker.get("loaded") is True,
        "normalUsesLowTouch": normal.get("route") == "low_touch",
        "normalSkipsReranker": int(normal.get("rerankerRuns", 0)) == 0,
        "normalDoesNotShowCitation": int(normal.get("citationCount", 0)) == 0,
        "allApiCallsSucceeded": all(int(level.get("apiErrors", 0)) == 0 for level in levels),
        "noHighRiskAutoPass": all(int(level.get("highRiskAutoPass", 0)) == 0 for level in levels),
        "allCitationsValid": all(int(level.get("citationInvalid", 0)) == 0 for level in levels),
        "fallbackRemainsSafe": all(bool(level.get("fallbackSafe")) for level in levels),
        "b2Executed": sum(int(level.get("rerankerRuns", 0)) for level in levels) > 0,
        "allRiskQueriesExecuteDense": all(
            int(level.get("denseCacheMissDelta", 0)) >= int(level.get("requestCount", 0))
            for level in levels
        ),
    }
    return checks


def run(args: argparse.Namespace) -> dict[str, Any]:
    readiness, _ = request_json("GET", f"{args.ai_url}/api/v1/system/readiness")
    suffix = uuid.uuid4().hex[:8]
    normal_response, normal_ms = request_json(
        "POST",
        f"{args.ai_url}/api/v1/review/analyze",
        {
            "review_id": f"step234-normal-{suffix}",
            "product_id": "P-STEP234",
            "product_name": "Step 23.4 reliability fixture",
            "review_text": "包装完整，物流正常，使用体验不错。",
            "image_urls": [],
            "rating": 5,
            "rating_source": "USER_PROVIDED",
        },
    )
    normal = summarize_response("normal", normal_response, normal_ms)
    levels = [
        run_concurrency_level(args.ai_url, concurrency, max(args.requests_per_level, concurrency), suffix)
        for concurrency in (1, 2, 4)
    ]
    checks = evaluate_gate(readiness, normal, levels)
    return {
        "schemaVersion": "step234-b2-runtime-reliability-v1",
        "gate": "PASS" if all(checks.values()) else "FAIL",
        "frozenBenchmarkExecuted": False,
        "modelChanged": False,
        "rrfChanged": False,
        "topKChanged": False,
        "rawReviewTextPersisted": False,
        "checks": checks,
        "readiness": {
            "status": readiness.get("status"),
            "retrievalMode": (readiness.get("policyRag") or {}).get("retrievalMode"),
            "rerankerStatus": ((readiness.get("policyRag") or {}).get("reranker") or {}).get("status"),
            "rerankerLoaded": ((readiness.get("policyRag") or {}).get("reranker") or {}).get("loaded"),
        },
        "normal": normal,
        "concurrencyLevels": levels,
    }


def main() -> None:
    args = parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["gate"] != "PASS":
        raise SystemExit("STEP234_B2_RELIABILITY_GATE_FAILED")


if __name__ == "__main__":
    main()
