from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import torch

from app.policy_rag.embedding import (
    QWEN3_OFFICIAL_RETRIEVAL_PROFILE,
    QwenEmbeddingConfig,
    QwenOfficialTransformersEmbeddingProvider,
)
from scripts.run_step233a_qwen_embedding_ab import make_candidate_index_portable


class RecordingTokenizer:
    def __init__(self):
        self.padding_side = "right"
        self.calls: list[dict] = []

    def __call__(self, batch, **kwargs):
        self.calls.append({"batch": list(batch), **kwargs})
        return {
            "input_ids": torch.ones((len(batch), 3), dtype=torch.long),
            "attention_mask": torch.ones((len(batch), 3), dtype=torch.long),
        }


class PositionModel:
    config = SimpleNamespace(hidden_size=4)

    def __call__(self, **tokens):
        batch = tokens["input_ids"].shape[0]
        hidden = torch.zeros((batch, 3, 4), dtype=torch.float32)
        hidden[:, 0, 0] = 1.0
        hidden[:, 1, 1] = 1.0
        hidden[:, 2, 2] = 1.0
        return SimpleNamespace(last_hidden_state=hidden)


def _provider() -> tuple[QwenOfficialTransformersEmbeddingProvider, RecordingTokenizer]:
    provider = QwenOfficialTransformersEmbeddingProvider(
        QwenEmbeddingConfig(batch_size=8, max_length=512),
        query_instruction="Retrieve policy clauses for review governance",
    )
    tokenizer = RecordingTokenizer()
    provider._tokenizer = tokenizer
    provider._model = PositionModel()
    return provider, tokenizer


def test_official_profile_separates_query_and_document_inputs():
    provider, tokenizer = _provider()

    documents = provider.embed_documents(["policy clause one", "policy clause two"])
    query = provider.embed_query("five-star cashback")

    assert tokenizer.padding_side == "left"
    assert tokenizer.calls[0]["batch"] == ["policy clause one", "policy clause two"]
    assert tokenizer.calls[1]["batch"] == [
        "Instruct: Retrieve policy clauses for review governance\nQuery:five-star cashback"
    ]
    assert all(call["max_length"] == 512 for call in tokenizer.calls)
    assert np.allclose(documents[:, 2], 1.0)
    assert np.allclose(query[:, 2], 1.0)


def test_official_profile_metadata_is_versioned_and_reproducible():
    provider, _ = _provider()
    provider.embed_query("paid review")

    metadata = provider.metadata()

    assert metadata["providerType"] == "qwen3-embedding-transformers-official-v2"
    assert metadata["embeddingProfile"] == QWEN3_OFFICIAL_RETRIEVAL_PROFILE
    assert metadata["pooling"] == "last-token"
    assert metadata["paddingSide"] == "left"
    assert metadata["queryInstructionApplied"] is True
    assert metadata["documentInstructionApplied"] is False
    assert len(metadata["queryInstructionHash"]) == 64
    assert len(metadata["modelFingerprint"]) == 32
    assert metadata["dimension"] == 4


def test_last_token_pool_supports_right_padded_inputs():
    hidden = torch.zeros((2, 4, 3), dtype=torch.float32)
    hidden[0, 1, 0] = 2.0
    hidden[1, 2, 1] = 3.0
    mask = torch.tensor([[1, 1, 0, 0], [1, 1, 1, 0]], dtype=torch.long)

    pooled = QwenOfficialTransformersEmbeddingProvider._last_token_pool(hidden, mask)

    assert pooled.tolist() == [[2.0, 0.0, 0.0], [0.0, 3.0, 0.0]]


def test_candidate_index_metadata_is_portable(tmp_path):
    metadata = {
        "status": "ready",
        "indexPath": r"D:\\private\\policy_vectors.faiss",
        "metaPath": r"D:\\private\\policy_vectors_meta.json",
        "provider": {"modelPath": r"D:\\private\\qwen", "modelName": "Qwen3"},
        "rows": [{"chunkId": "policy-1"}],
    }

    manifest = make_candidate_index_portable(tmp_path, metadata)
    persisted = json.loads((tmp_path / "policy_vectors_meta.json").read_text(encoding="utf-8"))

    assert manifest["indexPath"] == "policy_vectors.faiss"
    assert manifest["metaPath"] == "policy_vectors_meta.json"
    assert "rows" not in manifest
    assert "modelPath" not in manifest["provider"]
    assert persisted["rows"] == [{"chunkId": "policy-1"}]
