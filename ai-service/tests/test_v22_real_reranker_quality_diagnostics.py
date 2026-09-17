from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.reranker import LocalModelReranker, RerankerConfig


ROOT = Path(__file__).resolve().parents[2]


PAIRS = [
    ("refund fraud signed delivery dispute", "Signed logistics proof contradicts the buyer's no-receipt refund claim.", "The package color option is available in blue and green."),
    ("after sales broken screen complaint", "After-sales policy requires photo evidence for a broken screen complaint.", "The user changed the nickname last month."),
    ("counterfeit product authenticity risk", "Authenticity risk is high when the label and serial number do not match.", "Holiday shipping may be slower than usual."),
    ("seller harassment abusive message", "The review reports abusive seller messages after a refund request.", "The product page uses a white background."),
    ("private phone number leaked in review", "The review includes a phone number and should be masked before display.", "The size chart is measured in centimeters."),
    ("medical safety allergy reaction", "A buyer reports an allergy reaction and safety concern after use.", "The coupon expires at midnight."),
    ("fake positive review incentive", "The text mentions a gift card offered in exchange for a positive review.", "The warehouse sorted inventory on Tuesday."),
    ("image text conflict damaged item", "The image shows damage while the text claims the item is perfect.", "The navigation bar contains three menu items."),
    ("low confidence ambiguous complaint", "The complaint is vague and should be routed to human review.", "The product supports multiple languages."),
    ("refund abuse repeated claims", "Repeated refund claims without matching evidence indicate potential abuse.", "The brand story appears in the footer."),
    ("food safety expired product", "The customer reports receiving an expired food product.", "The display brightness can be adjusted."),
    ("battery overheating safety risk", "Battery overheating during charging is a serious safety risk.", "The manual has twenty pages."),
    ("wrong item received after order", "The buyer received a different item than the order record shows.", "The store banner changed this week."),
    ("personal address exposed", "The review exposes a personal delivery address and needs redaction.", "The default theme is light mode."),
    ("threatening seller response", "The seller response contains threats after a negative review.", "The payment page has a back button."),
    ("missing accessory complaint", "The customer reports missing accessories shown in the product listing.", "The app supports landscape screenshots."),
    ("warranty refusal evidence", "Warranty refusal conflicts with the documented coverage period.", "The font size is sixteen pixels."),
    ("quality defect batch issue", "Several reviews describe the same quality defect in one production batch.", "The homepage carousel has four images."),
    ("unsafe toy sharp edge", "The toy has a sharp edge that may injure children.", "The newsletter is sent every Friday."),
    ("logistics signature conflict", "Signed delivery evidence conflicts with the buyer's lost package claim.", "The color palette uses neutral gray."),
]


def _asset_model_path() -> str:
    direct = os.getenv("RAG_RERANKER_MODEL_PATH", "").strip()
    if direct:
        return direct
    manifest_path = os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", "").strip()
    if not manifest_path:
        pytest.skip("V22_ASSET_MANIFEST_UNAVAILABLE_SKIP")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    model_path = str((manifest.get("reranker") or {}).get("modelPath") or "")
    if not model_path:
        pytest.skip("RERANKER_MODEL_ASSET_UNAVAILABLE_SKIP")
    return model_path


