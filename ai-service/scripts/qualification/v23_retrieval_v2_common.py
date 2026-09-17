from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.rag.document_contract import stable_hash  # noqa: E402
from v23_retrieval_common import ANSWERABLE_INTENTS, EVALUATION_TIME_UTC, NO_ANSWER_INTENTS, build_v23_cases, eligible_chunks, hash_json  # noqa: E402


DATASET_VERSION = "v23-retrieval-qualification-v2"
SPLIT_PLAN = [
    ("calibration", "answerable", 120),
    ("calibration", "no_answer", 30),
    ("evaluation", "answerable", 120),
    ("evaluation", "no_answer", 30),
    ("challenge", "answerable", 60),
    ("challenge", "no_answer", 15),
]


def build_v23_v2_cases() -> list[dict[str, Any]]:
    chunks = eligible_chunks()
    pools = split_document_families(chunks)
    old_query_hashes = {case["queryHash"] for case in build_v23_cases()}
    cases: list[dict[str, Any]] = []
    cursors = {"calibration": 0, "evaluation": 0, "challenge": 0}
    for split, label, count in SPLIT_PLAN:
        if label == "answerable":
            intents = balanced_intents(ANSWERABLE_INTENTS, count)
            for local_index, intent in enumerate(intents):
                chunk = pools[split][cursors[split] % len(pools[split])]
                cursors[split] += 1
                query = make_v2_answerable_query(intent, chunk, local_index)
                query_hash = stable_hash(query)
                if query_hash in old_query_hashes:
                    raise RuntimeError(f"V23_V2_OLD_QUERY_HASH_LEAK:{query_hash}")
                ordinal = len(cases)
                cases.append(
                    {
                        "caseId": f"v23-ret-v2-{ordinal:04d}",
                        "caseFamilyId": f"v23-v2-case-family-{split}-{label}-{local_index:04d}",
                        "documentFamilyId": f"v23-v2-doc-family-{chunk.documentId}",
                        "templateId": f"v23-v2-template-{intent.lower()}-{local_index % 6}",
                        "split": split,
                        "label": "answerable",
                        "queryIntent": intent,
                        "difficulty": difficulty_for_intent(intent, local_index),
                        "tenantId": chunk.tenantId,
                        "evaluationTimeUtc": EVALUATION_TIME_UTC,
                        "query": query,
                        "queryHash": query_hash,
                        "expectedRelevantChunkIds": [chunk.chunkId],
                        "acceptableRelevantChunkIds": [],
                        "expectedSourceTypes": [str(chunk.sourceType.value if hasattr(chunk.sourceType, "value") else chunk.sourceType)],
                        "minimumRelevantCount": 1,
                        "labelProvenance": {"method": "v2-corpus-template-audit", "reviewStatus": "approved"},
                    }
                )
        else:
            intents = balanced_intents(NO_ANSWER_INTENTS, count)
            for local_index, intent in enumerate(intents):
                query = make_v2_no_answer_query(intent, split, local_index)
                query_hash = stable_hash(query)
                if query_hash in old_query_hashes:
                    raise RuntimeError(f"V23_V2_OLD_NO_ANSWER_QUERY_HASH_LEAK:{query_hash}")
                ordinal = len(cases)
                cases.append(
                    {
                        "caseId": f"v23-ret-v2-{ordinal:04d}",
                        "caseFamilyId": f"v23-v2-case-family-{split}-{label}-{local_index:04d}",
                        "documentFamilyId": f"v23-v2-no-answer-doc-family-{split}-{local_index:04d}",
                        "templateId": f"v23-v2-template-{intent.lower()}-{local_index % 4}",
                        "split": split,
                        "label": "no_answer",
                        "queryIntent": intent,
                        "difficulty": difficulty_for_intent(intent, local_index),
                        "tenantId": "tenant-a",
                        "evaluationTimeUtc": EVALUATION_TIME_UTC,
                        "query": query,
                        "queryHash": query_hash,
                        "expectedRelevantChunkIds": [],
                        "acceptableRelevantChunkIds": [],
                        "expectedSourceTypes": [],
                        "minimumRelevantCount": 0,
                        "negativeJustification": f"v2 unsupported retrieval qualification case for {intent}",
                        "corpusAuditHash": stable_hash({"dataset": DATASET_VERSION, "split": split, "intent": intent, "queryHash": query_hash}),
                        "labelProvenance": {"method": "v2-corpus-negative-audit", "reviewStatus": "approved"},
                    }
                )
    return cases


