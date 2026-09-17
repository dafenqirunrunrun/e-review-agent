from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.rag.document_contract import stable_hash
from app.core.config import settings
from app.observability.workflow_observer import NoopWorkflowObserver, WorkflowObserver


def _latency_summary(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "avg": 0, "p95": 0, "max": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "count": len(values),
        "avg": int(sum(values) / len(values)),
        "p95": int(ordered[p95_index]),
        "max": int(ordered[-1]),
    }


class PolicyEmbeddingProvider(Protocol):
    provider_type: str

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        ...

    def embed_query(self, text: str) -> np.ndarray:
        ...

    def metadata(self) -> dict[str, Any]:
        ...

    def health(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class QwenEmbeddingConfig:
    model_name: str = "Qwen/Qwen3-Embedding-0.6B"
    model_path: Path | None = None
    device: str = "cpu"
    batch_size: int = 8
    max_length: int = 512
    normalize: bool = True
    allow_remote: bool = False


class DisabledPolicyEmbeddingProvider:
    provider_type = "disabled"

    def __init__(self, reason: str = "POLICY_EMBEDDING_DISABLED"):
        self.reason = reason

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        raise RuntimeError(self.reason)

    def embed_query(self, text: str) -> np.ndarray:
        raise RuntimeError(self.reason)

    def metadata(self) -> dict[str, Any]:
        return {
            "providerType": self.provider_type,
            "modelName": "",
            "dimension": 0,
            "normalize": False,
            "loaded": False,
            "fallbackReason": self.reason,
        }

    def health(self) -> dict[str, Any]:
        return {"status": "disabled", "loaded": False, "reason": self.reason}


class QwenTransformersEmbeddingProvider:
    provider_type = "qwen3-embedding-transformers"

    def __init__(self, config: QwenEmbeddingConfig):
        self.config = config
        self._tokenizer: Any = None
        self._model: Any = None
        self._device = config.device
        self._dimension = 0
        self._load_error = ""
        self._cold_start_latency_ms = 0
        self._last_embedding_latency_ms = 0
        self._model_load_count = 0
        self._queue_wait_ms = 0
        self._compute_ms = 0
        self._gate = threading.BoundedSemaphore(settings.policy_rag.embedding_max_concurrency)
        self._load_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._queue_wait_samples: list[int] = []
        self._compute_samples: list[int] = []

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed_documents(texts, observer=None)

    def _embed_documents(
        self,
        texts: list[str],
        *,
        observer: WorkflowObserver | None,
    ) -> np.ndarray:
        self._validate_texts(texts)
        runtime_observer = observer or NoopWorkflowObserver()
        started = time.perf_counter()
        if self._model is None:
            with runtime_observer.span("embedding_model_load", "span") as span:
                self._ensure_loaded()
                span.update(output={"dimension": int(getattr(self._model.config, "hidden_size", 0))})
        else:
            self._ensure_loaded()
        import torch

        queue_started = time.perf_counter()
        with runtime_observer.span("embedding_queue_wait", "span") as queue_span:
            acquired = self._gate.acquire(timeout=settings.policy_rag.embedding_queue_timeout_ms / 1000)
            self._queue_wait_ms = int((time.perf_counter() - queue_started) * 1000)
            queue_span.update(
                output={"queueWaitMs": self._queue_wait_ms},
                status="success" if acquired else "timeout",
            )
            if not acquired:
                self._record_latency(queue_wait_ms=self._queue_wait_ms)
                raise RuntimeError("EMBEDDING_QUEUE_TIMEOUT")
        rows = []
        compute_started = time.perf_counter()
        try:
            with runtime_observer.span(
                "embedding_compute",
                "embedding",
                metadata={"batchCount": (len(texts) + self.config.batch_size - 1) // self.config.batch_size},
            ) as compute_span:
                with torch.inference_mode():
                    for offset in range(0, len(texts), self.config.batch_size):
                        batch = [str(item) for item in texts[offset : offset + self.config.batch_size]]
                        tokens = self._tokenizer(
                            batch,
                            padding=True,
                            truncation=True,
                            max_length=self.config.max_length,
                            return_tensors="pt",
                        )
                        tokens = {key: value.to(self._device) for key, value in tokens.items()}
                        output = self._model(**tokens)
                        hidden = output.last_hidden_state
                        mask = tokens["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
                        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
                        rows.append(pooled.float().cpu().numpy())
                compute_span.update(output={"resultCount": len(texts)})
        finally:
            self._compute_ms = int((time.perf_counter() - compute_started) * 1000)
            self._record_latency(queue_wait_ms=self._queue_wait_ms, compute_ms=self._compute_ms)
            self._gate.release()
        matrix = np.concatenate(rows).astype("float32")
        if self.config.normalize:
            matrix = _normalize(matrix)
        self._dimension = int(matrix.shape[1])
        self._last_embedding_latency_ms = int((time.perf_counter() - started) * 1000)
        return _validate_matrix(matrix, normalize=self.config.normalize)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])

    def embed_query_observed(self, text: str, observer: WorkflowObserver) -> np.ndarray:
        return self._embed_documents([text], observer=observer)

    def metadata(self) -> dict[str, Any]:
        if self._dimension <= 0 and self._model is not None:
            self._dimension = int(getattr(self._model.config, "hidden_size", 0))
        return {
            "providerType": self.provider_type,
            "modelName": self.config.model_name,
            "modelPath": str(self.config.model_path or ""),
            "dimension": self._dimension,
            "device": self._device,
            "normalize": self.config.normalize,
            "loaded": self._model is not None,
            "library": "transformers",
            "libraryVersion": _package_version("transformers"),
            "pooling": "attention-mask-mean",
            "maxLength": self.config.max_length,
            "allowRemote": self.config.allow_remote,
            "modelFingerprint": stable_hash(
                {
                    "provider": self.provider_type,
                    "modelName": self.config.model_name,
                    "modelPath": str(self.config.model_path or ""),
                    "normalize": self.config.normalize,
                    "dimension": self._dimension,
                    "pooling": "attention-mask-mean",
                }
            )[:32],
            "coldStartLatencyMs": self._cold_start_latency_ms,
            "lastEmbeddingLatencyMs": self._last_embedding_latency_ms,
            "modelLoadCount": self._model_load_count,
            "queueWaitMs": self._queue_wait_ms,
            "embeddingComputeMs": self._compute_ms,
            "embeddingGate": {
                "maxConcurrency": settings.policy_rag.embedding_max_concurrency,
                "queueTimeoutMs": settings.policy_rag.embedding_queue_timeout_ms,
                "queueWaitMs": _latency_summary(self._queue_wait_samples),
                "computeMs": _latency_summary(self._compute_samples),
            },
        }

    def health(self) -> dict[str, Any]:
        if self._model is not None:
            return {"status": "ready", "loaded": True, "reason": ""}
        if self.config.model_path and not self.config.model_path.exists():
            return {"status": "unavailable", "loaded": False, "reason": "QWEN_EMBEDDING_MODEL_PATH_NOT_FOUND"}
        if not self.config.allow_remote and not self.config.model_path:
            return {"status": "unavailable", "loaded": False, "reason": "QWEN_EMBEDDING_LOCAL_PATH_REQUIRED"}
        return {"status": "configured", "loaded": False, "reason": ""}

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            started = time.perf_counter()
            source = str(self.config.model_path) if self.config.model_path else self.config.model_name
            if self.config.model_path and not self.config.model_path.exists():
                self._load_error = "QWEN_EMBEDDING_MODEL_PATH_NOT_FOUND"
                raise RuntimeError(self._load_error)
            if not self.config.allow_remote and not self.config.model_path:
                self._load_error = "QWEN_EMBEDDING_LOCAL_PATH_REQUIRED"
                raise RuntimeError(self._load_error)
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer
            except ImportError as exc:
                self._load_error = "PROVIDER_DEPENDENCY_MISSING:transformers_or_torch"
                raise RuntimeError(self._load_error) from exc
            use_cuda = self.config.device == "cuda" and torch.cuda.is_available()
            self._device = "cuda" if use_cuda else "cpu"
            if self._device == "cpu" and settings.policy_rag.cpu_threads > 0:
                torch.set_num_threads(settings.policy_rag.cpu_threads)
            self._tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=not self.config.allow_remote)
            self._model = AutoModel.from_pretrained(source, local_files_only=not self.config.allow_remote)
            self._model.eval().to(self._device)
            self._model_load_count += 1
            self._dimension = int(getattr(self._model.config, "hidden_size", 0))
            self._cold_start_latency_ms = int((time.perf_counter() - started) * 1000)

    def _record_latency(self, *, queue_wait_ms: int, compute_ms: int | None = None) -> None:
        with self._metrics_lock:
            self._queue_wait_samples.append(queue_wait_ms)
            if compute_ms is not None:
                self._compute_samples.append(compute_ms)

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if not texts:
            raise ValueError("EMBEDDING_EMPTY_BATCH")
        if any(not str(text).strip() for text in texts):
            raise ValueError("EMBEDDING_EMPTY_TEXT")


