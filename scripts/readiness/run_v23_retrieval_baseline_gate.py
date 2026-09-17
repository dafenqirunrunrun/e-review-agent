from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    baseline = read_json(OUT / "v23-current-retrieval-baseline.json")
    checks = {
        "baselinePresent": bool(baseline),
        "datasetHashPresent": len(str(baseline.get("datasetHash", ""))) == 64,
        "knowledgeHashPresent": len(str(baseline.get("knowledgeSnapshotHash", ""))) == 64,
        "configurationHashPresent": bool(baseline.get("configurationHash")),
        "bm25ExecutionsPositive": baseline.get("bm25Executions", 0) > 0,
        "denseExecutionsPositive": baseline.get("denseExecutions", 0) > 0,
        "rrfExecutionsPositive": baseline.get("rrfExecutions", 0) > 0,
        "bm25MetricsComplete": metrics_complete(baseline.get("bm25Metrics") or {}),
        "denseMetricsComplete": metrics_complete(baseline.get("denseMetrics") or {}),
        "rrfMetricsComplete": metrics_complete(baseline.get("rrfMetrics") or {}),
        "unionOracleMetricsComplete": metrics_complete(baseline.get("unionOracleMetrics") or {}),
        "metricsHashPresent": len(str(baseline.get("baselineMetricsHash", ""))) == 64,
    }
    payload = {
        "schemaVersion": "agent-rag-v23-retrieval-baseline-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "datasetHash": baseline.get("datasetHash", ""),
        "baselineMetricsHash": baseline.get("baselineMetricsHash", ""),
        "qualityClaim": "BASELINE_COMPLETE_NOT_QUALITY_PASS",
    }
    write_json(OUT / "v23-retrieval-baseline-gate.json", payload)
    if payload["status"] == "PASS":
        print("E_REVIEW_V23_RETRIEVAL_BASELINE_COMPLETE")
        return 0
    print("E_REVIEW_V23_RETRIEVAL_BASELINE_BLOCKED")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 1


def metrics_complete(metrics: dict[str, Any]) -> bool:
    required = ["recallAt5", "recallAt10", "recallAt20", "recallAt50", "recallAt100", "hitRateAt5", "hitRateAt10", "hitRateAt20", "hitRateAt50", "mrr", "ndcgAt5"]
    return all(key in metrics for key in required)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
