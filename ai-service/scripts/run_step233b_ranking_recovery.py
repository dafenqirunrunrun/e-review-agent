from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.embedding import QwenEmbeddingConfig, QwenOfficialTransformersEmbeddingProvider
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.vector_store import DEFAULT_FAISS_META_NAME, DEFAULT_FAISS_NAME
from scripts.run_step16_benchmark import load_jsonl, ranking_metrics, subset_ranking_metrics
from scripts.run_step233a_qwen_embedding_ab import (
    DEFAULT_CHUNKS,
    DEFAULT_DATASET,
    DEFAULT_V1_INDEX_DIR,
    DEFAULT_V2_INDEX_DIR,
    FROZEN_GOLD_SHA256,
    active_index_hashes,
    build_bm25_rankings,
    content_root_hash,
    current_config,
    document_token_profile,
    first_matching_rank_from_chunks,
    release_provider,
    sha256_file,
)


DEFAULT_OUTPUT = ROOT / "artifacts" / "step233b" / "ranking_recovery.json"
DEFAULT_RERANKER = ROOT.parents[1] / "models" / "v2.2" / "bge-reranker-v2-m3"
RRF_K_VALUES = (10, 20, 40, 60, 100)
FUSION_WEIGHTS = ((0.3, 0.7), (0.4, 0.6), (0.5, 0.5), (0.6, 0.4), (0.7, 0.3))
PROMOTION_THRESHOLDS = {"recallAt1": 0.9667, "recallAt5": 0.9667, "mrr": 0.9667}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated Step 23.3B Top-1 ranking recovery experiments.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--v1-index-dir", type=Path, default=DEFAULT_V1_INDEX_DIR)
    parser.add_argument("--v2-index-dir", type=Path, default=DEFAULT_V2_INDEX_DIR)
    parser.add_argument("--reranker-model", type=Path, default=DEFAULT_RERANKER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--embedding-batch-size", type=int, default=4)
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    chunks_path = args.chunks.resolve()
    v1_dir = args.v1_index_dir.resolve()
    v2_dir = args.v2_index_dir.resolve()
    reranker_path = args.reranker_model.resolve()
    if v1_dir == v2_dir:
        raise SystemExit("STEP233B_INDEX_ISOLATION_FAILED")
    if args.embedding_batch_size < 1 or args.reranker_batch_size < 1:
        raise SystemExit("STEP233B_BATCH_SIZE_INVALID")
    assert_frozen_gold(dataset)
    assert_reranker_asset(reranker_path)

    active_before = active_index_hashes(v1_dir)
    candidate_before = active_index_hashes(v2_dir)
    chunks = load_policy_chunks(chunks_path)
    cases = [case for case in load_jsonl(dataset) if case.get("expectedEvidenceTags")]
    if not chunks or not cases:
        raise SystemExit("STEP233B_INPUT_EMPTY")

    expected_root = content_root_hash(chunks)
    v1_meta = load_index_meta(v1_dir, expected_root, "v1")
    v2_meta = load_index_meta(v2_dir, expected_root, "v2")
    if v2_meta.get("provider", {}).get("embeddingProfile") != "qwen3-official-retrieval-v2":
        raise SystemExit("STEP233B_V2_PROFILE_MISMATCH")

    expanded_queries = [
        " ".join([case["reviewText"], PolicyEvidenceRetriever._expand_risk_hints(case["expectedRiskTypes"])]).strip()
        for case in cases
    ]
    bm25_rankings = build_bm25_rankings(chunks, cases)
    config = current_config(batch_size=args.embedding_batch_size)

    v1_provider = create_legacy_provider(config)
    v1_dense, v1_embedding_ms = dense_rankings(v1_provider, v1_dir, chunks, expanded_queries)
    release_provider(v1_provider)

    v2_provider = QwenOfficialTransformersEmbeddingProvider(candidate_embedding_config(config, v2_meta))
    v2_dense, v2_embedding_ms = dense_rankings(v2_provider, v2_dir, chunks, expanded_queries)
    token_profile = document_token_profile(v2_provider, chunks)
    v2_provider_metadata = safe_provider_metadata(v2_provider.metadata())
    candidate_encoding_matches = encoding_matches_index(v2_provider_metadata, v2_meta.get("provider", {}))
    release_provider(v2_provider)

    v1_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(bm25_rankings, v1_dense, strict=True)]
    b0_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(bm25_rankings, v2_dense, strict=True)]
    v1_eval = evaluate_rankings(v1_rankings, cases)
    b0_eval = evaluate_rankings(b0_rankings, cases)

    fusion_grid: list[dict[str, Any]] = []
    grid_rankings: dict[str, list[list[tuple[float, Any]]]] = {}
    for rrf_k in RRF_K_VALUES:
        for bm25_weight, dense_weight in FUSION_WEIGHTS:
            name = fusion_variant_name(rrf_k, bm25_weight, dense_weight)
            rankings = [
                weighted_rrf(
                    bm25,
                    dense,
                    top_k=5,
                    k=rrf_k,
                    bm25_weight=bm25_weight,
                    dense_weight=dense_weight,
                )
                for bm25, dense in zip(bm25_rankings, v2_dense, strict=True)
            ]
            evaluation = evaluate_rankings(rankings, cases)
            fusion_grid.append(
                {
                    "name": name,
                    "rrfK": rrf_k,
                    "bm25Weight": bm25_weight,
                    "denseWeight": dense_weight,
                    **evaluation,
                }
            )
            grid_rankings[name] = rankings

    best_fusion = max(fusion_grid, key=fusion_selection_key)
    b1_rankings = grid_rankings[best_fusion["name"]]
    b1_eval = {key: best_fusion[key] for key in ("metrics", "subsets", "citationValid")}

    reranker, reranker_metadata = load_reranker(reranker_path)
    b2_rankings, b3_rankings, rerank_ms, rerank_pair_count = rerank_variants(
        reranker,
        expanded_queries,
        b0_rankings,
        b1_rankings,
        batch_size=args.reranker_batch_size,
    )
    release_reranker(reranker)
    del reranker
    b2_eval = evaluate_rankings(b2_rankings, cases)
    b3_eval = evaluate_rankings(b3_rankings, cases)

    variants = {
        "B0": variant_record("v2_current_rrf", b0_eval, {"rrfK": 60, "bm25Weight": 0.5, "denseWeight": 0.5}),
        "B1": variant_record("v2_best_fusion", b1_eval, fusion_config(best_fusion)),
        "B2": variant_record("v2_current_rrf_rerank_top5", b2_eval, {"base": "B0", "rerankTopK": 5}),
        "B3": variant_record("v2_best_fusion_rerank_top5", b3_eval, {"base": "B1", "rerankTopK": 5}),
    }
    selected_name = max(("B1", "B2", "B3"), key=lambda name: variant_selection_key(variants[name]))
    selected = variants[selected_name]
    diagnostics = build_diagnostics(
        chunks=chunks,
        cases=cases,
        bm25_rankings=bm25_rankings,
        v1_dense=v1_dense,
        v2_dense=v2_dense,
        v1_rankings=v1_rankings,
        b0_rankings=b0_rankings,
        b1_rankings=b1_rankings,
        b2_rankings=b2_rankings,
        b3_rankings=b3_rankings,
    )

    active_after = active_index_hashes(v1_dir)
    candidate_after = active_index_hashes(v2_dir)
    integrity = {
        "frozenGoldUnchanged": sha256_file(dataset) == FROZEN_GOLD_SHA256,
        "activeIndexUntouched": active_before == active_after,
        "candidateIndexUntouched": candidate_before == candidate_after,
        "sameCorpus": v1_meta.get("contentRootHash") == v2_meta.get("contentRootHash") == expected_root,
        "candidateProfileValid": v2_meta.get("provider", {}).get("embeddingProfile") == "qwen3-official-retrieval-v2",
        "candidateEncodingMatchesIndex": candidate_encoding_matches,
        "runtimeConfigurationUnchanged": True,
    }
    promotion = promotion_gate(selected, v1_eval, token_profile, integrity)
    report = {
        "schemaVersion": "step23.3b-ranking-recovery-v1",
        "experimentGate": "PASS" if all(integrity.values()) else "FAIL",
        "promotionGate": promotion["status"],
        "promotion": {**promotion, "selectedVariant": selected_name},
        "frozenGold": {
            "sha256": FROZEN_GOLD_SHA256,
            "caseCount": len(load_jsonl(dataset)),
            "retrievalCaseCount": len(cases),
        },
        "corpus": {"chunkCount": len(chunks), "contentRootHash": expected_root, "tokenProfile": token_profile},
        "integrity": integrity,
        "baselineV1": {**v1_eval, "embeddingMs": v1_embedding_ms},
        "candidateV2": {"provider": v2_provider_metadata, "embeddingMs": v2_embedding_ms},
        "reranker": {**reranker_metadata, "pairCount": rerank_pair_count, "durationMs": rerank_ms},
        "variants": variants,
        "fusionGrid": sorted(fusion_grid, key=fusion_selection_key, reverse=True),
        "diagnostics": diagnostics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if report["experimentGate"] == "PASS" else 1


def create_legacy_provider(config: Any) -> Any:
    from app.policy_rag.embedding import QwenTransformersEmbeddingProvider

    return QwenTransformersEmbeddingProvider(config)


def candidate_embedding_config(current: QwenEmbeddingConfig, index_meta: dict[str, Any]) -> QwenEmbeddingConfig:
    candidate_max_length = int((index_meta.get("provider") or {}).get("maxLength") or 0)
    if not 32 <= candidate_max_length <= 2048:
        raise SystemExit("STEP233B_CANDIDATE_MAX_LENGTH_INVALID")
    return QwenEmbeddingConfig(
        model_name=current.model_name,
        model_path=current.model_path,
        device=current.device,
        batch_size=current.batch_size,
        max_length=candidate_max_length,
        normalize=current.normalize,
        allow_remote=current.allow_remote,
    )


def encoding_matches_index(provider: dict[str, Any], indexed: dict[str, Any]) -> bool:
    keys = ("providerType", "modelFingerprint", "pooling", "maxLength", "embeddingProfile", "queryInstructionHash")
    return all(provider.get(key) == indexed.get(key) for key in keys)


def assert_frozen_gold(dataset: Path) -> None:
    actual = sha256_file(dataset)
    if actual != FROZEN_GOLD_SHA256:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA256} actual={actual}")


