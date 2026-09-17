from __future__ import annotations

from app.policy_rag.models import PolicySearchResult
from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.parser import PolicyDocumentParser
from scripts.run_step24_multiformat_eval import QuerySpec, evaluate_ranked_case


def _result(*, document_id: str, snippet: str, url: str = "https://example.test/policy") -> PolicySearchResult:
    return PolicySearchResult(
        evidenceId="E1",
        chunkId=f"chunk-{document_id}-123456",
        sourceType="policy",
        sourceName="Example policy",
        sourceUrl=url,
        title="Policy section",
        snippet=snippet,
        riskTypes=["review_policy"],
        evidenceTags=["review_policy"],
        score=1.0,
        contentHash="1234567890abcdef",
        sectionPath=["Policy", "Section"],
        retrieval={"documentId": document_id},
    )


def test_source_only_hit_is_not_counted_as_supporting_evidence() -> None:
    case = QuerySpec(
        "case-1",
        "query",
        ("expected",),
        {"expected": ("required anchor",)},
        "test",
    )
    result = evaluate_ranked_case(case, [_result(document_id="expected", snippet="same source, wrong passage")])

    assert result["firstSourceRank"] == 1
    assert result["firstEvidenceRank"] == 0


def test_first_supporting_evidence_rank_drives_mrr_input() -> None:
    case = QuerySpec(
        "case-2",
        "query",
        ("expected",),
        {"expected": ("required anchor",)},
        "test",
    )
    results = [
        _result(document_id="other", snippet="required anchor"),
        _result(document_id="expected", snippet="contains required anchor"),
    ]
    evaluated = evaluate_ranked_case(case, results)

    assert evaluated["firstEvidenceRank"] == 2
    assert evaluated["firstSourceRank"] == 2
    assert 0 < evaluated["ndcgAt5"] < 1


def test_citation_validation_rejects_incomplete_source_url() -> None:
    case = QuerySpec(
        "case-3",
        "query",
        ("expected",),
        {"expected": ("anchor",)},
        "test",
    )
    evaluated = evaluate_ranked_case(
        case,
        [_result(document_id="expected", snippet="anchor", url="local-file")],
    )

    assert evaluated["firstEvidenceRank"] == 1
    assert evaluated["citationValid"] is False


def test_chunk_windows_use_the_persisted_token_count_contract() -> None:
    content = " ".join(f"Section {index}." for index in range(400))
    document = PolicyDocumentParser().parse_text(
        source_id="long-policy",
        source_url="https://example.test/long-policy",
        source_name="Long policy",
        source_type="policy",
        content=content,
    )

    chunks = PolicyStructureChunker(child_max_tokens=80, child_overlap_tokens=12).chunk(document)

    assert chunks
    assert max(chunk.tokenCount for chunk in chunks) <= 80
    assert min(chunk.tokenCount for chunk in chunks) > 12


def test_chunker_removes_exact_duplicates_within_the_same_section() -> None:
    document = PolicyDocumentParser().parse_text(
        source_id="duplicate-policy",
        source_url="https://example.test/duplicate-policy",
        source_name="Duplicate policy",
        source_type="policy",
        content="# Policy\n\nRepeated policy evidence text.\n\nRepeated policy evidence text.",
    )

    chunks = PolicyStructureChunker().chunk(document)

    assert len(chunks) == 1


def test_numbered_policy_items_remain_independent_citation_units() -> None:
    document = PolicyDocumentParser().parse_text(
        source_id="list-policy",
        source_url="https://example.test/list-policy",
        source_name="List policy",
        source_type="policy",
        content=(
            "# Review policy\n\n"
            "1. Publish all genuine reviews.\n"
            "2. Disclose material commercial relationships clearly.\n"
            "3. Do not suppress negative reviews."
        ),
    )

    chunks = PolicyStructureChunker().chunk(document)

    assert len(chunks) == 3
    assert all(chunk.metadata["blockType"] == "list" for chunk in chunks)
    assert any("commercial relationships" in chunk.text for chunk in chunks)
