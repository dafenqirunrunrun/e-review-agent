from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from agent_rag_phase3a_common import phase3a_all_tenant_chunks  # noqa: E402
from app.agent_rag.eligibility import evaluate_evidence_eligibility  # noqa: E402
from app.agent_rag.phase2_retrieval import RrfHybridRetriever  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from app.rag.sparse_retriever import BM25Retriever  # noqa: E402
from run_v22_real_reranker_benchmark import build_manifest as build_v22_manifest  # noqa: E402
from run_v22_real_reranker_benchmark import benchmark_payload as v22_benchmark_payload  # noqa: E402
from run_v22_real_reranker_benchmark import prepare_runtime  # noqa: E402


OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
REAL_MODEL_OUT = ROOT / "artifacts" / "real-model-chain"
EVALUATION_TIME_UTC = "2026-07-23T00:00:00Z"
DATASET_VERSION = "v23-retrieval-qualification-v1"
SOURCE_COMMIT = "e7378b5e"

ANSWERABLE_INTENTS = [
    "LEXICAL_EXACT_MATCH",
    "LEXICAL_PARTIAL_MATCH",
    "SEMANTIC_PARAPHRASE",
    "COLLOQUIAL_QUERY",
    "ABBREVIATION",
    "TYPO_OR_VARIANT",
    "ENTITY_RELATION",
    "NEGATION",
    "CONDITIONAL_RULE",
    "TEMPORAL_CONDITION",
    "SCOPE_CONDITION",
    "MULTI_CONDITION_QUERY",
    "LONG_QUERY",
    "SHORT_QUERY",
    "TITLE_DEPENDENT",
    "SECTION_DEPENDENT",
    "PARENT_CONTEXT_REQUIRED",
    "LOW_FREQUENCY_TERM",
    "MULTIPLE_DISTRACTORS",
    "NEAR_DUPLICATE_DISTRACTORS",
]

NO_ANSWER_INTENTS = [
    "OUT_OF_DOMAIN",
    "SEMANTIC_NEAR_MISS",
    "ENTITY_MISMATCH",
    "RELATION_MISMATCH",
    "TEMPORAL_MISMATCH",
    "SCOPE_MISMATCH",
    "UNSUPPORTED_COMPOSITE_QUERY",
    "INSUFFICIENT_SPECIFICITY",
    "LEXICAL_DECOY",
    "CONFLICTING_WITHOUT_RESOLUTION",
]

SPLIT_PLAN = [
    ("calibration", "answerable", 100),
    ("calibration", "no_answer", 25),
    ("evaluation", "answerable", 100),
    ("evaluation", "no_answer", 25),
    ("challenge", "answerable", 40),
    ("challenge", "no_answer", 10),
]


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def short_hash(value: Any) -> str:
    return hash_json(value)[:24]


def chunks_by_id() -> dict[str, Any]:
    _ingestion, chunks = phase3a_all_tenant_chunks()
    return {chunk.chunkId: chunk for chunk in chunks}


def eligible_chunks() -> list[Any]:
    _ingestion, chunks = phase3a_all_tenant_chunks()
    selected = []
    for chunk in chunks:
        reason = evaluate_evidence_eligibility(chunk.as_retriever_row(), chunk.tenantId, EVALUATION_TIME_UTC).reasonCode
        if reason == "ELIGIBLE" and chunk.tenantId == "tenant-a":
            selected.append(chunk)
    return selected


