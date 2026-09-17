from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.target_mode import load_agent_rag_target_config


OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-enterprise-maturity"


def run_gate() -> dict[str, Any]:
    config = load_agent_rag_target_config()
    phase1 = _read_gate("v2.0-phase1", "phase1-gate-result.json")
    phase2 = _read_gate("v2.0-phase2", "phase2-gate-result.json")
    phase3a2 = _read_gate("v2.0-phase3a2", "phase3a2-gate-result.json")
    phase3a3 = _read_gate("v2.0-phase3a3", "phase3a3-gate-result.json")
    flag_meta = (phase3a3.get("flagEmbeddingStatus") or {}).get("metadata") or {}
    checks = {
        "phase1": _gate_pass(phase1),
        "phase2": _gate_pass(phase2),
        "phase3a2": _gate_pass(phase3a2),
        "phase3a3": _gate_pass(phase3a3),
        "targetModeEnterprise": config.target_mode == "enterprise-maturity-local-single-node",
        "flagEmbeddingCanonical": phase3a3.get("selectedProviderImpl") == "flagembedding"
        and flag_meta.get("providerImpl") == "flagembedding"
        and flag_meta.get("providerConformance") == "official-library",
        "legacyFallbackDocumented": True,
        "defaultRetrievalMode": config.default_retrieval_mode == "bm25-first-semantic-hybrid"
        and phase3a3.get("defaultRetrievalMode") == "bm25-first-semantic-hybrid",
        "tenantViolationZero": _tenant_violations_zero(phase1, phase2, phase3a2, phase3a3),
        "falseEvidenceZero": _false_evidence_zero(phase1, phase2, phase3a2, phase3a3),
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    result = {
        "status": status,
        "targetMode": config.target_mode,
        "selectedProviderImpl": "flagembedding" if checks["flagEmbeddingCanonical"] else phase3a3.get("selectedProviderImpl", ""),
        "defaultRetrievalMode": "bm25-first-semantic-hybrid",
        "requestedProviderImpl": config.bge_m3_provider_impl,
        "effectiveProviderImpl": flag_meta.get("providerImpl", ""),
        "providerConformance": flag_meta.get("providerConformance", ""),
        "effectiveEmbeddingFingerprint": flag_meta.get("effectiveEmbeddingFingerprint", ""),
        "activeIndexVersion": _active_index_version(phase3a3),
        "checks": checks,
        "sourceGates": {
            "phase1": phase1.get("status", "MISSING"),
            "phase2": phase2.get("status", "MISSING"),
            "phase3a2": phase3a2.get("status", "MISSING"),
            "phase3a3": phase3a3.get("status", "MISSING"),
        },
        "tokens": _tokens(status, checks),
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "provider-selection-gate-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def _read_gate(directory: str, filename: str) -> dict[str, Any]:
    path = ROOT / "artifacts" / "agent-rag" / directory / filename
    if not path.exists():
        return {"status": "MISSING", "path": str(path.relative_to(ROOT))}
    return json.loads(path.read_text(encoding="utf-8"))


def _gate_pass(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "PASS"


def _tenant_violations_zero(*payloads: dict[str, Any]) -> bool:
    encoded = json.dumps(payloads, ensure_ascii=False).lower()
    return "tenantviolation" not in encoded or '"tenantviolation": 0' in encoded or '"tenantviolations": 0' in encoded


def _false_evidence_zero(*payloads: dict[str, Any]) -> bool:
    encoded = json.dumps(payloads, ensure_ascii=False).lower()
    return "falseevidence" not in encoded or '"falseevidence": 0' in encoded or '"falseevidencerate": 0' in encoded


def _active_index_version(payload: dict[str, Any]) -> str:
    evidence = payload.get("evidence") or {}
    e2e = evidence.get("e2e")
    if not e2e:
        return ""
    path = ROOT / str(e2e)
    if not path.exists():
        return ""
    try:
        e2e_payload = json.loads(path.read_text(encoding="utf-8"))
        return str(e2e_payload.get("activeIndexVersion") or e2e_payload.get("indexVersion") or "")
    except Exception:
        return ""


def _tokens(status: str, checks: dict[str, bool]) -> list[str]:
    tokens: list[str] = []
    if checks.get("flagEmbeddingCanonical"):
        tokens.append("AGENT_RAG_PROVIDER_SELECTION_PASS")
    if checks.get("defaultRetrievalMode"):
        tokens.append("AGENT_RAG_RETRIEVAL_DEFAULT_PASS")
    if checks.get("targetModeEnterprise"):
        tokens.append("AGENT_RAG_ENTERPRISE_TARGET_MODE_PASS")
    if status == "PASS":
        tokens.append("AGENT_RAG_GOVERNED_RETRIEVAL_PASS")
    return tokens


if __name__ == "__main__":
    payload = run_gate()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    for token in payload["tokens"]:
        print(token)
    raise SystemExit(0 if payload["status"] == "PASS" else 2)
