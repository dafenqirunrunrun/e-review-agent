from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-bge-m3-sparse-route-closure.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checks = payload.get("checks", {})
    required_statuses = {
        "BGE_M3_SPARSE_RUNTIME_VERIFIED",
        "BGE_M3_SPARSE_ENCODING_NOT_REPRODUCIBLE",
        "BGE_M3_SPARSE_ROUTE_REJECTED_FOR_V2_3",
    }
    statuses = set(payload.get("status", []))
    conditions = {
        "24-run Matrix Complete": payload.get("precisionMatrixRunCount") == 24
        and payload.get("phase94BPsqGate", {}).get("completeRunCount") == 24,
        "No Stable Encoding Configuration": payload.get("finalDecision") == "NO_STABLE_SPARSE_ENCODING_CONFIGURATION",
        "Index Rebuild Not Allowed": checks.get("sparseIndexRebuildAllowed") is False,
        "Retrieval Calibration Not Allowed": checks.get("sparseRetrievalCalibrationAllowed") is False,
        "Phase 9.4C Not Allowed": checks.get("phase94cThreeWayFusionAllowed") is False,
        "Runtime Integration Not Allowed": checks.get("runtimeIntegrationAllowed") is False,
        "Runtime Verified But Route Rejected": checks.get("runtimeVerified") is True
        and checks.get("sparseRouteAllowedForV23Runtime") is False,
        "Status Set Complete": required_statuses.issubset(statuses),
        "No Global Failure Claim": payload.get("decisionBoundary", {}).get("doesNotClaimGlobalModelFailure") is True
        and payload.get("decisionBoundary", {}).get("doesNotClaimFlagEmbeddingGlobalFailure") is True,
    }
    failed = [name for name, ok in conditions.items() if not ok]
    if failed:
        print("E_REVIEW_V23_BGE_M3_SPARSE_ROUTE_CLOSURE_BLOCKED")
        for item in failed:
            print(f"FAILED: {item}")
        return 1
    print("E_REVIEW_V23_BGE_M3_SPARSE_ROUTE_CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
