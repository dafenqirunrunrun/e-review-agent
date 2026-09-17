from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def _read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_v23_metric_contract_separates_raw_union_budgeted_union_and_rrf():
    audit = _read("v23-retrieval-metric-contract-audit.json")
    corrected = _read("v23-current-retrieval-baseline-corrected.json")
    assert audit["status"] == "PASS"
    assert audit["checks"]["oldMetricContradictionDetected"] is True
    assert audit["checks"]["rawBudgetedRrfSeparated"] is True
    assert corrected["rawUnionRecall"]["coverageAt100"] >= corrected["denseRecall"]["coverageAt100"]
    assert corrected["rawUnionRecall"]["coverageAt100"] >= corrected["bm25Recall"]["coverageAt100"]
    assert corrected["rawUnionRecall"]["recallAt100"] >= corrected["denseRecall"]["recallAt100"]
    assert corrected["rawUnionRecall"]["recallAt100"] >= corrected["bm25Recall"]["recallAt100"]
    assert corrected["rawUnionRecall"]["coverageAt100"] >= corrected["rrfRecall"]["coverageAt100"]


def test_v23_metric_contract_gate_passes():
    gate = _read("v23-retrieval-metric-contract-gate.json")
    assert gate["status"] == "PASS"
    assert gate["checks"]["rawUnionGteDenseCoverage"] is True
    assert gate["checks"]["rawUnionGteDenseRecall"] is True
