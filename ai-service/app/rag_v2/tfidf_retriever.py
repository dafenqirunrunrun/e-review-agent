from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag_v2.corpus_loader import case_text


class TfidfRetriever:
    def __init__(self, cases: List[Dict]):
        self.cases = cases
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), min_df=1, sublinear_tf=True)
        self.matrix = None
        self.rebuild(cases)

    def rebuild(self, cases: List[Dict]) -> None:
        self.cases = list(cases)
        self.matrix = self.vectorizer.fit_transform([case_text(row) for row in self.cases]) if self.cases else None

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not query or not query.strip() or self.matrix is None:
            return []
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix)[0]
        indexes = scores.argsort()[::-1][: max(0, min(top_k, len(self.cases)))]
        results = []
        for rank, index in enumerate(indexes, start=1):
            row = dict(self.cases[int(index)])
            row.update(rank=rank, lexical_score=float(scores[index]))
            results.append(row)
        return results