QWEN3_OFFICIAL_RETRIEVAL_PROFILE = "qwen3-official-retrieval-v2"
DEFAULT_POLICY_QUERY_INSTRUCTION = (
    "Given an e-commerce review risk description, retrieve policy clauses that support the governance decision"
)


class QwenOfficialTransformersEmbeddingProvider(QwenTransformersEmbeddingProvider):
    """Isolated Qwen3 candidate that follows the model card retrieval semantics."""

    provider_type = "qwen3-embedding-transformers-official-v2"

    def __init__(
        self,
        config: QwenEmbeddingConfig,
        *,
        query_instruction: str = DEFAULT_POLICY_QUERY_INSTRUCTION,
    ):
        super().__init__(config)
        self.query_instruction = " ".join(str(query_instruction).split())
        if not self.query_instruction:
            raise ValueError("QWEN_QUERY_INSTRUCTION_REQUIRED")

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed_official(texts, query_mode=False, observer=None)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed_official(texts, query_mode=True, observer=None)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed_official([text], query_mode=True, observer=None)

    def embed_query_observed(self, text: str, observer: WorkflowObserver) -> np.ndarray:
        return self._embed_official([text], query_mode=True, observer=observer)

    def metadata(self) -> dict[str, Any]:
        metadata = super().metadata()
        instruction_hash = stable_hash(self.query_instruction)
        metadata.pop("modelPath", None)
        metadata.update(
            {
                "providerType": self.provider_type,
                "modelSource": "local" if self.config.model_path else "remote",
                "embeddingProfile": QWEN3_OFFICIAL_RETRIEVAL_PROFILE,
                "pooling": "last-token",
                "paddingSide": "left",
                "queryInstructionApplied": True,
                "documentInstructionApplied": False,
                "queryInstructionHash": instruction_hash,
                "modelFingerprint": stable_hash(
                    {
                        "provider": self.provider_type,
                        "profile": QWEN3_OFFICIAL_RETRIEVAL_PROFILE,
                        "modelName": self.config.model_name,
                        "modelPath": str(self.config.model_path or ""),
                        "normalize": self.config.normalize,
                        "pooling": "last-token",
                        "paddingSide": "left",
                        "maxLength": self.config.max_length,
                        "queryInstructionHash": instruction_hash,
                    }
                )[:32],
            }
        )
        return metadata

    def _ensure_loaded(self) -> None:
        super()._ensure_loaded()
        self._tokenizer.padding_side = "left"

    def _embed_official(
        self,
        texts: list[str],
        *,
        query_mode: bool,
        observer: WorkflowObserver | None,
    ) -> np.ndarray:
        self._validate_texts(texts)
        runtime_observer = observer or NoopWorkflowObserver()
        started = time.perf_counter()
        if self._model is None:
            with runtime_observer.span("embedding_model_load", "span") as span:
                self._ensure_loaded()
                span.update(output={"dimension": int(getattr(self._model.config, "hidden_size", 0))})
        else:
            self._ensure_loaded()

        import torch

        queue_started = time.perf_counter()
        with runtime_observer.span("embedding_queue_wait", "span") as queue_span:
            acquired = self._gate.acquire(timeout=settings.policy_rag.embedding_queue_timeout_ms / 1000)
            self._queue_wait_ms = int((time.perf_counter() - queue_started) * 1000)
            queue_span.update(
                output={"queueWaitMs": self._queue_wait_ms},
                status="success" if acquired else "timeout",
            )
            if not acquired:
                self._record_latency(queue_wait_ms=self._queue_wait_ms)
                raise RuntimeError("EMBEDDING_QUEUE_TIMEOUT")

        rows = []
        compute_started = time.perf_counter()
        try:
            with runtime_observer.span(
                "embedding_compute",
                "embedding",
                metadata={
                    "batchCount": (len(texts) + self.config.batch_size - 1) // self.config.batch_size,
                    "embeddingProfile": QWEN3_OFFICIAL_RETRIEVAL_PROFILE,
                    "inputRole": "query" if query_mode else "document",
                },
            ) as compute_span:
                with torch.inference_mode():
                    for offset in range(0, len(texts), self.config.batch_size):
                        raw_batch = [str(item) for item in texts[offset : offset + self.config.batch_size]]
                        batch = self._query_inputs(raw_batch) if query_mode else raw_batch
                        tokens = self._tokenizer(
                            batch,
                            padding=True,
                            truncation=True,
                            max_length=self.config.max_length,
                            return_tensors="pt",
                        )
                        tokens = {key: value.to(self._device) for key, value in tokens.items()}
                        output = self._model(**tokens)
                        rows.append(self._last_token_pool(output.last_hidden_state, tokens["attention_mask"]).float().cpu().numpy())
                compute_span.update(output={"resultCount": len(texts)})
        finally:
            self._compute_ms = int((time.perf_counter() - compute_started) * 1000)
            self._record_latency(queue_wait_ms=self._queue_wait_ms, compute_ms=self._compute_ms)
            self._gate.release()

        matrix = np.concatenate(rows).astype("float32")
        if self.config.normalize:
            matrix = _normalize(matrix)
        self._dimension = int(matrix.shape[1])
        self._last_embedding_latency_ms = int((time.perf_counter() - started) * 1000)
        return _validate_matrix(matrix, normalize=self.config.normalize)

    def _query_inputs(self, texts: list[str]) -> list[str]:
        return [f"Instruct: {self.query_instruction}\nQuery:{text}" for text in texts]

    @staticmethod
    def _last_token_pool(last_hidden_states: Any, attention_mask: Any) -> Any:
        import torch

        if bool((attention_mask[:, -1].sum() == attention_mask.shape[0]).item()):
            return last_hidden_states[:, -1]
        sequence_lengths = attention_mask.sum(dim=1) - 1
        return last_hidden_states[
            torch.arange(last_hidden_states.shape[0], device=last_hidden_states.device),
            sequence_lengths,
        ]


