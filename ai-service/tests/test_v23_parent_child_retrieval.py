from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_common import SimpleBm25, build_parent_units, parent_content, rrf  # noqa: E402


def test_parent_bm25_returns_parent_ids() -> None:
    parents = build_parent_units()
    index = SimpleBm25([(parent.parent_id, parent_content(parent, "P2", 256)) for parent in parents])
    ids = index.search("refund governed knowledge", 5)
    assert ids
    assert all(item.startswith("parent-") for item in ids)


def test_rrf_is_deterministic_and_deduplicated() -> None:
    first = rrf([["a", "b", "c"], ["b", "d"]], k=4)
    second = rrf([["a", "b", "c"], ["b", "d"]], k=4)
    assert first == second
    assert len(first) == len(set(first))
    assert first[0] == "b"
