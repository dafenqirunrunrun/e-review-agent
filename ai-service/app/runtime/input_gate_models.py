from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SemanticInputResult:
    category: str
    confidence: float
    provider: str
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class InjectionScanResult:
    detected: bool
    score: float
    provider: str
    status: str = "ready"


_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "CHAT": (
        "你好，今天过得怎么样",
        "こんにちは、元気ですか",
        "Hello, how are you today?",
        "안녕하세요 반가워요",
    ),
    "OUT_OF_SCOPE": (
        "给我讲个笑话",
        "今天天气怎么样",
        "Write a poem for me",
        "Explain a business or technical concept to me",
        "How do I reset my account password?",
        "Help me write Python code",
        "今日の天気を教えて",
        "アカウントのパスワードをリセットする方法を教えて",
        "제품 관리라는 개념을 설명해 주세요",
    ),
    "GIBBERISH": (
        "大会第哦啊四大行",
        "asdf qwer zxcv",
        "啊的呀得额嗯额",
        "意味のない文字列です",
    ),
    "REVIEW": (
        "这个商品很好用，物流也很快",
        "The product works well but delivery was slow",
        "この商品は使いやすいですが配送が遅いです",
        "제품은 괜찮지만 배송이 느렸습니다",
    ),
    "GOVERNANCE_QUERY": (
        "商家要求五星好评截图返现",
        "The seller paid customers to post five-star reviews",
        "販売者が星5のレビューと引き換えに返金を約束した",
        "배터리가 부풀고 충전 중에 연기가 났습니다",
    ),
}


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


class MultilingualPrototypeClassifier:
    """Small semantic helper backed by the existing local Qwen embedding model."""

    def __init__(self) -> None:
        self.enabled = _enabled("E_REVIEW_INPUT_GATE_SEMANTIC_ENABLED")
        self._lock = threading.Lock()
        self._provider: Any = None
        self._prototype_matrix: np.ndarray | None = None
        self._prototype_categories: list[str] = []

    def classify(self, text: str) -> SemanticInputResult:
        if not self.enabled:
            return SemanticInputResult("UNCERTAIN", 0.0, "disabled")
        try:
            self._ensure_loaded()
            query = self._provider.embed_documents([text])[0]
            similarities = self._prototype_matrix @ query
            scores: dict[str, float] = {}
            for category in _PROTOTYPES:
                values = [
                    float(similarities[index])
                    for index, item_category in enumerate(self._prototype_categories)
                    if item_category == category
                ]
                scores[category] = max(values) if values else -1.0
            ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            category, top_score = ordered[0]
            margin = top_score - ordered[1][1]
            confidence = max(0.0, min(1.0, (top_score + 1.0) / 2.0 + max(0.0, margin) * 0.5))
            return SemanticInputResult(category, round(confidence, 4), "qwen3_embedding_prototypes", scores)
        except Exception:
            return SemanticInputResult("UNCERTAIN", 0.0, "semantic_unavailable")

    def _ensure_loaded(self) -> None:
        if self._provider is not None and self._prototype_matrix is not None:
            return
        with self._lock:
            if self._provider is not None and self._prototype_matrix is not None:
                return
            from app.policy_rag.embedding import create_policy_embedding_provider

            provider = create_policy_embedding_provider()
            texts: list[str] = []
            categories: list[str] = []
            for category, examples in _PROTOTYPES.items():
                texts.extend(examples)
                categories.extend([category] * len(examples))
            self._provider = provider
            self._prototype_matrix = provider.embed_documents(texts)
            self._prototype_categories = categories


class LocalDuoGuardScanner:
    """Optional local jailbreak detector. Errors degrade to the conservative long path."""

    JAILBREAK_INDEX = 11

    def __init__(self) -> None:
        self.enabled = _enabled("E_REVIEW_INPUT_GATE_GUARD_ENABLED")
        self.model_path = os.getenv("E_REVIEW_INPUT_GATE_GUARD_MODEL_PATH", "").strip()
        self.device = os.getenv("E_REVIEW_INPUT_GATE_GUARD_DEVICE", "cpu").strip() or "cpu"
        self.threshold = float(os.getenv("E_REVIEW_INPUT_GATE_GUARD_THRESHOLD", "0.5"))
        self._lock = threading.Lock()
        self._tokenizer: Any = None
        self._model: Any = None

    def scan(self, text: str) -> InjectionScanResult:
        if not self.enabled:
            return InjectionScanResult(False, 0.0, "disabled", "disabled")
        try:
            self._ensure_loaded()
            import torch

            tokens = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            tokens = {key: value.to(self.device) for key, value in tokens.items()}
            with torch.inference_mode():
                logits = self._model(**tokens).logits[0]
                score = float(torch.sigmoid(logits)[self.JAILBREAK_INDEX].detach().cpu())
            return InjectionScanResult(score >= self.threshold, round(score, 4), "duoguard_0_5b")
        except Exception as exc:
            return InjectionScanResult(False, 0.0, "duoguard_unavailable", type(exc).__name__)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            if not self.model_path or not Path(self.model_path).exists():
                raise FileNotFoundError("DUOGUARD_MODEL_PATH_MISSING")
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path,
                local_files_only=True,
                torch_dtype=torch.float32 if self.device == "cpu" else "auto",
            ).to(self.device)
            model.eval()
            self._tokenizer = tokenizer
            self._model = model