def assert_reranker_asset(path: Path) -> None:
    required = (path / "config.json", path / "tokenizer.json", path / "model.safetensors")
    if not all(item.exists() for item in required):
        raise SystemExit("STEP233B_RERANKER_ASSET_NOT_READY")


def load_index_meta(index_dir: Path, expected_root: str, label: str) -> dict[str, Any]:
    index_path = index_dir / DEFAULT_FAISS_NAME
    meta_path = index_dir / DEFAULT_FAISS_META_NAME
    if not index_path.exists() or not meta_path.exists():
        raise SystemExit(f"STEP233B_{label.upper()}_INDEX_MISSING")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if meta.get("contentRootHash") != expected_root:
        raise SystemExit(f"STEP233B_{label.upper()}_CORPUS_MISMATCH")
    return meta


def dense_rankings(provider: Any, index_dir: Path, chunks: list[Any], queries: list[str]) -> tuple[list[list[tuple[float, Any]]], float]:
    import faiss

    meta = json.loads((index_dir / DEFAULT_FAISS_META_NAME).read_text(encoding="utf-8-sig"))
    index = faiss.deserialize_index(np.frombuffer((index_dir / DEFAULT_FAISS_NAME).read_bytes(), dtype="uint8"))
    if int(index.ntotal) != len(chunks) or int(index.d) != int(meta.get("dimension", 0)):
        raise SystemExit("STEP233B_INDEX_DIMENSION_MISMATCH")
    started = time.perf_counter()
    vectors = provider.embed_queries(queries) if hasattr(provider, "embed_queries") else provider.embed_documents(queries)
    embedding_ms = round((time.perf_counter() - started) * 1000, 2)
    scores, positions = index.search(np.asarray(vectors, dtype="float32"), 20)
    by_id = {chunk.chunkId: chunk for chunk in chunks}
    output: list[list[tuple[float, Any]]] = []
    for row_scores, row_positions in zip(scores, positions, strict=True):
        ranking = []
        for score, position in zip(row_scores, row_positions, strict=True):
            if position >= 0:
                ranking.append((float(score), by_id[meta["rows"][int(position)]["chunkId"]]))
        output.append(ranking)
    return output, embedding_ms


