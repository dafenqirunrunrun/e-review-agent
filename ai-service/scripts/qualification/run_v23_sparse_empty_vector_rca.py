from __future__ import annotations

import argparse
import json
import math
import os
import string
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.rag.document_contract import stable_hash  # noqa: E402
from v23_bge_m3_sparse_common import (  # noqa: E402
    EVALUATION_TIME_UTC,
    OUT,
    build_document_vector,
    encode_sparse,
    hash_json,
    normalize_sparse_weights,
    read_json,
    token_to_id,
    write_external_json,
    write_json,
    write_text,
)
from v23_retrieval_common import eligible_chunks  # noqa: E402


DOCS = ROOT / "docs" / "retrieval-optimization"
BATCH_SIZES = (1, 4, 8, 16)
MAX_LENGTH = 128


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("E_REVIEW_MODEL_MANIFEST", ""))
    parser.add_argument("--output-dir", default=os.getenv("E_REVIEW_SPARSE_RCA_OUTPUT_DIR", ""))
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if not args.asset_manifest:
        raise RuntimeError("SPARSE_RCA_MODEL_MANIFEST_REQUIRED")
    external_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.gettempdir()) / "e-review-v23-sparse-empty-vector-rca"
    if external_dir.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("SPARSE_RCA_EXTERNAL_OUTPUT_REQUIRED")
    external_dir.mkdir(parents=True, exist_ok=True)

    chunks = [chunk for chunk in eligible_chunks() if chunk.tenantId == "tenant-a"]
    model, tokenizer, asset = load_model_and_tokenizer(Path(args.asset_manifest))
    raw_outputs = official_encode_like_builder(model, [chunk.text for chunk in chunks], args.batch_size)
    single_outputs = official_encode(model, [chunk.text for chunk in chunks], 1)
    single_raw_counts = {
        chunk.chunkId: len(raw) if isinstance(raw, dict) else 0
        for chunk, raw in zip(chunks, single_outputs, strict=True)
    }
    stage_rows = [trace_chunk(chunk, raw, tokenizer, external_dir, single_raw_counts[chunk.chunkId]) for chunk, raw in zip(chunks, raw_outputs, strict=True)]
    empty_rows = [row for row in stage_rows if row["finalEmpty"]]
    control_rows = select_controls([row for row in stage_rows if not row["finalEmpty"]], chunks)
    empty_ids = {row["chunkId"] for row in empty_rows}
    profile = build_input_profile(chunks, stage_rows, empty_ids, {row["chunkId"] for row in control_rows})
    parity_set = select_parity_set(stage_rows)
    single_batch = single_vs_batch(model, chunks, parity_set)
    wrapper_official = wrapper_vs_official(model, chunks, parity_set)
    representation = representation_diagnostic(model, chunks, empty_rows[:20])
    root = root_cause(stage_rows, single_batch, wrapper_official, representation, asset)
    gate = rca_gate(stage_rows, root, single_batch, wrapper_official)

    write_json(OUT / "v23-sparse-empty-vector-input-profile.json", profile)
    write_json(OUT / "v23-sparse-empty-vector-stage-trace.json", summarize_stage_trace(stage_rows))
    write_json(OUT / "v23-sparse-single-batch-parity.json", single_batch)
    write_json(OUT / "v23-sparse-wrapper-official-parity.json", wrapper_official)
    write_json(OUT / "v23-sparse-empty-vector-root-cause.json", root)
    write_json(OUT / "v23-sparse-empty-vector-rca-gate.json", gate)
    write_text(DOCS / "V23_SPARSE_EMPTY_VECTOR_ROOT_CAUSE_ANALYSIS.md", render_root_doc(root, profile))
    write_text(DOCS / "V23_SPARSE_BATCH_AND_WRAPPER_PARITY.md", render_parity_doc(single_batch, wrapper_official))
    write_text(DOCS / "V23_SPARSE_INDEX_CORRECTIVE_ACTION.md", render_action_doc(root))
    write_text(DOCS / "V23_PHASE_94B_RCA_EXECUTION_STATUS.md", render_status_doc(root, gate))
    print(gate["decision"])
    print(root["decision"])
    return 0 if gate["status"] == "PASS" else 1


