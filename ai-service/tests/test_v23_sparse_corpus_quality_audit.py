from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "ai-service" / "scripts" / "qualification"
for item in (ROOT / "ai-service", ROOT / "ai-service" / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_v23_sparse_corpus_quality_audit as dqa  # noqa: E402


class FakeTokenizer:
    def __call__(self, text: str, **_: object) -> dict[str, list[int]]:
        return {"input_ids": list(range(max(1, len(text.split()))))}


def make_chunk(text: str, *, content_hash: str | None = None, row_content: str | None = None) -> SimpleNamespace:
    row_value = text if row_content is None else row_content
    return SimpleNamespace(
        chunkId=dqa.stable_hash(text)[:24],
        documentId="doc-a",
        contentHash=content_hash or dqa.stable_hash(text),
        text=text,
        tenantId="tenant-a",
        sourceType="policy",
        sectionTitle="Refund rules",
        title="Refund rules",
        visibility="tenant",
        as_retriever_row=lambda: {"content": row_value, "text": row_value},
    )


def test_model_input_field_hash_passes_expected_content() -> None:
    payload = dqa.build_field_audit([make_chunk("customer refund rule should verify order")], FakeTokenizer())
    assert payload["gate"]["status"] == "PASS"
    assert payload["gate"]["expectedFieldUsedCount"] == 1


def test_wrong_field_detection_blocks_gate() -> None:
    payload = dqa.build_field_audit([make_chunk("customer refund rule", row_content="title only")], FakeTokenizer())
    assert payload["gate"]["status"] == "BLOCKED"
    assert payload["gate"]["sourceFieldReplacedCount"] == 1


def test_short_and_label_classification() -> None:
    label = dqa.quality_features("refund", 1)
    sentence = dqa.quality_features("customer should verify order before refund approval", 12)
    assert dqa.classify_chunk_quality(label) == "LABEL_OR_CATEGORY_VALUE"
    assert dqa.classify_chunk_quality(sentence) in {"SHORT_NATURAL_LANGUAGE", "NATURAL_LANGUAGE_SENTENCE"}


def test_precision_result_parsing() -> None:
    result = {
        "rows": [
            {"fp16Empty": True, "fp32Empty": False},
            {"fp16Empty": True, "fp32Empty": True},
        ]
    }
    assert dqa.precision_conclusion(result) == "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED"


def test_control_result_interpretation() -> None:
    def row(rate: float) -> dict[str, float]:
        return {"rawSparseNonEmptyRate": rate}

    result = {
        "A_OFFICIAL_COMPATIBLE_ENGLISH": row(1.0),
        "B_SYNTHETIC_CHINESE_RULES": row(1.0),
        "C_PROJECT_CONTENT_ONLY": row(0.0),
        "D_SECTION_CONTENT": row(1.0),
        "D_TITLE_SECTION_CONTENT": row(1.0),
        "D_PARENT_SUMMARY_CONTENT": row(1.0),
    }
    assert dqa.interpret_control(result) == "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"


def test_representation_safe_scope_excludes_sensitive_identity() -> None:
    chunk = make_chunk("customer should verify order before refund approval")
    text = f"[Scope] source_type={dqa.source_type(chunk)} visibility={chunk.visibility}\n[Title] {chunk.title}\n[Section] {chunk.sectionTitle}\n[Content] {chunk.text}"
    assert "tenant-a" not in text
    assert "Case ID" not in text
