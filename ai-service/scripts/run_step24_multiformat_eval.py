from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.document_ingestion.models import NormalizedDocument
from app.document_ingestion.router import DocumentParserRouter
from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.embedding import create_policy_embedding_provider
from app.policy_rag.index_store import build_policy_index, load_policy_chunks
from app.policy_rag.models import ParsedPolicyDocument, PolicyChunk, PolicySourceManifest, PolicySearchResult
from app.policy_rag.retriever import PolicyEvidenceRetriever


DEFAULT_RAW = ROOT / "artifacts" / "step24_multiformat_quality" / "raw"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step24_multiformat_quality" / "evaluation"
HEAVY_PARSER_GATE = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class SourceSpec:
    document_id: str
    filename: str
    source_name: str
    source_url: str
    source_type: str
    jurisdiction: str
    format_group: str
    required_anchors: tuple[str, ...]
    expected_node_types: tuple[str, ...] = ()
    license_class: str = "public_reference_restricted"


@dataclass(frozen=True)
class QuerySpec:
    case_id: str
    query: str
    expected_documents: tuple[str, ...]
    anchors_by_document: dict[str, tuple[str, ...]]
    category: str
    risk_hints: tuple[str, ...] = ()
    business_critical: bool = False


SOURCES = (
    SourceSpec(
        "ocrmypdf_multipage_scan",
        "ocrmypdf_multipage_scan.pdf",
        "OCRmyPDF multipage OCR test fixture",
        "https://github.com/ocrmypdf/OCRmyPDF/blob/main/tests/resources/multipage.pdf",
        "ocr_test_fixture",
        "global",
        "scanned_pdf",
        ("MISS WATSON'S LECTURE", "spiritual gifts", "paper money", "one thousand seven hundred and seventy-five"),
        ("paragraph",),
        "public_reference_restricted",
    ),
    SourceSpec(
        "ftc_reviews_guide_pdf",
        "ftc_reviews_guide_digital.pdf",
        "FTC Featuring Online Customer Reviews",
        "https://www.ftc.gov/system/files/documents/plain-language/1006a_featuring-online-customer-reviews-508_0.pdf",
        "regulatory_guidance",
        "us",
        "digital_pdf",
        ("Review collection", "incentive", "negative reviews", "fake"),
        ("section", "list_item"),
        "public_domain",
    ),
    SourceSpec(
        "ftc_wireless_complaints_xlsx",
        "ftc_wireless_complaints.xlsx",
        "FTC AT&T Wireless Complaints",
        "https://www.ftc.gov/system/files/attachments/frequently-requested-records/att_wireless_complaints.xlsx",
        "public_dataset",
        "us",
        "xlsx",
        ("Deception/Misrepresentation", "Failure to Honor Refund Policy", "Mobile: Carrier Rates"),
        ("sheet", "table", "table_row"),
        "public_domain",
    ),
    SourceSpec(
        "rfc9110_txt",
        "rfc9110_http_semantics.txt",
        "RFC 9110 HTTP Semantics",
        "https://www.rfc-editor.org/rfc/rfc9110.txt",
        "technical_standard",
        "global",
        "txt",
        ("If-None-Match", "304 (Not Modified)", "Content-Type"),
        ("paragraph",),
    ),
    SourceSpec(
        "accessni_policy_docx",
        "accessni_policy_statement.docx",
        "AccessNI Sample Policy Statement",
        "https://www.nidirect.gov.uk/sites/default/files/2025-10/Sample-Policy-Statement-%20Registered-Bodies.DOCX",
        "government_policy",
        "uk",
        "docx",
        ("Storage and Access", "Retention", "Disclosure Information"),
        ("title", "section"),
    ),
    SourceSpec(
        "govuk_online_reviews_html",
        "govuk_online_reviews.html",
        "CMA Reviews Guidance for Online Review Sites",
        "https://www.gov.uk/government/publications/reviews-guidance-for-online-review-sites/reviews-guidance-for-online-review-sites",
        "regulatory_guidance",
        "uk",
        "html",
        ("Include negative reviews", "offer incentives for positive reviews", "remove or delay publication"),
        ("title", "section", "list_item"),
    ),
)