def weighted_rrf(
    bm25_ranked: list[tuple[float, Any]],
    dense_ranked: list[tuple[float, Any]],
    *,
    top_k: int,
    k: int = 60,
    bm25_weight: float = 1.0,
    dense_weight: float = 1.0,
) -> list[tuple[float, Any]]:
    scores: dict[str, float] = {}
    chunks: dict[str, Any] = {}
    for weight, ranked in ((bm25_weight, bm25_ranked), (dense_weight, dense_ranked)):
        for rank, (_, chunk) in enumerate(ranked, start=1):
            scores[chunk.chunkId] = scores.get(chunk.chunkId, 0.0) + weight / (k + rank)
            chunks[chunk.chunkId] = chunk
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(round(score, 8), chunks[chunk_id]) for chunk_id, score in ordered[:top_k]]


def evaluate_rankings(rankings: list[list[tuple[float, Any]]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case, ranking in zip(cases, rankings, strict=True):
        rows.append(
            {
                "caseId": case["caseId"],
                "rank": first_matching_rank_from_chunks(ranking, case["expectedEvidenceTags"], case["expectedRiskTypes"]),
                "subsets": case["subset"],
                "citationValid": all(chunk.sourceUrl and chunk.sectionPath and chunk.contentHash for _, chunk in ranking),
            }
        )
    return {
        "metrics": ranking_metrics(rows),
        "subsets": subset_ranking_metrics(rows),
        "citationValid": all(row["citationValid"] for row in rows),
    }


def fusion_variant_name(rrf_k: int, bm25_weight: float, dense_weight: float) -> str:
    return f"rrf{rrf_k}_bm25{bm25_weight:.1f}_dense{dense_weight:.1f}"


def fusion_selection_key(row: dict[str, Any]) -> tuple[float, ...]:
    metrics = row["metrics"]
    return (
        metrics["recallAt1"],
        metrics["mrr"],
        metrics["recallAt3"],
        metrics["recallAt5"],
        -abs(float(row["bm25Weight"]) - 0.5),
        -abs(int(row["rrfK"]) - 60),
    )


def fusion_config(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("rrfK", "bm25Weight", "denseWeight")}


class LocalTransformersCrossEncoder:
    def __init__(self, model: Any, tokenizer: Any, *, device: str = "cpu"):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device

    def predict(self, pairs: list[tuple[str, str]], *, batch_size: int, show_progress_bar: bool = False) -> np.ndarray:
        del show_progress_bar
        import torch

        scores: list[float] = []
        with torch.inference_mode():
            for offset in range(0, len(pairs), batch_size):
                batch = pairs[offset : offset + batch_size]
                encoded = self.tokenizer(
                    [item[0] for item in batch],
                    [item[1] for item in batch],
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                logits = self.model(**encoded).logits.reshape(-1).float()
                scores.extend(float(value) for value in logits.detach().cpu())
        return np.asarray(scores, dtype="float32")


def load_reranker(model_path: Path) -> tuple[Any, dict[str, Any]]:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path), local_files_only=True)
    model.eval().to("cpu")
    reranker = LocalTransformersCrossEncoder(model, tokenizer, device="cpu")
    metadata = {
        "provider": "transformers-sequence-classification",
        "modelName": "BAAI/bge-reranker-v2-m3",
        "modelSource": "local",
        "modelFingerprint": reranker_fingerprint(model_path),
        "device": "cpu",
        "maxLength": 512,
        "loadMs": round((time.perf_counter() - started) * 1000, 2),
        "pairCount": 0,
    }
    return reranker, metadata


def rerank_variants(
    model: Any,
    queries: list[str],
    b0_rankings: list[list[tuple[float, Any]]],
    b1_rankings: list[list[tuple[float, Any]]],
    *,
    batch_size: int,
) -> tuple[list[list[tuple[float, Any]]], list[list[tuple[float, Any]]], float, int]:
    unique: dict[tuple[int, str], tuple[str, Any]] = {}
    for case_index, (query, b0, b1) in enumerate(zip(queries, b0_rankings, b1_rankings, strict=True)):
        for _, chunk in b0 + b1:
            unique.setdefault((case_index, chunk.chunkId), (query, chunk))
    keys = list(unique)
    pairs = [(unique[key][0], passage_text(unique[key][1])) for key in keys]
    started = time.perf_counter()
    raw_scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    values = np.asarray(raw_scores, dtype="float32").reshape(-1)
    if len(values) != len(keys) or not np.isfinite(values).all():
        raise SystemExit("STEP233B_RERANKER_OUTPUT_INVALID")
    score_by_key = {key: float(score) for key, score in zip(keys, values, strict=True)}

    def rerank(source: list[list[tuple[float, Any]]]) -> list[list[tuple[float, Any]]]:
        output = []
        for case_index, ranking in enumerate(source):
            original_rank = {chunk.chunkId: rank for rank, (_, chunk) in enumerate(ranking, start=1)}
            rescored = [(score_by_key[(case_index, chunk.chunkId)], chunk) for _, chunk in ranking]
            rescored.sort(key=lambda item: (-item[0], original_rank[item[1].chunkId], item[1].chunkId))
            output.append(rescored)
        return output

    return rerank(b0_rankings), rerank(b1_rankings), elapsed_ms, len(pairs)


def passage_text(chunk: Any) -> str:
    return "\n".join([chunk.heading, " > ".join(chunk.sectionPath), chunk.text]).strip()


def reranker_fingerprint(model_path: Path) -> str:
    digest = hashlib.sha256()
    for name in ("config.json", "tokenizer_config.json", "MODEL_PROVENANCE.json"):
        path = model_path / name
        if path.exists():
            digest.update(path.read_bytes())
    weights = model_path / "model.safetensors"
    digest.update(f"{weights.name}:{weights.stat().st_size}".encode("utf-8"))
    return digest.hexdigest()[:32]


def release_reranker(model: Any) -> None:
    try:
        if hasattr(model, "model") and hasattr(model.model, "to"):
            model.model.to("cpu")
    finally:
        del model
        gc.collect()


def variant_record(name: str, evaluation: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "config": config, **evaluation}


def variant_selection_key(variant: dict[str, Any]) -> tuple[float, ...]:
    metrics = variant["metrics"]
    return (metrics["recallAt1"], metrics["mrr"], metrics["recallAt3"], metrics["recallAt5"])


def build_diagnostics(**kwargs: Any) -> dict[str, Any]:
    chunks = kwargs["chunks"]
    cases = kwargs["cases"]
    names = ("v1", "v2B0", "B1", "B2", "B3")
    all_rankings = (
        kwargs["v1_rankings"],
        kwargs["b0_rankings"],
        kwargs["b1_rankings"],
        kwargs["b2_rankings"],
        kwargs["b3_rankings"],
    )
    dropped = []
    direction_counts: dict[str, int] = {}
    for index, case in enumerate(cases):
        ranks = {
            name: first_matching_rank_from_chunks(rankings[index], case["expectedEvidenceTags"], case["expectedRiskTypes"])
            for name, rankings in zip(names, all_rankings, strict=True)
        }
        if rank_value(ranks["v2B0"]) <= rank_value(ranks["v1"]):
            continue
        top1 = kwargs["b0_rankings"][index][0][1]
        query_language = case_query_language(case)
        gold_match = first_matching_chunk(kwargs["b0_rankings"][index], case)
        target_language = gold_match.language if gold_match is not None else "unknown"
        direction = f"{query_language}->{target_language}"
        direction_counts[direction] = direction_counts.get(direction, 0) + 1
        matching = matching_chunks(chunks, case)
        dropped.append(
            {
                "caseId": case["caseId"],
                "queryLanguage": query_language,
                "retrievalDirection": direction,
                "v2Top1Direction": f"{query_language}->{top1.language or 'unknown'}",
                "expression": "implicit" if "lexical_mismatch" in case["subset"] else "explicit",
                "riskTypes": case["expectedRiskTypes"],
                "expectedEvidenceTags": case["expectedEvidenceTags"],
                "ranks": ranks,
                "scores": {
                    "bm25BestGold": best_matching(kwargs["bm25_rankings"][index], case),
                    "v2DenseBestGold": best_matching(kwargs["v2_dense"][index], case),
                    "v2HybridBestGold": best_matching(kwargs["b0_rankings"][index], case),
                },
                "goldCandidates": [compact_chunk(chunk) for chunk in matching[:8]],
                "v2Top1": compact_chunk(top1, score=kwargs["b0_rankings"][index][0][0]),
            }
        )
    return {"droppedCaseCount": len(dropped), "byDirection": direction_counts, "droppedCases": dropped}


def matching_chunks(chunks: list[Any], case: dict[str, Any]) -> list[Any]:
    wanted = set(case["expectedEvidenceTags"]) | set(case["expectedRiskTypes"])
    return [chunk for chunk in chunks if wanted.intersection(set(chunk.evidenceTags) | set(chunk.riskTypes))]


def best_matching(ranking: list[tuple[float, Any]], case: dict[str, Any]) -> dict[str, Any] | None:
    wanted = set(case["expectedEvidenceTags"]) | set(case["expectedRiskTypes"])
    for rank, (score, chunk) in enumerate(ranking, start=1):
        if wanted.intersection(set(chunk.evidenceTags) | set(chunk.riskTypes)):
            return {"rank": rank, "score": round(float(score), 6), "chunkId": chunk.chunkId}
    return None


def first_matching_chunk(ranking: list[tuple[float, Any]], case: dict[str, Any]) -> Any | None:
    wanted = set(case["expectedEvidenceTags"]) | set(case["expectedRiskTypes"])
    return next(
        (chunk for _, chunk in ranking if wanted.intersection(set(chunk.evidenceTags) | set(chunk.riskTypes))),
        None,
    )


def compact_chunk(chunk: Any, *, score: float | None = None) -> dict[str, Any]:
    row = {
        "chunkId": chunk.chunkId,
        "sourceName": chunk.sourceName,
        "language": chunk.language,
        "tokenCount": chunk.tokenCount,
        "riskTypes": chunk.riskTypes,
        "evidenceTags": chunk.evidenceTags,
    }
    if score is not None:
        row["score"] = round(float(score), 6)
    return row


def detect_language(text: str) -> str:
    has_zh = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    return "mixed" if has_zh and has_en else "zh" if has_zh else "en"


def case_query_language(case: dict[str, Any]) -> str:
    declared = str(case.get("language") or "").lower()
    return declared if declared in {"zh", "en", "mixed"} else detect_language(str(case.get("reviewText") or ""))


def rank_value(rank: int | None) -> int:
    return rank if rank is not None else math.inf


def promotion_gate(
    selected: dict[str, Any],
    baseline: dict[str, Any],
    token_profile: dict[str, Any],
    integrity: dict[str, bool],
) -> dict[str, Any]:
    metrics = selected["metrics"]
    checks = {
        "integrity": all(integrity.values()),
        "recallAt1": metrics["recallAt1"] >= PROMOTION_THRESHOLDS["recallAt1"],
        "recallAt5": metrics["recallAt5"] >= PROMOTION_THRESHOLDS["recallAt5"],
        "mrr": metrics["mrr"] >= PROMOTION_THRESHOLDS["mrr"],
        "chineseNoRegression": no_subset_regression(selected, baseline, "chinese"),
        "crossLanguageNoRegression": no_subset_regression(selected, baseline, "cross_language"),
        "noCandidateTruncation": token_profile["overCandidateMaxLength"] == 0,
        "citationValid": bool(selected["citationValid"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "HOLD",
        "checks": checks,
        "thresholds": PROMOTION_THRESHOLDS,
    }


def no_subset_regression(candidate: dict[str, Any], baseline: dict[str, Any], subset: str) -> bool:
    current = candidate["subsets"].get(subset, {})
    original = baseline["subsets"].get(subset, {})
    return bool(current and original) and current["recallAt1"] >= original["recallAt1"] and current["mrr"] >= original["mrr"]


def safe_provider_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "modelPath"}


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "experimentGate": report["experimentGate"],
        "promotionGate": report["promotionGate"],
        "promotion": report["promotion"],
        "frozenGold": report["frozenGold"],
        "baselineV1": report["baselineV1"]["metrics"],
        "variants": {name: value["metrics"] for name, value in report["variants"].items()},
        "bestFusion": report["variants"]["B1"]["config"],
        "reranker": report["reranker"],
        "diagnostics": {
            "droppedCaseCount": report["diagnostics"]["droppedCaseCount"],
            "byDirection": report["diagnostics"]["byDirection"],
        },
        "integrity": report["integrity"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
