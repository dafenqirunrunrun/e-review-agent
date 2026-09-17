from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.eligibility import ELIGIBILITY_VERSION, evaluate_evidence_eligibility  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from v23_retrieval_common import EVALUATION_TIME_UTC, OUT, eligible_chunks, hash_json, sparse_top_ids, write_json, write_text  # noqa: E402
from v23_retrieval_v2_common import DATASET_VERSION, build_v23_v2_cases, build_v23_v2_manifest  # noqa: E402


DOCS = ROOT / "docs" / "retrieval-optimization"
INDEX_FORMAT_VERSION = "agent-rag-v23-bge-m3-sparse-index-v1"
SCORE_TYPE = "BGE_M3_LEARNED_SPARSE_DOT_PRODUCT"
RETRIEVAL_CONTENT_VERSION = "content-only"
MINIMUM_SPARSE_WEIGHT = 0.0
K_VALUES = (5, 10, 20, 50, 100)


@dataclass(frozen=True)
class SparseDocumentVector:
    chunkId: str
    contentHash: str
    sourceId: str
    sourceType: str
    tenantScopeHash: str
    eligibilityHash: str
    tokenIds: list[int]
    weights: list[float]

    @property
    def nonZeroDimensionCount(self) -> int:
        return len(self.tokenIds)

    @property
    def vectorHash(self) -> str:
        return hash_json({"tokenIds": self.tokenIds, "weights": [round(value, 8) for value in self.weights]})

    def validate(self) -> None:
        if not self.tokenIds or not self.weights:
            raise ValueError("SPARSE_EMPTY_DOCUMENT_VECTOR")
        if len(self.tokenIds) != len(self.weights):
            raise ValueError("SPARSE_TOKEN_WEIGHT_LENGTH_MISMATCH")
        if self.tokenIds != sorted(set(self.tokenIds)):
            raise ValueError("SPARSE_TOKEN_IDS_NOT_UNIQUE_SORTED")
        for weight in self.weights:
            if not math.isfinite(float(weight)):
                raise ValueError("SPARSE_WEIGHT_NOT_FINITE")
            if float(weight) < 0:
                raise ValueError("SPARSE_WEIGHT_NEGATIVE")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_external_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct == 0.5:
        return round(float(statistics.median(ordered)), 3)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return round(float(ordered[index]), 3)


def safe_chunk_metadata(chunk: Any, generation: int = 1) -> dict[str, Any]:
    source_type = str(chunk.sourceType.value if hasattr(chunk.sourceType, "value") else chunk.sourceType)
    row = chunk.as_retriever_row()
    return {
        "chunkId": chunk.chunkId,
        "contentHash": chunk.contentHash,
        "sourceId": chunk.documentId,
        "sourceType": source_type,
        "tenantScopeHash": stable_hash({"tenantId": chunk.tenantId, "visibility": chunk.visibility}),
        "tenantIdHash": stable_hash(chunk.tenantId),
        "effectiveFrom": chunk.effectiveFrom,
        "expiresAt": chunk.effectiveTo,
        "active": row.get("active", True),
        "disabled": str(row.get("status") or "").lower() == "disabled",
        "tombstoned": bool(row.get("deleted", False)),
        "knowledgeSnapshotHash": knowledge_snapshot_hash(),
        "indexGeneration": generation,
        "documentVersion": chunk.documentVersion,
        "visibility": chunk.visibility,
    }


def eligibility_hash(chunk: Any) -> str:
    meta = safe_chunk_metadata(chunk)
    return stable_hash(
        {
            "eligibilityVersion": ELIGIBILITY_VERSION,
            "contentHash": chunk.contentHash,
            "tenantScopeHash": meta["tenantScopeHash"],
            "effectiveFrom": chunk.effectiveFrom,
            "expiresAt": chunk.effectiveTo,
            "status": str(chunk.status.value if hasattr(chunk.status, "value") else chunk.status),
            "retrievalContentVersion": RETRIEVAL_CONTENT_VERSION,
        }
    )


