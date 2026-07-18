import time
from typing import Dict, List, Optional

from app.rag_v2.corpus_loader import case_text
from app.rag_v2.dense_encoder import BgeM3Encoder
from app.rag_v2.faiss_store import FaissVectorStore
from app.rag_v2.reranker import NeuralReranker, RuleReranker
from app.rag_v2.tfidf_retriever import TfidfRetriever


def normalize(values: Dict[str, float]) -> Dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if high <= low:
        return {key: (1.0 if high > 0 else 0.0) for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


class HybridRetriever:
    def __init__(self, cases: List[Dict], tfidf: TfidfRetriever, encoder: BgeM3Encoder,
                 store: FaissVectorStore, rule_reranker: RuleReranker,
                 neural_reranker: Optional[NeuralReranker], weights: Dict[str, float], candidate_k: int = 20):
        self.cases = cases
        self.case_map = {row["case_id"]: row for row in cases}
        self.tfidf = tfidf
        self.encoder = encoder
        self.store = store
        self.rule_reranker = rule_reranker
        self.neural_reranker = neural_reranker
        self.weights = weights
        self.candidate_k = candidate_k

    def search(self, request: Dict) -> Dict:
        started = time.perf_counter()
        query = (request.get("query_text") or "").strip()
        strategy = request.get("strategy") or "hybrid_rerank"
        top_k = int(request.get("top_k") or 5)
        if not query:
            return self._response(query, strategy, [], 0, started, "none", False)
        lexical = self.tfidf.search(query, self.candidate_k)
        dense: List[Dict] = []
        dense_failed = False
        if strategy in {"dense", "hybrid", "hybrid_rerank"}:
            try:
                vector = self.encoder.encode_queries([query])[0]
                dense = self.store.search(vector, self.candidate_k)
            except (RuntimeError, FileNotFoundError, ValueError):
                dense_failed = True
                if strategy == "dense":
                    return self._response(query, strategy, [], 0, started, "none", True)
        if strategy == "tfidf":
            candidates = lexical
        elif strategy == "dense":
            candidates = dense
        else:
            candidates = self._merge(lexical, dense)
        reranker_name = "none"
        if strategy == "hybrid_rerank" and candidates:
            reranker = self.neural_reranker if self.neural_reranker and self.neural_reranker.available else self.rule_reranker
            reranker_name = reranker.provider
            try:
                candidates, _ = reranker.rerank(request, candidates)
            except (RuntimeError, ImportError):
                candidates, _ = self.rule_reranker.rerank(request, candidates)
                reranker_name = "rule_fallback"
        candidates = self._score(candidates, request, strategy)
        return self._response(query, strategy, candidates[:top_k], len(candidates), started, reranker_name, dense_failed)

    def _merge(self, lexical: List[Dict], dense: List[Dict]) -> List[Dict]:
        merged: Dict[str, Dict] = {}
        for row in lexical + dense:
            case_id = row["case_id"]
            merged.setdefault(case_id, dict(self.case_map[case_id]))
            merged[case_id].update({key: value for key, value in row.items() if key in {"lexical_score", "dense_score"}})
        return list(merged.values())

    def _score(self, candidates: List[Dict], request: Dict, strategy: str) -> List[Dict]:
        lexical = normalize({row["case_id"]: float(row.get("lexical_score") or 0) for row in candidates})
        dense = normalize({row["case_id"]: float(row.get("dense_score") or 0) for row in candidates})
        rerank = normalize({row["case_id"]: float(row.get("rerank_score") or 0) for row in candidates})
        output = []
        for row in candidates:
            item = dict(row)
            case_id = item["case_id"]
            metadata = sum([
                0.45 if request.get("risk_type") and request.get("risk_type") == item.get("risk_type") else 0,
                0.30 if request.get("risk_level") and request.get("risk_level") == item.get("risk_level") else 0,
                0.25 if request.get("product_category") and request.get("product_category") == item.get("product_category") else 0,
            ])
            item["lexical_score"] = round(lexical.get(case_id, 0.0), 6)
            item["dense_score"] = round(dense.get(case_id, 0.0), 6)
            item["rerank_score"] = round(rerank.get(case_id, 0.0), 6)
            item["metadata_match_score"] = round(metadata, 6)
            if strategy == "tfidf":
                final = item["lexical_score"]
            elif strategy == "dense":
                final = item["dense_score"]
            else:
                final = (self.weights["alpha"] * item["lexical_score"] + self.weights["beta"] * item["dense_score"] +
                         self.weights["gamma"] * item["rerank_score"] + self.weights["delta"] * metadata)
            item["final_score"] = round(final, 6)
            item.setdefault("evidence_overlap", 0.0)
            output.append(item)
        output.sort(key=lambda row: row["final_score"], reverse=True)
        for rank, row in enumerate(output, start=1):
            row["rank"] = rank
        return output

    @staticmethod
    def _response(query: str, strategy: str, hits: List[Dict], candidate_count: int,
                  started: float, reranker: str, fallback: bool) -> Dict:
        return {
            "query_summary": query[:160], "strategy": strategy, "candidate_count": candidate_count,
            "hit_count": len(hits), "top_score": float(hits[0]["final_score"]) if hits else 0.0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "reranker_provider": reranker, "fallback_used": fallback, "hits": hits,
        }
