from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-admin-operations" / "admin-operations-summary.json"
SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"RAG_BGE_M3_MODEL_PATH",
        r"Authorization",
        r"password",
        r"token",
        r"system prompt",
        r"[A-Za-z]:\\\\",
    ]
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-base-url", default="http://127.0.0.1:8083")
    parser.add_argument("--username", default=os.environ.get("LITEMALL_ADMIN_USERNAME", "admin123"))
    parser.add_argument("--password-env", default="LITEMALL_ADMIN_PASSWORD")
    parser.add_argument("--subject-prefix", default="phase2-admin-runtime-" + time.strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()
    password = os.environ.get(args.password_env, "admin123")

    result = {
        "schemaVersion": "1.0.0",
        "status": "FAIL",
        "frontendBuild": os.environ.get("AGENT_RAG_ADMIN_FRONTEND_BUILD", "UNKNOWN"),
        "frontendUnit": os.environ.get("AGENT_RAG_ADMIN_FRONTEND_UNIT", "UNKNOWN"),
        "javaTargeted": os.environ.get("AGENT_RAG_ADMIN_JAVA_TARGETED", "UNKNOWN"),
        "apiCaseCount": 0,
        "apiPassed": 0,
        "apiFailed": 0,
        "cases": {},
        "tenantViolations": 0,
        "permissionViolations": 0,
        "overridePreservedOriginal": False,
        "replayCreatedNewRun": False,
        "evidenceSensitiveLeakCount": 0,
        "createdRunIds": [],
        "summary": {},
    }

    try:
        login = post_json(args.admin_base_url + "/admin/auth/login", {"username": args.username, "password": password})
        mark(result, "adminLogin", login.get("errno") == 0)
        token = ((login.get("data") or {}).get("token") or "")
        mark(result, "adminToken", bool(token))

        unauthorized = get_json(args.admin_base_url + "/admin/agent-rag/health", "")
        unauthorized_rejected = unauthorized.get("errno") != 0
        mark(result, "permissionNoTokenRejected", unauthorized_rejected)
        if not unauthorized_rejected:
            result["permissionViolations"] += 1

        health = get_json(args.admin_base_url + "/admin/agent-rag/health", token)
        runtime = (health.get("data") or {}).get("runtime") or {}
        circuit = (health.get("data") or {}).get("circuitBreaker") or {}
        mark(result, "runtimeHealth", health.get("errno") == 0 and bool(runtime) and bool(circuit))

        normal = analyze(args.admin_base_url, token, args.subject_prefix + "-normal", "Synthetic admin operations fixture: packaging is acceptable and delivery is normal.")
        high = analyze(args.admin_base_url, token, args.subject_prefix + "-high", "Synthetic admin operations fixture: broken package, refund request, after-sales complaint and public negative review risk.")
        fallback = analyze(
            args.admin_base_url,
            token,
            args.subject_prefix + "-fallback",
            "Synthetic admin operations fixture: force schema repair and rule fallback visibility.",
            {"forceInvalidModelOutput": True},
        )
        created = [normal, high, fallback]
        result["createdRunIds"] = [((item.get("data") or {}).get("run") or {}).get("id") for item in created]
        mark(result, "analyzeRuns", all(run_id for run_id in result["createdRunIds"]))
        mark(result, "highRiskRun", ((high.get("data") or {}).get("run") or {}).get("riskLevel") in ("high", "critical", "medium"))
        fallback_run = (fallback.get("data") or {}).get("run") or {}
        mark(result, "fallbackRun", fallback_run.get("id") is not None and fallback_run.get("fallbackUsed") is True)

        overview = get_json(args.admin_base_url + "/admin/agent-rag/overview", token)
        overview_data = overview.get("data") or {}
        mark(result, "overview", overview.get("errno") == 0 and non_negative_fields(overview_data, ["todayRunCount", "todayFallbackCount", "todayFailureCount"]))

        runs = get_json(args.admin_base_url + "/admin/agent-rag/runs?limit=50", token)
        runs_data = runs.get("data") or {}
        created_ids = set(run_id for run_id in result["createdRunIds"] if run_id)
        items = [item for item in (runs_data.get("items") or []) if item.get("id") in created_ids]
        mark(result, "runList", runs.get("errno") == 0 and len(items) >= 1 and runs_data.get("total", 0) >= 1)
        mark(result, "runListFields", has_list_fields(items))

        high_run = (high.get("data") or {}).get("run") or {}
        high_id = high_run.get("id")
        detail = get_json(f"{args.admin_base_url}/admin/agent-rag/runs/{high_id}", token)
        detail_data = detail.get("data") or {}
        mark(result, "runDetail", detail.get("errno") == 0 and bool(detail_data.get("originalDecision")) and bool(detail_data.get("effectiveDecision")))

        evidence = get_json(f"{args.admin_base_url}/admin/agent-rag/runs/{high_id}/evidence", token)
        evidence_data = evidence.get("data") or {}
        evidence_text = evidence_data.get("boundedJson") or ""
        leak_count = sensitive_leak_count(evidence_text)
        result["evidenceSensitiveLeakCount"] = leak_count
        mark(result, "evidenceTimeline", evidence.get("errno") == 0 and bool(evidence_data.get("bundleHash")) and leak_count == 0)

        bad_override = post_json(
            args.admin_base_url + "/admin/agent-rag/override",
            {"runId": high_id, "newRiskLevel": "medium", "newAction": "manual_review", "reason": "short", "operatorId": 1},
            token,
        )
        mark(result, "overrideValidation", bad_override.get("errno") != 0)
        override = post_json(
            args.admin_base_url + "/admin/agent-rag/override",
            {
                "runId": high_id,
                "newRiskLevel": "medium",
                "newAction": "manual_review",
                "reason": "Synthetic admin operations validates append-only human override.",
                "operatorId": 1,
            },
            token,
        )
        after_override = get_json(f"{args.admin_base_url}/admin/agent-rag/runs/{high_id}", token)
        after_data = after_override.get("data") or {}
        result["overridePreservedOriginal"] = (
            override.get("errno") == 0
            and ((after_data.get("originalDecision") or {}).get("riskLevel") == high_run.get("riskLevel"))
            and ((after_data.get("effectiveDecision") or {}).get("overridden") is True)
        )
        mark(result, "override", result["overridePreservedOriginal"])

        replay = post_json(f"{args.admin_base_url}/admin/agent-rag/runs/{high_id}/replay", {}, token)
        replay_run = (replay.get("data") or {}).get("run") or {}
        result["replayCreatedNewRun"] = replay.get("errno") == 0 and replay_run.get("id") and replay_run.get("id") != high_id
        mark(result, "replay", result["replayCreatedNewRun"])
        compare = get_json(f"{args.admin_base_url}/admin/agent-rag/runs/{high_id}/compare/{replay_run.get('id')}", token)
        compare_data = compare.get("data") or {}
        mark(result, "compare", compare.get("errno") == 0 and "changes" in compare_data and "citationAdded" in (compare_data.get("changes") or {}))

        result["summary"] = {
            "runtimeStatus": runtime.get("status"),
            "circuitState": circuit.get("state"),
            "overviewTotal": overview_data.get("todayRunCount"),
            "listed": len(items),
        }
    except Exception as exc:  # pragma: no cover - diagnostic path
        result["cases"]["unexpectedException"] = "FAIL:" + str(exc)[:240]
        result["apiFailed"] += 1

    result["apiCaseCount"] = len(result["cases"])
    result["apiPassed"] = sum(1 for value in result["cases"].values() if value == "PASS")
    result["apiFailed"] = result["apiCaseCount"] - result["apiPassed"]
    result["status"] = "PASS" if result["apiFailed"] == 0 and result["tenantViolations"] == 0 and result["permissionViolations"] == 0 and result["evidenceSensitiveLeakCount"] == 0 else "FAIL"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_ADMIN_RUNTIME_E2E_PASS")
        return 0
    print("AGENT_RAG_ADMIN_RUNTIME_E2E_FAIL")
    print(json.dumps({"cases": result["cases"], "apiFailed": result["apiFailed"]}, ensure_ascii=False))
    return 1


def analyze(base_url: str, token: str, subject_id: str, query: str, context: dict | None = None) -> dict:
    payload = {
        "requestId": short_request_id(subject_id),
        "tenantId": "__forged_client_tenant__",
        "subjectType": "review",
        "subjectId": subject_id,
        "query": query,
        "runtimeMode": "local-model",
        "schemaVersion": "2.0.0",
        "retrieval": {
            "enabled": True,
            "topK": 8,
            "rerankTopK": 4,
            "requestedMode": "bm25-first-semantic-hybrid",
            "publicTenantEnabled": True,
        },
        "context": context or {"syntheticFixture": True, "case": "admin-operations"},
    }
    return post_json(base_url + "/admin/agent-rag/analyze", payload, token)


def get_json(url: str, token: str) -> dict:
    headers = {"X-Litemall-Admin-Token": token} if token else {}
    request = urllib.request.Request(url, headers=headers)
    return read_json(request)


def post_json(url: str, payload: dict, token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Litemall-Admin-Token"] = token
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    return read_json(request)


def read_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"errno": exc.code, "errmsg": body[:240]}


def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def mark(result: dict, name: str, passed: bool) -> None:
    result["cases"][name] = "PASS" if passed else "FAIL"


def non_negative_fields(data: dict, fields: list[str]) -> bool:
    for field in fields:
        value = data.get(field)
        if not isinstance(value, (int, float)) or value < 0:
            return False
    return True


def has_list_fields(items: list[dict]) -> bool:
    if not items:
        return False
    required = ["id", "requestId", "status", "originalRiskLevel", "effectiveRiskLevel", "fallbackUsed", "overrideCount", "durationMs"]
    return all(field in items[0] for field in required)


def sensitive_leak_count(text: str) -> int:
    return sum(1 for pattern in SENSITIVE_PATTERNS if pattern.search(text or ""))


def short_request_id(subject_id: str) -> str:
    suffix = subject_id.rsplit("-", 1)[-1][:10]
    millis = str(int(time.time() * 1000))[-8:]
    return f"admops-{suffix}-{millis}"


if __name__ == "__main__":
    raise SystemExit(main())