def knowledge_snapshot_hash() -> str:
    manifest = read_json(OUT / "v23-retrieval-qualification-v2-manifest.json")
    return manifest.get("knowledgeSnapshotHash") or hash_json([chunk.contentHash for chunk in eligible_chunks()])


def load_environment_lock() -> dict[str, Any]:
    return {
        "environment": read_json(OUT / "v23-bge-m3-sparse-isolated-environment.json"),
        "runtimeSmoke": read_json(OUT / "v23-bge-m3-sparse-runtime-smoke.json"),
        "tokenizerParity": read_json(OUT / "v23-bge-m3-sparse-tokenizer-parity.json"),
        "environmentGate": read_json(OUT / "v23-bge-m3-sparse-environment-gate.json"),
    }


def verify_phase94a_environment() -> None:
    lock = load_environment_lock()
    gate = lock["environmentGate"]
    if gate.get("status") != "PASS":
        raise RuntimeError("SPARSE_ENVIRONMENT_GATE_NOT_PASS")
    if not gate.get("checks", {}).get("realSparseExecution"):
        raise RuntimeError("SPARSE_REAL_RUNTIME_NOT_VERIFIED")
    if not gate.get("checks", {}).get("tokenizerParityPass"):
        raise RuntimeError("SPARSE_TOKENIZER_PARITY_NOT_VERIFIED")


def load_bge_m3_model(asset_manifest: Path):
    from FlagEmbedding import BGEM3FlagModel

    manifest = read_json(asset_manifest)
    embedding = manifest.get("embedding") or {}
    if embedding.get("modelId") != "BAAI/bge-m3":
        raise RuntimeError("SPARSE_INDEX_INPUT_CONTRACT_MISMATCH")
    started = time.perf_counter()
    model = BGEM3FlagModel(embedding["modelPath"], use_fp16=True, device="cuda")
    return model, manifest, round((time.perf_counter() - started) * 1000, 3)


def encode_sparse(model: Any, texts: list[str], *, batch_size: int, max_length: int = 128) -> tuple[list[dict[int, float]], dict[str, Any]]:
    started = time.perf_counter()
    encoded = model.encode(texts, batch_size=batch_size, max_length=max_length, return_dense=False, return_sparse=True, return_colbert_vecs=False)
    duration = round((time.perf_counter() - started) * 1000, 3)
    raw_vectors = encoded["lexical_weights"]
    return [normalize_sparse_weights(item) for item in raw_vectors], {"durationMs": duration, "batchSize": batch_size, "itemCount": len(texts)}


def normalize_sparse_weights(weights: dict[Any, Any]) -> dict[int, float]:
    out: dict[int, float] = {}
    for token, value in weights.items():
        weight = float(value)
        if weight <= MINIMUM_SPARSE_WEIGHT:
            continue
        token_id = token_to_id(token)
        out[token_id] = max(out.get(token_id, 0.0), round(weight, 8))
    return dict(sorted(out.items()))


def token_to_id(token: Any) -> int:
    text = str(token)
    if text.isdigit():
        return int(text)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def build_document_vector(chunk: Any, vector: dict[int, float]) -> SparseDocumentVector:
    metadata = safe_chunk_metadata(chunk)
    doc_vector = SparseDocumentVector(
        chunkId=chunk.chunkId,
        contentHash=chunk.contentHash,
        sourceId=chunk.documentId,
        sourceType=metadata["sourceType"],
        tenantScopeHash=metadata["tenantScopeHash"],
        eligibilityHash=eligibility_hash(chunk),
        tokenIds=list(vector.keys()),
        weights=list(vector.values()),
    )
    doc_vector.validate()
    return doc_vector


def vector_to_postings(vector: SparseDocumentVector) -> list[tuple[int, str, float]]:
    return [(token_id, vector.chunkId, weight) for token_id, weight in zip(vector.tokenIds, vector.weights, strict=True)]


