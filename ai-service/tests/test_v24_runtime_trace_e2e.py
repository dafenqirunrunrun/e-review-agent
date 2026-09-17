from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_controlled_e2e_artifact_has_no_business_writes_or_external_tools() -> None:
    payload = json.loads((ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-e2e.json").read_text(encoding="utf-8"))
    assert payload["requests"] == 20
    assert payload["requestCorrelationMatches"] == 20
    assert payload["traceIntegrityPasses"] == 20
    assert payload["businessWrites"] == 0
    assert payload["externalToolCalls"] == 0