class QwenSentenceTransformerEmbeddingProvider:
    provider_type = "qwen3-embedding-sentence-transformers"

    def __init__(self, config: QwenEmbeddingConfig):
        self.config = config
        self._model: Any = None
        self._dimension = 0
        self._load_error = ""
        self._cold_start_latency_ms = 0
        self._last_embedding_latency_ms = 0

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._validate_texts(texts)
        started = time.perf_counter()
        self._ensure_loaded()
        matrix = self._model.encode(
            [str(item) for item in texts],
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        values = np.asarray(matrix, dtype="float32")
        if self.config.normalize:
            values = _normalize(values)
        self._dimension = int(values.shape[1])
        self._last_embedding_latency_ms = int((time.perf_counter() - started) * 1000)
        return _validate_matrix(values, normalize=self.config.normalize)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])

    def metadata(self) -> dict[str, Any]:
        if self._dimension <= 0 and self._model is not None:
            probe = self.embed_query("dimension probe")
            self._dimension = int(probe.shape[1])
        return {
            "providerType": self.provider_type,
            "modelName": self.config.model_name,
            "modelPath": str(self.config.model_path or ""),
            "dimension": self._dimension,
            "device": self.config.device,
            "normalize": self.config.normalize,
            "loaded": self._model is not None,
            "library": "sentence-transformers",
            "libraryVersion": _package_version("sentence-transformers"),
            "maxLength": self.config.max_length,
            "allowRemote": self.config.allow_remote,
            "modelFingerprint": stable_hash(
                {
                    "provider": self.provider_type,
                    "modelName": self.config.model_name,
                    "modelPath": str(self.config.model_path or ""),
                    "normalize": self.config.normalize,
                    "dimension": self._dimension,
                }
            )[:32],
            "coldStartLatencyMs": self._cold_start_latency_ms,
            "lastEmbeddingLatencyMs": self._last_embedding_latency_ms,
        }

    def health(self) -> dict[str, Any]:
        if self._model is not None:
            return {"status": "ready", "loaded": True, "reason": ""}
        if self.config.model_path and not self.config.model_path.exists():
            return {"status": "unavailable", "loaded": False, "reason": "QWEN_EMBEDDING_MODEL_PATH_NOT_FOUND"}
        if not self.config.allow_remote and not self.config.model_path:
            return {"status": "unavailable", "loaded": False, "reason": "QWEN_EMBEDDING_LOCAL_PATH_REQUIRED"}
        return {"status": "configured", "loaded": False, "reason": ""}

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        started = time.perf_counter()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            self._load_error = "PROVIDER_DEPENDENCY_MISSING:sentence-transformers"
            raise RuntimeError(self._load_error) from exc

        source = str(self.config.model_path) if self.config.model_path else self.config.model_name
        if self.config.model_path and not self.config.model_path.exists():
            self._load_error = "QWEN_EMBEDDING_MODEL_PATH_NOT_FOUND"
            raise RuntimeError(self._load_error)
        if not self.config.allow_remote and not self.config.model_path:
            self._load_error = "QWEN_EMBEDDING_LOCAL_PATH_REQUIRED"
            raise RuntimeError(self._load_error)
        self._model = SentenceTransformer(
            source,
            device=self.config.device,
            local_files_only=not self.config.allow_remote,
        )
        self._cold_start_latency_ms = int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if not texts:
            raise ValueError("EMBEDDING_EMPTY_BATCH")
        if any(not str(text).strip() for text in texts):
            raise ValueError("EMBEDDING_EMPTY_TEXT")


