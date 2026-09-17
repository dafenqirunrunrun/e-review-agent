from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.policy_rag.embedding import (
    DEFAULT_POLICY_QUERY_INSTRUCTION,
    QWEN3_OFFICIAL_RETRIEVAL_PROFILE,
    QwenEmbeddingConfig,
    QwenOfficialTransformersEmbeddingProvider,
    QwenTransformersEmbeddingProvider,
)
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.vector_store import DEFAULT_FAISS_META_NAME, DEFAULT_FAISS_NAME, build_policy_faiss_index
from scripts.run_step16_benchmark import load_jsonl, ranking_metrics, subset_ranking_metrics


FROZEN_GOLD_SHA256 = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
DEFAULT_DATASET = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
DEFAULT_CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
DEFAULT_V1_INDEX_DIR = ROOT / "data" / "policy_rag_real" / "index"
DEFAULT_V2_INDEX_DIR = ROOT / "artifacts" / "step233a" / "qwen_official_v2"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step233a" / "qwen_embedding_ab.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Step 23.3A Qwen embedding semantics A/B.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--v1-index-dir", type=Path, default=DEFAULT_V1_INDEX_DIR)
    parser.add_argument("--v2-index-dir", type=Path, default=DEFAULT_V2_INDEX_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--query-instruction", default=DEFAULT_POLICY_QUERY_INSTRUCTION)
    parser.add_argument("--reuse-v2-index", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    chunks_path = args.chunks.resolve()
    v1_dir = args.v1_index_dir.resolve()
    v2_dir = args.v2_index_dir.resolve()
    if v1_dir == v2_dir:
        raise SystemExit("STEP233A_INDEX_ISOLATION_FAILED")
    if not 32 <= args.max_length <= 2048:
        raise SystemExit("STEP233A_MAX_LENGTH_INVALID")

    gold_sha = sha256_file(dataset)
    if gold_sha != FROZEN_GOLD_SHA256:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA256} actual={gold_sha}")

    active_hashes_before = active_index_hashes(v1_dir)
    chunks = load_policy_chunks(chunks_path)
    cases = [case for case in load_jsonl(dataset) if case.get("expectedEvidenceTags")]
    if not chunks or not cases:
        raise SystemExit("STEP233A_INPUT_EMPTY")

    config = current_config(batch_size=args.batch_size)
    bm25_rankings = build_bm25_rankings(chunks, cases)

    v1_provider = QwenTransformersEmbeddingProvider(config)
    v1 = evaluate_profile(
        name="legacy_v1",
        provider=v1_provider,
        index_dir=v1_dir,
        chunks=chunks,
        cases=cases,
        bm25_rankings=bm25_rankings,
    )
    release_provider(v1_provider)

    v2_config = QwenEmbeddingConfig(
        model_name=config.model_name,
        model_path=config.model_path,
        device=config.device,
        batch_size=args.batch_size,
        max_length=args.max_length,
        normalize=config.normalize,
        allow_remote=config.allow_remote,
    )
    v2_provider = QwenOfficialTransformersEmbeddingProvider(
        v2_config,
        query_instruction=args.query_instruction,
    )
    v2_manifest = ensure_v2_index(v2_dir, chunks, v2_provider, reuse=args.reuse_v2_index)
    token_profile = document_token_profile(v2_provider, chunks)
    v2 = evaluate_profile(
        name="official_v2",
        provider=v2_provider,
        index_dir=v2_dir,
        chunks=chunks,
        cases=cases,
        bm25_rankings=bm25_rankings,
    )
    release_provider(v2_provider)

    active_hashes_after = active_index_hashes(v1_dir)
    active_untouched = active_hashes_before == active_hashes_after
    promotion = promotion_gate(v1, v2, v2_manifest, active_untouched)
    report = {
        "schemaVersion": "step23.3a-qwen-embedding-ab-v1",
        "experimentGate": "PASS" if active_untouched else "FAIL",
        "promotionGate": promotion,
        "frozenGold": {"sha256": gold_sha, "caseCount": len(load_jsonl(dataset)), "retrievalCaseCount": len(cases)},
        "corpus": {
            "chunkCount": len(chunks),
            "contentRootHash": content_root_hash(chunks),
            "tokenProfile": token_profile,
        },
        "isolation": {
            "activeIndexUntouched": active_untouched,
            "activeIndexHashesBefore": active_hashes_before,
            "activeIndexHashesAfter": active_hashes_after,
            "candidateIndexDirectory": display_path(v2_dir),
            "runtimeConfigurationChanged": False,
        },
        "profiles": {"legacyV1": v1, "officialV2": v2},
        "comparison": compare_profiles(v1, v2),
        "candidateIndex": safe_index_manifest(v2_manifest),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if report["experimentGate"] == "PASS" else 1


def current_config(*, batch_size: int) -> QwenEmbeddingConfig:
    policy = settings.policy_rag
    return QwenEmbeddingConfig(
        model_name=policy.embedding_model,
        model_path=Path(policy.embedding_model_path) if policy.embedding_model_path else None,
        device=policy.embedding_device,
        batch_size=batch_size,
        max_length=policy.embedding_max_length,
        normalize=os.getenv("E_REVIEW_POLICY_RAG_EMBEDDING_NORMALIZE", "true").lower() in {"1", "true", "yes", "on"},
        allow_remote=policy.embedding_allow_remote,
    )


def ensure_v2_index(
    output_dir: Path,
    chunks: list[Any],
    provider: QwenOfficialTransformersEmbeddingProvider,
    *,
    reuse: bool,
) -> dict[str, Any]:
    meta_path = output_dir / DEFAULT_FAISS_META_NAME
    if reuse and (output_dir / DEFAULT_FAISS_NAME).exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        expected = provider.metadata()
        if (
            meta.get("contentRootHash") == content_root_hash(chunks)
            and meta.get("provider", {}).get("modelFingerprint") == expected.get("modelFingerprint")
        ):
            return make_candidate_index_portable(output_dir, meta)
    manifest = build_policy_faiss_index(chunks, output_dir=output_dir, provider=provider)
    if manifest.get("status") != "ready":
        raise SystemExit(f"STEP233A_V2_INDEX_BUILD_FAILED:{manifest.get('fallbackReason', 'unknown')}")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    return make_candidate_index_portable(output_dir, meta)


def make_candidate_index_portable(output_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    portable = dict(meta)
    portable["indexPath"] = DEFAULT_FAISS_NAME
    portable["metaPath"] = DEFAULT_FAISS_META_NAME
    if isinstance(portable.get("provider"), dict):
        portable["provider"] = safe_provider_metadata(portable["provider"])
    (output_dir / DEFAULT_FAISS_META_NAME).write_text(
        json.dumps(portable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {key: value for key, value in portable.items() if key != "rows"}


def build_bm25_rankings(chunks: list[Any], cases: list[dict[str, Any]]) -> list[list[tuple[float, Any]]]:
    retriever = PolicyEvidenceRetriever(chunks)
    rankings = []
    for case in cases:
        risks = list(case["expectedRiskTypes"])
        expanded = " ".join([case["reviewText"], retriever._expand_risk_hints(risks)]).strip()
        rankings.append(retriever._bm25_search(expanded, risks, top_k=20))
    return rankings


def evaluate_profile(
    *,
    name: str,
    provider: Any,
    index_dir: Path,
    chunks: list[Any],
    cases: list[dict[str, Any]],
    bm25_rankings: list[list[tuple[float, Any]]],
) -> dict[str, Any]:
    import faiss

    meta = json.loads((index_dir / DEFAULT_FAISS_META_NAME).read_text(encoding="utf-8-sig"))
    index = faiss.deserialize_index(np.frombuffer((index_dir / DEFAULT_FAISS_NAME).read_bytes(), dtype="uint8"))
    if int(index.ntotal) != len(chunks) or int(index.d) != int(meta.get("dimension", 0)):
        raise SystemExit(f"STEP233A_INDEX_INCOMPATIBLE:{name}")
    if meta.get("contentRootHash") != content_root_hash(chunks):
        raise SystemExit(f"STEP233A_CORPUS_MISMATCH:{name}")

    expanded_queries = [
        " ".join([case["reviewText"], PolicyEvidenceRetriever._expand_risk_hints(case["expectedRiskTypes"])]).strip()
        for case in cases
    ]
    started = time.perf_counter()
    if hasattr(provider, "embed_queries"):
        query_vectors = provider.embed_queries(expanded_queries)
    else:
        query_vectors = provider.embed_documents(expanded_queries)
    embedding_ms = round((time.perf_counter() - started) * 1000, 2)
    scores, positions = index.search(np.asarray(query_vectors, dtype="float32"), 20)
    chunk_by_id = {chunk.chunkId: chunk for chunk in chunks}
    rows_by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for offset, case in enumerate(cases):
        dense = []
        for score, position in zip(scores[offset], positions[offset]):
            if position < 0:
                continue
            chunk_id = meta["rows"][int(position)]["chunkId"]
            dense.append((float(score), chunk_by_id[chunk_id]))
        fused = PolicyEvidenceRetriever._fuse(bm25_rankings[offset], dense, top_k=5)
        for mode, ranking in (("dense", dense[:5]), ("hybrid", fused)):
            rank = first_matching_rank_from_chunks(ranking, case["expectedEvidenceTags"], case["expectedRiskTypes"])
            rows_by_mode[mode].append(
                {
                    "caseId": case["caseId"],
                    "rank": rank,
                    "subsets": case["subset"],
                    "top": [
                        {
                            "chunkId": chunk.chunkId,
                            "score": round(float(score), 6),
                            "source": chunk.sourceName,
                        }
                        for score, chunk in ranking[:5]
                    ],
                    "citationValid": all(chunk.sourceUrl and chunk.sectionPath and chunk.contentHash for _, chunk in ranking[:5]),
                }
            )

    modes = {}
    for mode, rows in rows_by_mode.items():
        modes[mode] = {
            "metrics": ranking_metrics(rows),
            "subsets": subset_ranking_metrics(rows),
            "citationValid": all(row["citationValid"] for row in rows),
            "sampleTopK": rows[:12],
        }
    return {
        "name": name,
        "provider": safe_provider_metadata(provider.metadata()),
        "index": {
            "vectorCount": int(index.ntotal),
            "dimension": int(index.d),
            "contentRootHash": meta.get("contentRootHash"),
        },
        "queryBatchEmbeddingMs": embedding_ms,
        "modes": modes,
    }


def first_matching_rank_from_chunks(
    ranking: list[tuple[float, Any]],
    expected_tags: list[str],
    expected_risks: list[str],
) -> int | None:
    wanted = set(expected_tags) | set(expected_risks)
    for rank, (_, chunk) in enumerate(ranking, start=1):
        if wanted.intersection(set(chunk.evidenceTags) | set(chunk.riskTypes)):
            return rank
    return None


def document_token_profile(provider: QwenOfficialTransformersEmbeddingProvider, chunks: list[Any]) -> dict[str, Any]:
    provider._ensure_loaded()
    encoded = provider._tokenizer(
        [chunk.text for chunk in chunks],
        padding=False,
        truncation=False,
        add_special_tokens=True,
    )
    lengths = sorted(len(ids) for ids in encoded["input_ids"])
    return {
        "min": lengths[0],
        "median": round(statistics.median(lengths), 2),
        "p95": lengths[min(len(lengths) - 1, math.ceil(len(lengths) * 0.95) - 1)],
        "max": lengths[-1],
        "overLegacy96": sum(length > 96 for length in lengths),
        "overCandidateMaxLength": sum(length > provider.config.max_length for length in lengths),
        "candidateMaxLength": provider.config.max_length,
    }


def promotion_gate(v1: dict[str, Any], v2: dict[str, Any], manifest: dict[str, Any], active_untouched: bool) -> str:
    v1_hybrid = v1["modes"]["hybrid"]["metrics"]
    v2_hybrid = v2["modes"]["hybrid"]["metrics"]
    ready = (
        active_untouched
        and manifest.get("status") == "ready"
        and v2["modes"]["dense"]["citationValid"]
        and v2["modes"]["hybrid"]["citationValid"]
    )
    quality = (
        v2_hybrid["recallAt1"] >= v1_hybrid["recallAt1"]
        and v2_hybrid["recallAt3"] >= v1_hybrid["recallAt3"]
        and v2_hybrid["recallAt5"] >= v1_hybrid["recallAt5"]
        and v2_hybrid["mrr"] >= v1_hybrid["mrr"]
    )
    return "PASS" if ready and quality else "HOLD"


def compare_profiles(v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    comparison = {}
    for mode in ("dense", "hybrid"):
        before = v1["modes"][mode]["metrics"]
        after = v2["modes"][mode]["metrics"]
        comparison[mode] = {
            key: round(after[key] - before[key], 4)
            for key in ("recallAt1", "recallAt3", "recallAt5", "mrr")
        }
    return comparison


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "experimentGate": report["experimentGate"],
        "promotionGate": report["promotionGate"],
        "frozenGold": report["frozenGold"],
        "corpus": report["corpus"],
        "isolation": {
            "activeIndexUntouched": report["isolation"]["activeIndexUntouched"],
            "runtimeConfigurationChanged": report["isolation"]["runtimeConfigurationChanged"],
            "candidateIndexDirectory": report["isolation"]["candidateIndexDirectory"],
        },
        "legacyV1": {
            "provider": report["profiles"]["legacyV1"]["provider"],
            "queryBatchEmbeddingMs": report["profiles"]["legacyV1"]["queryBatchEmbeddingMs"],
            "metrics": {mode: value["metrics"] for mode, value in report["profiles"]["legacyV1"]["modes"].items()},
        },
        "officialV2": {
            "provider": report["profiles"]["officialV2"]["provider"],
            "queryBatchEmbeddingMs": report["profiles"]["officialV2"]["queryBatchEmbeddingMs"],
            "metrics": {mode: value["metrics"] for mode, value in report["profiles"]["officialV2"]["modes"].items()},
        },
        "comparison": report["comparison"],
        "candidateIndex": {
            key: report["candidateIndex"].get(key)
            for key in ("status", "vectorCount", "chunkCount", "dimension", "contentRootHash")
        },
    }


def safe_provider_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "modelPath"}


def safe_index_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    safe = {
        key: value
        for key, value in manifest.items()
        if key not in {"indexPath", "metaPath", "rows"}
    }
    if isinstance(safe.get("provider"), dict):
        safe["provider"] = safe_provider_metadata(safe["provider"])
    return safe


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return "external-candidate-directory"


def active_index_hashes(index_dir: Path) -> dict[str, str]:
    return {
        name: sha256_file(index_dir / name)
        for name in (DEFAULT_FAISS_NAME, DEFAULT_FAISS_META_NAME)
    }


def content_root_hash(chunks: list[Any]) -> str:
    from app.rag.document_contract import stable_hash

    return stable_hash({"chunks": [chunk.contentHash for chunk in chunks]})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def release_provider(provider: Any) -> None:
    provider._model = None
    provider._tokenizer = None
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
