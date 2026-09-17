import os
from pathlib import Path

from pydantic import BaseModel


def _load_local_env() -> None:
    """Load developer-local ai-service/.env without overriding explicit process env."""
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except Exception:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class PolicyRagSettings(BaseModel):
    enabled: bool = True
    dense_enabled: bool = True
    bm25_fallback_enabled: bool = True
    index_path: str = "data/policy_rag_real/index/policy_chunks.jsonl"
    managed_index_root: str = "../storage/document-library/policy-index"
    strict_index: bool = False
    vector_store: str = "faiss"
    faiss_index_name: str = "policy_vectors.faiss"
    faiss_meta_name: str = "policy_vectors_meta.json"
    retrieval_top_k: int = 3
    embedding_provider: str = "qwen"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_model_path: str = ""
    embedding_impl: str = "transformers"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 4
    embedding_max_length: int = 96
    embedding_allow_remote: bool = False
    warmup_enabled: bool = False
    embedding_max_concurrency: int = 1
    embedding_queue_timeout_ms: int = 30000
    query_cache_enabled: bool = True
    query_cache_ttl_seconds: int = 300
    cpu_threads: int = 0
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_model_path: str = ""
    reranker_device: str = "cpu"
    reranker_batch_size: int = 5
    reranker_candidate_k: int = 5
    reranker_final_k: int = 3
    reranker_latency_budget_ms: int = 2500
    reranker_max_concurrency: int = 1
    reranker_queue_timeout_ms: int = 1000
    reranker_warmup_enabled: bool = False

    @classmethod
    def from_env(cls) -> "PolicyRagSettings":
        return cls(
            enabled=_env_bool("E_REVIEW_POLICY_RAG_ENABLED", True),
            dense_enabled=_env_bool("E_REVIEW_POLICY_RAG_DENSE_RETRIEVAL_ENABLED", _env_bool("E_REVIEW_POLICY_RAG_DENSE_ENABLED", True)),
            bm25_fallback_enabled=_env_bool("E_REVIEW_POLICY_RAG_BM25_FALLBACK_ENABLED", True),
            index_path=_env_str("E_REVIEW_POLICY_RAG_INDEX_PATH", "data/policy_rag_real/index/policy_chunks.jsonl"),
            managed_index_root=_env_str("E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT", "../storage/document-library/policy-index"),
            strict_index=_env_bool("E_REVIEW_POLICY_RAG_STRICT_INDEX", False),
            vector_store=_env_str("E_REVIEW_POLICY_RAG_VECTOR_STORE", "faiss"),
            retrieval_top_k=_env_int("E_REVIEW_POLICY_RAG_TOP_K", 3, minimum=1, maximum=10),
            embedding_provider=_env_str("E_REVIEW_POLICY_RAG_EMBEDDING_PROVIDER", "qwen"),
            embedding_model=_env_str("E_REVIEW_POLICY_RAG_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"),
            embedding_model_path=_env_str("E_REVIEW_POLICY_RAG_EMBEDDING_MODEL_PATH", ""),
            embedding_impl=_env_str("E_REVIEW_POLICY_RAG_EMBEDDING_IMPL", "transformers"),
            embedding_device=_env_str("E_REVIEW_POLICY_RAG_EMBEDDING_DEVICE", "cpu"),
            embedding_batch_size=_env_int("E_REVIEW_POLICY_RAG_EMBEDDING_BATCH_SIZE", 4, minimum=1, maximum=64),
            embedding_max_length=_env_int("E_REVIEW_POLICY_RAG_EMBEDDING_MAX_LENGTH", 96, minimum=32, maximum=2048),
            embedding_allow_remote=_env_bool("E_REVIEW_POLICY_RAG_EMBEDDING_ALLOW_REMOTE", False),
            warmup_enabled=_env_bool("E_REVIEW_POLICY_RAG_WARMUP_ENABLED", False),
            embedding_max_concurrency=_env_int("E_REVIEW_POLICY_RAG_EMBEDDING_MAX_CONCURRENCY", 1, minimum=1, maximum=8),
            embedding_queue_timeout_ms=_env_int("E_REVIEW_POLICY_RAG_EMBEDDING_QUEUE_TIMEOUT_MS", 30000, minimum=100, maximum=120000),
            query_cache_enabled=_env_bool("E_REVIEW_POLICY_RAG_QUERY_CACHE_ENABLED", True),
            query_cache_ttl_seconds=_env_int("E_REVIEW_POLICY_RAG_QUERY_CACHE_TTL_SECONDS", 300, minimum=1, maximum=3600),
            cpu_threads=_env_int("E_REVIEW_POLICY_RAG_CPU_THREADS", 0, minimum=0, maximum=64),
            reranker_enabled=_env_bool("E_REVIEW_POLICY_RAG_RERANKER_ENABLED", False),
            reranker_model=_env_str("E_REVIEW_POLICY_RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            reranker_model_path=_env_str("E_REVIEW_POLICY_RAG_RERANKER_MODEL_PATH", ""),
            reranker_device=_env_str("E_REVIEW_POLICY_RAG_RERANKER_DEVICE", "cpu"),
            reranker_batch_size=_env_int("E_REVIEW_POLICY_RAG_RERANKER_BATCH_SIZE", 5, minimum=1, maximum=32),
            reranker_candidate_k=_env_int("E_REVIEW_POLICY_RAG_RERANKER_CANDIDATE_K", 5, minimum=2, maximum=20),
            reranker_final_k=_env_int("E_REVIEW_POLICY_RAG_RERANKER_FINAL_K", 3, minimum=1, maximum=10),
            reranker_latency_budget_ms=_env_int(
                "E_REVIEW_POLICY_RAG_RERANKER_LATENCY_BUDGET_MS",
                _env_int("E_REVIEW_POLICY_RAG_RERANKER_TIMEOUT_MS", 2500, minimum=100, maximum=60000),
                minimum=100,
                maximum=60000,
            ),
            reranker_max_concurrency=_env_int("E_REVIEW_POLICY_RAG_RERANKER_MAX_CONCURRENCY", 1, minimum=1, maximum=4),
            reranker_queue_timeout_ms=_env_int("E_REVIEW_POLICY_RAG_RERANKER_QUEUE_TIMEOUT_MS", 1000, minimum=10, maximum=30000),
            reranker_warmup_enabled=_env_bool(
                "E_REVIEW_POLICY_RAG_RERANKER_WARMUP_ENABLED",
                _env_bool("E_REVIEW_POLICY_RAG_WARMUP_ENABLED", False),
            ),
        )

    @property
    def redacted(self) -> dict:
        model_path_status = "configured" if self.embedding_model_path else "not_configured"
        if self.embedding_model_path and not Path(self.embedding_model_path).exists():
            model_path_status = "missing"
        reranker_path_status = "configured" if self.reranker_model_path else "not_configured"
        if self.reranker_model_path and not Path(self.reranker_model_path).exists():
            reranker_path_status = "missing"
        return {
            "enabled": self.enabled,
            "denseEnabled": self.dense_enabled,
            "bm25FallbackEnabled": self.bm25_fallback_enabled,
            "indexConfigured": bool(self.index_path),
            "managedIndexEnabled": bool(self.managed_index_root),
            "strictIndex": self.strict_index,
            "vectorStore": self.vector_store,
            "retrievalTopK": self.retrieval_top_k,
            "embeddingProvider": self.embedding_provider,
            "embeddingModel": self.embedding_model,
            "embeddingModelPath": model_path_status,
            "embeddingImpl": self.embedding_impl,
            "embeddingDevice": self.embedding_device,
            "embeddingAllowRemote": self.embedding_allow_remote,
            "warmupEnabled": self.warmup_enabled,
            "cpuThreads": self.cpu_threads,
            "reranker": {
                "enabled": self.reranker_enabled,
                "model": self.reranker_model,
                "modelPath": reranker_path_status,
                "device": self.reranker_device,
                "candidateK": self.reranker_candidate_k,
                "finalK": self.reranker_final_k,
                "latencyBudgetMs": self.reranker_latency_budget_ms,
                "warmupEnabled": self.reranker_warmup_enabled,
            },
        }


class Settings(BaseModel):
    service_name: str = "E-Review Agent AI Service"
    api_prefix: str = "/api/v1"
    default_port: int = 8008
    cases_path: str = "data/review_cases.json"
    agent_framework_provider: str = "langgraph"

    @property
    def agent_framework_enabled(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_ENABLED", False)

    @property
    def agent_framework_fallback_enabled(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_FALLBACK_ENABLED", True)

    @property
    def agent_framework_require_api_key(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_REQUIRE_API_KEY", False)

    @property
    def agentic_workflow_enabled(self) -> bool:
        return _env_bool("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", False)

    @property
    def agentic_max_iterations(self) -> int:
        return _env_int("E_REVIEW_AGENTIC_MAX_ITERATIONS", 2, minimum=1, maximum=3)

    @property
    def agentic_memory_enabled(self) -> bool:
        return _env_bool("E_REVIEW_AGENTIC_MEMORY_ENABLED", True)

    @property
    def agentic_memory_recent_turns(self) -> int:
        return _env_int("E_REVIEW_AGENTIC_MEMORY_RECENT_TURNS", 2, minimum=1, maximum=8)

    @property
    def agentic_memory_max_context_tokens(self) -> int:
        return _env_int("E_REVIEW_AGENTIC_MEMORY_MAX_CONTEXT_TOKENS", 800, minimum=128, maximum=8192)

    @property
    def agentic_checkpoint_enabled(self) -> bool:
        # Opt in so existing stateless callers keep their historical semantics.
        return _env_bool("E_REVIEW_AGENTIC_CHECKPOINT_ENABLED", False)

    @property
    def agentic_checkpoint_dir(self) -> str:
        return _env_str("E_REVIEW_AGENTIC_CHECKPOINT_DIR", "data/workflow_checkpoints")

    @property
    def langfuse_enabled(self) -> bool:
        return _env_bool("LANGFUSE_ENABLED", False)

    @property
    def langfuse_host(self) -> str:
        return _env_str("LANGFUSE_HOST", _env_str("LANGFUSE_BASE_URL", ""))

    @property
    def langfuse_environment(self) -> str:
        return _env_str("LANGFUSE_ENVIRONMENT", "local")

    @property
    def langfuse_release(self) -> str:
        return _env_str("LANGFUSE_RELEASE", "")

    @property
    def langfuse_service_name(self) -> str:
        return _env_str("OTEL_SERVICE_NAME", "e-review-ai-service")

    @property
    def langfuse_sample_rate(self) -> float:
        try:
            return min(1.0, max(0.0, float(_env_str("LANGFUSE_SAMPLE_RATE", "1.0"))))
        except ValueError:
            return 1.0

    @property
    def intent_router_provider(self) -> str:
        return _env_str("E_REVIEW_AGENTIC_INTENT_ROUTER_PROVIDER", "rule").lower()

    @property
    def intent_router_model(self) -> str:
        return _env_str("E_REVIEW_AGENTIC_INTENT_ROUTER_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

    @property
    def intent_router_timeout_ms(self) -> int:
        return _env_int("E_REVIEW_AGENTIC_INTENT_ROUTER_TIMEOUT_MS", 3000, minimum=1000, maximum=30000)

    @property
    def intent_router_rule_enhancements_enabled(self) -> bool:
        return _env_bool("E_REVIEW_AGENTIC_ROUTER_RULE_ENHANCEMENTS_ENABLED", True)

    @property
    def high_risk_safety_gate_enabled(self) -> bool:
        return _env_bool("E_REVIEW_HIGH_RISK_SAFETY_GATE_ENABLED", True)

    @property
    def fast_eligibility_shadow_enabled(self) -> bool:
        return _env_bool("E_REVIEW_FAST_ELIGIBILITY_SHADOW_ENABLED", False)

    @property
    def fast_eligibility_shadow_policy_path(self) -> str:
        return _env_str(
            "E_REVIEW_FAST_ELIGIBILITY_SHADOW_POLICY_PATH",
            "artifacts/step213h_fast_eligibility_gate/fast_eligibility_policy_v1.json",
        )

    @property
    def fast_eligibility_shadow_output_dir(self) -> str:
        return _env_str(
            "E_REVIEW_FAST_ELIGIBILITY_SHADOW_OUTPUT_DIR",
            "artifacts/step214_fast_eligibility_shadow",
        )

    @property
    def fast_eligibility_shadow_report_path(self) -> str:
        return _env_str(
            "E_REVIEW_FAST_ELIGIBILITY_SHADOW_REPORT_PATH",
            "../docs/FAST_ELIGIBILITY_SHADOW_REPORT.md",
        )

    @property
    def fast_eligibility_runtime_enabled(self) -> bool:
        return _env_bool("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED", False)

    @property
    def fast_eligibility_runtime_canary_percent(self) -> int:
        return _env_int("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_CANARY_PERCENT", 100, minimum=0, maximum=100)

    @property
    def fast_eligibility_runtime_policy_path(self) -> str:
        return _env_str(
            "E_REVIEW_FAST_ELIGIBILITY_RUNTIME_POLICY_PATH",
            "artifacts/step213h_fast_eligibility_gate/fast_eligibility_policy_v1.json",
        )

    @property
    def human_review_enabled(self) -> bool:
        return _env_bool("E_REVIEW_HUMAN_REVIEW_ENABLED", True)

    @property
    def policy_evidence_display_enabled(self) -> bool:
        return _env_bool("E_REVIEW_POLICY_EVIDENCE_DISPLAY_ENABLED", True)

    @property
    def policy_rag(self) -> PolicyRagSettings:
        return PolicyRagSettings.from_env()

    @property
    def openai_api_key_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()
