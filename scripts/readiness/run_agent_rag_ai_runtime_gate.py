from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-java-runtime" / "ai-runtime-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    result = {
        "schemaVersion": "1.0.0",
        "status": "FAIL",
        "baseUrl": args.base_url,
        "health": {},
        "analyze": {},
        "missing": [],
    }
    try:
        health = get_json(args.base_url + "/api/v1/internal/agent-rag/dense/health")
        result["health"] = sanitize_health(health)
        require(result, health.get("status") == "ready", "health.status")
        require(result, health.get("targetMode") == "enterprise-maturity-local-single-node", "targetMode")
        require(result, health.get("effectiveProviderImpl") == "flagembedding", "effectiveProviderImpl")
        require(result, health.get("providerConformance") == "official-library", "providerConformance")
        require(result, health.get("indexCompatible") is True, "indexCompatible")
        require(result, health.get("fallbackUsed") is False, "fallbackUsed")

        request_id = "ai-runtime-gate-" + str(int(time.time() * 1000))
        payload = {
            "requestId": request_id,
            "tenantId": "__local__",
            "subjectType": "review",
            "subjectId": "ai-runtime-gate-subject",
            "query": "Broken package asks refund and after-sales review.",
            "runtimeMode": "local-model",
            "schemaVersion": "2.0.0",
            "retrieval": {"enabled": True, "topK": 8, "rerankTopK": 4, "publicTenantEnabled": True},
            "context": {"syntheticFixture": True},
        }
        analyzed = post_json(args.base_url + "/api/v1/agent-rag/analyze", payload)
        result["analyze"] = {
            "requestIdMatches": analyzed.get("requestId") == request_id,
            "tenantId": analyzed.get("tenantId"),
            "subjectId": analyzed.get("subjectId"),
            "riskLevel": (analyzed.get("decision") or {}).get("riskLevel"),
            "schemaVersion": (analyzed.get("runtime") or {}).get("schemaVersion"),
            "targetMode": (analyzed.get("runtime") or {}).get("targetMode"),
            "citationCount": len(((analyzed.get("retrieval") or {}).get("citations") or [])),
            "fallbackUsed": (analyzed.get("runtime") or {}).get("fallbackUsed"),
        }
        require(result, result["analyze"]["requestIdMatches"], "analyze.requestId")
        require(result, result["analyze"]["tenantId"] == "__local__", "analyze.tenant")
        require(result, result["analyze"]["schemaVersion"] == "2.0.0", "analyze.schema")
        require(result, result["analyze"]["targetMode"] == "enterprise-maturity-local-single-node", "analyze.targetMode")
        result["status"] = "PASS" if not result["missing"] else "FAIL"
    except Exception as exc:  # pragma: no cover - gate diagnostics
        result["missing"].append(f"query-error:{exc}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_AI_RUNTIME_PASS")
        return 0
    print("AGENT_RAG_AI_RUNTIME_FAIL")
    print(json.dumps({"missing": result["missing"]}, ensure_ascii=False))
    return 1


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")[:500]) from exc


def require(result: dict, condition: bool, name: str) -> None:
    if not condition:
        result["missing"].append(name)


def sanitize_health(health: dict) -> dict:
    allowed = [
        "status",
        "targetMode",
        "defaultRetrievalMode",
        "requestedProvider",
        "requestedProviderImpl",
        "effectiveProvider",
        "effectiveProviderImpl",
        "providerConformance",
        "library",
        "libraryVersion",
        "modelLoaded",
        "device",
        "embeddingDimension",
        "activeIndexVersion",
        "indexCompatible",
        "fallbackUsed",
    ]
    return {key: health.get(key) for key in allowed}


if __name__ == "__main__":
    raise SystemExit(main())