QUERIES = (
    QuerySpec(
        "business-incentive-cn",
        "商家要求五星好评截图后才返现，这种做法有什么政策依据？",
        ("ftc_reviews_guide_pdf", "govuk_online_reviews_html"),
        {
            "ftc_reviews_guide_pdf": ("incentive", "positive"),
            "govuk_online_reviews_html": ("incentives for positive reviews",),
        },
        "review_governance",
        ("rating_manipulation",),
        True,
    ),
    QuerySpec(
        "business-suppression-cn",
        "平台能不能隐藏、删除或拖延发布消费者的真实差评？",
        ("govuk_online_reviews_html", "ftc_reviews_guide_pdf"),
        {
            "govuk_online_reviews_html": ("negative reviews", "remove", "delay"),
            "ftc_reviews_guide_pdf": ("negative reviews", "exclude"),
        },
        "review_governance",
        ("review_suppression",),
        True,
    ),
    QuerySpec(
        "business-fake-en",
        "How should a platform handle fake or manipulated customer reviews?",
        ("ftc_reviews_guide_pdf", "govuk_online_reviews_html"),
        {
            "ftc_reviews_guide_pdf": ("fake", "manipulated"),
            "govuk_online_reviews_html": ("fake reviews",),
        },
        "review_governance",
        ("fake_review",),
        True,
    ),
    QuerySpec(
        "business-interest-cn",
        "评论网站和商家存在商业关系时，是否需要向用户披露？",
        ("govuk_online_reviews_html", "ftc_reviews_guide_pdf"),
        {
            "govuk_online_reviews_html": ("commercial relationships",),
            "ftc_reviews_guide_pdf": ("material connection", "disclosed"),
        },
        "review_governance",
        ("rating_manipulation",),
        True,
    ),
    QuerySpec(
        "scan-watson-en",
        "What did Miss Watson say a person could get by praying?",
        ("ocrmypdf_multipage_scan",),
        {"ocrmypdf_multipage_scan": ("Miss Watson", "spiritual gifts")},
        "format_recovery",
    ),
    QuerySpec(
        "scan-france-paper-money-en",
        "Which country rolled downhill while making paper money and spending it?",
        ("ocrmypdf_multipage_scan",),
        {"ocrmypdf_multipage_scan": ("France", "paper money", "spending it")},
        "format_recovery",
    ),
    QuerySpec(
        "xlsx-refund-cn",
        "无线运营商投诉中，哪些记录涉及未履行退款政策？",
        ("ftc_wireless_complaints_xlsx",),
        {"ftc_wireless_complaints_xlsx": ("Failure to Honor Refund Policy",)},
        "table_retrieval",
        ("after_sales_risk",),
    ),
    QuerySpec(
        "xlsx-deception-en",
        "Mobile carrier rates and plans complaints involving deception or misrepresentation",
        ("ftc_wireless_complaints_xlsx",),
        {"ftc_wireless_complaints_xlsx": ("Deception/Misrepresentation", "Mobile: Carrier Rates")},
        "table_retrieval",
    ),
    QuerySpec(
        "txt-conditional-en",
        "What are the HTTP If-None-Match conditional request semantics?",
        ("rfc9110_txt",),
        {"rfc9110_txt": ("If-None-Match",)},
        "plain_text_retrieval",
    ),
    QuerySpec(
        "txt-304-cn",
        "HTTP 语义中 304 Not Modified 表示什么？",
        ("rfc9110_txt",),
        {"rfc9110_txt": ("304 (Not Modified)", "304 Not Modified")},
        "plain_text_retrieval",
    ),
    QuerySpec(
        "docx-storage-en",
        "How should AccessNI disclosure information be securely stored, retained and disposed?",
        ("accessni_policy_docx",),
        {"accessni_policy_docx": ("Storage and Access", "Retention", "Disposal")},
        "office_retrieval",
    ),
    QuerySpec(
        "docx-access-cn",
        "AccessNI 政策中谁可以访问 disclosure information？",
        ("accessni_policy_docx",),
        {"accessni_policy_docx": ("access", "Disclosure Information")},
        "office_retrieval",
    ),
)


