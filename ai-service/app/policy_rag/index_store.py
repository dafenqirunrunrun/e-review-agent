from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.embedding import PolicyEmbeddingProvider, create_policy_embedding_provider
from app.policy_rag.models import ParsedPolicyDocument, PolicyChunk, utc_now
from app.policy_rag.vector_store import build_policy_faiss_index
from app.rag.document_contract import stable_hash


DEFAULT_INDEX_DIR = Path("data/policy_rag")
DEFAULT_CHUNKS_NAME = "policy_chunks.jsonl"
DEFAULT_MANIFEST_NAME = "policy_manifest.json"


def build_policy_index(
    documents: Iterable[ParsedPolicyDocument],
    *,
    output_dir: Path | str = DEFAULT_INDEX_DIR,
    chunker: PolicyStructureChunker | None = None,
    build_dense: bool | None = None,
    embedding_provider: PolicyEmbeddingProvider | None = None,
    review_relevant_only: bool = False,
) -> dict:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    chunker = chunker or PolicyStructureChunker()

    chunks: list[PolicyChunk] = []
    manifests = []
    for document in documents:
        manifests.append(document.manifest.model_dump())
        chunks.extend(chunker.chunk(document))
    if review_relevant_only:
        chunks = [chunk for chunk in chunks if _review_relevant(chunk)]

    chunks_path = target_dir / DEFAULT_CHUNKS_NAME
    manifest_path = target_dir / DEFAULT_MANIFEST_NAME
    write_policy_chunks(chunks_path, chunks)

    index_hash = stable_hash("|".join(chunk.contentHash for chunk in chunks))
    dense_enabled = _env_bool("E_REVIEW_POLICY_RAG_DENSE_ENABLED", True) if build_dense is None else build_dense
    dense_manifest = (
        build_policy_faiss_index(
            chunks,
            output_dir=target_dir,
            provider=embedding_provider or create_policy_embedding_provider(),
        )
        if dense_enabled
        else {"schemaVersion": "policy-rag-faiss-v1", "status": "disabled", "fallbackReason": "DENSE_BUILD_DISABLED"}
    )
    manifest = {
        "schemaVersion": "policy-rag-index-v1",
        "generatedAt": utc_now(),
        "chunkPath": str(chunks_path),
        "chunkCount": len(chunks),
        "sourceCount": len(manifests),
        "indexHash": index_hash,
        "retrieval": {
            "sparse": {"status": "ready", "strategy": "bm25"},
            "dense": dense_manifest,
            "fallback": "bm25",
        },
        "sources": manifests,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def write_policy_chunks(path: Path | str, chunks: Iterable[PolicyChunk]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as file:
        for chunk in chunks:
            file.write(chunk.model_dump_json() + "\n")


def load_policy_chunks(path: Path | str) -> list[PolicyChunk]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"policy index not found: {source}")
    chunks: list[PolicyChunk] = []
    with source.open("r", encoding="utf-8-sig") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                chunks.append(PolicyChunk.model_validate(json.loads(text)))
            except Exception as exc:
                raise ValueError(f"invalid policy chunk at {source}:{line_no}") from exc
    return chunks


def _env_bool(name: str, default: bool) -> bool:
    value = str(os.getenv(name, str(default))).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _review_relevant(chunk: PolicyChunk) -> bool:
    # A legal clause can govern review handling without containing the current
    # keyword vocabulary (for example, a general consumer-remedy provision).
    # The public policy corpus is deliberately small, so retain every numbered
    # law/regulation clause and filter only unnumbered document noise by terms.
    if chunk.sourceType in {"law", "regulation"} and chunk.clauseId:
        return True
    if any(risk != "review_policy" for risk in chunk.riskTypes):
        return True
    text = " ".join([chunk.heading, chunk.text]).lower()
    terms = [
        "review",
        "rating",
        "testimonial",
        "endorsement",
        "feedback",
        "评价",
        "评论",
        "信用",
        "刷单",
        "好评",
        "差评",
        "虚假",
        "退货",
        "退款",
        "售后",
        "换货",
        "修理",
        "返还",
        "退还",
        "价款",
        "运费",
        "无理由",
        "隐私",
        "个人信息",
    ]
    return any(term in text for term in terms)