def create_policy_embedding_provider(provider: str | None = None) -> PolicyEmbeddingProvider:
    selected = (provider or settings.policy_rag.embedding_provider).strip().lower()
    if selected in {"", "disabled", "none", "off"}:
        return DisabledPolicyEmbeddingProvider()
    if selected not in {"qwen", "qwen3", "qwen3-embedding"}:
        return DisabledPolicyEmbeddingProvider(f"UNSUPPORTED_POLICY_EMBEDDING_PROVIDER:{selected}")
    policy_settings = settings.policy_rag
    model_path = policy_settings.embedding_model_path
    config = QwenEmbeddingConfig(
        model_name=policy_settings.embedding_model,
        model_path=Path(model_path) if model_path else None,
        device=policy_settings.embedding_device,
        batch_size=policy_settings.embedding_batch_size,
        max_length=policy_settings.embedding_max_length,
        normalize=os.getenv("E_REVIEW_POLICY_RAG_EMBEDDING_NORMALIZE", "true").lower() in {"1", "true", "yes", "on"},
        allow_remote=policy_settings.embedding_allow_remote,
    )
    return _cached_provider(selected, config)


_PROVIDER_CACHE: dict[str, PolicyEmbeddingProvider] = {}


def _cached_provider(selected: str, config: QwenEmbeddingConfig) -> PolicyEmbeddingProvider:
    impl = settings.policy_rag.embedding_impl.strip().lower()
    key = stable_hash({"selected": selected, "impl": impl, "config": {**config.__dict__, "model_path": str(config.model_path or "")}})
    if key in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[key]
    if impl in {"sentence-transformers", "sentence_transformers"}:
        provider: PolicyEmbeddingProvider = QwenSentenceTransformerEmbeddingProvider(config)
    else:
        provider = QwenTransformersEmbeddingProvider(config)
    _PROVIDER_CACHE[key] = provider
    return provider


