"""Deterministic evaluation contracts for document ingestion and policy RAG."""

from app.rag_quality.contract import METRIC_CONTRACT_VERSION, metric_contract
from app.rag_quality.evaluator import evaluate_retrieval_run

__all__ = ["METRIC_CONTRACT_VERSION", "evaluate_retrieval_run", "metric_contract"]
