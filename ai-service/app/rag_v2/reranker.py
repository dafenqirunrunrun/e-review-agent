import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def tokens(value: str) -> set:
    return set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", (value or "").lower()))


class RerankerBase(ABC):
    provider = "base"

    @abstractmethod
    def rerank(self, query: Dict, candidates: List[Dict]) -> Tuple[List[Dict], float]:
        raise NotImplementedError


class RuleReranker(RerankerBase):
    provider = "rule"

    def rerank(self, query: Dict, candidates: List[Dict]) -> Tuple[List[Dict], float]:
        started = time.perf_counter()
        query_tokens = tokens(query.get("query_text", ""))
        hard = set(query.get("hard_negative_case_ids") or [])
        output = []
        for candidate in candidates:
            case_tokens = tokens(" ".join([
                candidate.get("title", ""), candidate.get("scenario", ""),
                " ".join(candidate.get("evidence") or []), " ".join(candidate.get("tags") or []),
            ]))
            overlap = len(query_tokens & case_tokens) / max(1, len(query_tokens))
            score = 0.35 * overlap
            score += 0.25 if query.get("risk_type") and query.get("risk_type") == candidate.get("risk_type") else 0.0
            score += 0.15 if query.get("risk_level") and query.get("risk_level") == candidate.get("risk_level") else 0.0
            score += 0.15 if query.get("product_category") and query.get("product_category") == candidate.get("product_category") else 0.0
            evidence_hit = sum(1 for word in query.get("evidence_keywords") or [] if word and word in " ".join(candidate.get("evidence") or []))
            score += min(0.10, evidence_hit * 0.05)
            if candidate.get("case_id") in hard:
                score -= 0.25
            row = dict(candidate)
            row["evidence_overlap"] = round(overlap, 6)
            row["rerank_score"] = round(max(0.0, min(1.0, score)), 6)
            output.append(row)
        output.sort(key=lambda row: row["rerank_score"], reverse=True)
        return output, round((time.perf_counter() - started) * 1000, 2)


class NeuralReranker(RerankerBase):
    provider = "neural"

    def __init__(self, model_dir: Path, device: str = "cuda", batch_size: int = 8):
        self.model_dir = Path(model_dir)
        self.requested_device = device
        self.batch_size = batch_size
        self.tokenizer = None
        self.model = None
        self.device = None

    @property
    def available(self) -> bool:
        weights = [self.model_dir / name for name in ("model.safetensors", "pytorch_model.bin")]
        return (
            self.model_dir.is_dir()
            and (self.model_dir / "config.json").exists()
            and any(path.exists() and path.stat().st_size > 1_000_000_000 for path in weights)
        )

    def _load(self) -> None:
        if self.model is not None:
            return
        if not self.available:
            raise RuntimeError("NEURAL_RERANKER_NOT_AVAILABLE")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.device = "cuda" if self.requested_device == "cuda" and torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(str(self.model_dir), local_files_only=True)
        self.model.eval().to(self.device)

    def rerank(self, query: Dict, candidates: List[Dict]) -> Tuple[List[Dict], float]:
        self._load()
        import torch
        started = time.perf_counter()
        pairs = [(query.get("query_text", ""), str(row.get("scenario", ""))) for row in candidates]
        scores: List[float] = []
        with torch.inference_mode():
            for offset in range(0, len(pairs), self.batch_size):
                batch = pairs[offset: offset + self.batch_size]
                encoded = self.tokenizer(
                    [item[0] for item in batch], [item[1] for item in batch],
                    padding=True, truncation=True, max_length=512, return_tensors="pt",
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                logits = self.model(**encoded).logits.view(-1).float()
                scores.extend(torch.sigmoid(logits).cpu().tolist())
        output = []
        for row, score in zip(candidates, scores):
            item = dict(row)
            item["rerank_score"] = round(float(score), 6)
            output.append(item)
        output.sort(key=lambda row: row["rerank_score"], reverse=True)
        return output, round((time.perf_counter() - started) * 1000, 2)