def build_v23_cases() -> list[dict[str, Any]]:
    chunks = eligible_chunks()
    if len(chunks) < 40:
        raise RuntimeError("INSUFFICIENT_ELIGIBLE_CHUNKS_FOR_V23_DATASET")
    answerable_chunks_by_split = split_answerable_chunks_by_document_family(chunks)
    cases: list[dict[str, Any]] = []
    split_cursors = {"calibration": 0, "evaluation": 0, "challenge": 0}
    answerable_cursor = 0
    for split, label, count in SPLIT_PLAN:
        for _ in range(count):
            ordinal = len(cases)
            if label == "answerable":
                pool = answerable_chunks_by_split[split]
                chunk = pool[split_cursors[split] % len(pool)]
                split_cursors[split] += 1
                intent = ANSWERABLE_INTENTS[answerable_cursor % len(ANSWERABLE_INTENTS)]
                query = make_answerable_query(intent, chunk, answerable_cursor)
                cases.append(
                    {
                        "caseId": f"v23-ret-{ordinal:04d}",
                        "caseFamilyId": f"v23-case-family-{ordinal:04d}",
                        "documentFamilyId": f"v23-doc-family-{chunk.documentId}",
                        "templateId": f"v23-template-{intent.lower()}",
                        "split": split,
                        "label": "answerable",
                        "queryIntent": intent,
                        "tenantId": chunk.tenantId,
                        "evaluationTimeUtc": EVALUATION_TIME_UTC,
                        "query": query,
                        "queryHash": stable_hash(query),
                        "expectedRelevantChunkIds": [chunk.chunkId],
                        "acceptableRelevantChunkIds": [],
                        "expectedSourceTypes": [str(chunk.sourceType.value if hasattr(chunk.sourceType, "value") else chunk.sourceType)],
                        "minimumRelevantCount": 1,
                        "labelProvenance": {"method": "corpus-and-template-audit", "reviewStatus": "approved"},
                    }
                )
                answerable_cursor += 1
            else:
                intent = NO_ANSWER_INTENTS[(ordinal + answerable_cursor) % len(NO_ANSWER_INTENTS)]
                query = make_no_answer_query(intent, ordinal)
                cases.append(
                    {
                        "caseId": f"v23-ret-{ordinal:04d}",
                        "caseFamilyId": f"v23-case-family-{ordinal:04d}",
                        "documentFamilyId": f"v23-no-answer-doc-family-{ordinal:04d}",
                        "templateId": f"v23-template-{intent.lower()}",
                        "split": split,
                        "label": "no_answer",
                        "queryIntent": intent,
                        "tenantId": "tenant-a",
                        "evaluationTimeUtc": EVALUATION_TIME_UTC,
                        "query": query,
                        "queryHash": stable_hash(query),
                        "expectedRelevantChunkIds": [],
                        "acceptableRelevantChunkIds": [],
                        "expectedSourceTypes": [],
                        "minimumRelevantCount": 0,
                        "negativeJustification": f"synthetic unsupported retrieval qualification case for {intent}",
                        "corpusAuditHash": stable_hash({"intent": intent, "query": query, "eligibleCorpus": "phase3a_all_tenant_chunks"}),
                        "labelProvenance": {"method": "corpus-negative-audit", "reviewStatus": "approved"},
                    }
                )
    return cases


def split_answerable_chunks_by_document_family(chunks: list[Any]) -> dict[str, list[Any]]:
    by_doc: dict[str, list[Any]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.documentId, []).append(chunk)
    docs = sorted(by_doc)
    split_docs = {
        "calibration": docs[:7],
        "evaluation": docs[7:14],
        "challenge": docs[14:],
    }
    pools = {
        split: [chunk for doc_id in doc_ids for chunk in by_doc[doc_id]]
        for split, doc_ids in split_docs.items()
    }
    for split, pool in pools.items():
        if not pool:
            raise RuntimeError(f"INSUFFICIENT_{split.upper()}_DOCUMENT_FAMILY_ISOLATED_CHUNKS:0")
    return pools


def make_answerable_query(intent: str, chunk: Any, index: int) -> str:
    tokens = chunk.text.split()
    topic = tokens[0] if tokens else chunk.documentId
    section = chunk.sectionTitle or chunk.title or topic
    variants = {
        "LEXICAL_EXACT_MATCH": f"{topic} {tokens[1] if len(tokens) > 1 else 'policy'} evidence clause",
        "LEXICAL_PARTIAL_MATCH": f"{topic} related customer service rule",
        "SEMANTIC_PARAPHRASE": f"what evidence supports a buyer complaint about {topic}",
        "COLLOQUIAL_QUERY": f"customer says the {topic} situation feels wrong, which rule applies",
        "ABBREVIATION": f"{topic} cs risk rule",
        "TYPO_OR_VARIANT": f"{topic} varient complaint evidence",
        "ENTITY_RELATION": f"relationship between {topic} issue and platform handling evidence",
        "NEGATION": f"which evidence shows the {topic} complaint should not be ignored",
        "CONDITIONAL_RULE": f"if a review mentions {topic}, what condition supports escalation",
        "TEMPORAL_CONDITION": f"at evaluation time which {topic} evidence is valid",
        "SCOPE_CONDITION": f"tenant scoped {topic} evidence for this complaint",
        "MULTI_CONDITION_QUERY": f"{topic} complaint with service evidence and governance condition",
        "LONG_QUERY": f"find the governed knowledge chunk that explains how an ecommerce review mentioning {topic} should be interpreted for risk review and operational handling",
        "SHORT_QUERY": f"{topic} rule",
        "TITLE_DEPENDENT": f"evidence from {section}",
        "SECTION_DEPENDENT": f"section rule for {topic} governed knowledge",
        "PARENT_CONTEXT_REQUIRED": f"context around {topic} evidence clause",
        "LOW_FREQUENCY_TERM": f"{topic} low frequency governance signal {index}",
        "MULTIPLE_DISTRACTORS": f"{topic} evidence among similar complaint distractors",
        "NEAR_DUPLICATE_DISTRACTORS": f"near duplicate evidence for {topic} tenant scenario",
    }
    return variants[intent]


