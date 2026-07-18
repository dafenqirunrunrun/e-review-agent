import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


class FaissVectorStore:
    def __init__(self, index_path: Path, meta_path: Path):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.index = None
        self.metadata: Dict = {}

    @property
    def available(self) -> bool:
        return self.index_path.exists() and self.meta_path.exists()

    def build(self, vectors: np.ndarray, cases: List[Dict], model_name: str, dimension: int) -> Dict:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
        if len(vectors) != len(cases):
            raise ValueError("FAISS_METADATA_VECTOR_COUNT_MISMATCH")
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != dimension:
            raise ValueError("FAISS_VECTOR_DIMENSION_MISMATCH")
        faiss.normalize_L2(matrix)
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(matrix)
        self.metadata = {
            "index_version": datetime.now(timezone.utc).strftime("bge-m3-%Y%m%dT%H%M%SZ"),
            "model_name": model_name,
            "dimension": dimension,
            "case_count": len(cases),
            "case_ids": [row["case_id"] for row in cases],
            "cases": cases,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "index_type": "IndexFlatIP",
            "normalized": True,
        }
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_bytes(faiss.serialize_index(self.index).tobytes())
        self.meta_path.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return self.metadata

    def load(self) -> Dict:
        if not self.available:
            raise RuntimeError("FAISS_INDEX_NOT_AVAILABLE")
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
        serialized = np.frombuffer(self.index_path.read_bytes(), dtype="uint8")
        self.index = faiss.deserialize_index(serialized)
        self.metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
        if self.index.ntotal != len(self.metadata.get("case_ids") or []):
            raise ValueError("FAISS_INDEX_METADATA_MISMATCH")
        return self.metadata

    def search(self, query_vector: np.ndarray, top_k: int) -> List[Dict]:
        if self.index is None:
            self.load()
        import faiss
        vector = np.asarray(query_vector, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vector)
        scores, indexes = self.index.search(vector, min(top_k, self.index.ntotal))
        rows = []
        cases = self.metadata.get("cases") or []
        for rank, (score, index) in enumerate(zip(scores[0], indexes[0]), start=1):
            if index < 0:
                continue
            row = dict(cases[int(index)])
            row.update(rank=rank, dense_score=float(score))
            rows.append(row)
        return rows