# Frozen before execution. These are product-utility thresholds, not promotion gates.
THRESHOLDS = {
    "parseSuccessRate": 0.83,
    "sourceAnchorRetention": 0.80,
    "nodeSourceRefCoverage": 0.95,
    "chunkCitationValidity": 1.0,
    "businessEvidenceRecallAt5": 0.80,
    "allCaseEvidenceRecallAt5": 0.75,
    "mrrAt5": 0.65,
    "ndcgAt5": 0.70,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Step 24 multi-format parse/chunk/retrieval evaluation.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--skip-dense", action="store_true")
    parser.add_argument("--reuse-normalized", action="store_true")
    args = parser.parse_args()
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    missing = [spec.filename for spec in SOURCES if not (raw_dir / spec.filename).is_file()]
    if missing:
        raise SystemExit(f"MULTIFORMAT_SOURCE_MISSING files={missing}")

    evaluation_id = _stable_hash(
        {
            "sources": [source.__dict__ for source in SOURCES],
            "queries": [query.__dict__ for query in QUERIES],
            "thresholds": THRESHOLDS,
        }
    )
    parse_started = time.perf_counter()
    if args.reuse_normalized:
        parsed, failures = _load_normalized(output_dir / "normalized")
    else:
        parsed, failures = _parse_batch(raw_dir, output_dir / "normalized", max(1, min(args.workers, 8)))
    parse_elapsed_ms = round((time.perf_counter() - parse_started) * 1000, 3)
    documents = [_to_policy_document(spec, parsed[spec.document_id]) for spec in SOURCES if spec.document_id in parsed]

    chunker = PolicyStructureChunker(child_max_tokens=220, child_overlap_tokens=32)
    index_dir = output_dir / "index"
    provider = create_policy_embedding_provider()
    manifest = build_policy_index(
        documents,
        output_dir=index_dir,
        chunker=chunker,
        build_dense=not args.skip_dense,
        embedding_provider=provider,
    )
    chunks = load_policy_chunks(index_dir / "policy_chunks.jsonl")
    dense_ready = manifest["retrieval"]["dense"].get("status") == "ready"
    retriever = PolicyEvidenceRetriever.from_jsonl(
        index_dir / "policy_chunks.jsonl",
        enable_dense=dense_ready,
        embedding_provider=provider,
    )

    variants: dict[str, Any] = {"bm25": _evaluate_variant(retriever, "bm25")}
    if dense_ready:
        variants["dense"] = _evaluate_variant(retriever, "dense")
        variants["hybrid"] = _evaluate_variant(retriever, "hybrid")
    else:
        variants["hybrid"] = {
            "actualMode": "bm25_fallback",
            "fallbackReason": manifest["retrieval"]["dense"].get("fallbackReason", "DENSE_INDEX_UNAVAILABLE"),
            **_evaluate_variant(retriever, "hybrid"),
        }

    parser_quality = _parser_quality(parsed, failures)
    chunk_quality = _chunk_quality(chunks)
    selected = variants["hybrid"]
    gates = {
        "parseSuccessRate": parser_quality["parseSuccessRate"] >= THRESHOLDS["parseSuccessRate"],
        "sourceAnchorRetention": parser_quality["sourceAnchorRetention"] >= THRESHOLDS["sourceAnchorRetention"],
        "nodeSourceRefCoverage": parser_quality["nodeSourceRefCoverage"] >= THRESHOLDS["nodeSourceRefCoverage"],
        "chunkCitationValidity": chunk_quality["citationValidity"] >= THRESHOLDS["chunkCitationValidity"],
        "businessEvidenceRecallAt5": selected["metrics"]["businessEvidenceRecallAt5"] >= THRESHOLDS["businessEvidenceRecallAt5"],
        "allCaseEvidenceRecallAt5": selected["metrics"]["evidenceRecallAt5"] >= THRESHOLDS["allCaseEvidenceRecallAt5"],
        "mrrAt5": selected["metrics"]["mrrAt5"] >= THRESHOLDS["mrrAt5"],
        "ndcgAt5": selected["metrics"]["ndcgAt5"] >= THRESHOLDS["ndcgAt5"],
    }
    report = {
        "schemaVersion": "step24-multiformat-business-eval-v1",
        "evaluationId": evaluation_id,
        "gate": "PASS" if all(gates.values()) else "PASS_WITH_LIMITATIONS" if gates["parseSuccessRate"] and gates["chunkCitationValidity"] else "FAIL",
        "scope": "isolated_candidate_only",
        "thresholdsFrozenBeforeRun": True,
        "thresholds": THRESHOLDS,
        "gateChecks": gates,
        "batch": {
            "requestedSourceCount": len(SOURCES),
            "parsedSourceCount": len(parsed),
            "failedSourceCount": len(failures),
            "workers": max(1, min(args.workers, 8)),
            "heavyParserConcurrency": 1,
            "normalizedArtifactsReused": args.reuse_normalized,
            "parseElapsedMs": parse_elapsed_ms,
        },
        "sources": _source_manifest(raw_dir, parsed, failures),
        "parserQuality": parser_quality,
        "chunkQuality": chunk_quality,
        "index": {
            "chunkCount": len(chunks),
            "bm25Status": manifest["retrieval"]["sparse"]["status"],
            "dense": _safe_dense_manifest(manifest["retrieval"]["dense"]),
        },
        "retrieval": variants,
        "metricNotes": {
            "evidenceRecallAtK": "Share of queries with a source-correct, anchor-supporting chunk in Top-K.",
            "mrrAt5": "Mean reciprocal rank of the first source-correct, anchor-supporting chunk.",
            "ndcgAt5": "Graded ranking quality: 2=source and evidence anchor match, 1=source-only match.",
            "candidateDiversityAt5": "Mean unique document ratio in Top-5; diagnostic only, not a gate.",
        },
        "limitations": _limitations(parsed, failures, dense_ready, chunk_quality),
    }
    report_path = output_dir / "multiformat_quality_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate": report["gate"],
        "evaluationId": evaluation_id,
        "batch": report["batch"],
        "parserQuality": parser_quality,
        "chunkQuality": chunk_quality,
        "retrievalMetrics": {name: value["metrics"] for name, value in variants.items()},
        "report": str(report_path),
    }, ensure_ascii=False, indent=2))
    return 0 if report["gate"] != "FAIL" else 2


