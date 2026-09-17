from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_corpus_quality_audit as dqa  # noqa: E402


def test_precision_empty_not_caused_by_fp16_when_both_empty() -> None:
    assert dqa.precision_conclusion({"rows": [{"fp16Empty": True, "fp32Empty": True}]}) == "SPARSE_EMPTY_NOT_CAUSED_BY_FP16"


def test_precision_parity_when_both_non_empty() -> None:
    assert dqa.precision_conclusion({"rows": [{"fp16Empty": False, "fp32Empty": False}]}) == "SPARSE_PRECISION_PARITY_PASS"


def test_sparse_summary_does_not_store_weight_map() -> None:
    summary = dqa.summarize_sparse_outputs(["hello world"], [{1: 0.5, 2: 0.25}], {"durationMs": 10.0})
    assert summary["rawSparseNonEmptyRate"] == 1.0
    assert "weights" not in summary
