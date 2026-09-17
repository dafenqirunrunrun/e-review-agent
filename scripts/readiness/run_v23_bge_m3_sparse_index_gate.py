from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    gate = read_json(OUT / "v23-bge-m3-sparse-environment-gate.json")
    build = read_json(OUT / "v23-bge-m3-sparse-index-build.json")
    integrity = read_json(OUT / "v23-bge-m3-sparse-index-integrity.json")
    repeat = read_json(OUT / "v23-bge-m3-sparse-index-repeatability.json")
    checks = {
        "environmentGatePass": gate.get("status") == "PASS",
        "realSparseExecution": gate.get("checks", {}).get("realSparseExecution") is True,
        "eligibleChunkCountPositive": build.get("eligibleChunkCount", 0) > 0,
        "encodedEqualsEligible": build.get("encodedChunkCount") == build.get("eligibleChunkCount"),
        "invalidWeightChunkCountZero": build.get("invalidWeightChunkCount") == 0,
        "contentHashMismatchCountZero": build.get("contentHashMismatchCount") == 0,
        "expiredIndexedCountZero": integrity.get("expiredIndexedCount") == 0,
        "inactiveIndexedCountZero": integrity.get("inactiveIndexedCount") == 0,
        "disabledIndexedCountZero": integrity.get("disabledIndexedCount") == 0,
        "tenantViolationCountZero": integrity.get("tenantViolationCount") == 0,
        "emptyVectorRateAllowed": float(build.get("emptyVectorChunkRate", 1.0)) <= 0.001,
        "canonicalIndexHashStable": repeat.get("canonicalIndexHashStable") is True,
    }
    result = {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-index-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
    }
    write_json(OUT / "v23-bge-m3-sparse-index-gate.json", result)
    if result["status"] == "PASS":
        print("E_REVIEW_V23_BGE_M3_SPARSE_INDEX_PASS")
        return 0
    print("E_REVIEW_V23_BGE_M3_SPARSE_INDEX_BLOCKED")
    return 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