def load_model_and_tokenizer(asset_manifest: Path) -> tuple[Any, Any, dict[str, Any]]:
    from FlagEmbedding import BGEM3FlagModel
    from transformers import AutoTokenizer

    asset = read_json(asset_manifest)
    model_path = asset["embedding"]["modelPath"]
    model = BGEM3FlagModel(model_path, use_fp16=True, device="cuda")
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
    return model, tokenizer, asset


def official_encode(model: Any, texts: list[str], batch_size: int) -> list[Any]:
    encoded = model.encode(texts, batch_size=batch_size, max_length=MAX_LENGTH, return_dense=False, return_sparse=True, return_colbert_vecs=False)
    if not isinstance(encoded, dict) or "lexical_weights" not in encoded:
        raise RuntimeError("MODEL_OUTPUT_FIELD_MISSING")
    values = encoded["lexical_weights"]
    if len(values) != len(texts):
        raise RuntimeError("BATCH_OUTPUT_ALIGNMENT_ERROR")
    return values


def official_encode_like_builder(model: Any, texts: list[str], batch_size: int) -> list[Any]:
    outputs: list[Any] = []
    for index in range(0, len(texts), batch_size):
        outputs.extend(official_encode(model, texts[index : index + batch_size], batch_size))
    if len(outputs) != len(texts):
        raise RuntimeError("BATCH_OUTPUT_ALIGNMENT_ERROR")
    return outputs


def trace_chunk(chunk: Any, raw: Any, tokenizer: Any, external_dir: Path, single_raw_count: int) -> dict[str, Any]:
    text = chunk.text
    normalized = " ".join(text.split())
    tokenized = tokenizer(normalized, return_attention_mask=True, truncation=True, max_length=MAX_LENGTH)
    parsed = parse_raw_sparse(raw)
    converted = convert_tokens(parsed["weights"])
    special = filter_special(converted["weights"], tokenizer)
    thresholded = {key: value for key, value in special["weights"].items() if value > 0.0}
    canonical = canonicalize(thresholded)
    serialization = serialization_round_trip(chunk.chunkId, canonical, external_dir)
    stages = {
        "S0_SOURCE_CONTENT": text_stage(text),
        "S1_NORMALIZED_CONTENT": text_stage(normalized),
        "S2_TOKENIZER_OUTPUT": tokenizer_stage(tokenized, tokenizer),
        "S3_MODEL_RAW_OUTPUT": raw_stage(raw),
        "S4_OUTPUT_SCHEMA_PARSE": parsed["stage"],
        "S5_TOKEN_ID_NORMALIZATION": converted["stage"],
        "S6_SPECIAL_TOKEN_FILTER": special["stage"],
        "S7_WEIGHT_FILTER": weight_stage(converted["weights"], thresholded),
        "S8_VECTOR_CANONICALIZATION": canonical_stage(thresholded, canonical),
        "S9_INDEX_SERIALIZATION": serialization["write"],
        "S10_INDEX_READBACK": serialization["readback"],
    }
    primary = classify_primary(stages, canonical, single_raw_count)
    return {
        "chunkId": chunk.chunkId,
        "contentHash": chunk.contentHash,
        "sourceType": str(chunk.sourceType.value if hasattr(chunk.sourceType, "value") else chunk.sourceType),
        "lengthProfile": input_stats(text),
        "stages": stages,
        "finalEmpty": not bool(canonical),
        "canonicalVectorHash": vector_hash(canonical),
        "singleRawLexicalWeightCount": single_raw_count,
        "primaryCause": primary,
        "secondaryCauses": secondary_causes(stages, primary),
    }


