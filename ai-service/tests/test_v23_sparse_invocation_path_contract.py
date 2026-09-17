from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_precision_stability_matrix as psq  # noqa: E402


def test_invocation_path_diff_records_material_output_difference() -> None:
    payload = psq.invocation_path_diff()
    rows = payload["comparisons"]["PathA_vs_PathB"]
    assert any(row["field"] == "outputSchemaVersion" and row["materialDifference"] for row in rows)


def test_path_manifest_does_not_expose_local_model_path() -> None:
    payload = psq.path_manifest("DQA_CONTROL_PATH", "FlagEmbedding.encode", "raw_lexical_weights", True, (1, 8))
    rendered = str(payload)
    assert ("D:" + "\\") not in rendered
    assert ("Us" + "ers") not in rendered


def test_order_hash_is_order_sensitive() -> None:
    assert psq.hash_json(["b", "a"]) != psq.hash_json(["a", "b"])
