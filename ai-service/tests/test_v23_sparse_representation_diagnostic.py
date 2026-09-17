from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_corpus_quality_audit as dqa  # noqa: E402


def test_field_count_prefers_minimal_representation() -> None:
    assert dqa.field_count("R1_SECTION_CONTENT") < dqa.field_count("R3_SAFE_SCOPE_TITLE_SECTION_CONTENT")


def test_dqa_gate_requires_all_sections() -> None:
    gate = dqa.build_dqa_gate(
        {"eligibleChunkCount": 153, "rows": [{}] * 153},
        {"eligibleChunkCount": 153, "metrics": {"x": 1}},
        {"gate": {"status": "PASS"}},
        {"conclusion": "SPARSE_PRECISION_PARITY_PASS"},
        {"conclusion": "HISTORICAL_NON_EMPTY_SET_NOT_FULLY_IDENTIFIABLE"},
        {"gate": {"status": "PASS"}},
        {"primaryRootCause": "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"},
    )
    assert gate["status"] == "PASS"
    assert gate["phase94cAllowed"] is False
