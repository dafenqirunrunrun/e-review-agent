from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_real_retrieval_trace_artifact_does_not_enable_experimental_routes() -> None:
    payload = json.loads((ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-real-retrieval.json").read_text(encoding="utf-8"))
    assert payload["realDenseRequired"] is True
    assert payload["sparseEnabled"] is False
    assert payload["realRerankerEnabled"] is False
    assert payload["parentAwareEnabled"] is False
    if not payload["realDenseAvailable"]:
        assert payload["status"] == "REAL_RETRIEVAL_TRACE_BLOCKED_ASSET_UNAVAILABLE"