def _candidate(chunk_id: str, content: str, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(
        retrieverType="fixture",
        tenantId="tenant-a",
        documentId=f"doc-{chunk_id}",
        chunkId=chunk_id,
        sparseScore=1.0 / rank,
        sparseRank=rank,
        rawRank=rank,
        fusionScore=1.0 / rank,
        fusionRank=rank,
        row={
            "tenant_id": "tenant-a",
            "document_id": f"doc-{chunk_id}",
            "chunk_id": chunk_id,
            "content": content,
            "content_hash": f"{chunk_id}abc123contenthash",
            "source_type": "policy",
            "title": f"Diagnostic {chunk_id}",
            "active": True,
            "deleted": False,
        },
    )


def _config(*, normalize: bool) -> RerankerConfig:
    return RerankerConfig(
        requested_type="local-model",
        model_path=_asset_model_path(),
        model_name="BAAI/bge-reranker-v2-m3",
        device=os.getenv("RAG_RERANKER_DEVICE", "cuda"),
        use_fp16=os.getenv("RAG_RERANKER_USE_FP16", "true").lower() == "true",
        batch_size=4,
        max_length=384,
        candidate_k=2,
        final_k=2,
        timeout_ms=60000,
        real_required=True,
        provider_impl="flagembedding",
        normalize=normalize,
        model_id="BAAI/bge-reranker-v2-m3",
        model_revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
    )


@pytest.mark.real_reranker
@pytest.mark.requires_model_asset
def test_v22_real_reranker_score_direction_and_normalized_order():
    pytest.importorskip("FlagEmbedding")
    raw_reranker = LocalModelReranker(_config(normalize=False))
    normalized_reranker = LocalModelReranker(_config(normalize=True))
    raw_positive_wins = 0
    normalized_positive_wins = 0
    order_mismatches: list[str] = []

    for index, (query, positive, negative) in enumerate(PAIRS):
        candidates = [
            _candidate(f"p{index:02d}", positive, 1),
            _candidate(f"n{index:02d}", negative, 2),
        ]
        raw = raw_reranker.rerank(query, candidates, top_k=2, tenant_id="tenant-a")
        normalized = normalized_reranker.rerank(query, candidates, top_k=2, tenant_id="tenant-a")
        assert raw.effectiveType == "local-model"
        assert normalized.effectiveType == "local-model"
        assert raw.fallbackUsed is False
        assert normalized.fallbackUsed is False
        assert all(math.isfinite(score) for score in raw.scores + normalized.scores)
        if raw.candidates[0].chunkId.startswith("p"):
            raw_positive_wins += 1
        if normalized.candidates[0].chunkId.startswith("p"):
            normalized_positive_wins += 1
        if [item.chunkId for item in raw.candidates] != [item.chunkId for item in normalized.candidates]:
            order_mismatches.append(query)

    assert raw_positive_wins >= 18
    assert normalized_positive_wins >= 18
    assert order_mismatches == []


@pytest.mark.real_reranker
@pytest.mark.requires_model_asset
def test_v22_real_reranker_flagembedding_transformers_parity():
    pytest.importorskip("FlagEmbedding")
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    model_path = _asset_model_path()
    pair_inputs = [(query, passage) for query, positive, negative in PAIRS[:15] for passage in (positive, negative)]

    from FlagEmbedding import FlagReranker

    flag = FlagReranker(model_path, use_fp16=True)
    flag_scores = [float(value) for value in flag.compute_score(pair_inputs, batch_size=4, max_length=384, normalize=False)]

    tokenizer = transformers.AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = transformers.AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    if torch.cuda.is_available():
        model = model.to("cuda")
    model.eval()
    hf_scores: list[float] = []
    with torch.no_grad():
        for start in range(0, len(pair_inputs), 4):
            batch = pair_inputs[start : start + 4]
            inputs = tokenizer(
                [item[0] for item in batch],
                [item[1] for item in batch],
                padding=True,
                truncation=True,
                max_length=384,
                return_tensors="pt",
            )
            if torch.cuda.is_available():
                inputs = {key: value.to("cuda") for key, value in inputs.items()}
            logits = model(**inputs).logits.reshape(-1)
            hf_scores.extend(float(value) for value in logits.detach().cpu())

    assert len(flag_scores) == len(hf_scores) == len(pair_inputs)
    assert all(math.isfinite(score) for score in flag_scores + hf_scores)
    assert _spearman(flag_scores, hf_scores) >= 0.999
    assert _top_order(flag_scores, 10) == _top_order(hf_scores, 10)


def _top_order(values: list[float], top_k: int) -> list[int]:
    return sorted(range(len(values)), key=lambda index: (-values[index], index))[:top_k]


def _spearman(left: list[float], right: list[float]) -> float:
    left_ranks = _ranks(left)
    right_ranks = _ranks(right)
    mean_left = sum(left_ranks) / len(left_ranks)
    mean_right = sum(right_ranks) / len(right_ranks)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left_ranks, right_ranks, strict=True))
    left_den = math.sqrt(sum((a - mean_left) ** 2 for a in left_ranks))
    right_den = math.sqrt(sum((b - mean_right) ** 2 for b in right_ranks))
    return numerator / (left_den * right_den)


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = (index + 1 + end) / 2
        for original_index, _ in ordered[index:end]:
            ranks[original_index] = average
        index = end
    return ranks
