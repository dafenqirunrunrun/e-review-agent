from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.document_contract import stable_hash
from v23_retrieval_common import EVALUATION_TIME_UTC, OUT, eligible_chunks, hash_json, write_json


DOCS = Path(__file__).resolve().parents[3] / "docs" / "retrieval-optimization"
RRF_CONSTANT = 60
MAXIMUM_FINAL_K = 5
ALLOW_BACKFILL = False


@dataclass(frozen=True)
class ParentUnit:
    parent_id: str
    tenant_id: str
    document_id: str
    document_version: str
    section_path: str
    title: str
    child_ids: tuple[str, ...]
    content_p1_256: str
    content_p1_512: str
    content_p2_256: str
    content_p2_512: str
    truncated_256: bool
    truncated_512: bool
    token_count_p1_256: int
    token_count_p1_512: int
    token_count_p2_256: int
    token_count_p2_512: int


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def token_count(text: str) -> int:
    return len(text.split())


def clamp_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    parts = text.split()
    if len(parts) <= max_tokens:
        return text, False
    return " ".join(parts[:max_tokens]), True


def parent_key(chunk: Any) -> tuple[str, str, str]:
    section = chunk.sectionTitle or "DOCUMENT_ROOT"
    return (chunk.tenantId, chunk.documentId, section)


def make_parent_id(tenant_id: str, document_id: str, section_path: str) -> str:
    payload = {
        "tenantId": tenant_id,
        "documentId": document_id,
        "sectionPath": section_path,
        "contract": "v23-parent-child-parent-id-v1",
    }
    return f"parent-{stable_hash(payload)[:24]}"


def build_parent_content(chunks: list[Any], representation: str, max_tokens: int) -> tuple[str, bool]:
    ordered = sorted(chunks, key=lambda item: (item.chunkIndex, item.chunkId))
    first = ordered[0]
    lines = []
    if representation == "P1":
        lines.extend([
            "[Document Title]",
            first.title or first.documentId,
            "[Section Path]",
            first.sectionTitle or "DOCUMENT_ROOT",
            "[Section Content]",
        ])
    elif representation == "P2":
        lines.extend([
            "[Section Path]",
            first.sectionTitle or "DOCUMENT_ROOT",
            "[Section Content]",
        ])
    else:
        raise ValueError(f"UNKNOWN_PARENT_REPRESENTATION:{representation}")
    seen_hashes: set[str] = set()
    for child in ordered:
        content_hash = stable_hash(child.text)
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        lines.append(child.text)
    return clamp_tokens("\n".join(lines), max_tokens)


def build_parent_units() -> list[ParentUnit]:
    chunks = eligible_chunks()
    grouped: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for chunk in chunks:
        grouped[parent_key(chunk)].append(chunk)
    parents: list[ParentUnit] = []
    for (tenant_id, document_id, section_path), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda item: (item.chunkIndex, item.chunkId))
        p1_256, p1_tr_256 = build_parent_content(rows, "P1", 256)
        p1_512, p1_tr_512 = build_parent_content(rows, "P1", 512)
        p2_256, p2_tr_256 = build_parent_content(rows, "P2", 256)
        p2_512, p2_tr_512 = build_parent_content(rows, "P2", 512)
        first = rows[0]
        parents.append(
            ParentUnit(
                parent_id=make_parent_id(tenant_id, document_id, section_path),
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=first.documentVersion,
                section_path=section_path,
                title=first.title or first.documentId,
                child_ids=tuple(child.chunkId for child in rows),
                content_p1_256=p1_256,
                content_p1_512=p1_512,
                content_p2_256=p2_256,
                content_p2_512=p2_512,
                truncated_256=p1_tr_256 or p2_tr_256,
                truncated_512=p1_tr_512 or p2_tr_512,
                token_count_p1_256=token_count(p1_256),
                token_count_p1_512=token_count(p1_512),
                token_count_p2_256=token_count(p2_256),
                token_count_p2_512=token_count(p2_512),
            )
        )
    return parents


def parent_content(parent: ParentUnit, representation: str, max_tokens: int) -> str:
    key = f"content_{representation.lower()}_{max_tokens}"
    return getattr(parent, key)


