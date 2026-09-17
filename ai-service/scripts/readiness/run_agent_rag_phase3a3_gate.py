from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a3_common import provider_status, write_phase3a3_json
from diagnostics.run_bge_m3_provider_resource_benchmark import run as run_resource
from diagnostics.run_bge_m3_provider_sanity import run as run_sanity
from e2e.run_agent_rag_phase3a3_provider_index_e2e import run as run_e2e
from evaluation.run_agent_rag_phase3a3_provider_eval import run as run_eval


def run_gate() -> dict:
    flag_status = provider_status("flagembedding")
    sanity = run_sanity()
    evaluation = run_eval()
    resource = run_resource()
    e2e = run_e2e()
    phase3a2 = _run_phase3a2_gate()
    official = flag_status["status"] == "READY"
    checks = {
        "officialProvider": official,
        "providerFingerprint": bool((flag_status.get("metadata") or {}).get("effectiveEmbeddingFingerprint")),
        "providerIndexCompatibility": e2e.get("status") == "PASS",
        "providerAbEvaluation": evaluation.get("providers", {}).get("flagembedding", {}).get("status") == "PASS",
        "providerFallback": e2e.get("scenarios", {}).get("flagIndexFlagProvider", {}).get("status") in {"PASS", "BLOCKED"},
        "phase3a2Regression": phase3a2["returnCode"] == 0,
        "pipCheck": _pip_check()["returnCode"] == 0,
        "realDenseActuallyExecutable": official,
    }
    pass_all = all(checks.values())
    quality = evaluation.get("qualityConclusion", "AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_BLOCKED")
    result = {
        "status": "PASS" if pass_all else "BLOCKED",
        "checks": checks,
        "qualityConclusion": quality,
        "selectedProviderImpl": evaluation.get("selectedProviderImpl", "legacy-cls"),
        "defaultRetrievalMode": evaluation.get("defaultRetrievalMode", "bm25-first-semantic-hybrid"),
        "flagEmbeddingStatus": flag_status,
        "evidence": {
            "sanity": "artifacts/agent-rag/v2.0-phase3a3/provider-sanity-summary.json",
            "evaluation": "artifacts/agent-rag/v2.0-phase3a3/provider-evaluation-summary.json",
            "resource": "artifacts/agent-rag/v2.0-phase3a3/provider-resource-summary.json",
            "e2e": "artifacts/agent-rag/v2.0-phase3a3/provider-index-e2e-summary.json",
        },
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "LARGE_SCALE_KNOWLEDGE_NOT_VERIFIED",
            "PRODUCTION_CONCURRENCY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    result["tokens"] = _tokens(result)
    write_phase3a3_json("phase3a3-gate-result.json", result)
    return result


def _run_phase3a2_gate() -> dict:
    completed = subprocess.run([sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase3a2_gate.py"], cwd=ROOT, text=True, capture_output=True)
    return {"returnCode": completed.returncode, "stdoutTail": completed.stdout[-1200:], "stderrTail": completed.stderr[-1200:]}


def _pip_check() -> dict:
    completed = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT, text=True, capture_output=True)
    return {"returnCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _tokens(result: dict) -> list[str]:
    tokens = []
    if result["checks"]["officialProvider"]:
        tokens.append("AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER_PASS")
    if result["checks"]["providerFingerprint"]:
        tokens.append("AGENT_RAG_PROVIDER_INDEX_FINGERPRINT_PASS")
    if result["checks"]["providerAbEvaluation"]:
        tokens.append("AGENT_RAG_PROVIDER_AB_EVALUATION_PASS")
    if result["checks"]["providerFallback"]:
        tokens.append("AGENT_RAG_PROVIDER_FALLBACK_PASS")
    tokens.append(result["qualityConclusion"])
    if result["status"] == "PASS":
        tokens.append("AGENT_RAG_PHASE3A3_PASS")
    tokens.extend(result["boundaries"])
    return tokens


if __name__ == "__main__":
    payload = run_gate()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    for token in payload["tokens"]:
        print(token)
    raise SystemExit(0 if payload["status"] == "PASS" else 2)
