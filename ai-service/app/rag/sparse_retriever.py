from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def tokenize(text: str, stopwords: set[str] | None = None) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    stops = stopwords or set()
    return [token for token in TOKEN_RE.findall(normalized) if token and token not in stops]


@dataclass(frozen=True)
class SparseHit:
    chunk_id: str
    document_id: str
    score: float
    rank: int
    explanation: dict[str, float]


class BM25Retriever:
    def __init__(self, chunks: list[dict], stopwords: set[str] | None = None, k1: float = 1.5, b: float = 0.75):
        self.stopwords = stopwords or set()
        self.k1 = k1
        self.b = b
        self.chunks = [row for row in chunks if row.get("active", True) and not row.get("deleted", False)]
        self.doc_tokens = [tokenize(str(row.get("content") or ""), self.stopwords) for row in self.chunks]
        self.avgdl = sum(len(tokens) for tokens in self.doc_tokens) / max(1, len(self.doc_tokens))
        self.df = self._df(self.doc_tokens)

    def search(
        self,
        query: str,
        top_k: int = 20,
        *,
        tenant_id: str | None = None,
        document_version: str | None = None,
        min_trust_level: str | None = None,
    ) -> list[SparseHit]:
        query_tokens = tokenize(query, self.stopwords)
        scored = []
        for row, tokens in zip(self.chunks, self.doc_tokens):
            if tenant_id and row.get("tenant_id") != tenant_id:
                continue
            if document_version and row.get("document_version") != document_version:
                continue
            if min_trust_level and row.get("trust_level") != min_trust_level:
                continue
            score, explanation = self._score(query_tokens, tokens)
            if score > 0:
                scored.append((score, row, explanation))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SparseHit(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                score=round(score, 6),
                rank=rank,
                explanation={key: round(value, 6) for key, value in explanation.items()},
            )
            for rank, (score, row, explanation) in enumerate(scored[:top_k], start=1)
        ]

    @staticmethod
    def _df(docs: Iterable[list[str]]) -> dict[str, int]:
        df: dict[str, int] = {}
        for tokens in docs:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        return df

    def _score(self, query_tokens: list[str], doc_tokens: list[str]) -> tuple[float, dict[str, float]]:
        if not query_tokens or not doc_tokens:
            return 0.0, {}
        freqs: dict[str, int] = {}
        for token in doc_tokens:
            freqs[token] = freqs.get(token, 0) + 1
        total = 0.0
        explanation = {}
        n_docs = max(1, len(self.doc_tokens))
        for token in query_tokens:
            tf = freqs.get(token, 0)
            if tf <= 0:
                continue
            idf = math.log(1 + (n_docs - self.df.get(token, 0) + 0.5) / (self.df.get(token, 0) + 0.5))
            denom = tf + self.k1 * (1 - self.b + self.b * len(doc_tokens) / max(1e-9, self.avgdl))
            contribution = idf * (tf * (self.k1 + 1)) / denom
            total += contribution
            explanation[token] = contribution
        return total, explanation
