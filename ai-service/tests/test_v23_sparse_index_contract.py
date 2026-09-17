from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from qualification.v23_bge_m3_sparse_common import SparseDocumentVector, raw_union, sparse_dot  # noqa: E402


def test_sparse_vector_validation_rejects_empty_and_invalid_weights():
    valid = SparseDocumentVector("c1", "h" * 12, "s1", "policy", "t", "e", [1, 2], [0.2, 0.3])
    valid.validate()
    for token_ids, weights in [([], []), ([1], [math.nan]), ([1], [-0.1]), ([2, 1], [0.1, 0.2])]:
        try:
            SparseDocumentVector("c1", "h" * 12, "s1", "policy", "t", "e", token_ids, weights).validate()
        except ValueError:
            continue
        raise AssertionError("invalid sparse vector accepted")


def test_sparse_dot_product_uses_shared_tokens_only():
    assert sparse_dot({1: 0.5, 2: 0.5}, {2: 2.0, 3: 9.0}) == 1.0


def test_sparse_tie_break_and_raw_union_are_deterministic():
    assert raw_union(["b", "a"], ["a", "c"], k=2) == ["a", "b", "c"]
