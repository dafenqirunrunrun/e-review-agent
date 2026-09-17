from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-java-runtime" / "admin-runtime-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-base-url", default="http://127.0.0.1:8083")
    parser.add_argument("--username", default=os.environ.get("LITEMALL_ADMIN_USERNAME", "admin123"))
    parser.add_argument("--password-env", default="LITEMALL_ADMIN_PASSWORD")
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()
    password = os.environ.get(args.password_env, "admin123")

    result = {
        "schemaVersion": "1.0.0",
        "status": "FAIL",
        "adminBaseUrl": args.admin_base_url,
        "health": {},
        "missing": [],
    }
    try:
        login = post_json(args.admin_base_url + "/admin/auth/login", {"username": args.username, "password": password})
        require(result, login.get("errno") == 0, "admin.login")
        token = ((login.get("data") or {}).get("token") or "")
        require(result, bool(token), "admin.token")
        health = get_json(args.admin_base_url + "/admin/agent-rag/health", token)
        require(result, health.get("errno") == 0, "agent-rag.health.errno")
        data = health.get("data") or {}
        runtime = data.get("runtime") or {}
        circuit = data.get("circuitBreaker") or {}
        result["health"] = {
            "runtimeStatus": runtime.get("status"),
            "targetMode": runtime.get("targetMode"),
            "effectiveProviderImpl": runtime.get("effectiveProviderImpl"),
            "providerConformance": runtime.get("providerConformance"),
            "indexCompatible": runtime.get("indexCompatible"),
            "fallbackUsed": runtime.get("fallbackUsed"),
            "circuitBreakerState": circuit.get("state"),
        }
        require(result, runtime.get("status") == "ready", "runtime.status")
        require(result, runtime.get("targetMode") == "enterprise-maturity-local-single-node", "runtime.targetMode")
        require(result, runtime.get("effectiveProviderImpl") == "flagembedding", "runtime.provider")
        require(result, runtime.get("providerConformance") == "official-library", "runtime.conformance")
        require(result, runtime.get("indexCompatible") is True, "runtime.indexCompatible")
        require(result, runtime.get("fallbackUsed") is False, "runtime.fallbackUsed")
        require(result, circuit.get("state") == "CLOSED", "circuit.closed")
        result["status"] = "PASS" if not result["missing"] else "FAIL"
    except Exception as exc:  # pragma: no cover - gate diagnostics
        result["missing"].append(f"query-error:{exc}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_ADMIN_API_RUNTIME_PASS")
        return 0
    print("AGENT_RAG_ADMIN_API_RUNTIME_FAIL")
    print(json.dumps({"missing": result["missing"]}, ensure_ascii=False))
    return 1


def get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"X-Litemall-Admin-Token": token})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")[:500]) from exc


def require(result: dict, condition: bool, name: str) -> None:
    if not condition:
        result["missing"].append(name)


if __name__ == "__main__":
    raise SystemExit(main())