def sparse_dot(query: dict[int, float], document: dict[int, float]) -> float:
    if len(query) > len(document):
        query, document = document, query
    return sum(float(value) * float(document.get(token_id, 0.0)) for token_id, value in query.items())


def score_index(query_vector: dict[int, float], index: dict[str, Any], *, tenant_id_hash: str, top_k: int) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    postings = index["postings"]
    metadata = index["chunks"]
    for token_id, query_weight in query_vector.items():
        for item in postings.get(str(token_id), []):
            chunk_id = item["chunkId"]
            meta = metadata.get(chunk_id)
            if not meta:
                continue
            if meta["tenantIdHash"] not in {tenant_id_hash, stable_hash("__public__")}:
                continue
            scores[chunk_id] = scores.get(chunk_id, 0.0) + float(query_weight) * float(item["weight"])
    ranked = sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:top_k]
    return [{"chunkId": chunk_id, "sparseScore": round(score, 8), "sparseRank": rank} for rank, (chunk_id, score) in enumerate(ranked, start=1)]


def load_external_index(index_dir: Path) -> dict[str, Any]:
    postings = read_json(index_dir / "sparse-postings.json")
    chunks = read_json(index_dir / "sparse-chunks.json")
    manifest = read_json(index_dir / "sparse-index-manifest.json")
    return {"postings": postings, "chunks": chunks, "manifest": manifest}


def score_ids(ids: list[str], relevant: set[str]) -> dict[str, float]:
    first = next((index for index, chunk_id in enumerate(ids, start=1) if chunk_id in relevant), 0)
    out: dict[str, float] = {}
    for k in K_VALUES:
        hit = any(chunk_id in relevant for chunk_id in ids[:k])
        out[f"recallAt{k}"] = 1.0 if hit else 0.0
        out[f"coverageAt{k}"] = 1.0 if hit else 0.0
    out["mrr"] = 0.0 if not first else round(1.0 / first, 8)
    out["ndcgAt5"] = 0.0 if not first or first > 5 else round(1.0 / math.log2(first + 1), 8)
    out["bestRelevantRank"] = float(first)
    return out


def aggregate_scores(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {}
    keys = [key for key in rows[0] if key != "bestRelevantRank"]
    out = {key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in keys}
    ranks = [int(row["bestRelevantRank"]) for row in rows if row.get("bestRelevantRank")]
    out["missCount"] = len(rows) - len(ranks)
    out["caseCount"] = len(rows)
    return out


def raw_union(left: list[str], right: list[str], third: list[str] | None = None, *, k: int = 100) -> list[str]:
    best_rank_by_id: dict[str, int] = {}
    for ids in [left[:k], right[:k], (third or [])[:k]]:
        for rank, chunk_id in enumerate(ids, start=1):
            best_rank_by_id[chunk_id] = min(best_rank_by_id.get(chunk_id, 10_000), rank)
    return [chunk_id for chunk_id, _rank in sorted(best_rank_by_id.items(), key=lambda item: (item[1], item[0]))]


def calibration_cases() -> list[dict[str, Any]]:
    return [case for case in build_v23_v2_cases() if case["split"] == "calibration"]


def answerable_calibration_cases() -> list[dict[str, Any]]:
    return [case for case in calibration_cases() if case["label"] == "answerable"]


def no_answer_calibration_cases() -> list[dict[str, Any]]:
    return [case for case in calibration_cases() if case["label"] == "no_answer"]


def relevant_ids(case: dict[str, Any]) -> set[str]:
    return set(case["expectedRelevantChunkIds"]) | set(case["acceptableRelevantChunkIds"])


def summarize_sensitive_policy() -> dict[str, Any]:
    return {
        "storesFullQueries": False,
        "storesFullChunks": False,
        "storesTokenWeightMapInRepoArtifacts": False,
        "externalIndexPathPersistedInRepo": False,
    }


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
