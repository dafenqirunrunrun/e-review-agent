from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.rag.dense_retriever import HashDenseRetriever
from app.rag.document_contract import stable_hash
from app.agent_rag.observability import metrics_registry, model_residency


class BaseEmbeddingProvider(Protocol):
    provider_type: str

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        ...

    def embed_query(self, text: str) -> np.ndarray:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def metadata(self) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class BgeM3ProviderConfig:
    model_path: Path
    device: str = "cpu"
    batch_size: int = 8
    max_length: int = 512
    normalize: bool = True
    load_on_startup: bool = False
    provider_impl: str = "legacy-cls"
    use_fp16: bool = False


class DisabledEmbeddingProvider:
    provider_type = "disabled"

    def __init__(self, reason: str = "DENSE_PROVIDER_DISABLED"):
        self.reason = reason

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        raise RuntimeError(self.reason)

    def embed_query(self, text: str) -> np.ndarray:
        raise RuntimeError(self.reason)

    def health(self) -> dict[str, Any]:
        return {"status": "disabled", "loaded": False, "reason": self.reason}

    def metadata(self) -> dict[str, Any]:
        return {
            "providerType": self.provider_type,
            "modelName": "",
            "modelFingerprint": "",
            "dimension": 0,
            "device": "none",
            "normalize": False,
            "loaded": False,
            "runtimeVersion": "agent-rag-phase3a-v1",
            "providerImpl": "disabled",
            "providerConformance": "disabled",
            "assetFingerprint": "",
            "providerFingerprint": "",
            "effectiveEmbeddingFingerprint": "",
        }

    def close(self) -> None:
        return None


class HashEmbeddingProvider:
    provider_type = "hash"

    def __init__(self, *, dimensions: int = 64, normalize: bool = True):
        self.dimensions = dimensions
        self.normalize = normalize

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._validate_texts(texts)
        rows = [{"chunk_id": f"chunk-{idx}", "document_id": f"doc-{idx}", "content": text} for idx, text in enumerate(texts)]
        retriever = HashDenseRetriever(rows, dimensions=self.dimensions)
        matrix = np.vstack([retriever._embed(text) for text in texts]).astype("float32")
        return _normalize(matrix) if self.normalize else matrix

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])

    def health(self) -> dict[str, Any]:
        return {"status": "ready", "loaded": True, "reason": ""}

    def metadata(self) -> dict[str, Any]:
        return {
            "providerType": self.provider_type,
            "modelName": "hash-dense-fixture",
            "modelFingerprint": stable_hash({"provider": self.provider_type, "dimension": self.dimensions, "normalize": self.normalize})[:32],
            "dimension": self.dimensions,
            "device": "cpu",
            "normalize": self.normalize,
            "loaded": True,
            "runtimeVersion": "agent-rag-phase3a-v1",
            "library": "internal-hash",
            "libraryVersion": "n/a",
            "encodeMethod": "HashDenseRetriever._embed",
            "queryInstruction": "",
            "documentInstruction": "",
            "pooling": "hash-token-projection",
            "maxLength": 0,
            "dtype": "float32",
            "providerImpl": "hash",
            "providerConformance": "deterministic-fixture",
            "assetFingerprint": stable_hash({"asset": "hash-dense-fixture", "dimension": self.dimensions})[:32],
            "providerFingerprint": stable_hash({"impl": "hash", "dimension": self.dimensions, "normalize": self.normalize})[:32],
            "effectiveEmbeddingFingerprint": stable_hash({"asset": "hash-dense-fixture", "impl": "hash", "dimension": self.dimensions, "normalize": self.normalize})[:32],
        }

    def close(self) -> None:
        return None

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if not texts:
            raise ValueError("EMBEDDING_EMPTY_BATCH")
        if any(not str(text).strip() for text in texts):
            raise ValueError("EMBEDDING_EMPTY_TEXT")


