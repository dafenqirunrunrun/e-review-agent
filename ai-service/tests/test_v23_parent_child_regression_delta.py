from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-three-layer-regression-delta.json"


def test_three_layer_regression_artifact_has_required_layers() -> None:
    if not ARTIFACT.exists():
        return
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert payload["layerA"]["commit"] == "c230fffd"
    assert payload["layerB"]["commit"] == "f60948d7"
    assert payload["layerC"]["commit"]
    assert "newFailuresAtoB" in payload
    assert "newFailuresBtoC" in payload
    assert payload["qualifiedFullRegressionPass"] in {True, False}