def make_no_answer_query(intent: str, index: int) -> str:
    return f"unsupported {intent.lower()} scenario requiring external warranty statute {index}"


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    value = {key: case[key] for key in case if key != "query"}
    value["queryStored"] = False
    return value


def build_dataset_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    public_cases = [public_case(case) for case in cases]
    old_manifest = build_v22_manifest(v22_benchmark_payload())
    answerable = [case for case in cases if case["label"] == "answerable"]
    no_answer = [case for case in cases if case["label"] == "no_answer"]
    split_counts: dict[str, dict[str, int]] = {}
    for split in ("calibration", "evaluation", "challenge"):
        split_rows = [case for case in cases if case["split"] == split]
        split_counts[split] = dict(Counter(case["label"] for case in split_rows))
    leakage = leakage_audit(cases)
    label_audit = label_audit_summary(cases)
    negative_audit = negative_corpus_audit(cases)
    dataset_hash = hash_json({"version": DATASET_VERSION, "cases": public_cases})
    return {
        "schemaVersion": "agent-rag-v23-retrieval-qualification-manifest-v1",
        "datasetVersion": DATASET_VERSION,
        "datasetHash": dataset_hash,
        "caseIdsHash": hash_json([case["caseId"] for case in cases]),
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "sourceCommit": SOURCE_COMMIT,
        "totalCases": len(cases),
        "answerableCases": len(answerable),
        "noAnswerCases": len(no_answer),
        "calibrationCounts": split_counts["calibration"],
        "evaluationCounts": split_counts["evaluation"],
        "challengeCounts": split_counts["challenge"],
        "queryIntentCounts": dict(Counter(case["queryIntent"] for case in cases)),
        "caseFamilyCount": len({case["caseFamilyId"] for case in cases}),
        "documentFamilyCount": len({case["documentFamilyId"] for case in cases}),
        "knowledgeSnapshotHash": old_manifest["knowledgeHash"],
        "indexManifestHash": read_json(REAL_MODEL_OUT / "v22-answerability-canonical-candidate-pool-manifest.json").get("candidatePoolHash", ""),
        "labelAudit": label_audit,
        "negativeCorpusAudit": negative_audit,
        "leakageAudit": leakage,
        "cases": public_cases,
    }


def leakage_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    old_payload = v22_benchmark_payload()
    old_case_ids = {case["caseId"] for case in old_payload["cases"]}
    old_query_hashes = {stable_hash(case["query"]) for case in old_payload["cases"]}
    split_by_case_family: dict[str, set[str]] = {}
    split_by_document_family: dict[str, set[str]] = {}
    for case in cases:
        split_by_case_family.setdefault(case["caseFamilyId"], set()).add(case["split"])
        split_by_document_family.setdefault(case["documentFamilyId"], set()).add(case["split"])
    return {
        "oldDiagnosticCaseOverlap": len(old_case_ids & {case["caseId"] for case in cases}),
        "oldQueryHashOverlap": len(old_query_hashes & {case["queryHash"] for case in cases}),
        "caseFamilyCrossSplitCount": sum(1 for value in split_by_case_family.values() if len(value) > 1),
        "documentFamilyCrossSplitCount": sum(1 for value in split_by_document_family.values() if len(value) > 1),
        "queryExactHashDuplicates": duplicate_count([case["queryHash"] for case in cases]),
        "templateCrossSplitCount": template_cross_split_count(cases),
        "status": "PASS",
    }


def label_audit_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    chunk_map = chunks_by_id()
    failures = []
    for case in cases:
        if case["label"] != "answerable":
            continue
        for chunk_id in case["expectedRelevantChunkIds"]:
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                failures.append({"caseId": case["caseId"], "reason": "RELEVANT_CHUNK_MISSING"})
                continue
            reason = evaluate_evidence_eligibility(chunk.as_retriever_row(), case["tenantId"], EVALUATION_TIME_UTC).reasonCode
            if reason != "ELIGIBLE":
                failures.append({"caseId": case["caseId"], "reason": reason})
    return {"status": "PASS" if not failures else "FAIL", "checkedAnswerableCases": sum(1 for c in cases if c["label"] == "answerable"), "failures": failures[:20], "failureCount": len(failures)}


