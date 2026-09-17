from __future__ import annotations

import hashlib
import importlib
import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.agent_rag.observability import model_residency
from app.agent_rag.eligibility import filter_eligible_candidates, utc_now
from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.v22_assets import load_v22_model_asset


RERANKER_VERSION = "agent-rag-reranker-v1"


class RerankerUnavailable(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RerankerConfig:
    requested_type: str = "deterministic"
    model_path: str = ""
    model_name: str = ""
    device: str = "cpu"
    use_fp16: bool = False
    batch_size: int = 4
    max_length: int = 512
    candidate_k: int = 20
    final_k: int = 5
    timeout_ms: int = 5000
    max_concurrency: int = 1
    queue_timeout_ms: int = 1000
    fallback_type: str = "deterministic"
    real_required: bool = False
    provider_impl: str = ""
    normalize: bool = True
    model_id: str = ""
    model_revision: str = ""
    model_fingerprint: str = ""


@dataclass(frozen=True)
class RerankerAssetAudit:
    configured: bool
    exists: bool
    pathHint: str = ""
    configPresent: bool = False
    tokenizerPresent: bool = False
    weightsPresent: bool = False
    weightsIndexPresent: bool = False
    fingerprint: str = ""
    blockedReason: str = ""


@dataclass(frozen=True)
class RerankResult:
    candidates: list[RetrievalCandidate]
    scores: list[float]
    requestedType: str
    effectiveType: str
    modelId: str = ""
    modelRevision: str = ""
    modelName: str = ""
    modelFingerprint: str = ""
    inputCount: int = 0
    outputCount: int = 0
    durationMs: int = 0
    fallbackUsed: bool = False
    fallbackReason: str = ""
    version: str = RERANKER_VERSION
    assetAudit: RerankerAssetAudit | None = None


class BaseReranker(Protocol):
    def rerank(self, query: str, candidates: list[RetrievalCandidate], *, top_k: int, tenant_id: str = "", request_id: str = "", evaluation_time_utc: str | None = None) -> RerankResult:
        ...


def load_reranker_config(env: dict[str, str] | None = None) -> RerankerConfig:
    source = env or os.environ
    asset = load_v22_model_asset("reranker", source)
    return RerankerConfig(
        requested_type=source.get("RAG_RERANKER_TYPE", "deterministic").strip() or "deterministic",
        model_path=source.get("RAG_RERANKER_MODEL_PATH", "").strip() or asset.model_path,
        model_name=source.get("RAG_RERANKER_MODEL_NAME", source.get("E_REVIEW_RERANKER_MODEL", "")).strip() or asset.model_id,
        device=source.get("RAG_RERANKER_DEVICE", "cpu").strip() or "cpu",
        use_fp16=source.get("RAG_RERANKER_USE_FP16", "false").lower() == "true",
        batch_size=max(1, int(source.get("RAG_RERANKER_BATCH_SIZE", "4") or "4")),
        max_length=max(16, int(source.get("RAG_RERANKER_MAX_LENGTH", "512") or "512")),
        candidate_k=max(1, int(source.get("RAG_RERANKER_CANDIDATE_K", source.get("RAG_FUSION_TOP_K", "20")) or "20")),
        final_k=max(1, int(source.get("RAG_RERANKER_MAXIMUM_FINAL_K", source.get("RAG_RERANKER_FINAL_K", source.get("RAG_RERANKER_TOP_K", "5"))) or "5")),
        timeout_ms=max(1, int(source.get("RAG_RERANKER_TIMEOUT_MS", "5000") or "5000")),
        max_concurrency=max(1, int(source.get("RAG_RERANKER_MAX_CONCURRENCY", "1") or "1")),
        queue_timeout_ms=max(1, int(source.get("RAG_RERANKER_QUEUE_TIMEOUT_MS", "1000") or "1000")),
        fallback_type=source.get("RAG_RERANKER_FALLBACK_TYPE", "deterministic").strip() or "deterministic",
        real_required=source.get("RAG_REAL_RERANKER_REQUIRED", "false").lower() == "true",
        provider_impl=source.get("RAG_RERANKER_PROVIDER_IMPL", "").strip() or asset.provider,
        normalize=source.get("RAG_RERANKER_NORMALIZE", "true").lower() == "true",
        model_id=asset.model_id,
        model_revision=asset.revision,
        model_fingerprint=asset.fingerprint,
    )


def audit_reranker_model_asset(config: RerankerConfig) -> RerankerAssetAudit:
    if not config.model_path:
        return RerankerAssetAudit(configured=False, exists=False, blockedReason="MODEL_PATH_NOT_CONFIGURED")
    root = Path(config.model_path)
    exists = root.exists() and root.is_dir()
    if not exists:
        return RerankerAssetAudit(configured=True, exists=False, pathHint=root.name, blockedReason="MODEL_NOT_FOUND")
    files = [p for p in root.rglob("*") if p.is_file()]
    config_present = (root / "config.json").exists()
    tokenizer_present = any((root / name).exists() for name in ["tokenizer.json", "tokenizer_config.json", "sentencepiece.bpe.model"])
    weights_present = any(p.suffix in {".safetensors", ".bin", ".pt"} for p in files)
    weights_index_present = any(p.name.endswith(".index.json") for p in files)
    h = hashlib.sha256()
    if config.model_fingerprint:
        h.update(config.model_fingerprint.encode("utf-8"))
    else:
        for p in sorted(files, key=lambda item: item.relative_to(root).as_posix())[:512]:
            h.update(p.relative_to(root).as_posix().encode("utf-8"))
            h.update(str(p.stat().st_size).encode("ascii"))
    blocked = ""
    if not config_present:
        blocked = "CONFIG_MISSING"
    elif not tokenizer_present:
        blocked = "TOKENIZER_MISSING"
    elif not weights_present:
        blocked = "WEIGHTS_MISSING"
    return RerankerAssetAudit(
        configured=True,
        exists=True,
        pathHint=root.name,
        configPresent=config_present,
        tokenizerPresent=tokenizer_present,
        weightsPresent=weights_present,
        weightsIndexPresent=weights_index_present,
        fingerprint=(config.model_fingerprint or h.hexdigest())[:24],
        blockedReason=blocked,
    )


class DisabledReranker:
    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig(requested_type="disabled")

    def rerank(self, query: str, candidates: list[RetrievalCandidate], *, top_k: int, tenant_id: str = "", request_id: str = "", evaluation_time_utc: str | None = None) -> RerankResult:
        del query, request_id
        evaluation_time = evaluation_time_utc or utc_now()
        eligible, _ = filter_eligible_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        selected = list(eligible[:top_k])
        return RerankResult(
            candidates=selected,
            scores=[float(item.fusionScore) for item in selected],
            requestedType=self.config.requested_type,
            effectiveType="disabled",
            inputCount=len(candidates),
            outputCount=len(selected),
        )


class DeterministicGovernedReranker:
    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()

    def rerank(self, query: str, candidates: list[RetrievalCandidate], *, top_k: int, tenant_id: str = "", request_id: str = "", evaluation_time_utc: str | None = None) -> RerankResult:
        del request_id
        started = time.perf_counter()
        evaluation_time = evaluation_time_utc or utc_now()
        _validate_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        terms = {token for token in query.lower().split() if token}
        scored: list[tuple[float, int, str, RetrievalCandidate]] = []
        for original_rank, item in enumerate(candidates, start=1):
            content = str(item.row.get("content") or item.row.get("text") or "").lower()
            overlap = sum(1 for token in terms if token in content)
            score = float(item.fusionScore) + overlap * 0.01
            _validate_score(score)
            scored.append((score, original_rank, item.chunkId, item))
        scored.sort(key=lambda value: (-value[0], value[1], value[2]))
        eligible_ranked, _ = filter_eligible_candidates([item for _, _, _, item in scored], tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        eligible_ids = {item.chunkId for item in eligible_ranked}
        selected_pairs = [entry for entry in scored if entry[3].chunkId in eligible_ids][:top_k]
        selected = [item for _, _, _, item in selected_pairs]
        duration_ms = round((time.perf_counter() - started) * 1000)
        return RerankResult(
            candidates=selected,
            scores=[round(score, 8) for score, _, _, _ in selected_pairs],
            requestedType=self.config.requested_type,
            effectiveType="deterministic",
            inputCount=len(candidates),
            outputCount=len(selected),
            durationMs=duration_ms,
            version=RERANKER_VERSION,
        )


class LocalModelReranker:
    _cache_lock = threading.Lock()
    _model_cache: dict[tuple[str, str, bool, str], tuple[str, Any]] = {}

    def __init__(self, config: RerankerConfig):
        self.config = config
        self.asset_audit = audit_reranker_model_asset(config)
        self._model: Any | None = None
        self._provider_name = ""

    def rerank(self, query: str, candidates: list[RetrievalCandidate], *, top_k: int, tenant_id: str = "", request_id: str = "", evaluation_time_utc: str | None = None) -> RerankResult:
        del request_id
        started = time.perf_counter()
        evaluation_time = evaluation_time_utc or utc_now()
        _validate_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        if not candidates:
            return RerankResult(candidates=[], scores=[], requestedType=self.config.requested_type, effectiveType="local-model", inputCount=0, outputCount=0, assetAudit=self.asset_audit)
        if self.asset_audit.blockedReason:
            raise RerankerUnavailable(self.asset_audit.blockedReason)
        with model_residency.acquire("reranker:bge-reranker-v2-m3", unload_callback=LocalModelReranker.unload_all, device=self.config.device):
            model = self._load_model()
            pairs = [(query, str(item.row.get("content") or item.row.get("text") or "")) for item in candidates[: self.config.candidate_k]]
            try:
                if self._provider_name == "flagembedding":
                    raw_scores = model.compute_score(
                        pairs,
                        batch_size=self.config.batch_size,
                        max_length=self.config.max_length,
                        normalize=self.config.normalize,
                    )
                else:
                    raw_scores = model.predict(pairs, batch_size=self.config.batch_size)
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower():
                    raise RerankerUnavailable("CUDA_OOM") from exc
                raise
        scores = [float(score) for score in raw_scores]
        if len(scores) != len(pairs):
            raise RerankerUnavailable("OUTPUT_COUNT_MISMATCH")
        for score in scores:
            _validate_score(score)
        ranked = sorted(zip(scores, candidates[: self.config.candidate_k], strict=True), key=lambda value: (-value[0], value[1].rawRank or 9999, value[1].chunkId))
        eligible_ranked, _ = filter_eligible_candidates([item for _, item in ranked], tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        eligible_ids = {item.chunkId for item in eligible_ranked}
        selected = [entry for entry in ranked if entry[1].chunkId in eligible_ids][:top_k]
        return RerankResult(
            candidates=[item for _, item in selected],
            scores=[round(score, 8) for score, _ in selected],
            requestedType=self.config.requested_type,
            effectiveType="local-model",
            modelId=self.config.model_id or self.config.model_name,
            modelRevision=self.config.model_revision,
            modelName=self.config.model_id or self.config.model_name or self.asset_audit.pathHint,
            modelFingerprint=self.config.model_fingerprint[:24] or self.asset_audit.fingerprint,
            inputCount=len(candidates),
            outputCount=len(selected),
            durationMs=round((time.perf_counter() - started) * 1000),
            assetAudit=self.asset_audit,
        )

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        cache_key = (
            self.config.model_path,
            self.config.provider_impl or "auto",
            self.config.use_fp16,
            self.config.device,
        )
        with self._cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is not None:
                self._provider_name, self._model = cached
                return self._model
            if (self.config.provider_impl in {"", "flagembedding"} or not self.config.provider_impl) and importlib.util.find_spec("FlagEmbedding"):
                module = importlib.import_module("FlagEmbedding")
                cls = getattr(module, "FlagReranker")
                self._provider_name = "flagembedding"
                self._model = cls(self.config.model_path, use_fp16=self.config.use_fp16)
                self._model_cache[cache_key] = (self._provider_name, self._model)
                return self._model
            if self.config.provider_impl in {"", "sentence-transformers", "sentence_transformers"} and importlib.util.find_spec("sentence_transformers"):
                module = importlib.import_module("sentence_transformers")
                cls = getattr(module, "CrossEncoder")
                self._provider_name = "sentence-transformers"
                self._model = cls(self.config.model_path, device=self.config.device, max_length=self.config.max_length)
                self._model_cache[cache_key] = (self._provider_name, self._model)
                return self._model
        raise RerankerUnavailable("DEPENDENCY_MISSING")

    @classmethod
    def unload_all(cls) -> None:
        with cls._cache_lock:
            cached = list(cls._model_cache.values())
            cls._model_cache.clear()
        for _provider, model in cached:
            try:
                if hasattr(model, "model") and hasattr(model.model, "to"):
                    model.model.to("cpu")
                elif hasattr(model, "to"):
                    model.to("cpu")
            except Exception:
                pass
        try:
            import gc
            import torch

            del cached
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            return None


class GovernedReranker:
    def __init__(self, config: RerankerConfig | None = None, *, model_reranker: BaseReranker | None = None):
        self.config = config or load_reranker_config()
        self._model_reranker = model_reranker

    def rerank(self, query: str, candidates: list[RetrievalCandidate], *, top_k: int | None = None, tenant_id: str = "", request_id: str = "", evaluation_time_utc: str | None = None) -> RerankResult:
        evaluation_time = evaluation_time_utc or utc_now()
        eligible_candidates, eligibility = filter_eligible_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
        reasons = {decision.reasonCode for decision in eligibility if not decision.eligible}
        if reasons & {"TENANT_MISMATCH", "TENANT_SCOPE_INVALID"}:
            raise RerankerUnavailable("TENANT_SCOPE_VIOLATION")
        if reasons & {"INACTIVE", "DISABLED", "TOMBSTONED"}:
            raise RerankerUnavailable("INACTIVE_CANDIDATE")
        final_k = min(top_k or self.config.final_k, max(1, len(eligible_candidates))) if eligible_candidates else (top_k or self.config.final_k)
        requested = self.config.requested_type
        if requested in {"disabled", "none"}:
            return DisabledReranker(self.config).rerank(query, eligible_candidates, top_k=final_k, tenant_id=tenant_id, request_id=request_id, evaluation_time_utc=evaluation_time)
        if requested in {"deterministic", "rule", "lexical"}:
            return DeterministicGovernedReranker(self.config).rerank(query, eligible_candidates, top_k=final_k, tenant_id=tenant_id, request_id=request_id, evaluation_time_utc=evaluation_time)
        return self._rerank_with_model(query, eligible_candidates, final_k=final_k, tenant_id=tenant_id, request_id=request_id, evaluation_time_utc=evaluation_time)

    def _rerank_with_model(self, query: str, candidates: list[RetrievalCandidate], *, final_k: int, tenant_id: str, request_id: str, evaluation_time_utc: str | None) -> RerankResult:
        started = time.perf_counter()
        try:
            provider = self._model_reranker or LocalModelReranker(self.config)
            try:
                result = provider.rerank(query, candidates[: self.config.candidate_k], top_k=final_k, tenant_id=tenant_id, request_id=request_id, evaluation_time_utc=evaluation_time_utc)
            except TypeError as exc:
                if "evaluation_time_utc" not in str(exc):
                    raise
                result = provider.rerank(query, candidates[: self.config.candidate_k], top_k=final_k, tenant_id=tenant_id, request_id=request_id)
            if result.durationMs > self.config.timeout_ms:
                raise RerankerUnavailable("EXECUTION_TIMEOUT")
            if result.outputCount > result.inputCount:
                raise RerankerUnavailable("OUTPUT_COUNT_MISMATCH")
            return result
        except RerankerUnavailable as exc:
            if self.config.real_required:
                raise
            return self._fallback(query, candidates, final_k, exc.code, tenant_id, request_id, started, evaluation_time_utc)
        except Exception as exc:
            if self.config.real_required:
                raise
            if isinstance(exc, TimeoutError):
                return self._fallback(query, candidates, final_k, "QUEUE_TIMEOUT", tenant_id, request_id, started, evaluation_time_utc)
            reason = "CUDA_OOM" if "out of memory" in str(exc).lower() else "UNKNOWN_ERROR"
            return self._fallback(query, candidates, final_k, reason, tenant_id, request_id, started, evaluation_time_utc)

    def _fallback(self, query: str, candidates: list[RetrievalCandidate], final_k: int, reason: str, tenant_id: str, request_id: str, started: float, evaluation_time_utc: str | None) -> RerankResult:
        result = DeterministicGovernedReranker(self.config).rerank(query, candidates, top_k=final_k, tenant_id=tenant_id, request_id=request_id, evaluation_time_utc=evaluation_time_utc)
        return RerankResult(
            candidates=result.candidates,
            scores=result.scores,
            requestedType=self.config.requested_type,
            effectiveType=f"{self.config.fallback_type}-fallback",
            inputCount=len(candidates),
            outputCount=len(result.candidates),
            durationMs=round((time.perf_counter() - started) * 1000),
            fallbackUsed=True,
            fallbackReason=reason,
            version=RERANKER_VERSION,
            assetAudit=audit_reranker_model_asset(self.config),
        )


def _validate_candidates(candidates: list[RetrievalCandidate], *, tenant_id: str = "", evaluation_time_utc: str | None = None) -> None:
    allowed = {tenant_id, "__public__", ""} if tenant_id else set()
    seen: set[str] = set()
    for item in candidates:
        if tenant_id and item.tenantId not in allowed:
            raise RerankerUnavailable("TENANT_SCOPE_VIOLATION")
        if item.chunkId in seen:
            raise RerankerUnavailable("DUPLICATE_CANDIDATE")
        seen.add(item.chunkId)
        row = item.row or {}
        decision = filter_eligible_candidates([item], tenant_id=tenant_id or item.tenantId, evaluation_time_utc=evaluation_time_utc or utc_now())[1][0]
        if not decision.eligible:
            raise RerankerUnavailable(f"{decision.reasonCode}_CANDIDATE")


def _validate_score(score: float) -> None:
    if math.isnan(score) or math.isinf(score):
        raise RerankerUnavailable("INVALID_SCORE")