def _parse_batch(raw_dir: Path, normalized_dir: Path, workers: int) -> tuple[dict[str, NormalizedDocument], dict[str, str]]:
    normalized_dir.mkdir(parents=True, exist_ok=True)
    parsed: dict[str, NormalizedDocument] = {}
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="multiformat-parse") as executor:
        futures = {executor.submit(_parse_source, raw_dir, normalized_dir, spec): spec for spec in SOURCES}
        for future in as_completed(futures):
            spec = futures[future]
            try:
                parsed[spec.document_id] = future.result()
            except Exception as exc:
                failures[spec.document_id] = f"{type(exc).__name__}:{str(exc)[:240]}"
    return parsed, failures


def _load_normalized(normalized_dir: Path) -> tuple[dict[str, NormalizedDocument], dict[str, str]]:
    parsed: dict[str, NormalizedDocument] = {}
    failures: dict[str, str] = {}
    for spec in SOURCES:
        path = normalized_dir / f"{spec.document_id}.json"
        try:
            document = NormalizedDocument.model_validate_json(path.read_text(encoding="utf-8-sig"))
            if document.documentId != spec.document_id or document.sourceUri != spec.source_url:
                raise ValueError("NORMALIZED_SOURCE_IDENTITY_MISMATCH")
            parsed[spec.document_id] = document
        except Exception as exc:
            failures[spec.document_id] = f"{type(exc).__name__}:{str(exc)[:240]}"
    return parsed, failures