class BgeM3EmbeddingProvider:
    provider_type = "bge-m3-legacy-cls"
    model_name = "BAAI/bge-m3"
    implementation_version = "agent-rag-bge-m3-provider-v1"
    provider_impl = "legacy-cls"
    provider_conformance = "legacy-experimental"
    library_name = "transformers"
    encode_method = "AutoModel.last_hidden_state[:,0]"
    pooling = "cls-token"

    def __init__(self, config: BgeM3ProviderConfig):
        self.config = config
        self._lock = threading.Lock()
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str = config.device
        self._dimension: int = 0
        self._loaded = False
        self._load_error = ""
        self.last_embedding_duration_ms = 0
        self.last_embedding_duration_ns = 0
        self.cold_start_ms = 0
        self.cold_start_ns = 0
        if config.load_on_startup:
            self._ensure_loaded()

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._validate_texts(texts)
        self._ensure_loaded()
        import torch

        started = time.perf_counter_ns()
        vectors: list[np.ndarray] = []
        gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
        with gate:
            with torch.inference_mode():
                for offset in range(0, len(texts), self.config.batch_size):
                    batch = [str(item)[: self.config.max_length * 8] for item in texts[offset : offset + self.config.batch_size]]
                    tokens = self._tokenizer(batch, padding=True, truncation=True, max_length=self.config.max_length, return_tensors="pt")
                    tokens = {key: value.to(self._device) for key, value in tokens.items()}
                    hidden = self._model(**tokens).last_hidden_state[:, 0]
                    if self.config.normalize:
                        hidden = torch.nn.functional.normalize(hidden, p=2, dim=1)
                    vectors.append(hidden.float().cpu().numpy())
        matrix = np.concatenate(vectors).astype("float32")
        self.last_embedding_duration_ns = time.perf_counter_ns() - started
        self.last_embedding_duration_ms = round(self.last_embedding_duration_ns / 1_000_000, 3)
        metrics_registry.observe("embedding_latency_ms", self.last_embedding_duration_ms)
        self._dimension = int(matrix.shape[1])
        return _validate_matrix(matrix, normalize=self.config.normalize)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready" if self._loaded else ("failed" if self._load_error else "not_loaded"),
            "loaded": self._loaded,
            "reason": self._load_error,
            "device": self._device if self._loaded else self.config.device,
            "dimension": self._dimension,
            "modelFingerprint": self._fingerprint() if self._asset_available() else "",
            "assetFingerprint": self._asset_fingerprint() if self._asset_available() else "",
            "providerFingerprint": self._provider_fingerprint() if self._asset_available() else "",
            "effectiveEmbeddingFingerprint": self._fingerprint() if self._asset_available() else "",
        }

    def metadata(self) -> dict[str, Any]:
        if not self._loaded:
            self._ensure_loaded()
        return {
            "providerType": self.provider_type,
            "providerImpl": self.provider_impl,
            "providerConformance": self.provider_conformance,
            "modelName": self.model_name,
            "modelFingerprint": self._fingerprint(),
            "assetFingerprint": self._asset_fingerprint(),
            "providerFingerprint": self._provider_fingerprint(),
            "effectiveEmbeddingFingerprint": self._fingerprint(),
            "dimension": self._dimension,
            "device": self._device,
            "normalize": self.config.normalize,
            "loaded": self._loaded,
            "runtimeVersion": self.implementation_version,
            "library": self.library_name,
            "libraryVersion": _package_version(self.library_name),
            "encodeMethod": self.encode_method,
            "queryInstruction": "",
            "documentInstruction": "",
            "pooling": self.pooling,
            "maxLength": self.config.max_length,
            "dtype": "float32-output",
            "useFp16": False,
        }

    def close(self) -> None:
        with self._lock:
            self._tokenizer = None
            self._model = None
            self._loaded = False
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            started = time.perf_counter_ns()
            if not self._asset_available():
                self._load_error = "BGE_M3_MODEL_ASSET_UNAVAILABLE"
                raise RuntimeError(self._load_error)
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer

                use_cuda = self.config.device == "cuda" and torch.cuda.is_available()
                self._device = "cuda" if use_cuda else "cpu"
                gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
                with gate:
                    self._tokenizer = AutoTokenizer.from_pretrained(str(self.config.model_path), local_files_only=True)
                    self._model = AutoModel.from_pretrained(str(self.config.model_path), local_files_only=True)
                    self._model.eval().to(self._device)
                self._dimension = int(getattr(self._model.config, "hidden_size", 0))
                if self._dimension <= 0:
                    raise RuntimeError("BGE_M3_DIMENSION_INVALID")
                self._loaded = True
                self._load_error = ""
                self.cold_start_ns = time.perf_counter_ns() - started
                self.cold_start_ms = round(self.cold_start_ns / 1_000_000, 3)
            except Exception as exc:
                self._load_error = str(exc)[:240]
                raise

    def _asset_available(self) -> bool:
        path = self.config.model_path
        return (
            path.is_dir()
            and (path / "config.json").exists()
            and (path / "tokenizer_config.json").exists()
            and any((path / name).exists() for name in ("model.safetensors", "pytorch_model.bin"))
        )

    def _fingerprint(self) -> str:
        return hashlib.sha256(json.dumps({"assetFingerprint": self._asset_fingerprint(), "providerFingerprint": self._provider_fingerprint()}, sort_keys=True).encode("utf-8")).hexdigest()

    def _asset_fingerprint(self) -> str:
        if not self._asset_available():
            return ""
        config_hashes = {}
        for name in ["config.json", "tokenizer_config.json", "tokenizer.json", "sentence_bert_config.json", "modules.json"]:
            path = self.config.model_path / name
            if path.exists():
                config_hashes[name] = _sha256(path)
        weight_names = sorted(path.name for path in self.config.model_path.glob("*.safetensors")) or sorted(name for name in ["model.safetensors", "pytorch_model.bin"] if (self.config.model_path / name).exists())
        weight_sample = {name: {"size": (self.config.model_path / name).stat().st_size, "sampleSha256": _sha256_sample(self.config.model_path / name)} for name in weight_names[:4]}
        payload = {
            "modelName": self.model_name,
            "config": config_hashes,
            "weights": weight_sample,
            "dimension": self._dimension,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _provider_fingerprint(self) -> str:
        payload = {
            "providerImpl": self.provider_impl,
            "providerConformance": self.provider_conformance,
            "library": self.library_name,
            "libraryVersion": _package_version(self.library_name),
            "encodeMethod": self.encode_method,
            "pooling": self.pooling,
            "maxLength": self.config.max_length,
            "normalize": self.config.normalize,
            "useFp16": False,
            "effectiveDtype": "float32-output",
            "dimension": self._dimension,
            "implementationSchemaVersion": "agent-rag-provider-fingerprint-v1",
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if not texts:
            raise ValueError("EMBEDDING_EMPTY_BATCH")
        if any(not str(text).strip() for text in texts):
            raise ValueError("EMBEDDING_EMPTY_TEXT")


class OfficialBgeM3FlagProvider(BgeM3EmbeddingProvider):
    provider_type = "bge-m3"
    provider_impl = "flagembedding"
    provider_conformance = "official-library"
    library_name = "FlagEmbedding"
    encode_method = "BGEM3FlagModel.encode.dense_vecs"
    pooling = "provider-managed"
    implementation_version = "agent-rag-bge-m3-flagembedding-provider-v1"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._validate_texts(texts)
        self._ensure_loaded()
        started = time.perf_counter_ns()
        vectors: list[np.ndarray] = []
        gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
        with gate:
            for offset in range(0, len(texts), self.config.batch_size):
                batch = [str(item) for item in texts[offset : offset + self.config.batch_size]]
                encoded = self._model.encode(batch, batch_size=len(batch), max_length=self.config.max_length, return_dense=True, return_sparse=False, return_colbert_vecs=False)
                dense = encoded["dense_vecs"] if isinstance(encoded, dict) else getattr(encoded, "dense_vecs", None)
                if dense is None:
                    raise RuntimeError("FLAGEMBEDDING_DENSE_VECS_MISSING")
                vectors.append(np.asarray(dense, dtype="float32"))
        matrix = np.concatenate(vectors).astype("float32")
        if self.config.normalize:
            matrix = _normalize(matrix)
        self.last_embedding_duration_ns = time.perf_counter_ns() - started
        self.last_embedding_duration_ms = round(self.last_embedding_duration_ns / 1_000_000, 3)
        metrics_registry.observe("embedding_latency_ms", self.last_embedding_duration_ms)
        self._dimension = int(matrix.shape[1])
        return _validate_matrix(matrix, normalize=self.config.normalize)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            started = time.perf_counter_ns()
            if not self._asset_available():
                self._load_error = "MODEL_ASSET_NOT_FOUND"
                raise RuntimeError(self._load_error)
            try:
                from FlagEmbedding import BGEM3FlagModel

                use_cuda = self.config.device == "cuda" and _torch_cuda_available()
                self._device = "cuda" if use_cuda else "cpu"
                devices = [self._device] if self._device == "cuda" else None
                kwargs: dict[str, Any] = {"use_fp16": bool(self.config.use_fp16 and self._device == "cuda")}
                if devices:
                    kwargs["devices"] = devices
                gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
                with gate:
                    self._model = BGEM3FlagModel(str(self.config.model_path), **kwargs)
                    probe = self._model.encode(["provider dimension probe"], batch_size=1, max_length=min(self.config.max_length, 64), return_dense=True, return_sparse=False, return_colbert_vecs=False)
                dense = probe["dense_vecs"] if isinstance(probe, dict) else getattr(probe, "dense_vecs", None)
                if dense is None:
                    raise RuntimeError("FLAGEMBEDDING_DENSE_VECS_MISSING")
                self._dimension = int(np.asarray(dense).shape[1])
                if self._dimension <= 0:
                    raise RuntimeError("BGE_M3_DIMENSION_INVALID")
                self._loaded = True
                self._load_error = ""
                self.cold_start_ns = time.perf_counter_ns() - started
                self.cold_start_ms = round(self.cold_start_ns / 1_000_000, 3)
            except ImportError as exc:
                self._load_error = "PROVIDER_DEPENDENCY_MISSING:FlagEmbedding"
                raise RuntimeError(self._load_error) from exc
            except Exception as exc:
                self._load_error = str(exc)[:240]
                raise

    def metadata(self) -> dict[str, Any]:
        meta = super().metadata()
        meta["dtype"] = "float16-effective" if self.config.use_fp16 and self._device == "cuda" else "float32-effective"
        meta["useFp16"] = bool(self.config.use_fp16 and self._device == "cuda")
        return meta


class SentenceTransformerBgeM3Provider(BgeM3EmbeddingProvider):
    provider_type = "bge-m3"
    provider_impl = "sentence-transformers"
    provider_conformance = "model-card-reference"
    library_name = "sentence-transformers"
    encode_method = "SentenceTransformer.encode"
    pooling = "provider-managed"
    implementation_version = "agent-rag-bge-m3-sentence-transformers-provider-v1"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._validate_texts(texts)
        self._ensure_loaded()
        started = time.perf_counter_ns()
        gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
        with gate:
            matrix = self._model.encode(
                [str(item) for item in texts],
                batch_size=self.config.batch_size,
                normalize_embeddings=self.config.normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        matrix = np.asarray(matrix, dtype="float32")
        self.last_embedding_duration_ns = time.perf_counter_ns() - started
        self.last_embedding_duration_ms = round(self.last_embedding_duration_ns / 1_000_000, 3)
        metrics_registry.observe("embedding_latency_ms", self.last_embedding_duration_ms)
        self._dimension = int(matrix.shape[1])
        return _validate_matrix(matrix, normalize=self.config.normalize)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            started = time.perf_counter_ns()
            if not self._asset_available():
                self._load_error = "MODEL_ASSET_NOT_FOUND"
                raise RuntimeError(self._load_error)
            try:
                from sentence_transformers import SentenceTransformer

                use_cuda = self.config.device == "cuda" and _torch_cuda_available()
                self._device = "cuda" if use_cuda else "cpu"
                gate = model_residency.acquire("embedding:bge-m3", unload_callback=self.close, device=self._device) if self._device == "cuda" else _noop_gate()
                with gate:
                    self._model = SentenceTransformer(str(self.config.model_path), device=self._device, local_files_only=True)
                    probe = self._model.encode(["provider dimension probe"], batch_size=1, normalize_embeddings=self.config.normalize, convert_to_numpy=True, show_progress_bar=False)
                self._dimension = int(np.asarray(probe).shape[1])
                if self._dimension <= 0:
                    raise RuntimeError("BGE_M3_DIMENSION_INVALID")
                self._loaded = True
                self._load_error = ""
                self.cold_start_ns = time.perf_counter_ns() - started
                self.cold_start_ms = round(self.cold_start_ns / 1_000_000, 3)
            except ImportError as exc:
                self._load_error = "PROVIDER_DEPENDENCY_MISSING:sentence-transformers"
                raise RuntimeError(self._load_error) from exc
            except Exception as exc:
                self._load_error = f"REFERENCE_PROVIDER_COMPATIBILITY_BLOCKED:{str(exc)[:200]}"
                raise RuntimeError(self._load_error) from exc


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms == 0):
        raise ValueError("EMBEDDING_ZERO_VECTOR")
    return (matrix / norms.reshape(-1, 1)).astype("float32")


def _validate_matrix(matrix: np.ndarray, *, normalize: bool) -> np.ndarray:
    values = np.asarray(matrix, dtype="float32")
    if values.ndim != 2:
        raise ValueError("EMBEDDING_VECTOR_RANK_INVALID")
    if values.shape[0] <= 0 or values.shape[1] <= 0:
        raise ValueError("EMBEDDING_VECTOR_SHAPE_INVALID")
    if not np.isfinite(values).all():
        raise ValueError("EMBEDDING_VECTOR_NAN_OR_INF")
    if normalize:
        norms = np.linalg.norm(values, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-3):
            raise ValueError("EMBEDDING_VECTOR_NOT_NORMALIZED")
    return values


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_sample(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    with path.open("rb") as handle:
        digest.update(handle.read(1024 * 1024))
        if size > 1024 * 1024:
            handle.seek(max(0, size - 1024 * 1024))
            digest.update(handle.read(1024 * 1024))
    digest.update(str(size).encode("ascii"))
    return digest.hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except Exception:
        return "unknown"


class _noop_gate:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        return False
