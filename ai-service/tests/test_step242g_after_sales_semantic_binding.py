from __future__ import annotations

from app.policy_rag.index_store import load_policy_chunks
from scripts.build_step242g_after_sales_semantic_cases import build_rows, canonical_clause_text
from scripts.materialize_step242g_after_sales_semantic_qrels import CHUNKS, materialize, validate_cases


def test_semantic_binding_requires_standalone_clause_context() -> None:
    rows = build_rows(canonical_clause_text())
    chunks = load_policy_chunks(CHUNKS)
    cases, binding = materialize(rows, chunks)

    validate_cases(cases, chunks, binding)

    assert len(cases) == 48
    assert all(len(case.qrels) == len(chunks) for case in cases)
    assert all(any(qrel.relevance == 3 for qrel in case.qrels) for case in cases if not case.noAnswer)
    assert all(not any(qrel.relevance >= 2 for qrel in case.qrels) for case in cases if case.noAnswer)


def test_refund_time_clause_is_bound_after_review_relevance_filter() -> None:
    rows = build_rows(canonical_clause_text())
    chunks = load_policy_chunks(CHUNKS)
    cases, _ = materialize(rows, chunks)
    case = next(item for item in cases if item.caseId == "asv2-refund_time-dev")

    direct = [qrel for qrel in case.qrels if qrel.relevance == 3]

    assert direct
    assert all(qrel.clauseId == "十三" for qrel in direct)