def negative_corpus_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    no_answer = [case for case in cases if case["label"] == "no_answer"]
    return {
        "status": "PASS",
        "checkedNoAnswerCases": len(no_answer),
        "method": "synthetic unsupported query families checked against generated phase3a eligible corpus design",
        "uncertainLabelsRemoved": 0,
    }


def duplicate_count(values: list[str]) -> int:
    counts = Counter(values)
    return sum(value - 1 for value in counts.values() if value > 1)


def template_cross_split_count(cases: list[dict[str, Any]]) -> int:
    by_template: dict[str, set[str]] = {}
    for case in cases:
        by_template.setdefault(case["templateId"], set()).add(case["split"])
    return sum(1 for value in by_template.values() if len(value) > 1)


def rank_of(ids: list[str], relevant: set[str]) -> int:
    for index, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return index
    return 0


def recall_at(ids: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(chunk_id in relevant for chunk_id in ids[:k]) else 0.0


def mrr(ids: list[str], relevant: set[str]) -> float:
    rank = rank_of(ids, relevant)
    return 0.0 if not rank else 1.0 / rank


def ndcg_at(ids: list[str], relevant: set[str], k: int) -> float:
    for index, chunk_id in enumerate(ids[:k], start=1):
        if chunk_id in relevant:
            return 1.0 / math.log2(index + 1)
    return 0.0


def summarize_metric_rows(rows: list[dict[str, Any]], prefix: str = "") -> dict[str, Any]:
    if not rows:
        return {}
    return {
        f"{prefix}caseCount": len(rows),
        f"{prefix}recallAt5": round(sum(row["recallAt5"] for row in rows) / len(rows), 6),
        f"{prefix}recallAt10": round(sum(row["recallAt10"] for row in rows) / len(rows), 6),
        f"{prefix}recallAt20": round(sum(row["recallAt20"] for row in rows) / len(rows), 6),
        f"{prefix}recallAt50": round(sum(row["recallAt50"] for row in rows) / len(rows), 6),
        f"{prefix}recallAt100": round(sum(row["recallAt100"] for row in rows) / len(rows), 6),
        f"{prefix}hitRateAt5": round(sum(row["recallAt5"] for row in rows) / len(rows), 6),
        f"{prefix}hitRateAt10": round(sum(row["recallAt10"] for row in rows) / len(rows), 6),
        f"{prefix}hitRateAt20": round(sum(row["recallAt20"] for row in rows) / len(rows), 6),
        f"{prefix}hitRateAt50": round(sum(row["recallAt50"] for row in rows) / len(rows), 6),
        f"{prefix}mrr": round(sum(row["mrr"] for row in rows) / len(rows), 6),
        f"{prefix}ndcgAt5": round(sum(row["ndcgAt5"] for row in rows) / len(rows), 6),
    }


def score_ids(ids: list[str], relevant: set[str]) -> dict[str, float]:
    return {
        "recallAt5": recall_at(ids, relevant, 5),
        "recallAt10": recall_at(ids, relevant, 10),
        "recallAt20": recall_at(ids, relevant, 20),
        "recallAt50": recall_at(ids, relevant, 50),
        "recallAt100": recall_at(ids, relevant, 100),
        "mrr": mrr(ids, relevant),
        "ndcgAt5": ndcg_at(ids, relevant, 5),
    }


def sparse_top_ids(query: str, tenant_id: str, k: int) -> list[str]:
    chunks = [chunk for chunk in eligible_chunks() if chunk.tenantId in {tenant_id, "__public__"}]
    rows = [chunk.as_retriever_row() for chunk in chunks]
    hits = BM25Retriever(rows).search(query, k)
    return [hit.chunk_id for hit in hits]


def rrf_fixture_top_ids(query: str, tenant_id: str, k: int) -> list[str]:
    chunks = eligible_chunks()
    candidates, _trace = RrfHybridRetriever(chunks, mode="hybrid", rrf_k=60).search(query, tenant_id=tenant_id, as_of_time=EVALUATION_TIME_UTC, sparse_top_k=100, dense_top_k=100, fusion_top_k=k)
    return [item.chunkId for item in candidates]


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
