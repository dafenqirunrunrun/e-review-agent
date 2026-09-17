from __future__ import annotations

"""Exercise controlled Fast Eligibility activation through the live Admin and AI APIs."""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "step215_fast_runtime" / "fast_runtime_gate.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "FAST_ELIGIBILITY_RUNTIME_REPORT.md"
HIGH_RISKS = {
    "fake_review",
    "rating_manipulation",
    "review_suppression",
    "safety_or_fraud_risk",
    "privacy_risk",
    "harassment_or_abuse",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-url", default="http://127.0.0.1:8083")
    parser.add_argument("--ai-url", default="http://127.0.0.1:8008")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--latency-pairs", type=int, default=7)
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"STEP215_CONFIG_MISSING:{name}")
    return value


def mysql(query: str) -> list[str]:
    environment = dict(os.environ)
    environment["MYSQL_PWD"] = required_env("MYSQL_PASSWORD")
    completed = subprocess.run(
        [
            "mysql",
            "--default-character-set=utf8mb4",
            f"--host={required_env('MYSQL_HOST')}",
            f"--port={required_env('MYSQL_PORT')}",
            f"--user={required_env('MYSQL_USERNAME')}",
            f"--database={required_env('MYSQL_DATABASE')}",
            "--batch",
            "--raw",
            "--skip-column-names",
            "--execute",
            query,
        ],
        capture_output=True,
        check=True,
        env=environment,
    )
    return [line for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict, float]:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=190) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result, round((time.perf_counter() - started) * 1000, 3)


def login(admin_url: str) -> str:
    response, _ = request_json(
        "POST",
        f"{admin_url}/admin/auth/login",
        {
            "username": required_env("STEP2143_ADMIN_USERNAME"),
            "password": required_env("STEP2143_ADMIN_PASSWORD"),
        },
    )
    if response.get("errno") != 0 or not (response.get("data") or {}).get("token"):
        raise RuntimeError("STEP215_ADMIN_LOGIN_FAILED")
    return str(response["data"]["token"])


def analyze_admin(admin_url: str, token: str, payload: dict[str, Any]) -> tuple[int, dict, float]:
    response, elapsed = request_json(
        "POST",
        f"{admin_url}/admin/ai/review/analyze",
        payload,
        {"X-Litemall-Admin-Token": token},
    )
    if response.get("errno") != 0:
        raise RuntimeError(f"STEP215_ADMIN_ANALYZE_FAILED:{response.get('errmsg', 'unknown')}")
    data = response.get("data") or {}
    return int(data["analysisId"]), data["result"], elapsed


def analyze_ai(ai_url: str, payload: dict[str, Any]) -> tuple[dict, float]:
    return request_json("POST", f"{ai_url}/api/v1/review/analyze", payload)


def runtime_metadata(result: dict) -> dict:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    value = extra.get("fastEligibilityRuntime")
    return value if isinstance(value, dict) else {}


def policy_retrieval(result: dict) -> dict:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    value = extra.get("policyRetrieval")
    return value if isinstance(value, dict) else {}


def intent_reasons(result: dict) -> list[str]:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    intent = agentic.get("intent") if isinstance(agentic.get("intent"), dict) else {}
    return list(intent.get("reason_codes") or intent.get("reasonCodes") or [])


def summarize(name: str, result: dict, elapsed_ms: float) -> dict:
    runtime = runtime_metadata(result)
    nodes = [str(item.get("node")) for item in result.get("workflow_trace") or [] if isinstance(item, dict)]
    return {
        "case": name,
        "reviewId": result.get("review_id"),
        "executedChain": runtime.get("executedChain"),
        "policyDecision": runtime.get("policyDecision"),
        "reasonCode": runtime.get("reasonCode"),
        "decision": result.get("route_decision"),
        "riskTypes": result.get("risk_types") or [],
        "requiresHumanReview": bool(result.get("requires_human_review")),
        "safetyGateTriggered": "HIGH_RISK_SAFETY_GATE" in intent_reasons(result),
        "policyRetrievalMode": policy_retrieval(result).get("actualMode"),
        "llmProvider": result.get("llm_provider"),
        "nodes": nodes,
        "elapsedMs": elapsed_ms,
    }


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile))))
    return round(ordered[index], 3)


