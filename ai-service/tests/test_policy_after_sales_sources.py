from pathlib import Path
import re

from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.index_store import _review_relevant
from app.policy_rag.parser import PolicyDocumentParser
from app.policy_rag.sources import REAL_POLICY_SOURCES


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "policy_rag_real" / "raw"


def _source(source_id: str):
    return next(spec for spec in REAL_POLICY_SOURCES if spec.sourceId == source_id)


def _chunks(source_id: str):
    spec = _source(source_id)
    document = PolicyDocumentParser().parse_file(
        RAW_DIR / spec.fileName,
        source_id=spec.sourceId,
        source_url=spec.sourceUrl,
        source_name=spec.sourceName,
        source_type=spec.sourceType,
        language=spec.language,
        jurisdiction=spec.jurisdiction,
        license_class=spec.licenseClass,
    )
    return PolicyStructureChunker().chunk(document)


def test_consumer_law_quality_return_clause_is_traceable():
    chunks = _chunks("cn_consumer_rights_protection_law")

    clause_chunks = [chunk for chunk in chunks if chunk.clauseId == "二十四"]
    clause = next(chunk for chunk in clause_chunks if "不符合质量要求" in chunk.text)

    assert "退货" in clause.text
    assert all(chunk.text.lstrip().startswith("第二十四条") for chunk in clause_chunks)
    assert all(chunk.metadata["clauseContext"] == "第二十四条" for chunk in clause_chunks)
    assert "after_sales_risk" in clause.riskTypes
    assert "after_sales" in clause.evidenceTags
    assert clause.sourceUrl.startswith("https://www.samr.gov.cn/")
    assert clause.sectionPath
    assert clause.contentHash


def test_seven_day_return_clauses_are_traceable():
    chunks = _chunks("cn_online_return_without_reason")
    clause_ids = {chunk.clauseId for chunk in chunks}

    assert {"三", "十", "十三", "三十五"}.issubset(clause_ids)
    assert any("退款" in chunk.text and "after_sales" in chunk.evidenceTags for chunk in chunks)


def test_refund_time_clause_remains_in_review_relevant_index_scope():
    chunks = _chunks("cn_online_return_without_reason")
    clause = next(chunk for chunk in chunks if chunk.clauseId == "十三")

    assert "返还" in clause.text
    assert "after_sales_risk" in clause.riskTypes
    assert "after_sales" in clause.evidenceTags
    assert _review_relevant(clause) is True


def test_pdf_parser_repairs_intercharacter_cjk_spacing_before_chunking():
    chunks = _chunks("cn_consumer_rights_protection_law")
    terms = next(chunk for chunk in chunks if chunk.clauseId == "二十六")
    delay_chunks = [chunk for chunk in chunks if chunk.clauseId == "四十八"]
    delay = next(chunk for chunk in delay_chunks if "故意拖延" in chunk.text)

    assert "格式条款" in terms.text
    assert "故意拖延" in delay.text
    assert not re.search(r"[\u4e00-\u9fff][ \t]+[\u4e00-\u9fff]", terms.text)
    assert all(not re.search(r"[\u4e00-\u9fff][ \t]+[\u4e00-\u9fff]", chunk.text) for chunk in delay_chunks)