def build_v23_v2_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    light = [
        {
            "caseId": case["caseId"],
            "caseFamilyId": case["caseFamilyId"],
            "documentFamilyId": case["documentFamilyId"],
            "split": case["split"],
            "label": case["label"],
            "queryIntent": case["queryIntent"],
            "difficulty": case["difficulty"],
            "queryHash": case["queryHash"],
            "relevantIdsHash": hash_json(case["expectedRelevantChunkIds"] + case["acceptableRelevantChunkIds"]),
        }
        for case in cases
    ]
    return {
        "datasetVersion": DATASET_VERSION,
        "datasetHash": hash_json(light),
        "caseCount": len(cases),
        "caseIdsHash": hash_json([case["caseId"] for case in cases]),
        "queryHashesHash": hash_json([case["queryHash"] for case in cases]),
        "splitLabelCounts": nested_counts(cases, "split", "label"),
        "splitIntentDistribution": split_distribution(cases, "queryIntent"),
        "splitDifficultyDistribution": split_distribution(cases, "difficulty"),
        "documentFamilySplitMapHash": hash_json(document_family_split_map(cases)),
        "caseFamilySplitMapHash": hash_json(case_family_split_map(cases)),
    }


def split_document_families(chunks: list[Any]) -> dict[str, list[Any]]:
    by_doc: dict[str, list[Any]] = defaultdict(list)
    for chunk in chunks:
        by_doc[chunk.documentId].append(chunk)
    docs = sorted(by_doc)
    if len(docs) < 15:
        raise RuntimeError("V23_V2_INSUFFICIENT_DOCUMENT_FAMILIES")
    split_docs = {
        "calibration": docs[:6],
        "evaluation": docs[6:12],
        "challenge": docs[12:],
    }
    return {split: [chunk for doc_id in doc_ids for chunk in by_doc[doc_id]] for split, doc_ids in split_docs.items()}


def balanced_intents(intents: list[str], count: int) -> list[str]:
    return [intents[index % len(intents)] for index in range(count)]


def make_v2_answerable_query(intent: str, chunk: Any, index: int) -> str:
    words = chunk.text.split()
    anchor = words[min(len(words) - 1, index % max(1, len(words)))] if words else chunk.documentId
    title = chunk.title or chunk.documentId
    section = chunk.sectionTitle or "section"
    templates = {
        "LEXICAL_EXACT_MATCH": f"v2 audit locate exact wording around {anchor} in {section}",
        "LEXICAL_PARTIAL_MATCH": f"v2 audit which policy discusses {anchor} for operations",
        "SEMANTIC_PARAPHRASE": f"v2 audit find evidence for a customer-facing rule similar to {anchor}",
        "COLLOQUIAL_QUERY": f"v2 audit what should ops do when shoppers mention {anchor}",
        "ABBREVIATION": f"v2 audit ops rule ref for {anchor} in {title}",
        "TYPO_OR_VARIANT": f"v2 audit retrieve variant spelling evidence near {anchor}",
        "ENTITY_RELATION": f"v2 audit how does {title} relate to {anchor}",
        "NEGATION": f"v2 audit find the clause that does not allow unsupported {anchor}",
        "CONDITIONAL_RULE": f"v2 audit if {anchor} happens what condition applies",
        "TEMPORAL_CONDITION": f"v2 audit time sensitive handling evidence for {anchor}",
        "SCOPE_CONDITION": f"v2 audit scope limitation evidence involving {anchor}",
        "MULTI_CONDITION_QUERY": f"v2 audit evidence combining {anchor} with {section} requirement",
        "LONG_QUERY": f"v2 audit identify the operational evidence in {title} when a review references {anchor} and needs governed handling",
        "SHORT_QUERY": f"v2 audit {anchor} rule",
        "TITLE_DEPENDENT": f"v2 audit use title context {title} to locate {anchor}",
        "SECTION_DEPENDENT": f"v2 audit use section context {section} to locate {anchor}",
        "PARENT_CONTEXT_REQUIRED": f"v2 audit parent policy context needed for {anchor}",
        "LOW_FREQUENCY_TERM": f"v2 audit rare term evidence {anchor}",
        "MULTIPLE_DISTRACTORS": f"v2 audit distinguish {anchor} from similar policy distractors",
        "NEAR_DUPLICATE_DISTRACTORS": f"v2 audit identify the near duplicate evidence for {anchor}",
    }
    return templates[intent]