def remove_checkpoints(review_ids: list[str]) -> None:
    configured = os.getenv("E_REVIEW_AGENTIC_CHECKPOINT_DIR", "data/workflow_checkpoints")
    root = Path(configured)
    if not root.is_absolute():
        root = ROOT / root
    for review_id in review_ids:
        path = root / f"{hashlib.sha256(review_id.encode('utf-8')).hexdigest()}.json"
        if path.exists():
            path.unlink()


def write_outputs(result: dict, output: Path, report: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = result.get("metrics") or {}
    checks = result.get("checks") or {}
    failed = [name for name, passed in checks.items() if not passed]
    report.write_text(
        "\n".join(
            [
                "# Fast Eligibility Runtime Report",
                "",
                "## Result",
                "",
                f"`STEP21_5_RUNTIME_GATE = {result.get('gate', 'FAIL')}`",
                "",
                "## Live Chain",
                "",
                "`Admin API -> AI Service -> Intent Router -> frozen Fast Eligibility policy -> Fast or baseline chain`",
                "",
                f"- Runtime cases: `{metrics.get('sampleCount', 0)}`",
                f"- Fast / baseline: `{metrics.get('fastCount', 0)} / {metrics.get('baselineCount', 0)}`",
                f"- Runtime Fast activation: `{metrics.get('fastActivationRate', 0):.2%}`",
                f"- High-risk Fast: `{metrics.get('highRiskFast', 0)}`",
                f"- Safety Fast: `{metrics.get('safetyFast', 0)}`",
                f"- API errors: `{metrics.get('apiErrors', 0)}`",
                f"- Baseline/Fast decision mismatches: `{metrics.get('decisionMismatchCount', 0)}`",
                "",
                "## Latency Pair",
                "",
                f"- Baseline median / P95: `{metrics.get('baselineMedianMs', 0):.3f} / {metrics.get('baselineP95Ms', 0):.3f} ms`",
                f"- Fast median / P95: `{metrics.get('fastMedianMs', 0):.3f} / {metrics.get('fastP95Ms', 0):.3f} ms`",
                f"- Median reduction: `{metrics.get('medianLatencyReduction', 0):.2%}`",
                "",
                "## Safety And Isolation",
                "",
                f"- Checks: `{sum(bool(value) for value in checks.values())}/{len(checks)}`",
                f"- Failed checks: `{failed}`",
                f"- Fixture cleanup completed: `{str(result.get('cleanupCompleted', False)).lower()}`",
                "- Frozen benchmark executed: `false`",
                "- Router, Safety Gate, RAG and frozen Fast policy modified: `false`",
                "- Raw review text persisted in this artifact: `false`",
                "- Rollback: set `E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED=false` and restart AI Service.",
                "",
                "## Interpretation",
                "",
                "The Fast path is admitted only for requests already classified as low-touch with no risk hints and no image. All other requests retain the existing baseline workflow.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict:
    suffix = uuid.uuid4().hex[:8]
    token = login(args.admin_url)
    analysis_ids: list[int] = []
    review_ids: list[str] = []
    result: dict[str, Any] = {
        "schemaVersion": "fast-eligibility-runtime-gate-v1",
        "gate": "FAIL",
        "frozenBenchmarkExecuted": False,
        "routerModified": False,
        "safetyGateModified": False,
        "policyModified": False,
        "rawReviewTextPersisted": False,
        "cleanupCompleted": False,
    }
    try:
        readiness, _ = request_json("GET", f"{args.ai_url}/api/v1/system/readiness")
        runtime_status = readiness.get("fastEligibilityRuntime") or {}
        cases = [
            ("ordinary", "商品很好，物流也很快。", None, "UNKNOWN", []),
            ("standard", "尺寸偏小，但整体还能正常使用。", 5, "USER_PROVIDED", []),
            ("unknown", "商品不错，包装正常。", None, "UNKNOWN", []),
            ("ambiguous", "收到商品，先使用一段时间再说。", None, "UNKNOWN", []),
            ("lowRating", "尺寸偏小，但是还能使用。", 1, "USER_PROVIDED", []),
            ("highRisk", "商家要求五星截图后返现。", 5, "USER_PROVIDED", []),
            ("safety", "收到商品后漏电，非常危险。", 1, "USER_PROVIDED", []),
            ("image", "商品很好，物流也很快。", 5, "USER_PROVIDED", ["https://example.com/review.jpg"]),
        ]
        summaries = []
        for name, text, rating, rating_source, images in cases:
            review_id = f"step215-{name}-{suffix}"
            review_ids.append(review_id)
            analysis_id, response, elapsed = analyze_admin(
                args.admin_url,
                token,
                {
                    "reviewId": review_id,
                    "productId": 1181000,
                    "productName": "Step 21.5 runtime gate",
                    "reviewText": text,
                    "imageUrls": images,
                    "rating": rating,
                    "ratingSource": rating_source,
                },
            )
            analysis_ids.append(analysis_id)
            summaries.append(summarize(name, response, elapsed))

        latency_baseline: list[float] = []
        latency_fast: list[float] = []
        decision_mismatches = 0
        for index in range(max(1, args.latency_pairs)):
            base_id = f"step215-latency-base-{suffix}-{index}"
            fast_id = f"step215-latency-fast-{suffix}-{index}"
            review_ids.extend([base_id, fast_id])
            common = {
                "productId": "1181000",
                "productName": "Step 21.5 latency gate",
                "reviewText": "商品很好，物流也很快。",
                "imageUrls": [],
                "rating": 5,
                "ratingSource": "USER_PROVIDED",
                "ragEnabled": False,
            }
            baseline_payload = {**common, "reviewId": base_id, "auditMode": "fast_runtime_baseline"}
            fast_payload = {**common, "reviewId": fast_id}
            if index % 2:
                fast_response, fast_elapsed = analyze_ai(args.ai_url, fast_payload)
                baseline_response, baseline_elapsed = analyze_ai(args.ai_url, baseline_payload)
            else:
                baseline_response, baseline_elapsed = analyze_ai(args.ai_url, baseline_payload)
                fast_response, fast_elapsed = analyze_ai(args.ai_url, fast_payload)
            latency_baseline.append(baseline_elapsed)
            latency_fast.append(fast_elapsed)
            baseline_decision = (baseline_response.get("review_governance") or {}).get("decision") or {}
            fast_decision = (fast_response.get("review_governance") or {}).get("decision") or {}
            if (
                baseline_decision.get("code") != fast_decision.get("code")
                or baseline_response.get("risk_types") != fast_response.get("risk_types")
                or baseline_response.get("requires_human_review") != fast_response.get("requires_human_review")
            ):
                decision_mismatches += 1

        by_name = {row["case"]: row for row in summaries}
        fast_rows = [row for row in summaries if row["executedChain"] == "FAST_SHORT_CHAIN"]
        baseline_rows = [row for row in summaries if row["executedChain"] == "BASELINE_CHAIN"]
        high_fast = sum(
            row["executedChain"] == "FAST_SHORT_CHAIN" and bool(set(row["riskTypes"]).intersection(HIGH_RISKS))
            for row in summaries
        )
        safety_fast = sum(
            row["executedChain"] == "FAST_SHORT_CHAIN" and row["safetyGateTriggered"]
            for row in summaries
        )
        persisted_fast_trace = False
        fast_analysis_ids = [str(analysis_ids[index]) for index, row in enumerate(summaries) if row["executedChain"] == "FAST_SHORT_CHAIN"]
        if fast_analysis_ids:
            traces = mysql(
                "SELECT workflow_trace_json FROM litemall_review_ai_analysis WHERE id IN ("
                + ",".join(fast_analysis_ids)
                + ");"
            )
            persisted_fast_trace = bool(traces) and all(
                any(
                    item.get("node") == "fast_eligibility_gate"
                    and ((item.get("output") or {}).get("executedChain") == "FAST_SHORT_CHAIN")
                    for item in json.loads(trace)
                    if isinstance(item, dict)
                )
                for trace in traces
            )

        baseline_median = round(statistics.median(latency_baseline), 3)
        fast_median = round(statistics.median(latency_fast), 3)
        reduction = round((baseline_median - fast_median) / baseline_median, 6) if baseline_median else 0.0
        metrics = {
            "sampleCount": len(summaries),
            "fastCount": len(fast_rows),
            "baselineCount": len(baseline_rows),
            "fastActivationRate": round(len(fast_rows) / len(summaries), 6),
            "highRiskFast": high_fast,
            "safetyFast": safety_fast,
            "apiErrors": 0,
            "decisionMismatchCount": decision_mismatches,
            "baselineMedianMs": baseline_median,
            "baselineP95Ms": percentile(latency_baseline, 0.95),
            "fastMedianMs": fast_median,
            "fastP95Ms": percentile(latency_fast, 0.95),
            "medianLatencyReduction": reduction,
        }
        long_nodes = {"planner", "policy_evidence_retrieve", "reflection", "hybrid_rag_retrieval"}
        checks = {
            "runtimeEnabled": runtime_status.get("enabled") is True,
            "canaryAtOneHundredPercent": runtime_status.get("canaryPercent") == 100,
            "frozenPolicyAvailable": runtime_status.get("policyAvailable") is True,
            "frozenPolicyIntegrityReady": runtime_status.get("policyIntegrity") == "ready",
            "ordinaryUsesFast": by_name["ordinary"]["executedChain"] == "FAST_SHORT_CHAIN",
            "standardUsesFast": by_name["standard"]["executedChain"] == "FAST_SHORT_CHAIN",
            "unknownRatingUsesFast": by_name["unknown"]["executedChain"] == "FAST_SHORT_CHAIN",
            "ambiguousUsesBaseline": by_name["ambiguous"]["executedChain"] == "BASELINE_CHAIN",
            "lowRatingUsesBaseline": by_name["lowRating"]["executedChain"] == "BASELINE_CHAIN",
            "highRiskUsesBaseline": by_name["highRisk"]["executedChain"] == "BASELINE_CHAIN",
            "safetyUsesBaseline": by_name["safety"]["executedChain"] == "BASELINE_CHAIN",
            "imageUsesBaseline": by_name["image"]["executedChain"] == "BASELINE_CHAIN",
            "fastSkipsLongNodes": all(long_nodes.isdisjoint(row["nodes"]) for row in fast_rows),
            "fastSkipsPolicyRetrieval": all(row["policyRetrievalMode"] == "not_executed" for row in fast_rows),
            "fastSkipsModelEnhancement": all(row["llmProvider"] is None for row in fast_rows),
            "highRiskFastIsZero": high_fast == 0,
            "safetyFastIsZero": safety_fast == 0,
            "pairedDecisionsMatch": decision_mismatches == 0,
            "fastTracePersisted": persisted_fast_trace,
            "fastMedianLatencyImproved": fast_median < baseline_median,
            "fastP95LatencyNoRegression": percentile(latency_fast, 0.95) <= percentile(latency_baseline, 0.95) * 1.10,
        }
        result.update({"checks": checks, "cases": summaries, "metrics": metrics})
        result["gate"] = "PASS" if all(checks.values()) else "FAIL"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        try:
            if analysis_ids:
                joined = ",".join(str(value) for value in analysis_ids)
                mysql(f"DELETE FROM litemall_ai_governance_observation WHERE analysis_id IN ({joined});")
                mysql(f"DELETE FROM litemall_ai_review_risk_task WHERE analysis_id IN ({joined});")
                mysql(f"DELETE FROM litemall_review_ai_analysis WHERE id IN ({joined});")
            mysql(f"DELETE FROM litemall_ai_governance_observation WHERE review_id LIKE 'step215-%-{suffix}';")
            remove_checkpoints(review_ids)
            residue = sum(
                int(value)
                for value in mysql(
                    f"SELECT COUNT(*) FROM litemall_review_ai_analysis WHERE review_id LIKE 'step215-%-{suffix}'; "
                    f"SELECT COUNT(*) FROM litemall_ai_governance_observation WHERE review_id LIKE 'step215-%-{suffix}';"
                )
            )
            result["cleanupCompleted"] = residue == 0
            if residue:
                result["cleanupResidueCount"] = residue
                result["gate"] = "FAIL"
        except Exception as cleanup_error:
            result["cleanupError"] = f"{type(cleanup_error).__name__}:{cleanup_error}"
            result["gate"] = "FAIL"
        write_outputs(result, args.output, args.report)
    return result


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("gate") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
