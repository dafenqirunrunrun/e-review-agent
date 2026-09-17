from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def test_experimental_retrievers_default_off_if_present() -> None:
    path = OUT / "v23-retrieval-runtime-contamination-audit.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["realRerankerEnabledByDefault"] is False
    assert p["sparseRetrieverEnabledByDefault"] is False
    assert p["parentAwareRetrieverEnabledByDefault"] is False
    assert p["structuredRetrievalContentEnabledByDefault"] is False
    assert p["runtimeContaminationFree"] is True


def test_reference_baseline_keeps_experimental_features_off_if_present() -> None:
    path = OUT / "v23-retrieval-reference-baseline-lock.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["status"] == "REFERENCE_BASELINE"
    assert p["maximumFinalK"] == 5
    assert p["allowBackfill"] is False
    assert p["sparseEnabled"] is False
    assert p["realModelRerankerEnabled"] is False
    assert p["parentAwareEnabled"] is False
    assert p["structuredRepresentationEnabled"] is False
