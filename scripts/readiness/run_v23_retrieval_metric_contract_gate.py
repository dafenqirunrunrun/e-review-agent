from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    audit = read_json(OUT / "v23-retrieval-metric-contract-audit.json")
    corrected = read_json(OUT / "v23-current-retrieval-baseline-corrected.json")
    checks = {
        "auditPass": audit.get("status") == "PASS",
        "correctedBaselinePresent": corrected.get("status") == "COMPLETE",
        "rawUnionGteBm25Coverage": corrected.get("rawUnionRecall", {}).get("coverageAt100", 0) >= corrected.get("bm25Recall", {}).get("coverageAt100", 1),
        "rawUnionGteDenseCoverage": corrected.get("rawUnionRecall", {}).get("coverageAt100", 0) >= corrected.get("denseRecall", {}).get("coverageAt100", 1),
        "rawUnionGteBm25Recall": corrected.get("rawUnionRecall", {}).get("recallAt100", 0) >= corrected.get("bm25Recall", {}).get("recallAt100", 1),
        "rawUnionGteDenseRecall": corrected.get("rawUnionRecall", {}).get("recallAt100", 0) >= corrected.get("denseRecall", {}).get("recallAt100", 1),
        "metricFamiliesSeparated": all(key in corrected for key in ["rawUnionRecall", "rrfRecall", "unionBudgetedRecall"]),
        "oldContradictionRecorded": audit.get("checks", {}).get("oldMetricContradictionDetected") is True,
    }
    payload = {"schemaVersion": "agent-rag-v23-retrieval-metric-contract-gate-v1", "status": "PASS" if all(checks.values()) else "BLOCKED", "checks": checks}
    write_json(OUT / "v23-retrieval-metric-contract-gate.json", payload)
    print("E_REVIEW_V23_RETRIEVAL_METRIC_CONTRACT_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_RETRIEVAL_METRIC_CONTRACT_BLOCKED")
    return 0 if payload["status"] == "PASS" else 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
