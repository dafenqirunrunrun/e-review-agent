from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_qc2_common import canonical_hash, corpus_hash, ranked_ids_hash, ranking_hash, set_ids_hash  # noqa: E402


def test_ranked_ids_hash_is_order_sensitive() -> None:
    assert ranked_ids_hash(["a", "b", "c"]) == ranked_ids_hash(["a", "b", "c"])
    assert ranked_ids_hash(["a", "b", "c"]) != ranked_ids_hash(["b", "a", "c"])


def test_set_ids_hash_is_order_insensitive() -> None:
    assert set_ids_hash(["c", "a", "b"]) == set_ids_hash(["a", "b", "c"])


def test_ranking_hash_captures_tie_break_rank_change() -> None:
    assert ranking_hash(["a", "b"]) != ranking_hash(["b", "a"])


def test_corpus_hash_canonicalizes_case_order() -> None:
    first = [{"caseId": "2", "finalEvidenceIdsHash": "b"}, {"caseId": "1", "finalEvidenceIdsHash": "a"}]
    second = [{"caseId": "1", "finalEvidenceIdsHash": "a"}, {"caseId": "2", "finalEvidenceIdsHash": "b"}]
    assert corpus_hash(first, "finalEvidenceIdsHash") == corpus_hash(second, "finalEvidenceIdsHash")


def test_score_noise_does_not_affect_ids_hash() -> None:
    ids = ["a", "b", "c"]
    assert canonical_hash(ids) == canonical_hash(ids)
