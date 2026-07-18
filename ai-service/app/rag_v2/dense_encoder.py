import time
from pathlib import Path
from typing import List, Optional

import numpy as np


class BgeM3Encoder:
    def __init__(self, model_dir: Path, device: str = "cuda", batch_size: int = 16,
                 normalize: bool = True, max_length: int = 512):
        self.model_dir = Path(model_dir)
        self.requested_device = device
        self.batch_size = batch_size
        self.normalize = normalize
        self.max_length = max_length
        self.tokenizer = None
        self.model = None
        self.device = None
        self.dimension: Optional[int] = None
        self.last_latency_ms = 0.0

    @property
    def available(self) -> bool:
        weights = [self.model_dir / name for name in ("model.safetensors", "pytorch_model.bin")]
        return (
            self.model_dir.is_dir()
            and (self.model_dir / "config.json").exists()
            and any(path.exists() and path.stat().st_size > 2_200_000_000 for path in weights)
        )

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def _load(self) -> None:
        if self.loaded:
            return
        if not self.available:
            raise RuntimeError("BGE_M3_NOT_AVAILABLE")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("BGE_M3_DEPENDENCY_NOT_AVAILABLE") from exc
        use_cuda = self.requested_device == "cuda" and torch.cuda.is_available()
        self.device = "cuda" if use_cuda else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(self.model_dir), local_files_only=True)
        self.model.eval().to(self.device)
        self.dimension = int(getattr(self.model.config, "hidden_size", 0)) or None

    def _encode(self, texts: List[str]) -> np.ndarray:
        self._load()
        import torch

        started = time.perf_counter()
        vectors = []
        with torch.inference_mode():
            for offset in range(0, len(texts), self.batch_size):
                batch = texts[offset: offset + self.batch_size]
                tokens = self.tokenizer(batch, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
                tokens = {key: value.to(self.device) for key, value in tokens.items()}
                hidden = self.model(**tokens).last_hidden_state[:, 0]
                if self.normalize:
                    hidden = torch.nn.functional.normalize(hidden, p=2, dim=1)
                vectors.append(hidden.float().cpu().numpy())
        self.last_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if not vectors:
            return np.empty((0, self.dimension or 0), dtype="float32")
        result = np.concatenate(vectors).astype("float32")
        self.dimension = int(result.shape[1])
        return result

    def encode_documents(self, texts: List[str]) -> np.ndarray:
        return self._encode([str(text) for text in texts])

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        return self._encode([str(text) for text in texts])

    def unload(self) -> None:
        self.tokenizer = None
        self.model = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
