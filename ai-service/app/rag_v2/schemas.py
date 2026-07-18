from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Strategy = Literal["tfidf", "dense", "hybrid", "hybrid_rerank"]


class RagSearchRequest(BaseModel):
    query_text: str
    risk_type: Optional[str] = None
    risk_level: Optional[str] = None
    product_category: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    strategy: Strategy = "hybrid_rerank"
    hard_negative_case_ids: List[str] = []


class RetrievalHit(BaseModel):
    case_id: str
    rank: int
    final_score: float = 0.0
    lexical_score: float = 0.0
    dense_score: float = 0.0
    rerank_score: float = 0.0
    metadata_match_score: float = 0.0
    evidence_overlap: float = 0.0
    title: str
    risk_type: str
    risk_level: str
    evidence: List[str]
    operation_suggestion: str
    product_category: Optional[str] = None


class RagSearchResponse(BaseModel):
    query_summary: str
    strategy: str
    candidate_count: int
    hit_count: int
    top_score: float
    latency_ms: float
    embedding_provider: str
    reranker_provider: str
    fallback_used: bool
    hits: List[RetrievalHit]


class RagStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    corpus_size: int
    index_available: bool
    embedding_provider: str
    embedding_model: str
    embedding_model_available: bool
    reranker_provider: str
    reranker_model: str
    reranker_model_available: bool
    device: str
    strategy: str
    top_k: int
    index_version: Optional[str] = None
    load_error_summary: Optional[str] = None
    evaluation_metrics: Dict[str, object] = {}
    downstream_comparison: Dict[str, object] = {}
    failure_queries: List[Dict[str, object]] = []


class RagEvaluateRequest(BaseModel):
    strategies: List[Strategy] = ["tfidf", "dense", "hybrid", "hybrid_rerank"]


class RagEvaluateResponse(BaseModel):
    marker: str
    metrics: Dict[str, Dict[str, object]]
