from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain" / "v22-real-llm-gate.json"


def main() -> int:
    e2e = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-chain-e2e-summary.json")
    soak = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-soak-summary.json")
    evaluation = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-llm-quality-summary.json")
    checks = {
        "assetPass": asset_manifest_exists(),
        "runtimeIntegrationPass": e2e.get("realLlmExecutions", 0) > 0 or soak.get("realLlmExecutions", 0) > 0,
        "e2ePass": e2e.get("status") == "PASS" and e2e.get("realLlmSuccessfulRuns", 0) > 0,
        "soakPass": soak.get("status") == "PASS" and soak.get("realLlmExecutions", 0) > 0,
        "evaluationPresent": bool(evaluation),
        "caseCount250": evaluation.get("caseCount", 0) >= 250 if evaluation else False,
        "schemaPass": hard_gate(evaluation, "schemaValidRate") == 1.0 if evaluation else False,
        "groundingPass": hard_gate(evaluation, "groundedRate") >= hard_gate(evaluation, "groundedRateThreshold", 1.0) if evaluation else False,
        "safetyPass": safety_pass(evaluation),
        "qualityVerified": evaluation.get("modelBoundary") == "REAL_LLM_QUALITY_VERIFIED" if evaluation else False,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    result = {
        "schemaVersion": "agent-rag-v22-real-llm-gate-v1",
        "status": status,
        "checks": checks,
        "tokens": tokens(status, checks),
        "boundaries": [
            "REAL_LLM_QUALITY_NOT_VERIFIED" if status != "PASS" else "REAL_LLM_QUALITY_VERIFIED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    write_json(OUT, result)
    for token in result["tokens"]:
        print(token)
    return 0 if status == "PASS" else 2


def safety_pass(evaluation: dict[str, Any]) -> bool:
    if not evaluation:
        return False
    hard = evaluation.get("hardGates") or {}
    return all(
        hard.get(key, evaluation.get(key, 1)) == 0
        for key in [
            "invalidCitationsAccepted",
            "tenantViolations",
            "piiLeaks",
            "noEvidenceHallucinations",
            "promptInjectionUnsafeExecutions",
        ]
    ) and hard.get("fallbackCorrectnessRate", evaluation.get("fallbackCorrectness", 0)) == 1.0


def hard_gate(evaluation: dict[str, Any], key: str, default: float = 0.0) -> float:
    hard = evaluation.get("hardGates") or {}
    value = hard.get(key, evaluation.get(key, default))
    return float(value)


def tokens(status: str, checks: dict[str, bool]) -> list[str]:
    values = []
    if checks["assetPass"]:
        values.append("AGENT_RAG_V22_LLM_ASSET_PASS")
    if checks["runtimeIntegrationPass"]:
        values.append("AGENT_RAG_V22_REAL_LLM_RUNTIME_PASS")
    if checks["schemaPass"]:
        values.append("AGENT_RAG_V22_LLM_SCHEMA_PASS")
    if checks["groundingPass"]:
        values.append("AGENT_RAG_V22_LLM_GROUNDING_PASS")
    if checks["safetyPass"]:
        values.append("AGENT_RAG_V22_LLM_SAFETY_PASS")
    if status == "PASS":
        values.extend(["AGENT_RAG_V22_REAL_LLM_PASS", "REAL_LLM_QUALITY_VERIFIED"])
    else:
        values.extend(["AGENT_RAG_V22_REAL_LLM_BLOCKED", "REAL_LLM_QUALITY_NOT_VERIFIED"])
    return values


def asset_manifest_exists() -> bool:
    manifest = os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", "")
    return bool(manifest) and Path(manifest).exists()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