def _parse_source(raw_dir: Path, normalized_dir: Path, spec: SourceSpec) -> NormalizedDocument:
    router = DocumentParserRouter()
    path = raw_dir / spec.filename
    probe = router.probe(path)
    route = router.select_route(probe)
    started = time.perf_counter()
    if route.heavy:
        with HEAVY_PARSER_GATE:
            document = router.parse(
                path,
                document_id=spec.document_id,
                source_name=spec.source_name,
                source_type=spec.source_type,
                source_uri=spec.source_url,
                language="en",
                probe=probe,
            )
    else:
        document = router.parse(
            path,
            document_id=spec.document_id,
            source_name=spec.source_name,
            source_type=spec.source_type,
            source_uri=spec.source_url,
            language="en",
            probe=probe,
        )
    metadata = {**document.metadata, "evaluationParseElapsedMs": round((time.perf_counter() - started) * 1000, 3)}
    document = document.model_copy(update={"metadata": metadata})
    (normalized_dir / f"{spec.document_id}.json").write_text(
        document.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return document


def _to_policy_document(spec: SourceSpec, document: NormalizedDocument) -> ParsedPolicyDocument:
    parser_name = "mineru" if document.parser == "mineru" else "manual_markdown"
    manifest = PolicySourceManifest(
        sourceId=spec.document_id,
        sourceUrl=spec.source_url,
        sourceName=spec.source_name,
        sourceType=spec.source_type,
        jurisdiction=spec.jurisdiction,
        language=document.language,
        parser=parser_name,
        parserVersion=document.parserVersion,
        licenseClass=spec.license_class,
        contentHash=document.contentHash,
        metadata={
            "actualParser": document.parser,
            "documentFormat": document.format,
            "nodeCount": len(document.nodes),
            "assetCount": len(document.assets),
            "attempts": [item.model_dump(mode="json") for item in document.attempts],
        },
    )
    return ParsedPolicyDocument(
        manifest=manifest,
        markdown=document.markdown or "\n".join(node.text for node in document.nodes if node.text.strip()),
        structured={"format": document.format, "nodeCount": len(document.nodes), "assetCount": len(document.assets)},
        parserWarnings=document.warnings,
    )


def _parser_quality(parsed: dict[str, NormalizedDocument], failures: dict[str, str]) -> dict[str, Any]:
    rows = []
    total_anchors = 0
    found_anchors = 0
    total_nodes = 0
    referenced_nodes = 0
    for spec in SOURCES:
        document = parsed.get(spec.document_id)
        if document is None:
            rows.append({"documentId": spec.document_id, "format": spec.format_group, "status": "failed", "error": failures.get(spec.document_id, "unknown")})
            total_anchors += len(spec.required_anchors)
            continue
        searchable = "\n".join([document.markdown, *(node.text for node in document.nodes)]).casefold()
        found = [anchor for anchor in spec.required_anchors if anchor.casefold() in searchable]
        node_types = {node.type for node in document.nodes}
        total_anchors += len(spec.required_anchors)
        found_anchors += len(found)
        total_nodes += len(document.nodes)
        referenced_nodes += sum(bool(node.sourceRef.strip()) for node in document.nodes)
        rows.append({
            "documentId": spec.document_id,
            "format": spec.format_group,
            "status": "parsed",
            "parser": document.parser,
            "attempts": [item.model_dump(mode="json") for item in document.attempts],
            "markdownChars": len(document.markdown),
            "nodeCount": len(document.nodes),
            "assetCount": len(document.assets),
            "anchorRetention": round(len(found) / len(spec.required_anchors), 6) if spec.required_anchors else 1.0,
            "foundAnchors": found,
            "missingAnchors": [item for item in spec.required_anchors if item not in found],
            "expectedNodeTypesPresent": sorted(set(spec.expected_node_types).intersection(node_types)),
            "missingNodeTypes": sorted(set(spec.expected_node_types) - node_types),
            "sectionPathCoverage": _ratio(sum(bool(node.sectionPath) for node in document.nodes), len(document.nodes)),
            "sourceRefCoverage": _ratio(sum(bool(node.sourceRef.strip()) for node in document.nodes), len(document.nodes)),
            "elapsedMs": document.metadata.get("evaluationParseElapsedMs", 0.0),
        })
    return {
        "parseSuccessRate": _ratio(len(parsed), len(SOURCES)),
        "sourceAnchorRetention": _ratio(found_anchors, total_anchors),
        "nodeSourceRefCoverage": _ratio(referenced_nodes, total_nodes),
        "documents": rows,
    }


def _chunk_quality(chunks: list[PolicyChunk]) -> dict[str, Any]:
    by_document: dict[str, list[PolicyChunk]] = {}
    for chunk in chunks:
        by_document.setdefault(chunk.documentId, []).append(chunk)
    duplicate_count = len(chunks) - len({(chunk.documentId, chunk.contentHash) for chunk in chunks})
    return {
        "chunkCount": len(chunks),
        "byDocument": {key: len(value) for key, value in sorted(by_document.items())},
        "tokenCount": _distribution([chunk.tokenCount for chunk in chunks]),
        "oversizeCount": sum(chunk.tokenCount > 230 for chunk in chunks),
        "tinyCount": sum(chunk.tokenCount < 8 for chunk in chunks),
        "duplicateRate": _ratio(duplicate_count, len(chunks)),
        "sectionPathCoverage": _ratio(sum(bool(chunk.sectionPath) for chunk in chunks), len(chunks)),
        "parentLinkCoverage": _ratio(sum(bool(chunk.parentChunkId) for chunk in chunks), len(chunks)),
        "citationValidity": _ratio(sum(_chunk_citation_valid(chunk) for chunk in chunks), len(chunks)),
    }


def _evaluate_variant(retriever: PolicyEvidenceRetriever, mode: str) -> dict[str, Any]:
    rows = []
    actual_modes = []
    for case in QUERIES:
        results = retriever.search(case.query, risk_hints=list(case.risk_hints), top_k=5, mode=mode)
        actual_modes.append(_actual_mode(results, retriever))
        evaluated = evaluate_ranked_case(case, results, retriever)
        rows.append({
            "caseId": case.case_id,
            "query": case.query,
            "category": case.category,
            "businessCritical": case.business_critical,
            **evaluated,
            "top5": [
                {
                    "rank": rank,
                    "chunkId": item.chunkId,
                    "documentId": retriever.chunk_for_id(item.chunkId).documentId if retriever.chunk_for_id(item.chunkId) else "",
                    "sourceName": item.sourceName,
                    "sectionPath": item.sectionPath,
                    "score": round(item.score, 8),
                    "relevance": _relevance(case, item, retriever),
                    "snippet": item.snippet[:220],
                }
                for rank, item in enumerate(results, start=1)
            ],
        })
    evidence_ranks = [row["firstEvidenceRank"] for row in rows]
    business = [row for row in rows if row["businessCritical"]]
    metrics = {
        "caseCount": len(rows),
        "evidenceRecallAt3": _ratio(sum(rank and rank <= 3 for rank in evidence_ranks), len(rows)),
        "evidenceRecallAt5": _ratio(sum(rank and rank <= 5 for rank in evidence_ranks), len(rows)),
        "sourceRecallAt5": _ratio(sum(row["firstSourceRank"] and row["firstSourceRank"] <= 5 for row in rows), len(rows)),
        "businessEvidenceRecallAt5": _ratio(sum(row["firstEvidenceRank"] and row["firstEvidenceRank"] <= 5 for row in business), len(business)),
        "mrrAt5": round(statistics.mean((1 / rank if rank and rank <= 5 else 0) for rank in evidence_ranks), 6),
        "ndcgAt5": round(statistics.mean(row["ndcgAt5"] for row in rows), 6),
        "top1EvidenceAccuracy": _ratio(sum(rank == 1 for rank in evidence_ranks), len(rows)),
        "citationValidRate": _ratio(sum(row["citationValid"] for row in rows), len(rows)),
        "candidateDiversityAt5": round(statistics.mean(row["candidateDiversityAt5"] for row in rows), 6),
    }
    return {"requestedMode": mode, "actualModes": sorted(set(actual_modes)), "metrics": metrics, "cases": rows}


def evaluate_ranked_case(case: QuerySpec, results: list[PolicySearchResult], retriever: PolicyEvidenceRetriever | None = None) -> dict[str, Any]:
    relevance = [_relevance(case, item, retriever) for item in results[:5]]
    first_evidence = next((rank for rank, value in enumerate(relevance, start=1) if value >= 2), 0)
    first_source = next((rank for rank, value in enumerate(relevance, start=1) if value >= 1), 0)
    ideal = sorted(relevance + ([2] if 2 not in relevance else []), reverse=True)[:5]
    documents = [_result_document_id(item, retriever) for item in results[:5]]
    return {
        "firstEvidenceRank": first_evidence,
        "firstSourceRank": first_source,
        "ndcgAt5": round(_ndcg(relevance, ideal, 5), 6),
        "citationValid": all(_result_citation_valid(item) for item in results[:5]),
        "candidateDiversityAt5": _ratio(len(set(filter(None, documents))), len(results[:5])),
    }


def _relevance(case: QuerySpec, result: PolicySearchResult, retriever: PolicyEvidenceRetriever | None) -> int:
    document_id = _result_document_id(result, retriever)
    if document_id not in case.expected_documents:
        return 0
    anchors = case.anchors_by_document.get(document_id, ())
    searchable = " ".join([result.title, result.snippet, *result.sectionPath]).casefold()
    return 2 if any(anchor.casefold() in searchable for anchor in anchors) else 1


def _result_document_id(result: PolicySearchResult, retriever: PolicyEvidenceRetriever | None) -> str:
    if retriever is not None:
        chunk = retriever.chunk_for_id(result.chunkId)
        if chunk:
            return chunk.documentId
    return str(result.retrieval.get("documentId", ""))


def _actual_mode(results: list[PolicySearchResult], retriever: PolicyEvidenceRetriever) -> str:
    if results:
        mode = results[0].retrievalMode
        if mode == "hybrid_bm25_qwen_faiss_rrf":
            return "hybrid"
        if mode == "qwen_faiss_dense":
            return "dense"
        return "bm25_fallback"
    return "unavailable" if not retriever.last_fallback_used else "bm25_fallback"


def _source_manifest(raw_dir: Path, parsed: dict[str, NormalizedDocument], failures: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for spec in SOURCES:
        path = raw_dir / spec.filename
        document = parsed.get(spec.document_id)
        rows.append({
            "documentId": spec.document_id,
            "sourceName": spec.source_name,
            "sourceUrl": spec.source_url,
            "format": spec.format_group,
            "filename": spec.filename,
            "sizeBytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "status": "parsed" if document else "failed",
            "parser": document.parser if document else "",
            "failure": failures.get(spec.document_id, ""),
        })
    return rows


def _safe_dense_manifest(value: dict[str, Any]) -> dict[str, Any]:
    allowed = ("status", "vectorCount", "chunkCount", "dimension", "indexType", "metric", "contentRootHash", "fallbackReason")
    output = {key: value[key] for key in allowed if key in value}
    provider = value.get("provider") or {}
    output["provider"] = {
        key: provider.get(key)
        for key in ("providerType", "modelName", "dimension", "device", "normalize", "pooling", "maxLength")
        if key in provider
    }
    return output


def _limitations(parsed: dict[str, NormalizedDocument], failures: dict[str, str], dense_ready: bool, chunk_quality: dict[str, Any]) -> list[str]:
    output = []
    if failures:
        output.append("Some public samples could not be parsed; failures were isolated and retained in the result.")
    if not dense_ready:
        output.append("Dense index was unavailable, so hybrid results represent the production BM25 fallback path.")
    if chunk_quality["oversizeCount"]:
        output.append("Some chunks exceed the nominal token target and require manual inspection for semantic integrity.")
    if any(document.assets and not any(node.assetIds for node in document.nodes) for document in parsed.values()):
        output.append("At least one parser extracted assets without attaching them to a normalized content node.")
    output.append("Qrels are source-and-anchor based and measure business evidence sufficiency, not exhaustive chunk-level recall.")
    return output


def _chunk_citation_valid(chunk: PolicyChunk) -> bool:
    return bool(chunk.sourceName and chunk.sourceUrl.startswith(("http://", "https://")) and chunk.sectionPath and len(chunk.contentHash) >= 12)


def _result_citation_valid(result: PolicySearchResult) -> bool:
    return bool(result.sourceName and result.sourceUrl.startswith(("http://", "https://")) and result.sectionPath and len(result.contentHash) >= 12)


def _distribution(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "median": 0, "p95": 0, "max": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "min": ordered[0],
        "median": round(statistics.median(ordered), 3),
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def _ndcg(observed: list[int], ideal: list[int], k: int) -> float:
    def dcg(values: list[int]) -> float:
        return sum((2**value - 1) / math.log2(rank + 1) for rank, value in enumerate(values[:k], start=1))
    denominator = dcg(sorted(ideal, reverse=True))
    return dcg(observed) / denominator if denominator else 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else 0.0


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=list)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
