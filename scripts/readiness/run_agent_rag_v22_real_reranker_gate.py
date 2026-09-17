from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain" / "v22-real-reranker-gate.json"


def main() -> int:
    e2e = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-chain-e2e-summary.json")
    soak = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-soak-summary.json")
    benchmark = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-reranker-benchmark-summary.json")
    checks = {
        "assetPass": asset_manifest_exists(),
        "runtimeIntegrationPass": e2e.get("realRerankerExecutions", 0) > 0 or soak.get("realRerankerExecutions", 0) > 0,
        "e2ePass": e2e.get("status") == "PASS" and e2e.get("realRerankerSuccessfulRuns", 0) > 0,
        "soakPass": soak.get("status") == "PASS" and soak.get("realRerankerExecutions", 0) > 0,
        "benchmarkPresent": bool(benchmark),
        "falseEvidenceZero": benchmark.get("falseEvidenceRate", 0) == 0 if benchmark else False,
        "tenantViolationsZero": benchmark.get("tenantViolations", 0) == 0 if benchmark else False,
        "semanticImproved": benchmark.get("qualityDecision") == "AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED",
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    result = {
        "schemaVersion": "agent-rag-v22-real-reranker-gate-v1",
        "status": status,
        "checks": checks,
        "tokens": tokens(status, checks),
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED" if status != "PASS" else "MODEL_RERANKER_VERIFIED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    write_json(OUT, result)
    for token in result["tokens"]:
        print(token)
    return 0 if status == "PASS" else 2


def tokens(status: str, checks: dict[str, bool]) -> list[str]:
    values = []
    if checks["assetPass"]:
        values.append("AGENT_RAG_V22_RERANKER_ASSET_PASS")
    if checks["runtimeIntegrationPass"]:
        values.append("AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS")
    if checks["e2ePass"]:
        values.append("AGENT_RAG_V22_REAL_RERANKER_E2E_PASS")
    if checks["soakPass"]:
        values.append("AGENT_RAG_V22_REAL_RERANKER_SOAK_PASS")
    if status == "PASS":
        values.extend(["AGENT_RAG_V22_REAL_RERANKER_PASS", "MODEL_RERANKER_VERIFIED"])
    else:
        values.extend(["AGENT_RAG_V22_REAL_RERANKER_BLOCKED", "MODEL_RERANKER_NOT_VERIFIED"])
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
