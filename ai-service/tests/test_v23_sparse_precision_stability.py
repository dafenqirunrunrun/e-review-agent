from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_precision_stability_matrix as psq  # noqa: E402


def test_empty_chunk_hash_changes_with_empty_set() -> None:
    left = psq.hash_json(["a", "b"])
    right = psq.hash_json(["a"])
    assert left != right


def test_batch_parity_detects_sensitivity() -> None:
    base = {
        "status": "PASS",
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP16",
        "expectedInputCount": 153,
        "actualInputCount": 153,
        "rawOutputCount": 153,
        "rawNonEmptyRate": 1.0,
        "performance": {"fallbackUsed": False},
    }
    rows = [
        base | {"batchSize": 1, "repeatId": 1, "emptyChunkIdsHash": "x", "activeTokenIdsHash": "a"},
        base | {"batchSize": 1, "repeatId": 2, "emptyChunkIdsHash": "x", "activeTokenIdsHash": "a"},
        base | {"batchSize": 8, "repeatId": 1, "emptyChunkIdsHash": "y", "activeTokenIdsHash": "a"},
        base | {"batchSize": 8, "repeatId": 2, "emptyChunkIdsHash": "y", "activeTokenIdsHash": "a"},
    ]
    payload = psq.build_batch_parity(rows)
    assert payload["conclusion"] == "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"


def test_precision_comparison_counts_four_buckets() -> None:
    fp16 = {
        "status": "PASS",
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP16",
        "batchSize": 1,
        "repeatId": 1,
        "rawNonEmptyCount": 2,
        "rows": [
            {"chunkId": "a", "rawEmpty": False, "activeTokenIdsHash": "1"},
            {"chunkId": "b", "rawEmpty": True, "activeTokenIdsHash": "2"},
            {"chunkId": "c", "rawEmpty": False, "activeTokenIdsHash": "3"},
            {"chunkId": "d", "rawEmpty": True, "activeTokenIdsHash": "4"},
        ],
    }
    fp32 = fp16 | {
        "precision": "FP32",
        "rawNonEmptyCount": 2,
        "rows": [
            {"chunkId": "a", "rawEmpty": False, "activeTokenIdsHash": "1"},
            {"chunkId": "b", "rawEmpty": False, "activeTokenIdsHash": "2"},
            {"chunkId": "c", "rawEmpty": True, "activeTokenIdsHash": "3"},
            {"chunkId": "d", "rawEmpty": True, "activeTokenIdsHash": "4"},
        ],
    }
    payload = psq.build_precision_comparison([fp16, fp32])
    row = payload["rows"][0]
    assert row["bothNonEmpty"] == 1
    assert row["bothEmpty"] == 1
    assert row["fp16OnlyNonEmpty"] == 1
    assert row["fp32OnlyNonEmpty"] == 1


def test_index_rebuild_requires_stable_resource_acceptable() -> None:
    decision = psq.build_configuration_decision(
        [],
        {"rows": []},
        {"rows": []},
        {"conclusion": "NO_STABLE_SPARSE_PRECISION_CONFIGURATION"},
        {"gate": "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED"},
        {"conclusion": "INVOCATION_PATHS_EQUIVALENT"},
    )
    assert decision["sparseIndexRebuildAllowed"] is False
