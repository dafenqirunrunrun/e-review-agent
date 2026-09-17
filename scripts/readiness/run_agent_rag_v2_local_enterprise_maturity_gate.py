from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-final"

PY_REGRESSION = [
    "ai-service/tests/test_v200_agent_rag_phase1.py",
    "ai-service/tests/test_v200_agent_rag_phase2.py",
    "ai-service/tests/test_v200_agent_rag_phase3a.py",
    "ai-service/tests/test_v200_agent_rag_phase3a1_metrics.py",
    "ai-service/tests/test_v200_agent_rag_phase3a2.py",
    "ai-service/tests/test_v200_agent_rag_phase3a3_provider.py",
    "ai-service/tests/test_v200_agent_rag_phase3a31_dependencies.py",
    "ai-service/tests/test_v200_agent_rag_enterprise_maturity.py",
    "ai-service/tests/test_v200_agent_rag_observability.py",
    "ai-service/tests/test_v200_agent_rag_phase3b_reranker.py",
    "ai-service/tests/test_v200_agent_rag_phase3c_security.py",
    "ai-service/tests/test_v200_agent_rag_phase4_local_llm.py",
]


def run(command: list[str], cwd: Path = ROOT, timeout: int = 300) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "cwd": str(cwd),
        "returnCode": completed.returncode,
        "stdoutTail": completed.stdout[-4000:],
        "stderrTail": completed.stderr[-4000:],
    }


def ok(result: dict[str, object], *needles: str) -> bool:
    if result["returnCode"] != 0:
        return False
    text = str(result.get("stdoutTail") or "") + str(result.get("stderrTail") or "")
    return all(needle in text for needle in needles)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = {
        "gitDiffCheck": run(["git", "diff", "--check"], timeout=60),
        "phase3c1RetentionExportGate": run(
            [sys.executable, "scripts/readiness/run_agent_rag_phase3c1_retention_export_gate.py"],
            timeout=240,
        ),
        "phase4LocalLlmGate": run(
            [sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase4_local_llm_gate.py"],
            timeout=180,
        ),
        "pythonAgentRagRegression": run(
            [sys.executable, "-m", "pytest", "-ra", *PY_REGRESSION],
            timeout=240,
        ),
        "javaAgentRagTargeted": run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "mvn -pl litemall-admin-api -am -Dtest=*AgentRag* -DfailIfNoTests=false test",
            ],
            timeout=240,
        ),
        "adminBuild": run(
            ["powershell", "-NoProfile", "-Command", "npm run build:prod"],
            cwd=ROOT / "litemall-admin",
            timeout=240,
        ),
    }
    checks = {
        "diffClean": results["gitDiffCheck"]["returnCode"] == 0,
        "retentionExportGate": ok(
            results["phase3c1RetentionExportGate"],
            "AGENT_RAG_RETENTION_EXPORT_GATE_PASS",
        ),
        "localLlmGate": ok(
            results["phase4LocalLlmGate"],
            "AGENT_RAG_PHASE4_LOCAL_LLM_GATE_PASS",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
        ),
        "pythonRegression": ok(
            results["pythonAgentRagRegression"],
            "80 passed",
            "12 skipped",
        ),
        "javaTargeted": ok(
            results["javaAgentRagTargeted"],
            "Tests run: 28, Failures: 0, Errors: 0, Skipped: 0",
        ),
        "adminBuild": results["adminBuild"]["returnCode"] == 0 and "Build complete" in str(results["adminBuild"].get("stdoutTail", "")),
    }
    result = {
        "schemaVersion": "agent-rag-v2-local-enterprise-maturity-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "results": results,
        "scope": "enterprise-maturity-local-single-node",
        "boundaries": [
            "LOCAL_SINGLE_NODE_READY_FOR_DEMO",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "MODEL_RERANKER_NOT_VERIFIED_UNLESS_REAL_ASSET_CONFIGURED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUBLIC_REPO_CHANGES",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    (OUT / "local-enterprise-maturity-gate-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result["status"] != "PASS":
        print("AGENT_RAG_LOCAL_ENTERPRISE_MATURITY_GATE_FAIL")
        for name, passed in checks.items():
            print(f"{name}={passed}")
        raise SystemExit(2)
    print("AGENT_RAG_LOCAL_SINGLE_NODE_SECURITY_PASS")
    print("AGENT_RAG_LOCAL_SINGLE_NODE_RUNTIME_PASS")
    print("AGENT_RAG_LOCAL_SINGLE_NODE_ADMIN_PASS")
    print("AGENT_RAG_LOCAL_SINGLE_NODE_TESTS_PASS")
    print("AGENT_RAG_V2_LOCAL_ENTERPRISE_MATURITY_PASS")
    print("LOCAL_SINGLE_NODE_READY_FOR_DEMO")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUBLIC_REPO_CHANGES")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