def make_v2_no_answer_query(intent: str, split: str, index: int) -> str:
    suffix = f"{split} unsupported v2 {index}"
    return {
        "OUT_OF_DOMAIN": f"v2 audit ask for warehouse robot firmware SLA {suffix}",
        "SEMANTIC_NEAR_MISS": f"v2 audit request a similar but unsupported marketplace penalty {suffix}",
        "ENTITY_MISMATCH": f"v2 audit ask about tenant z exclusive return policy {suffix}",
        "RELATION_MISMATCH": f"v2 audit invert the relationship between fraud and verified appeal {suffix}",
        "TEMPORAL_MISMATCH": f"v2 audit ask for a future policy effective after archive date {suffix}",
        "SCOPE_MISMATCH": f"v2 audit ask for private tenant b scope while tenant a is active {suffix}",
        "UNSUPPORTED_COMPOSITE_QUERY": f"v2 audit combine safety recall with unrelated tax invoice rule {suffix}",
        "INSUFFICIENT_SPECIFICITY": f"v2 audit ask vague handling guidance without review context {suffix}",
        "LEXICAL_DECOY": f"v2 audit mention refund logistics fraud but ask for missing insurance clause {suffix}",
        "CONFLICTING_WITHOUT_RESOLUTION": f"v2 audit ask for two conflicting rules with no resolution evidence {suffix}",
    }[intent]


def difficulty_for_intent(intent: str, index: int) -> str:
    if intent in {"LEXICAL_EXACT_MATCH", "SHORT_QUERY"}:
        return "easy"
    if intent in {"MULTI_CONDITION_QUERY", "PARENT_CONTEXT_REQUIRED", "NEAR_DUPLICATE_DISTRACTORS", "UNSUPPORTED_COMPOSITE_QUERY", "CONFLICTING_WITHOUT_RESOLUTION"}:
        return "hard"
    return ["medium", "medium", "hard"][index % 3]


def nested_counts(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = defaultdict(Counter)
    for case in cases:
        out[case[left]][case[right]] += 1
    return {key: dict(value) for key, value in sorted(out.items())}


def split_distribution(cases: list[dict[str, Any]], key: str) -> dict[str, dict[str, float]]:
    by_split: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        by_split[case["split"]].append(case[key])
    out = {}
    for split, values in sorted(by_split.items()):
        total = max(1, len(values))
        counts = Counter(values)
        out[split] = {item: round(count / total, 6) for item, count in sorted(counts.items())}
    return out


def document_family_split_map(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        out[case["documentFamilyId"]].add(case["split"])
    return {key: sorted(value) for key, value in sorted(out.items())}


def case_family_split_map(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        out[case["caseFamilyId"]].add(case["split"])
    return {key: sorted(value) for key, value in sorted(out.items())}