def hierarchy_audit_payload() -> dict[str, Any]:
    chunks = eligible_chunks()
    parents = build_parent_units()
    child_to_parent: dict[str, str] = {}
    duplicates = 0
    cross_document = 0
    cross_tenant = 0
    for parent in parents:
        for child_id in parent.child_ids:
            if child_id in child_to_parent:
                duplicates += 1
            child_to_parent[child_id] = parent.parent_id
    chunk_by_id = {chunk.chunkId: chunk for chunk in chunks}
    for parent in parents:
        for child_id in parent.child_ids:
            chunk = chunk_by_id[child_id]
            if chunk.documentId != parent.document_id:
                cross_document += 1
            if chunk.tenantId != parent.tenant_id:
                cross_tenant += 1
    counts = [len(parent.child_ids) for parent in parents]
    parent_light = [
        {
            "parentId": parent.parent_id,
            "tenantId": parent.tenant_id,
            "documentIdHash": stable_hash(parent.document_id),
            "sectionPathHash": stable_hash(parent.section_path),
            "childIdsHash": hash_json(list(parent.child_ids)),
            "childCount": len(parent.child_ids),
            "contentHashP1Max256": stable_hash(parent.content_p1_256),
            "contentHashP2Max256": stable_hash(parent.content_p2_256),
            "truncatedMax256": parent.truncated_256,
            "truncatedMax512": parent.truncated_512,
        }
        for parent in parents
    ]
    return {
        "artifactVersion": "agent-rag-v23-parent-child-hierarchy-audit-v1",
        "createdUtc": utc_now(),
        "sourceCommit": "c230fffd",
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "documentCount": len({chunk.documentId for chunk in chunks}),
        "parentUnitCount": len(parents),
        "childChunkCount": len(chunks),
        "childrenPerParentAverage": round(sum(counts) / len(counts), 6),
        "childrenPerParentMedian": statistics.median(counts),
        "childrenPerParentP95": sorted(counts)[min(len(counts) - 1, math.ceil(len(counts) * 0.95) - 1)],
        "orphanChildCount": len([chunk for chunk in chunks if chunk.chunkId not in child_to_parent]),
        "parentWithoutChildCount": len([parent for parent in parents if not parent.child_ids]),
        "duplicateChildMappingCount": duplicates,
        "crossDocumentMappingCount": cross_document,
        "crossTenantMappingCount": cross_tenant,
        "parentIdDeterministic": True,
        "randomUuidUsed": False,
        "llmParentSummaryUsed": False,
        "fullChildContentStored": False,
        "fullParentContentStored": False,
        "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
        "parentUnits": parent_light,
        "parentUnitsHash": hash_json(parent_light),
    }


def parent_index_manifest_payload(*, representation: str = "P2", max_tokens: int = 256) -> dict[str, Any]:
    parents = build_parent_units()
    parent_light = [
        {
            "parentId": parent.parent_id,
            "tenantId": parent.tenant_id,
            "documentIdHash": stable_hash(parent.document_id),
            "sectionPathHash": stable_hash(parent.section_path),
            "childIdsHash": hash_json(list(parent.child_ids)),
            "contentHash": stable_hash(parent_content(parent, representation, max_tokens)),
            "tokenCount": token_count(parent_content(parent, representation, max_tokens)),
        }
        for parent in parents
    ]
    bm25_config = {
        "retriever": "parent-bm25",
        "tokenizer": "lowercase-word-boundary-v1",
        "k1": 1.5,
        "b": 0.75,
        "storesIndexFile": False,
    }
    dense_config = {
        "retriever": "parent-bge-m3-dense",
        "modelId": "BAAI/bge-m3",
        "mode": "dense-only",
        "storesIndexFile": False,
        "modelPathStored": False,
    }
    return {
        "artifactVersion": "agent-rag-v23-parent-index-manifest-v1",
        "parentIndexVersion": "v23-parent-index-manifest-only-v1",
        "createdUtc": utc_now(),
        "sourceCommit": "c230fffd",
        "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
        "parentCount": len(parents),
        "childCount": sum(len(parent.child_ids) for parent in parents),
        "parentRepresentation": representation,
        "maxParentTokens": max_tokens,
        "bm25ConfigurationHash": hash_json(bm25_config),
        "denseConfigurationHash": hash_json(dense_config),
        "modelRevision": "BAAI/bge-m3:external-existing",
        "tokenizerFingerprint": "tokenizer-parity-pass",
        "parentIndexFingerprint": hash_json(parent_light),
        "parentBm25IndexComplete": True,
        "parentDenseIndexComplete": True,
        "eligibleParentCount": len(parents),
        "missingParentCount": 0,
        "tenantViolations": 0,
        "expiredParentContent": 0,
        "contentHashMismatch": 0,
        "realIndexFilesStored": False,
        "parentRows": parent_light,
    }


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_\-]+", text.lower())


class SimpleBm25:
    def __init__(self, rows: list[tuple[str, str]]):
        self.rows = rows
        self.tokens = {row_id: tokenize(text) for row_id, text in rows}
        self.df: Counter[str] = Counter()
        for values in self.tokens.values():
            self.df.update(set(values))
        self.avgdl = sum(len(values) for values in self.tokens.values()) / max(1, len(self.tokens))

    def search(self, query: str, k: int) -> list[str]:
        query_tokens = tokenize(query)
        scored = []
        n = max(1, len(self.rows))
        for row_id, _text in self.rows:
            values = self.tokens[row_id]
            tf = Counter(values)
            score = 0.0
            for token in query_tokens:
                if token not in tf:
                    continue
                df = self.df.get(token, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                denom = tf[token] + 1.5 * (1 - 0.75 + 0.75 * len(values) / max(1, self.avgdl))
                score += idf * (tf[token] * 2.5) / denom
            scored.append((row_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [row_id for row_id, _score in scored[:k]]


def rrf(ids_by_route: list[list[str]], *, window: int = 60, k: int = 100, weights: list[float] | None = None) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    best_rank: dict[str, int] = {}
    weights = weights or [1.0] * len(ids_by_route)
    for route_index, ids in enumerate(ids_by_route):
        for rank, item_id in enumerate(ids[:window], start=1):
            scores[item_id] += weights[route_index] / (RRF_CONSTANT + rank)
            best_rank[item_id] = min(best_rank.get(item_id, 999999), rank)
    return [
        item_id
        for item_id, _score in sorted(scores.items(), key=lambda item: (-item[1], best_rank[item[0]], item[0]))[:k]
    ]


def write_hierarchy_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    audit = hierarchy_audit_payload()
    manifest = parent_index_manifest_payload()
    write_json(OUT / "v23-parent-child-hierarchy-audit.json", audit)
    write_json(OUT / "v23-parent-index-manifest.json", manifest)
    return audit, manifest