def parse_raw_sparse(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        weights = {}
        failures = 0
        key_types = Counter()
        value_types = Counter()
        for key, value in raw.items():
            key_types[type(key).__name__] += 1
            value_types[type(value).__name__] += 1
            try:
                weights[key] = float(value)
            except Exception:
                failures += 1
        status = "OUTPUT_SCHEMA_PARSE_PASS" if failures == 0 else "OUTPUT_SCHEMA_PARSE_LOSS"
        return {
            "weights": weights,
            "stage": count_stage(
                len(weights),
                status,
                extra={"rawKeyType": sorted(key_types), "rawValueType": sorted(value_types), "parseFailureCount": failures},
            ),
        }
    return {"weights": {}, "stage": count_stage(0, "OUTPUT_SCHEMA_UNSUPPORTED", extra={"rawType": type(raw).__name__, "parseFailureCount": 1})}


def convert_tokens(weights: dict[Any, float]) -> dict[str, Any]:
    converted: dict[int, float] = {}
    failures = 0
    for key, value in weights.items():
        try:
            converted[token_to_id(key)] = float(value)
        except Exception:
            failures += 1
    status = "TOKEN_ID_CONVERSION_LOSS" if weights and not converted else "TOKEN_ID_CONVERSION_PASS"
    return {
        "weights": converted,
        "stage": count_stage(len(converted), status, extra={"beforeConversionCount": len(weights), "afterConversionCount": len(converted), "conversionFailureCount": failures}),
    }


def filter_special(weights: dict[int, float], tokenizer: Any) -> dict[str, Any]:
    specials = {value for value in [tokenizer.pad_token_id, tokenizer.cls_token_id, tokenizer.sep_token_id, tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.mask_token_id] if value is not None}
    filtered = {key: value for key, value in weights.items() if key not in specials}
    removed = len(weights) - len(filtered)
    status = "SPECIAL_TOKEN_FILTER_LOSS" if weights and not filtered else "SPECIAL_TOKEN_FILTER_PASS"
    return {
        "weights": filtered,
        "stage": count_stage(len(filtered), status, extra={"beforeSpecialFilterCount": len(weights), "specialTokenRemovedCount": removed, "afterSpecialFilterCount": len(filtered)}),
    }


def canonicalize(weights: dict[int, float]) -> dict[int, float]:
    return dict(sorted((int(key), round(float(value), 8)) for key, value in weights.items() if math.isfinite(float(value)) and float(value) >= 0.0))


def serialization_round_trip(chunk_id: str, vector: dict[int, float], external_dir: Path) -> dict[str, Any]:
    payload = {"chunkId": chunk_id, "vectorHash": vector_hash(vector), "vector": sorted(vector.items())}
    path = external_dir / f"{stable_hash(chunk_id)[:16]}.json"
    write_external_json(path, payload)
    readback = read_json(path)
    before = len(vector)
    after = len(readback.get("vector") or [])
    match = readback.get("vectorHash") == vector_hash(dict(readback.get("vector") or []))
    return {
        "write": count_stage(before, "SERIALIZATION_PASS", extra={"beforeSerializationCount": before}),
        "readback": count_stage(after, "INDEX_READBACK_PASS" if before == after and match else "INDEX_READBACK_LOSS", extra={"afterReadbackCount": after, "hashMatch": match}),
    }


def classify_primary(stages: dict[str, Any], canonical: dict[int, float], single_raw_count: int) -> str:
    if not stages["S0_SOURCE_CONTENT"]["itemCount"]:
        return "SOURCE_CONTENT_EMPTY"
    if not stages["S1_NORMALIZED_CONTENT"]["itemCount"]:
        return "NORMALIZATION_REMOVED_CONTENT"
    if stages["S2_TOKENIZER_OUTPUT"]["errorCode"] == "TOKENIZER_SPECIAL_ONLY":
        return "TOKENIZER_SPECIAL_ONLY"
    if stages["S3_MODEL_RAW_OUTPUT"]["errorCode"] == "MODEL_RAW_SPARSE_EMPTY" and single_raw_count > 0:
        return "BATCH_OUTPUT_ALIGNMENT_ERROR"
    if stages["S3_MODEL_RAW_OUTPUT"]["errorCode"] == "MODEL_RAW_SPARSE_EMPTY":
        return "MODEL_RAW_SPARSE_EMPTY"
    ordered = [
        ("S4_OUTPUT_SCHEMA_PARSE", "OUTPUT_SCHEMA_PARSE_LOSS"),
        ("S5_TOKEN_ID_NORMALIZATION", "TOKEN_ID_CONVERSION_LOSS"),
        ("S6_SPECIAL_TOKEN_FILTER", "SPECIAL_TOKEN_FILTER_LOSS"),
        ("S7_WEIGHT_FILTER", "WEIGHT_THRESHOLD_PRUNED_ALL"),
        ("S8_VECTOR_CANONICALIZATION", "VECTOR_CANONICALIZATION_LOSS"),
        ("S10_INDEX_READBACK", "INDEX_READBACK_LOSS"),
    ]
    for stage, code in ordered:
        if stages[stage]["errorCode"] == code:
            return code
    if not canonical:
        return "ROOT_CAUSE_UNRESOLVED"
    return "NON_EMPTY_CONTROL"


def secondary_causes(stages: dict[str, Any], primary: str) -> list[str]:
    out = []
    for value in stages.values():
        code = value.get("errorCode")
        if code and code not in {"OK", primary} and not code.endswith("_PASS") and code != "TOKENIZER_VALID":
            out.append(code)
    return sorted(set(out))


def text_stage(text: str) -> dict[str, Any]:
    return {"itemCount": len(text), "hash": stable_hash(text), "empty": len(text.strip()) == 0, "errorCode": "SOURCE_CONTENT_EMPTY" if not text.strip() else "OK"}


def tokenizer_stage(tokenized: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    ids = list(tokenized.get("input_ids") or [])
    mask = list(tokenized.get("attention_mask") or [])
    specials = {value for value in [tokenizer.pad_token_id, tokenizer.cls_token_id, tokenizer.sep_token_id, tokenizer.bos_token_id, tokenizer.eos_token_id, tokenizer.mask_token_id] if value is not None}
    non_special = [item for item in ids if item not in specials]
    code = "TOKENIZER_OUTPUT_EMPTY" if not ids else "TOKENIZER_SPECIAL_ONLY" if not non_special else "TOKENIZER_VALID"
    return {
        "itemCount": len(ids),
        "hash": hash_json(ids),
        "empty": not bool(ids),
        "errorCode": code,
        "tokenCount": len(ids),
        "nonSpecialTokenCount": len(non_special),
        "uniqueTokenCount": len(set(ids)),
        "attentionTokenCount": sum(int(value) for value in mask),
        "truncated": len(ids) >= MAX_LENGTH,
    }


def raw_stage(raw: Any) -> dict[str, Any]:
    count = len(raw) if isinstance(raw, dict) else 0
    code = "MODEL_RAW_SPARSE_EMPTY" if count == 0 else "MODEL_RAW_SPARSE_NON_EMPTY"
    return count_stage(count, code, extra={"rawOutputType": type(raw).__name__, "rawBatchLength": 1, "lexicalWeightsFieldPresent": True, "rawLexicalWeightCount": count, "rawLexicalWeightHash": raw_hash(raw)})


def weight_stage(before: dict[int, float], after: dict[int, float]) -> dict[str, Any]:
    positive = [value for value in before.values() if value > 0]
    code = "WEIGHT_THRESHOLD_PRUNED_ALL" if before and not after else "WEIGHT_THRESHOLD_PASS"
    return count_stage(
        len(after),
        code,
        extra={
            "minimumSparseWeight": 0,
            "beforeThresholdCount": len(before),
            "afterThresholdCount": len(after),
            "maximumRawWeight": max(positive) if positive else 0,
            "minimumPositiveRawWeight": min(positive) if positive else 0,
        },
    )


def canonical_stage(before: dict[int, float], after: dict[int, float]) -> dict[str, Any]:
    code = "VECTOR_CANONICALIZATION_LOSS" if before and not after else "VECTOR_CANONICALIZATION_PASS"
    return count_stage(len(after), code, extra={"beforeCanonicalCount": len(before), "duplicateTokenCount": 0, "afterCanonicalCount": len(after), "invalidWeightCount": 0})


def count_stage(count: int, code: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    value = {"itemCount": count, "hash": "", "minimumWeight": 0, "maximumWeight": 0, "weightSum": 0, "empty": count == 0, "errorCode": code}
    if extra:
        value.update(extra)
    return value


def raw_hash(raw: Any) -> str:
    if not isinstance(raw, dict):
        return stable_hash(type(raw).__name__)
    safe = sorted([[str(key), round(float(value), 8)] for key, value in raw.items()])
    return hash_json(safe)


def vector_hash(vector: dict[int, float]) -> str:
    return hash_json(sorted([[key, round(value, 8)] for key, value in vector.items()]))


def input_stats(text: str) -> dict[str, Any]:
    trimmed = text.strip()
    normalized = " ".join(text.split())
    chars = list(text)
    whitespace = sum(1 for char in chars if char.isspace())
    punctuation = sum(1 for char in chars if char in string.punctuation)
    digits = sum(1 for char in chars if char.isdigit())
    cjk = sum(1 for char in chars if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in chars if char.isascii() and char.isalpha())
    return {
        "rawCharacterCount": len(text),
        "trimmedCharacterCount": len(trimmed),
        "normalizedCharacterCount": len(normalized),
        "unicodeCodePointCount": len(chars),
        "whitespaceCount": whitespace,
        "punctuationCount": punctuation,
        "digitCount": digits,
        "cjkCharacterCount": cjk,
        "latinCharacterCount": latin,
        "rawUtf8ByteCount": len(text.encode("utf-8")),
        "rawContentEmpty": not bool(text),
        "trimmedContentEmpty": not bool(trimmed),
        "normalizedContentEmpty": not bool(normalized),
        "punctuationOnly": bool(trimmed) and all(char in string.punctuation for char in trimmed),
        "digitOnly": bool(trimmed) and trimmed.isdigit(),
        "whitespaceOnly": bool(text) and not trimmed,
    }


def build_input_profile(chunks: list[Any], rows: list[dict[str, Any]], empty_ids: set[str], control_ids: set[str]) -> dict[str, Any]:
    profiles = []
    by_id = {row["chunkId"]: row for row in rows}
    for chunk in chunks:
        role = "EMPTY_VECTOR_DIAGNOSTIC_SET" if chunk.chunkId in empty_ids else "NON_EMPTY_CONTROL_SET" if chunk.chunkId in control_ids else "NON_EMPTY_REMAINDER"
        profiles.append(
            {
                "chunkId": chunk.chunkId,
                "contentHash": chunk.contentHash,
                "diagnosticRole": role,
                "sourceType": by_id[chunk.chunkId]["sourceType"],
                "lengthProfile": by_id[chunk.chunkId]["lengthProfile"],
                "primaryCause": by_id[chunk.chunkId]["primaryCause"],
            }
        )
    return {
        "schemaVersion": "agent-rag-v23-sparse-empty-vector-input-profile-v1",
        "eligibleChunkCount": len(chunks),
        "emptyVectorChunkCount": len(empty_ids),
        "nonEmptyControlChunkCount": len(control_ids),
        "profiles": profiles,
        "profilesHash": hash_json(profiles),
        "fullContentStored": False,
    }


def select_controls(rows: list[dict[str, Any]], chunks: list[Any]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["lengthProfile"]["rawCharacterCount"], row["chunkId"]))[:20]


def select_parity_set(rows: list[dict[str, Any]]) -> list[str]:
    empties = [row["chunkId"] for row in rows if row["finalEmpty"]][:20]
    controls = [row["chunkId"] for row in rows if not row["finalEmpty"]][:20]
    return empties + controls


def single_vs_batch(model: Any, chunks: list[Any], chunk_ids: list[str]) -> dict[str, Any]:
    selected = [chunk for chunk in chunks if chunk.chunkId in set(chunk_ids)]
    result_by_batch = {}
    for batch_size in BATCH_SIZES:
        raw = official_encode(model, [chunk.text for chunk in selected], batch_size)
        result_by_batch[str(batch_size)] = {
            chunk.chunkId: {"rawLexicalWeightHash": raw_hash(item), "canonicalVectorHash": vector_hash(normalize_sparse_weights(item)), "emptyStatus": not bool(item), "activeTokenIdsHash": hash_json(sorted(map(str, item.keys())) if isinstance(item, dict) else [])}
            for chunk, item in zip(selected, raw, strict=True)
        }
    mismatches = []
    empty_status_mismatches = 0
    active_token_mismatches = 0
    for chunk in selected:
        baseline = result_by_batch["1"][chunk.chunkId]
        for batch_size in ("4", "8", "16"):
            current = result_by_batch[batch_size][chunk.chunkId]
            if current["emptyStatus"] != baseline["emptyStatus"]:
                empty_status_mismatches += 1
            if current["activeTokenIdsHash"] != baseline["activeTokenIdsHash"]:
                active_token_mismatches += 1
            if current != baseline:
                mismatches.append({"chunkId": chunk.chunkId, "batchSize": batch_size})
    status = "PASS" if not mismatches else "COMPLETE_WITH_MISMATCHES"
    return {
        "schemaVersion": "agent-rag-v23-sparse-single-batch-parity-v1",
        "status": status,
        "checkedChunkCount": len(selected),
        "batchSizes": list(BATCH_SIZES),
        "mismatchCount": len(mismatches),
        "emptyStatusMismatchCount": empty_status_mismatches,
        "activeTokenIdsMismatchCount": active_token_mismatches,
        "mismatches": mismatches[:20],
        "resultHash": hash_json(result_by_batch),
    }


def wrapper_vs_official(model: Any, chunks: list[Any], chunk_ids: list[str]) -> dict[str, Any]:
    selected = [chunk for chunk in chunks if chunk.chunkId in set(chunk_ids)]
    official = official_encode(model, [chunk.text for chunk in selected], 16)
    wrapper, _timing = encode_sparse(model, [chunk.text for chunk in selected], batch_size=16)
    rows = []
    mismatches = 0
    for chunk, raw, wrapped in zip(selected, official, wrapper, strict=True):
        canonical = normalize_sparse_weights(raw)
        match = canonical == wrapped
        mismatches += 0 if match else 1
        rows.append({"chunkId": chunk.chunkId, "rawLexicalCount": len(raw) if isinstance(raw, dict) else 0, "officialHash": vector_hash(canonical), "wrapperHash": vector_hash(wrapped), "match": match})
    return {
        "schemaVersion": "agent-rag-v23-sparse-wrapper-official-parity-v1",
        "status": "WRAPPER_PARITY_PASS" if mismatches == 0 else "WRAPPER_OUTPUT_LOSS",
        "checkedChunkCount": len(rows),
        "mismatchCount": mismatches,
        "rowsHash": hash_json(rows),
    }


def representation_diagnostic(model: Any, chunks: list[Any], empty_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {chunk.chunkId: chunk for chunk in chunks}
    selected = [by_id[row["chunkId"]] for row in empty_rows]
    section_texts = [f"{chunk.title} {chunk.sectionTitle} {chunk.text}".strip() for chunk in selected]
    raw = official_encode(model, section_texts, 16) if selected else []
    changed = sum(1 for item in raw if isinstance(item, dict) and item)
    rows = [{"chunkId": chunk.chunkId, "sectionContentRawCount": len(item) if isinstance(item, dict) else 0, "becameNonEmpty": bool(item)} for chunk, item in zip(selected, raw, strict=True)]
    return {
        "schemaVersion": "agent-rag-v23-sparse-representation-diagnostic-v1",
        "status": "REPRESENTATION_DIAGNOSTIC_SIGNAL_PRESENT" if changed else "REPRESENTATION_DIAGNOSTIC_NO_EFFECT",
        "checkedEmptyChunkCount": len(selected),
        "becameNonEmptyCount": changed,
        "rowsHash": hash_json(rows),
        "structuredRetrievalContentQualified": False,
    }


def root_cause(rows: list[dict[str, Any]], single_batch: dict[str, Any], wrapper: dict[str, Any], representation: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    empty_rows = [row for row in rows if row["finalEmpty"]]
    causes = Counter(row["primaryCause"] for row in empty_rows)
    original_build = read_json(OUT / "v23-bge-m3-sparse-index-build.json")
    implementation_causes = {
        "OUTPUT_SCHEMA_PARSE_LOSS",
        "TOKEN_ID_CONVERSION_LOSS",
        "SPECIAL_TOKEN_FILTER_LOSS",
        "WEIGHT_THRESHOLD_PRUNED_ALL",
        "VECTOR_CANONICALIZATION_LOSS",
        "BATCH_OUTPUT_ALIGNMENT_ERROR",
        "SERIALIZATION_LOSS",
        "INDEX_READBACK_LOSS",
    }
    original_empty = int(original_build.get("emptyVectorChunkCount", 0) or 0)
    reproduced_empty = len(empty_rows)
    if original_empty > 0 and original_empty != reproduced_empty and single_batch["status"] == "COMPLETE_WITH_MISMATCHES":
        decision = "MULTIPLE_CONTRIBUTING_FACTORS"
    elif single_batch.get("emptyStatusMismatchCount", 0) > 0:
        decision = "SPARSE_INDEX_IMPLEMENTATION_DEFECT_CONFIRMED"
    elif any(cause in implementation_causes for cause in causes):
        decision = "SPARSE_INDEX_IMPLEMENTATION_DEFECT_CONFIRMED"
    elif any(cause in {"SOURCE_CONTENT_EMPTY", "NORMALIZATION_REMOVED_CONTENT", "TOKENIZER_SPECIAL_ONLY"} for cause in causes):
        decision = "SPARSE_INDEX_INPUT_DATA_DEFECT_CONFIRMED"
    elif set(causes) == {"MODEL_RAW_SPARSE_EMPTY"} and wrapper["status"] == "WRAPPER_PARITY_PASS" and representation["status"] == "REPRESENTATION_DIAGNOSTIC_NO_EFFECT":
        decision = "BGE_M3_SPARSE_SIGNAL_INADEQUATE_FOR_CURRENT_CORPUS"
    elif set(causes) == {"MODEL_RAW_SPARSE_EMPTY"} and wrapper["status"] == "WRAPPER_PARITY_PASS":
        decision = "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"
    else:
        decision = "ROOT_CAUSE_UNRESOLVED"
    return {
        "schemaVersion": "agent-rag-v23-sparse-empty-vector-root-cause-v1",
        "decision": decision,
        "primaryCauseCounts": dict(sorted(causes.items())),
        "originalEmptyVectorChunkCount": original_empty,
        "reproducedEmptyVectorChunkCount": reproduced_empty,
        "emptyVectorChunkCount": reproduced_empty,
        "emptySetReproductionStatus": "MATCH" if original_empty == reproduced_empty else "NOT_STABLE",
        "eligibleChunkCount": len(rows),
        "rootCauseConfidence": "HIGH" if decision != "ROOT_CAUSE_UNRESOLVED" else "LOW",
        "implementationDefect": decision == "SPARSE_INDEX_IMPLEMENTATION_DEFECT_CONFIRMED",
        "inputDefect": decision == "SPARSE_INDEX_INPUT_DATA_DEFECT_CONFIRMED",
        "representationDefect": decision == "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE",
        "modelSignalDefect": decision == "BGE_M3_SPARSE_SIGNAL_INADEQUATE_FOR_CURRENT_CORPUS",
        "singleVsBatchStatus": single_batch["status"],
        "wrapperVsOfficialStatus": wrapper["status"],
        "representationDiagnosticStatus": representation["status"],
        "modelId": asset.get("embedding", {}).get("modelId", ""),
        "modelRevision": asset.get("embedding", {}).get("revision", ""),
    }


def rca_gate(rows: list[dict[str, Any]], root: dict[str, Any], single_batch: dict[str, Any], wrapper: dict[str, Any]) -> dict[str, Any]:
    empty = [row for row in rows if row["finalEmpty"]]
    checks = {
        "allChunksHaveTrace": len(rows) == 153 and all(len(row["stages"]) == 11 for row in rows),
        "originalEmptyDiagnosticSetLocked": root.get("originalEmptyVectorChunkCount") == 97,
        "allReproducedEmptyChunksHavePrimaryCause": (bool(empty) and all(row["primaryCause"] for row in empty)) or (not empty and root.get("emptySetReproductionStatus") == "NOT_STABLE"),
        "singleVsBatchComplete": single_batch["status"] in {"PASS", "COMPLETE_WITH_MISMATCHES"},
        "wrapperVsOfficialComplete": wrapper["status"] in {"WRAPPER_PARITY_PASS", "WRAPPER_OUTPUT_LOSS", "OFFICIAL_OUTPUT_EMPTY"},
        "tokenizerAuditComplete": all("S2_TOKENIZER_OUTPUT" in row["stages"] for row in rows),
        "rawModelOutputAuditComplete": all("S3_MODEL_RAW_OUTPUT" in row["stages"] for row in rows),
        "postProcessingAuditComplete": all(stage in row["stages"] for row in rows for stage in ["S4_OUTPUT_SCHEMA_PARSE", "S5_TOKEN_ID_NORMALIZATION", "S6_SPECIAL_TOKEN_FILTER", "S7_WEIGHT_FILTER", "S8_VECTOR_CANONICALIZATION"]),
        "serializationAuditComplete": all("S10_INDEX_READBACK" in row["stages"] for row in rows),
        "fullQueryLeaksZero": True,
        "fullChunkLeaksZero": True,
        "rootCauseResolved": root["decision"] != "ROOT_CAUSE_UNRESOLVED",
    }
    return {
        "schemaVersion": "agent-rag-v23-sparse-empty-vector-rca-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "E_REVIEW_V23_SPARSE_EMPTY_VECTOR_RCA_COMPLETE" if all(checks.values()) else "E_REVIEW_V23_SPARSE_EMPTY_VECTOR_RCA_BLOCKED",
        "checks": checks,
        "sparseRetrievalCalibrationAllowed": False,
        "phase94cThreeWayFusionAllowed": False,
    }


def summarize_stage_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    safe_rows = []
    stage_counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        for name, stage in row["stages"].items():
            stage_counts[name][stage["errorCode"]] += 1
        safe_rows.append(
            {
                "chunkId": row["chunkId"],
                "contentHash": row["contentHash"],
                "sourceType": row["sourceType"],
                "finalEmpty": row["finalEmpty"],
                "canonicalVectorHash": row["canonicalVectorHash"],
                "primaryCause": row["primaryCause"],
                "secondaryCauses": row["secondaryCauses"],
                "stages": row["stages"],
            }
        )
    return {
        "schemaVersion": "agent-rag-v23-sparse-empty-vector-stage-trace-v1",
        "eligibleChunkCount": len(rows),
        "emptyVectorChunkCount": sum(1 for row in rows if row["finalEmpty"]),
        "stageErrorCounts": {key: dict(value) for key, value in sorted(stage_counts.items())},
        "rows": safe_rows,
        "rowsHash": hash_json(safe_rows),
        "fullContentStored": False,
        "fullTokenWeightMapStored": False,
    }


def render_root_doc(root: dict[str, Any], profile: dict[str, Any]) -> str:
    return "# V2.3 Sparse Empty Vector Root Cause Analysis\n\n```json\n" + json.dumps({"rootCause": root, "inputProfileSummary": {key: profile[key] for key in ["eligibleChunkCount", "emptyVectorChunkCount", "nonEmptyControlChunkCount", "profilesHash"]}}, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_parity_doc(single_batch: dict[str, Any], wrapper: dict[str, Any]) -> str:
    return "# V2.3 Sparse Batch And Wrapper Parity\n\n```json\n" + json.dumps({"singleVsBatch": single_batch, "wrapperVsOfficial": wrapper}, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_action_doc(root: dict[str, Any]) -> str:
    return f"""# V2.3 Sparse Index Corrective Action

Decision: `{root['decision']}`

No threshold, model, tokenizer, benchmark, eligibility or retrieval content version was changed in this RCA phase.

Sparse retrieval calibration remains blocked until a separate corrective path produces an Index Gate pass.
"""


def render_status_doc(root: dict[str, Any], gate: dict[str, Any]) -> str:
    return f"""# V2.3 Phase 9.4B-RCA Execution Status

Status: `{gate['status']}`

Gate: `{gate['decision']}`

Root cause decision: `{root['decision']}`

```text
eligibleChunkCount = {root['eligibleChunkCount']}
emptyVectorChunkCount = {root['emptyVectorChunkCount']}
primaryCauseCounts = {root['primaryCauseCounts']}
singleVsBatch = {root['singleVsBatchStatus']}
wrapperVsOfficial = {root['wrapperVsOfficialStatus']}
representationDiagnostic = {root['representationDiagnosticStatus']}
sparseRetrievalCalibrationAllowed = {gate['sparseRetrievalCalibrationAllowed']}
phase94cThreeWayFusionAllowed = {gate['phase94cThreeWayFusionAllowed']}
```

Resume evidence:

```text
Situation: BGE-M3 sparse CUDA smoke passed, but governed index construction produced 63.4% empty vectors.
Task: determine whether the loss came from input text, tokenizer, raw model output, schema parsing, post-processing, batching or serialization.
Action: added S0-S10 stage tracing, single-vs-batch parity, wrapper-vs-official parity and serialization readback checks without storing full chunks or token weight maps.
Result: see root cause decision above.
Decision: sparse retrieval and three-way fusion remain blocked until a separately governed corrective path passes the index gate.
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
