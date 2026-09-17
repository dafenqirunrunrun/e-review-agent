from app.policy_rag.index_store import _review_relevant
from app.policy_rag.models import PolicyChunk


def test_numbered_law_clause_is_not_removed_by_keyword_filter() -> None:
    clause = PolicyChunk(
        chunkId="a" * 24,
        documentId="consumer-law",
        sourceName="消费者权益保护法",
        sourceUrl="https://example.test/law",
        sourceType="law",
        language="zh",
        heading="消费者权益保护法 第二十六条",
        sectionPath=["消费者权益保护法"],
        clauseId="二十六",
        text="经营者应以显著方式提请消费者注意格式条款。",
        contentHash="b" * 64,
        tokenCount=20,
        riskTypes=["review_policy"],
        evidenceTags=["review_policy"],
    )

    assert _review_relevant(clause) is True