def warmup_policy_embedding_provider() -> dict[str, Any]:
    if not settings.policy_rag.warmup_enabled:
        return {"status": "skipped", "reason": "POLICY_RAG_WARMUP_DISABLED"}
    started = time.perf_counter()
    provider = create_policy_embedding_provider()
    try:
        provider.embed_query(
            "五星好评截图返现，商家要求消费者发布评价后联系客服领取现金奖励。 "
            "fake review rating manipulation paid review incentive policy"
        )
        return {"status": "ready", "latencyMs": int((time.perf_counter() - started) * 1000), "provider": provider.metadata()}
    except Exception as exc:
        return {"status": "degraded", "latencyMs": int((time.perf_counter() - started) * 1000), "reason": str(exc)[:240]}


def _validate_matrix(matrix: np.ndarray, *, normalize: bool) -> np.ndarray:
    values = np.asarray(matrix, dtype="float32")
    if values.ndim != 2 or values.shape[0] <= 0 or values.shape[1] <= 0:
        raise ValueError("EMBEDDING_VECTOR_SHAPE_INVALID")
    if not np.isfinite(values).all():
        raise ValueError("EMBEDDING_VECTOR_NAN_OR_INF")
    if normalize:
        norms = np.linalg.norm(values, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-3):
            raise ValueError("EMBEDDING_VECTOR_NOT_NORMALIZED")
    return values


def _normalize(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype="float32")
    norms = np.linalg.norm(values, axis=1)
    if np.any(norms == 0):
        raise ValueError("EMBEDDING_ZERO_VECTOR")
    return (values / norms.reshape(-1, 1)).astype("float32")


def _package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except Exception:
        return "unknown"
