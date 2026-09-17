from __future__ import annotations

from scripts.build_step242g_after_sales_semantic_cases import build_rows, canonical_clause_text, validate_rows


def test_semantic_cases_are_chunk_independent_and_balanced() -> None:
    clause_text = canonical_clause_text()
    rows = build_rows(clause_text)
    validation = validate_rows(rows, clause_text)

    assert validation["caseCount"] == 48
    assert validation["devCount"] == 24
    assert validation["holdoutCount"] == 24
    assert validation["legalTopicCount"] == 20
    assert validation["checks"]["everyTopicHasDevAndHoldoutParaphrase"] is True
    assert validation["checks"]["allSemanticReferencesResolve"] is True


def test_semantic_cases_do_not_bind_future_qrels_to_current_chunk_ids() -> None:
    rows = build_rows(canonical_clause_text())
    evidence = [reference for row in rows for reference in row["expectedEvidence"]]

    assert evidence
    assert all("chunkId" not in reference for reference in evidence)
    assert all(reference["relevance"] == 3 for reference in evidence)
    assert all(reference["requiredAnchors"] for reference in evidence)


def test_semantic_normal_controls_are_not_misrepresented_as_retrieval_gold() -> None:
    rows = build_rows(canonical_clause_text())
    controls = [row for row in rows if row["noAnswer"]]

    assert len(controls) == 8
    assert all(row["riskTypes"] == [] for row in controls)
    assert all(row["expectedEvidence"] == [] for row in controls)
    assert all("retrieval-level no-answer" in row["metadata"]["limitation"] for row in controls)
