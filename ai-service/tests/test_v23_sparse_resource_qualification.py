from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_precision_stability_matrix as psq  # noqa: E402


def test_resource_gate_blocks_when_no_stable_candidate() -> None:
    payload = psq.build_resource_result([], {"rows": []}, {"rows": []}, {"rows": []})
    assert payload["gate"] == "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED"


def test_sensitive_configuration_has_no_absolute_path() -> None:
    config = {
        "policyVersion": "x",
        "modelId": "BAAI/bge-m3",
        "configurationHash": "abc",
    }
    text = psq.render_configuration_yml(config)
    assert ("D:" + "\\") not in text
    assert ("C:" + "\\") not in text
