import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class RagV2Config:
    enabled: bool
    strategy: str
    top_k: int
    candidate_k: int
    alpha: float
    beta: float
    gamma: float
    delta: float
    corpus_path: Path
    query_path: Path
    index_path: Path
    meta_path: Path
    embedding_provider: str
    embedding_model: str
    embedding_model_dir: Path
    embedding_device: str
    embedding_batch_size: int
    embedding_normalize: bool
    embedding_max_length: int
    reranker_provider: str
    reranker_model: str
    reranker_model_dir: Path
    reranker_device: str
    reranker_batch_size: int


def load_config() -> RagV2Config:
    model_parent = ROOT.parent / "models"
    return RagV2Config(
        enabled=_bool("E_REVIEW_RAG_V2_ENABLED", False),
        strategy=os.getenv("E_REVIEW_RAG_V2_STRATEGY", "hybrid_rerank"),
        top_k=_int("E_REVIEW_RAG_TOP_K", 5),
        candidate_k=_int("E_REVIEW_RAG_CANDIDATE_K", 20),
        alpha=_float("E_REVIEW_RAG_ALPHA", 0.30),
        beta=_float("E_REVIEW_RAG_BETA", 0.40),
        gamma=_float("E_REVIEW_RAG_GAMMA", 0.20),
        delta=_float("E_REVIEW_RAG_DELTA", 0.10),
        corpus_path=Path(os.getenv("E_REVIEW_RAG_CASES_PATH", str(ROOT / "data/rag/cases/risk_cases_240.jsonl"))),
        query_path=Path(os.getenv("E_REVIEW_RAG_GOLDEN_PATH", str(ROOT / "data/rag/golden_queries/golden_queries_80.jsonl"))),
        index_path=Path(os.getenv("E_REVIEW_RAG_INDEX_PATH", str(ROOT / "data/rag/index/risk_cases_bge_m3.faiss"))),
        meta_path=Path(os.getenv("E_REVIEW_RAG_META_PATH", str(ROOT / "data/rag/index/risk_cases_bge_m3_meta.json"))),
        embedding_provider=os.getenv("E_REVIEW_EMBEDDING_PROVIDER", "bge_m3"),
        embedding_model="BAAI/bge-m3",
        embedding_model_dir=Path(os.getenv("E_REVIEW_BGE_M3_MODEL_DIR", str(model_parent / "bge-m3"))),
        embedding_device=os.getenv("E_REVIEW_EMBEDDING_DEVICE", "cuda"),
        embedding_batch_size=_int("E_REVIEW_EMBEDDING_BATCH_SIZE", 16),
        embedding_normalize=_bool("E_REVIEW_EMBEDDING_NORMALIZE", True),
        embedding_max_length=_int("E_REVIEW_EMBEDDING_MAX_LENGTH", 512),
        reranker_provider=os.getenv("E_REVIEW_RERANKER_PROVIDER", "neural"),
        reranker_model=os.getenv("E_REVIEW_RERANKER_MODEL", "BAAI/bge-reranker-base"),
        reranker_model_dir=Path(os.getenv("E_REVIEW_RERANKER_MODEL_DIR", str(model_parent / "rag-reranker"))),
        reranker_device=os.getenv("E_REVIEW_RERANKER_DEVICE", "cuda"),
        reranker_batch_size=_int("E_REVIEW_RERANKER_BATCH_SIZE", 8),
    )
