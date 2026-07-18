import json
from pathlib import Path
from typing import Dict, Optional

from app.rag_v2.config import RagV2Config, load_config
from app.rag_v2.corpus_loader import case_text, load_cases, load_jsonl
from app.rag_v2.dense_encoder import BgeM3Encoder
from app.rag_v2.evaluator import evaluate_queries
from app.rag_v2.faiss_store import FaissVectorStore
from app.rag_v2.hybrid_retriever import HybridRetriever
from app.rag_v2.reranker import NeuralReranker, RuleReranker
from app.rag_v2.tfidf_retriever import TfidfRetriever


class RagV2Service:
    def __init__(self, config: Optional[RagV2Config] = None):
        self.config = config or load_config()
        self.cases = load_cases(self.config.corpus_path) if self.config.corpus_path.exists() else []
        self.tfidf = TfidfRetriever(self.cases)
        self.encoder = BgeM3Encoder(
            self.config.embedding_model_dir, self.config.embedding_device, self.config.embedding_batch_size,
            self.config.embedding_normalize, self.config.embedding_max_length,
        )
        self.store = FaissVectorStore(self.config.index_path, self.config.meta_path)
        self.rule_reranker = RuleReranker()
        self.neural_reranker = NeuralReranker(
            self.config.reranker_model_dir, self.config.reranker_device, self.config.reranker_batch_size
        )
        self.retriever = HybridRetriever(
            self.cases, self.tfidf, self.encoder, self.store, self.rule_reranker, self.neural_reranker,
            {"alpha": self.config.alpha, "beta": self.config.beta, "gamma": self.config.gamma, "delta": self.config.delta},
            self.config.candidate_k,
        )

    def status(self) -> Dict:
        metadata = {}
        if self.config.meta_path.exists():
            try:
                metadata = json.loads(self.config.meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                metadata = {}
        eval_root = Path(__file__).resolve().parents[3] / "data/rag/eval"
        evaluation = self._read_json(eval_root / "rag_eval_results.json")
        downstream = self._read_json(eval_root / "qwen_rag_downstream_results.json")
        failures = []
        failure_path = eval_root / "rag_eval_failures.jsonl"
        if failure_path.exists():
            try:
                failures = [json.loads(line) for line in failure_path.read_text(encoding="utf-8").splitlines() if line.strip()][:20]
            except (json.JSONDecodeError, OSError):
                failures = []
        return {
            "corpus_size": len(self.cases), "index_available": self.store.available,
            "embedding_provider": self.config.embedding_provider, "embedding_model": self.config.embedding_model,
            "embedding_model_available": self.encoder.available,
            "reranker_provider": self.config.reranker_provider,
            "reranker_model": self.config.reranker_model,
            "reranker_model_available": self.neural_reranker.available,
            "device": self.config.embedding_device, "strategy": self.config.strategy, "top_k": self.config.top_k,
            "index_version": metadata.get("index_version"), "load_error_summary": None,
            "evaluation_metrics": evaluation.get("metrics") or {},
            "downstream_comparison": downstream.get("groups") or {},
            "failure_queries": failures,
        }

    @staticmethod
    def _read_json(path: Path) -> Dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def search(self, request: Dict) -> Dict:
        result = self.retriever.search(request)
        result["embedding_provider"] = self.config.embedding_provider
        return result

    def build_index(self) -> Dict:
        if not self.cases:
            raise RuntimeError("RAG_CORPUS_NOT_AVAILABLE")
        vectors = self.encoder.encode_documents([case_text(row) for row in self.cases])
        try:
            metadata = self.store.build(
                vectors, self.cases, self.config.embedding_model, int(vectors.shape[1])
            )
            metadata["embedding_latency_ms"] = self.encoder.last_latency_ms
            metadata["embedding_device"] = self.encoder.device
            self.config.meta_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        finally:
            self.encoder.unload()
        return metadata

    def evaluate(self, strategies) -> Dict:
        queries = load_jsonl(self.config.query_path)
        metrics = {strategy: evaluate_queries(self.retriever, queries, strategy, self.config.top_k) for strategy in strategies}
        passed = any(row["hit_at_3"] >= 0.80 and row["hit_at_5"] >= 0.90 and row["empty_retrieval_rate"] <= 0.10 for row in metrics.values())
        return {"marker": "HYBRID_RAG_EVAL_PASS" if passed else "HYBRID_RAG_EVAL_FAIL", "metrics": metrics}


_SERVICE: Optional[RagV2Service] = None


def rag_v2_service() -> RagV2Service:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RagV2Service()
    return _SERVICE
