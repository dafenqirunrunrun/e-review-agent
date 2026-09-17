from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.core.config import PolicyRagSettings, settings
from app.policy_rag.models import PolicyChunk, PolicySearchResult
from app.rag_v2.reranker import NeuralReranker


@dataclass(frozen=True)
class PolicyRerankOutcome:
    evidence: list[PolicySearchResult]
    metadata: dict[str, object]
    ranked_candidates: list[PolicySearchResult] = field(default_factory=list)


class PolicyEvidenceReranker:
    """Optional local BGE reranker for the strict policy-evidence path."""

    _cache_lock = threading.Lock()
    _model_cache: dict[str, NeuralReranker] = {}
    _semaphore_cache: dict[str, threading.BoundedSemaphore] = {}
    _fingerprint_cache: dict[str, str] = {}

    def __init__(
        self,
        config: PolicyRagSettings | None = None,
        *,
        model_factory: Callable[[Path, str, int], object] | None = None,
    ):
        self.config = config or settings.policy_rag
        self._model_factory = model_factory
        self.last_metadata = self._base_metadata()

    @property
    def enabled(self) -> bool:
        return bool(self.config.reranker_enabled)

    @property
    def candidate_k(self) -> int:
        return max(self.config.reranker_final_k, self.config.reranker_candidate_k)

    @property
    def final_k(self) -> int:
        return min(self.config.reranker_final_k, self.candidate_k)

    def rerank(
        self,
        query: str,
        candidates: list[PolicySearchResult],
        *,
        chunk_resolver: Callable[[str], PolicyChunk | None],
        candidate_limit: int | None = None,
    ) -> PolicyRerankOutcome:
        effective_candidate_k = self._effective_candidate_k(candidate_limit)
        original_candidates = self._renumber(candidates[:effective_candidate_k])
        original = original_candidates[: self.final_k]
        metadata = self._base_metadata(candidate_count=len(candidates), candidate_k=effective_candidate_k)
        if not self.enabled:
            metadata.update({"status": "disabled", "effectiveMode": "rrf", "outputCount": len(original)})
            return self._outcome(original, metadata, ranked_candidates=original_candidates)
        if len(candidates) < 2:
            metadata.update({"status": "skipped", "effectiveMode": "rrf", "outputCount": len(original)})
            return self._outcome(original, metadata, ranked_candidates=original_candidates)

        model_path = Path(self.config.reranker_model_path)
        if not self.config.reranker_model_path or not model_path.is_dir():
            return self._fallback(original_candidates, metadata, "RERANKER_MODEL_NOT_AVAILABLE")

        selected = candidates[:effective_candidate_k]
        rows: list[dict[str, object]] = []
        try:
            for rank, evidence in enumerate(selected, start=1):
                chunk = chunk_resolver(evidence.chunkId)
                if chunk is None:
                    return self._fallback(original_candidates, metadata, "RERANKER_CHUNK_NOT_AVAILABLE")
                rows.append(
                    {
                        "chunk_id": evidence.chunkId,
                        "scenario": self._passage_text(chunk),
                        "original_rank": rank,
                    }
                )
        except Exception:
            return self._fallback(original_candidates, metadata, "RERANKER_CHUNK_NOT_AVAILABLE")

        semaphore = self._shared_semaphore(model_path)
        wait_started = time.perf_counter()
        acquired = semaphore.acquire(timeout=self.config.reranker_queue_timeout_ms / 1000.0)
        queue_wait_ms = round((time.perf_counter() - wait_started) * 1000, 2)
        metadata["queueWaitMs"] = queue_wait_ms
        if not acquired:
            return self._fallback(original_candidates, metadata, "RERANKER_QUEUE_TIMEOUT")

        started = time.perf_counter()
        try:
            model = self._model(model_path)
            ranked, model_ms = model.rerank({"query_text": query}, rows)
            total_ms = round((time.perf_counter() - started) * 1000, 2)
            if len(ranked) != len(rows):
                return self._fallback(original_candidates, metadata, "RERANKER_OUTPUT_INVALID", duration_ms=total_ms)
            score_by_id: dict[str, float] = {}
            ordered_ids: list[str] = []
            for row in ranked:
                chunk_id = str(row.get("chunk_id", ""))
                score = float(row.get("rerank_score", float("nan")))
                if not chunk_id or not math.isfinite(score) or chunk_id in score_by_id:
                    return self._fallback(original_candidates, metadata, "RERANKER_OUTPUT_INVALID", duration_ms=total_ms)
                ordered_ids.append(chunk_id)
                score_by_id[chunk_id] = score
            evidence_by_id = {item.chunkId: item for item in selected}
            if any(chunk_id not in evidence_by_id for chunk_id in ordered_ids):
                return self._fallback(original_candidates, metadata, "RERANKER_OUTPUT_INVALID", duration_ms=total_ms)
            ranked_candidates = self._renumber([evidence_by_id[chunk_id] for chunk_id in ordered_ids])
            reranked = ranked_candidates[: self.final_k]
            metadata.update(
                {
                    "status": "ready",
                    "effectiveMode": "hybrid_bge_reranked",
                    "fallbackUsed": False,
                    "outputCount": len(reranked),
                    "rankedCandidateCount": len(ranked_candidates),
                    "durationMs": total_ms,
                    "modelComputeMs": round(float(model_ms), 2),
                    "sloExceeded": total_ms > self.config.reranker_latency_budget_ms,
                    "topScores": [
                        {"chunkId": chunk_id, "score": round(score_by_id[chunk_id], 6)}
                        for chunk_id in ordered_ids[: self.final_k]
                    ],
                }
            )
            return self._outcome(reranked, metadata, ranked_candidates=ranked_candidates)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            return self._fallback(original_candidates, metadata, self._safe_error_code(exc), duration_ms=duration_ms)
        finally:
            semaphore.release()

    def readiness(self) -> dict[str, object]:
        path = Path(self.config.reranker_model_path) if self.config.reranker_model_path else None
        available = bool(
            path
            and NeuralReranker(
                path,
                device=self.config.reranker_device,
                batch_size=self.config.reranker_batch_size,
            ).available
        )
        status = "disabled" if not self.enabled else ("ready" if available else "degraded")
        loaded = bool(path and self._cache_key(path) in self._model_cache)
        return {
            **self._base_metadata(),
            "status": status,
            "loaded": loaded,
            "modelPath": "configured" if available else ("missing" if path else "not_configured"),
            "fallbackMode": "rrf",
        }

    def warmup(self) -> dict[str, object]:
        if not self.enabled:
            return {"status": "skipped", "reason": "POLICY_RERANKER_DISABLED"}
        if not self.config.reranker_warmup_enabled:
            return {"status": "skipped", "reason": "POLICY_RERANKER_WARMUP_DISABLED"}
        started = time.perf_counter()
        try:
            model_path = Path(self.config.reranker_model_path)
            model = self._model(model_path)
            query = "五星好评截图返现是否构成虚假评价或评分操纵"
            passage = (
                "平台禁止以现金、返现、赠品或其他利益换取消费者发布指定倾向的评价，"
                "也禁止要求五星截图后发放奖励。此类行为可能构成有偿评价与评分操纵。"
            )
            _, compute_ms = model.rerank(
                {"query_text": query},
                [
                    {
                        "chunk_id": f"warmup-{index}",
                        "scenario": f"政策规范 > 评价真实性 > 条款 {index}\n{passage}",
                        "original_rank": index,
                    }
                    for index in range(1, self.candidate_k + 1)
                ],
            )
            return {
                "status": "ready",
                "latencyMs": round((time.perf_counter() - started) * 1000, 2),
                "modelComputeMs": round(float(compute_ms), 2),
                "model": self.config.reranker_model,
                "modelFingerprint": self._fingerprint(),
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "latencyMs": round((time.perf_counter() - started) * 1000, 2),
                "reason": self._safe_error_code(exc),
            }

    def observability_metadata(self) -> dict[str, object]:
        ready = self.readiness()
        return {
            "policyRerankerEnabled": self.enabled,
            "policyRerankerStatus": ready["status"],
            "policyRerankerModel": self.config.reranker_model,
            "policyRerankerFingerprint": ready["modelFingerprint"],
        }

    def _model(self, model_path: Path) -> object:
        if self._model_factory is not None:
            return self._model_factory(model_path, self.config.reranker_device, self.config.reranker_batch_size)
        key = self._cache_key(model_path)
        with self._cache_lock:
            model = self._model_cache.get(key)
            if model is None:
                if self.config.reranker_device == "cpu" and self.config.cpu_threads > 0:
                    import torch

                    torch.set_num_threads(self.config.cpu_threads)
                model = NeuralReranker(
                    model_path,
                    device=self.config.reranker_device,
                    batch_size=self.config.reranker_batch_size,
                )
                if not model.available:
                    raise RuntimeError("RERANKER_MODEL_NOT_AVAILABLE")
                self._model_cache[key] = model
            return model

    def _shared_semaphore(self, model_path: Path) -> threading.BoundedSemaphore:
        key = f"{self._cache_key(model_path)}:{self.config.reranker_max_concurrency}"
        with self._cache_lock:
            semaphore = self._semaphore_cache.get(key)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(self.config.reranker_max_concurrency)
                self._semaphore_cache[key] = semaphore
            return semaphore

    def _cache_key(self, model_path: Path) -> str:
        return "|".join(
            [
                str(model_path.resolve()),
                self.config.reranker_device,
                str(self.config.reranker_batch_size),
            ]
        )

    def _base_metadata(self, *, candidate_count: int = 0, candidate_k: int | None = None) -> dict[str, object]:
        effective_candidate_k = self.candidate_k if candidate_k is None else candidate_k
        return {
            "requestedMode": "hybrid_bge_reranked" if self.enabled else "rrf",
            "effectiveMode": "rrf",
            "model": self.config.reranker_model,
            "modelFingerprint": self._fingerprint(),
            "candidateK": effective_candidate_k,
            "finalK": self.final_k,
            "candidateCount": candidate_count,
            "outputCount": 0,
            "rankedCandidateCount": 0,
            "durationMs": 0.0,
            "queueWaitMs": 0.0,
            "fallbackUsed": False,
            "fallbackReason": "",
            "sloMs": self.config.reranker_latency_budget_ms,
            "sloExceeded": False,
        }

    def _effective_candidate_k(self, candidate_limit: int | None) -> int:
        if candidate_limit is None:
            return self.candidate_k
        # The caller may raise the small default budget for a difficult review,
        # but this low-level component never accepts an unbounded rerank batch.
        return min(20, max(2, int(candidate_limit)))

    def _fingerprint(self) -> str:
        if not self.config.reranker_model_path:
            return ""
        model_path = Path(self.config.reranker_model_path)
        if not model_path.is_dir():
            return ""
        cache_key = str(model_path.resolve())
        cached = self._fingerprint_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            digest = hashlib.sha256()
            for name in ("config.json", "tokenizer_config.json", "MODEL_PROVENANCE.json"):
                path = model_path / name
                if path.exists():
                    digest.update(path.read_bytes())
            for name in ("model.safetensors", "pytorch_model.bin"):
                weights = model_path / name
                if weights.exists():
                    digest.update(f"{weights.name}:{weights.stat().st_size}".encode("utf-8"))
                    break
            value = digest.hexdigest()[:32]
            self._fingerprint_cache[cache_key] = value
            return value
        except OSError:
            return ""

    @staticmethod
    def _passage_text(chunk: PolicyChunk) -> str:
        return "\n".join([chunk.heading, " > ".join(chunk.sectionPath), chunk.text]).strip()

    @staticmethod
    def _renumber(items: list[PolicySearchResult]) -> list[PolicySearchResult]:
        return [item.model_copy(update={"evidenceId": f"E{rank}"}) for rank, item in enumerate(items, start=1)]

    def _fallback(
        self,
        ranked_candidates: list[PolicySearchResult],
        metadata: dict[str, object],
        reason: str,
        *,
        duration_ms: float = 0.0,
    ) -> PolicyRerankOutcome:
        metadata.update(
            {
                "status": "fallback",
                "effectiveMode": "rrf_fallback",
                "fallbackUsed": True,
                "fallbackReason": reason,
                "outputCount": min(len(ranked_candidates), self.final_k),
                "rankedCandidateCount": len(ranked_candidates),
                "durationMs": duration_ms,
                "sloExceeded": duration_ms > self.config.reranker_latency_budget_ms,
            }
        )
        return self._outcome(ranked_candidates[: self.final_k], metadata, ranked_candidates=ranked_candidates)

    def _outcome(
        self,
        evidence: list[PolicySearchResult],
        metadata: dict[str, object],
        *,
        ranked_candidates: list[PolicySearchResult] | None = None,
    ) -> PolicyRerankOutcome:
        self.last_metadata = metadata
        return PolicyRerankOutcome(evidence=evidence, metadata=metadata, ranked_candidates=ranked_candidates or evidence)

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        value = str(exc).upper()
        if "NOT_AVAILABLE" in value:
            return "RERANKER_MODEL_NOT_AVAILABLE"
        if "OUT OF MEMORY" in value or "CUDA" in value:
            return "RERANKER_RESOURCE_ERROR"
        return "RERANKER_EXECUTION_FAILED"


def warmup_policy_reranker() -> dict[str, object]:
    """Load and exercise the local model once; startup remains fail-open."""
    return PolicyEvidenceReranker().warmup()
