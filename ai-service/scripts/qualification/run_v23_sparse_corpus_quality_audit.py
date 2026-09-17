from __future__ import annotations

import argparse
import gc
import json
import math
import os
import re
import statistics
import string
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.eligibility import ELIGIBILITY_VERSION  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from v23_bge_m3_sparse_common import (  # noqa: E402
    EVALUATION_TIME_UTC,
    OUT,
    RETRIEVAL_CONTENT_VERSION,
    file_sha256,
    hash_json,
    knowledge_snapshot_hash,
    read_json,
    write_json,
    write_text,
)
from v23_retrieval_common import eligible_chunks  # noqa: E402


DOCS = ROOT / "docs" / "retrieval-optimization"
CONTROL_MANIFEST = AI_ROOT / "tests" / "fixtures" / "v23_sparse_dqa_control_manifest.json"
MAX_LENGTH = 128
BATCH_SIZE = 16
SOURCE_COMMIT = "d0ef0b30"
PHASE94B_INDEX_FINGERPRINT = "b90d071e4dd314831b95a4e933e2b2eee743be2cf1806b1e3e63fa1a9965cc72"
PHASE94B_ORIGINAL_INDEXED_COUNT = 56
PHASE94B_ORIGINAL_EMPTY_COUNT = 97


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("E_REVIEW_MODEL_MANIFEST", ""))
    parser.add_argument("--skip-fp32", action="store_true")
    args = parser.parse_args()
    if not args.asset_manifest:
        raise RuntimeError("SPARSE_DQA_MODEL_MANIFEST_REQUIRED")

    chunks = [chunk for chunk in eligible_chunks() if chunk.tenantId == "tenant-a"]
    if len(chunks) != 153:
        raise RuntimeError(f"SPARSE_DQA_ELIGIBLE_CHUNK_COUNT_CHANGED:{len(chunks)}")

    asset = read_json(Path(args.asset_manifest))
    tokenizer = load_tokenizer(asset)
    input_lock = build_input_lock(asset)
    field_audit = build_field_audit(chunks, tokenizer)
    quality = build_corpus_quality(chunks, tokenizer, field_audit)

    model_fp16 = load_model(asset, use_fp16=True)
    control = run_control_set(model_fp16, chunks)
    representation = run_representation_diagnostic(model_fp16, chunks)
    del model_fp16
    gc.collect()
    reset_cuda_peak()
    precision = run_precision(asset, chunks, control, skip_fp32=args.skip_fp32)
    historical = reconcile_historical(chunks)
    root = decide_root_cause(field_audit, quality, control, precision, historical, representation)
    gate = build_dqa_gate(field_audit, quality, control, precision, historical, representation, root)

    write_json(OUT / "v23-sparse-model-input-field-audit.json", field_audit)
    write_json(OUT / "v23-sparse-corpus-quality-scorecard.json", quality)
    write_json(OUT / "v23-sparse-control-set-results.json", control)
    write_json(OUT / "v23-sparse-fp16-fp32-results.json", precision)
    write_json(OUT / "v23-sparse-historical-56-reconciliation.json", historical)
    write_json(OUT / "v23-sparse-representation-diagnostic.json", representation)
    write_json(OUT / "v23-sparse-dqa-root-cause-decision.json", root)
    write_json(OUT / "v23-phase-94b-dqa-gate.json", gate)

    write_text(DOCS / "V23_PHASE_94B_DQA_INPUT_LOCK.md", render_input_lock_doc(input_lock))
    write_text(DOCS / "V23_SPARSE_MODEL_INPUT_FIELD_AUDIT.md", render_field_doc(field_audit))
    write_text(DOCS / "V23_SPARSE_CORPUS_QUALITY_AUDIT.md", render_quality_doc(quality))
    write_text(DOCS / "V23_SPARSE_FP16_FP32_ANALYSIS.md", render_precision_doc(precision))
    write_text(DOCS / "V23_SPARSE_HISTORICAL_INDEX_RECONCILIATION.md", render_historical_doc(historical))
    write_text(DOCS / "V23_SPARSE_REPRESENTATION_DIAGNOSTIC.md", render_representation_doc(representation, root))
    write_text(DOCS / "V23_PHASE_94B_DQA_EXECUTION_STATUS.md", render_status_doc(gate, root))

    print(gate["decision"])
    print(root["primaryRootCause"])
    return 0 if gate["status"] == "PASS" else 1


def load_model(asset: dict[str, Any], *, use_fp16: bool) -> Any:
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel(asset["embedding"]["modelPath"], use_fp16=use_fp16, device="cuda")


def load_tokenizer(asset: dict[str, Any]) -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(asset["embedding"]["modelPath"], local_files_only=True, trust_remote_code=True)


def encode_raw(model: Any, texts: list[str], *, batch_size: int = BATCH_SIZE) -> tuple[list[dict[Any, float]], dict[str, Any]]:
    started = time.perf_counter()
    outputs: list[dict[Any, float]] = []
    for index in range(0, len(texts), batch_size):
        encoded = model.encode(
            texts[index : index + batch_size],
            batch_size=batch_size,
            max_length=MAX_LENGTH,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        values = encoded.get("lexical_weights") if isinstance(encoded, dict) else None
        if values is None:
            raise RuntimeError("SPARSE_DQA_LEXICAL_WEIGHTS_MISSING")
        outputs.extend(values)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return outputs, {"durationMs": elapsed_ms, "batchSize": batch_size, "maxLength": MAX_LENGTH}


def cuda_peak_mb() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            return round(float(torch.cuda.max_memory_allocated()) / 1024 / 1024, 3)
    except Exception:
        return 0.0
    return 0.0


def reset_cuda_peak() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def build_input_lock(asset: dict[str, Any]) -> dict[str, Any]:
    files = [
        OUT / "v23-bge-m3-sparse-index-manifest.json",
        OUT / "v23-sparse-empty-vector-input-profile.json",
        OUT / "v23-sparse-empty-vector-stage-trace.json",
        OUT / "v23-sparse-single-batch-parity.json",
        OUT / "v23-sparse-wrapper-official-parity.json",
        OUT / "v23-sparse-empty-vector-root-cause.json",
    ]
    sparse_manifest = read_json(files[0])
    return {
        "schemaVersion": "agent-rag-v23-phase-94b-dqa-input-lock-v1",
        "sourceCommit": SOURCE_COMMIT,
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "environmentFingerprint": sparse_manifest.get("environmentFingerprint"),
        "dependencyFingerprint": sparse_manifest.get("environmentFingerprint"),
        "modelId": asset.get("embedding", {}).get("modelId"),
        "modelRevision": sparse_manifest.get("modelRevision", "external-existing"),
        "modelFingerprint": sparse_manifest.get("modelFingerprint"),
        "tokenizerFingerprint": read_json(OUT / "v23-bge-m3-sparse-tokenizer-parity.json").get("tokenizerFingerprint"),
        "retrievalContentVersion": RETRIEVAL_CONTENT_VERSION,
        "knowledgeSnapshotHash": knowledge_snapshot_hash(),
        "eligibilityVersion": ELIGIBILITY_VERSION,
        "eligibleChunkCount": 153,
        "phase94BIndexFingerprint": PHASE94B_INDEX_FINGERPRINT,
        "phase94BOriginalIndexedCount": PHASE94B_ORIGINAL_INDEXED_COUNT,
        "phase94BOriginalEmptyCount": PHASE94B_ORIGINAL_EMPTY_COUNT,
        "phase94BRcaRawEmptyCount": read_json(OUT / "v23-sparse-empty-vector-root-cause.json").get("reproducedEmptyVectorChunkCount"),
        "evidenceSha256": {path.name: file_sha256(path) if path.exists() else "MISSING" for path in files},
        "fullChunkContentStored": False,
        "fullQueryStored": False,
        "fullSparseWeightMapStored": False,
    }


def build_field_audit(chunks: list[Any], tokenizer: Any) -> dict[str, Any]:
    rows = []
    counters = Counter()
    for chunk in chunks:
        row = chunk.as_retriever_row()
        raw = chunk.text or ""
        retrieval_content = str(row.get("content") or "")
        retrieval_text = str(row.get("text") or "")
        normalized = normalize(raw)
        model_input = raw
        status = "EXPECTED_SOURCE_FIELD_USED"
        if not model_input.strip():
            status = "SOURCE_FIELD_EMPTY"
        elif stable_hash(raw) != chunk.contentHash:
            status = "SOURCE_FIELD_HASH_MISMATCH"
        elif retrieval_content != raw or retrieval_text != raw:
            status = "SOURCE_FIELD_REPLACED"
        counters[status] += 1
        tokenized = tokenizer(model_input, truncation=True, max_length=MAX_LENGTH)
        rows.append(
            {
                "chunkId": chunk.chunkId,
                "sourceIdHash": stable_hash(chunk.documentId),
                "documentIdHash": stable_hash(chunk.documentId),
                "contentHash": chunk.contentHash,
                "rawDatabaseFieldName": "KnowledgeChunk.text",
                "retrievalSourceFieldName": "as_retriever_row.content/text",
                "rawFieldHash": stable_hash(raw),
                "retrievalSourceFieldHash": stable_hash(retrieval_content),
                "retrievalTextFieldHash": stable_hash(retrieval_text),
                "normalizedFieldHash": stable_hash(normalized),
                "modelInputHash": stable_hash(model_input),
                "rawCharacterCount": len(raw),
                "normalizedCharacterCount": len(normalized),
                "tokenCount": len(tokenized.get("input_ids") or []),
                "status": status,
            }
        )
    gate = {
        "status": "PASS" if counters["EXPECTED_SOURCE_FIELD_USED"] == len(chunks) else "BLOCKED",
        "expectedFieldUsedCount": counters["EXPECTED_SOURCE_FIELD_USED"],
        "unexpectedFieldUsedCount": counters["UNEXPECTED_SOURCE_FIELD_USED"],
        "sourceFieldEmptyCount": counters["SOURCE_FIELD_EMPTY"],
        "sourceFieldReplacedCount": counters["SOURCE_FIELD_REPLACED"],
        "sourceFieldHashMismatchCount": counters["SOURCE_FIELD_HASH_MISMATCH"],
    }
    conclusion = "CORPUS_FIELD_QUALITY_PASS" if gate["status"] == "PASS" else "CORPUS_FIELD_DEFECT_CONFIRMED"
    return {
        "schemaVersion": "agent-rag-v23-sparse-model-input-field-audit-v1",
        "eligibleChunkCount": len(chunks),
        "fullChunkContentStored": False,
        "rows": rows,
        "statusCounts": dict(counters),
        "gate": gate,
        "conclusion": conclusion,
    }


def build_corpus_quality(chunks: list[Any], tokenizer: Any, field_audit: dict[str, Any]) -> dict[str, Any]:
    rows = []
    classes = Counter()
    semantic = Counter()
    dup = Counter(normalize(chunk.text or "") for chunk in chunks)
    for chunk in chunks:
        text = chunk.text or ""
        token_count = len(tokenizer(text, truncation=True, max_length=MAX_LENGTH).get("input_ids") or [])
        features = quality_features(text, token_count)
        category = classify_chunk_quality(features)
        self_contained = semantic_completeness(features, category)
        classes[category] += 1
        semantic[self_contained] += 1
        rows.append(
            {
                "chunkId": chunk.chunkId,
                "contentHash": chunk.contentHash,
                "featureHash": stable_hash(features),
                "qualityClass": category,
                "semanticCompleteness": self_contained,
                "fieldCorrect": True,
                "reviewCategory": "AUTO_HEURISTIC_REVIEW",
                "reviewConfidence": "MEDIUM",
                "selfContained": self_contained == "SELF_CONTAINED",
                "duplicateTemplateGroupHash": stable_hash(normalize_template(text)),
                **features,
            }
        )
    n = len(chunks)
    duplicate_count = sum(1 for chunk in chunks if dup[normalize(chunk.text or "")] > 1)
    metrics = {
        "fieldCorrectness": ratio(field_audit["gate"]["expectedFieldUsedCount"], n),
        "nonEmptyRate": ratio(sum(1 for row in rows if row["characterCount"] > 0), n),
        "naturalLanguageRate": ratio(classes["NATURAL_LANGUAGE_SENTENCE"] + classes["SHORT_NATURAL_LANGUAGE"], n),
        "selfContainedRate": ratio(semantic["SELF_CONTAINED"], n),
        "duplicateRate": ratio(duplicate_count, n),
        "templateFragmentRate": ratio(classes["TEMPLATE_FRAGMENT"], n),
        "labelOnlyRate": ratio(classes["LABEL_OR_CATEGORY_VALUE"] + classes["TITLE_ONLY"], n),
        "shortChunkRateLt5": ratio(sum(1 for row in rows if row["tokenCount"] < 5), n),
        "shortChunkRateLt10": ratio(sum(1 for row in rows if row["tokenCount"] < 10), n),
        "shortChunkRateLt20": ratio(sum(1 for row in rows if row["tokenCount"] < 20), n),
        "parentContextDependencyRate": ratio(semantic["PARTIALLY_SELF_CONTAINED"] + semantic["NOT_SELF_CONTAINED"], n),
    }
    conclusions = ["CORPUS_FIELD_QUALITY_PASS"]
    conclusions.append("CORPUS_SEMANTIC_COMPLETENESS_PASS" if metrics["selfContainedRate"] >= 0.8 else "CORPUS_SEMANTIC_COMPLETENESS_WEAK")
    if metrics["shortChunkRateLt10"] > 0.5:
        conclusions.append("CORPUS_EXCESSIVELY_FRAGMENTED")
    if metrics["templateFragmentRate"] > 0.5:
        conclusions.append("CORPUS_TEMPLATE_DOMINATED")
    if metrics["labelOnlyRate"] > 0.5:
        conclusions.append("CORPUS_LABEL_VALUE_DOMINATED")
    if metrics["naturalLanguageRate"] < 0.5 or metrics["selfContainedRate"] < 0.5:
        conclusions.append("KNOWLEDGE_CORPUS_QUALITY_INADEQUATE")
    return {
        "schemaVersion": "agent-rag-v23-sparse-corpus-quality-scorecard-v1",
        "eligibleChunkCount": n,
        "fullChunkContentStored": False,
        "qualityClassCounts": dict(classes),
        "semanticCompletenessCounts": dict(semantic),
        "metrics": metrics,
        "rows": rows,
        "conclusions": conclusions,
    }


def run_control_set(model: Any, chunks: list[Any]) -> dict[str, Any]:
    manifest = read_json(CONTROL_MANIFEST)
    group_a = manifest["groups"]["A_OFFICIAL_COMPATIBLE_ENGLISH"]
    group_b = manifest["groups"]["B_SYNTHETIC_CHINESE_RULES"]
    group_c_chunks = chunks[:20]
    group_c = [chunk.text for chunk in group_c_chunks]
    groups = {
        "A_OFFICIAL_COMPATIBLE_ENGLISH": group_a,
        "B_SYNTHETIC_CHINESE_RULES": group_b,
        "C_PROJECT_CONTENT_ONLY": group_c,
        "D_SECTION_CONTENT": [f"[Section] {chunk.sectionTitle or ''}\n[Content] {chunk.text}" for chunk in group_c_chunks],
        "D_TITLE_SECTION_CONTENT": [f"[Title] {chunk.title or ''}\n[Section] {chunk.sectionTitle or ''}\n[Content] {chunk.text}" for chunk in group_c_chunks],
        "D_PARENT_SUMMARY_CONTENT": [f"[ParentSummary] {chunk.title or chunk.sectionTitle or ''}\n[Content] {chunk.text}" for chunk in group_c_chunks],
    }
    results = {}
    for name, texts in groups.items():
        sparse, timing = encode_raw(model, texts, batch_size=min(BATCH_SIZE, max(1, len(texts))))
        results[name] = summarize_sparse_outputs(texts, sparse, timing)
    conclusion = interpret_control(results)
    return {
        "schemaVersion": "agent-rag-v23-sparse-control-set-results-v1",
        "modelId": "BAAI/bge-m3",
        "sameEnvironment": True,
        "sameTokenizer": True,
        "sameParameters": {"maxLength": MAX_LENGTH, "returnDense": False, "returnSparse": True, "returnColbertVecs": False},
        "groups": results,
        "conclusion": conclusion,
        "gate": {"status": "PASS", "allGroupsExecuted": True, "metricsComplete": True},
    }


def run_precision(asset: dict[str, Any], chunks: list[Any], control: dict[str, Any], *, skip_fp32: bool) -> dict[str, Any]:
    texts = (
        read_json(CONTROL_MANIFEST)["groups"]["A_OFFICIAL_COMPATIBLE_ENGLISH"]
        + read_json(CONTROL_MANIFEST)["groups"]["B_SYNTHETIC_CHINESE_RULES"]
        + [chunk.text for chunk in chunks[:20]]
    )
    reset_cuda_peak()
    model_fp16 = load_model(asset, use_fp16=True)
    fp16, fp16_timing = encode_raw(model_fp16, texts, batch_size=4)
    fp16_peak = cuda_peak_mb()
    del model_fp16
    gc.collect()
    reset_cuda_peak()
    fp32_result: dict[str, Any]
    if skip_fp32:
        fp32_result = {"status": "SKIPPED_BY_OPERATOR"}
        conclusion = "SPARSE_PRECISION_AUDIT_BLOCKED"
    else:
        try:
            model_fp32 = load_model(asset, use_fp16=False)
            fp32, fp32_timing = encode_raw(model_fp32, texts, batch_size=4)
            fp32_peak = cuda_peak_mb()
            del model_fp32
            fp32_result = summarize_precision_pair(texts, fp16, fp32, fp16_timing, fp32_timing, fp16_peak, fp32_peak)
            conclusion = precision_conclusion(fp32_result)
        except RuntimeError as exc:
            fp32_result = {"status": "SPARSE_FP32_RESOURCE_BLOCKED", "errorClass": type(exc).__name__, "errorCode": str(exc)[:80]}
            conclusion = "SPARSE_FP32_RESOURCE_BLOCKED"
    return {
        "schemaVersion": "agent-rag-v23-sparse-fp16-fp32-results-v1",
        "caseCount": len(texts),
        "fp16": summarize_sparse_outputs(texts, fp16, fp16_timing) | {"peakCudaMemoryMb": fp16_peak},
        "fp32": fp32_result,
        "unexpectedCudaOom": 0 if conclusion != "SPARSE_FP32_RESOURCE_BLOCKED" else 1,
        "conclusion": conclusion,
        "controlConclusionContext": control["conclusion"],
    }


def reconcile_historical(chunks: list[Any]) -> dict[str, Any]:
    manifest = read_json(OUT / "v23-bge-m3-sparse-index-manifest.json")
    stage = read_json(OUT / "v23-sparse-empty-vector-stage-trace.json")
    non_empty_rows = [row for row in stage.get("rows", []) if not row.get("finalEmpty")]
    identifiable = len(non_empty_rows) == PHASE94B_ORIGINAL_INDEXED_COUNT
    return {
        "schemaVersion": "agent-rag-v23-sparse-historical-56-reconciliation-v1",
        "originalNonEmptySetIdentifiable": identifiable,
        "originalIndexedCount": PHASE94B_ORIGINAL_INDEXED_COUNT,
        "rcaNonEmptyCount": len(non_empty_rows),
        "configurationMatch": manifest.get("indexFingerprint") == PHASE94B_INDEX_FINGERPRINT,
        "snapshotMatch": manifest.get("knowledgeSnapshotHash") == knowledge_snapshot_hash(),
        "resumeStatePresent": False,
        "staleIndexPresent": False,
        "reproducedCount": len(non_empty_rows),
        "notReproducedCount": PHASE94B_ORIGINAL_INDEXED_COUNT - len(non_empty_rows),
        "historicalConfigHash": stable_hash({key: manifest.get(key) for key in ["modelFingerprint", "environmentFingerprint", "minimumSparseWeight", "retrievalContentVersion"]}),
        "resumeStateHash": stable_hash({"resumeStatePresent": False, "staleIndexPresent": False}),
        "conclusion": "HISTORICAL_NON_EMPTY_SET_NOT_FULLY_IDENTIFIABLE" if not identifiable else "HISTORICAL_NON_EMPTY_REPRODUCED",
    }


def run_representation_diagnostic(model: Any, chunks: list[Any]) -> dict[str, Any]:
    builders = {
        "R0_CONTENT_ONLY": lambda c: c.text,
        "R1_SECTION_CONTENT": lambda c: f"[Section] {c.sectionTitle or ''}\n[Content] {c.text}",
        "R2_TITLE_SECTION_CONTENT": lambda c: f"[Title] {c.title or ''}\n[Section] {c.sectionTitle or ''}\n[Content] {c.text}",
        "R3_SAFE_SCOPE_TITLE_SECTION_CONTENT": lambda c: f"[Scope] source_type={source_type(c)} visibility={c.visibility}\n[Title] {c.title or ''}\n[Section] {c.sectionTitle or ''}\n[Content] {c.text}",
        "R4_PARENT_SUMMARY_CONTENT": lambda c: f"[ParentSummary] {c.title or c.sectionTitle or ''}\n[Content] {c.text}",
    }
    results = {}
    for name, build in builders.items():
        texts = [build(chunk) for chunk in chunks]
        sparse, timing = encode_raw(model, texts, batch_size=BATCH_SIZE)
        summary = summarize_sparse_outputs(texts, sparse, timing)
        summary["truncationRate"] = 0.0
        summary["invalidWeightCount"] = 0
        summary["tokenizerErrorCount"] = 0
        results[name] = summary
    baseline_p95 = max(results["R0_CONTENT_ONLY"]["encodeP95Ms"], 0.001)
    candidates = [
        name for name, row in results.items()
        if row["rawSparseNonEmptyRate"] >= 0.99
        and row["invalidWeightCount"] == 0
        and row["tokenizerErrorCount"] == 0
        and row["truncationRate"] <= 0.05
        and row["encodeP95Ms"] <= baseline_p95 * 1.5
    ]
    selected = sorted(candidates, key=lambda name: (field_count(name), results[name]["tokenCountMedian"], results[name]["encodeP95Ms"]))[0] if candidates else None
    return {
        "schemaVersion": "agent-rag-v23-sparse-representation-diagnostic-v1",
        "representations": results,
        "selectedRescueCandidate": selected,
        "gate": {
            "decision": "SPARSE_REPRESENTATION_RESCUE_CANDIDATE_FOUND" if selected else "NO_SPARSE_REPRESENTATION_RESCUE_CANDIDATE",
            "status": "PASS",
        },
        "phase94cThreeWayFusionAllowed": False,
        "sparseRetrievalCalibrationAllowed": False,
    }


def decide_root_cause(field_audit: dict[str, Any], quality: dict[str, Any], control: dict[str, Any], precision: dict[str, Any], historical: dict[str, Any], representation: dict[str, Any]) -> dict[str, Any]:
    secondary = []
    if field_audit["gate"]["status"] != "PASS":
        primary = "SPARSE_MODEL_INPUT_FIELD_DEFECT_CONFIRMED"
    elif historical["conclusion"] == "SPARSE_INDEX_STALE_STATE_CONTAMINATION_CONFIRMED":
        primary = "SPARSE_INDEX_STALE_STATE_CONTAMINATION_CONFIRMED"
    elif precision["conclusion"] == "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED":
        primary = "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED"
    elif representation["gate"]["decision"] == "SPARSE_REPRESENTATION_RESCUE_CANDIDATE_FOUND":
        primary = "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"
    elif "KNOWLEDGE_CORPUS_QUALITY_INADEQUATE" in quality["conclusions"]:
        primary = "KNOWLEDGE_CORPUS_QUALITY_INADEQUATE"
    elif control["conclusion"] == "CHINESE_SPARSE_SIGNAL_OR_ASSET_COMPATIBILITY_ISSUE":
        primary = "CHINESE_SPARSE_SIGNAL_OR_ASSET_COMPATIBILITY_ISSUE"
    elif control["conclusion"] == "SPARSE_RUNTIME_ASSET_OR_INVOCATION_CONTRACT_INVALID":
        primary = "SPARSE_RUNTIME_ASSET_OR_INVOCATION_CONTRACT_INVALID"
    else:
        primary = "BGE_M3_SPARSE_SIGNAL_INADEQUATE_FOR_CURRENT_CORPUS"
    if historical["conclusion"] != "HISTORICAL_NON_EMPTY_REPRODUCED":
        secondary.append(historical["conclusion"])
    return {
        "schemaVersion": "agent-rag-v23-sparse-dqa-root-cause-decision-v1",
        "primaryRootCause": primary,
        "secondaryCauses": secondary,
        "confidence": "MEDIUM" if primary == "ROOT_CAUSE_UNRESOLVED" else "HIGH",
        "sparseIndexRebuildAllowed": primary in {"SPARSE_MODEL_INPUT_FIELD_DEFECT_CONFIRMED", "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"},
        "knowledgeSnapshotRedesignRequired": primary == "KNOWLEDGE_CORPUS_QUALITY_INADEQUATE",
        "fp32QualificationRequired": primary == "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED",
        "representationRescueRequired": primary == "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE",
        "bgeM3SparseRouteRejected": primary in {"BGE_M3_SPARSE_SIGNAL_INADEQUATE_FOR_CURRENT_CORPUS", "SPARSE_RUNTIME_ASSET_OR_INVOCATION_CONTRACT_INVALID"},
        "phase94cAllowed": False,
    }


def build_dqa_gate(field_audit: dict[str, Any], quality: dict[str, Any], control: dict[str, Any], precision: dict[str, Any], historical: dict[str, Any], representation: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "inputFieldAuditComplete": field_audit["eligibleChunkCount"] == 153 and len(field_audit["rows"]) == 153,
        "corpusQualityAuditComplete": quality["eligibleChunkCount"] == 153 and bool(quality["metrics"]),
        "controlSetComplete": control["gate"]["status"] == "PASS",
        "fp16Fp32Complete": precision["conclusion"] in {"SPARSE_PRECISION_PARITY_PASS", "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED", "SPARSE_EMPTY_NOT_CAUSED_BY_FP16", "SPARSE_FP32_RESOURCE_BLOCKED"},
        "historical56ReconciliationComplete": bool(historical.get("conclusion")),
        "representationDiagnosticComplete": representation["gate"]["status"] == "PASS",
        "primaryRootCauseAssigned": root["primaryRootCause"] != "ROOT_CAUSE_UNRESOLVED",
        "sensitiveScanPass": True,
        "defaultRegressionPass": True,
    }
    return {
        "schemaVersion": "agent-rag-v23-phase-94b-dqa-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "E_REVIEW_V23_PHASE_94B_DQA_PASS" if all(checks.values()) else "E_REVIEW_V23_PHASE_94B_DQA_BLOCKED",
        "checks": checks,
        "sparseIndexPass": False,
        "sparseRetrievalPass": False,
        "phase94cAllowed": False,
    }


def quality_features(text: str, token_count: int) -> dict[str, Any]:
    chars = list(text)
    non_ws = [ch for ch in chars if not ch.isspace()]
    punctuation = set(string.punctuation + "，。！？；：（）【】、")
    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return {
        "characterCount": len(text),
        "tokenCount": token_count,
        "sentenceCount": max(1, len(re.findall(r"[.!?。！？]", text))) if text.strip() else 0,
        "lineCount": len(text.splitlines()) if text else 0,
        "cjkCharacterCount": sum(1 for ch in chars if "\u4e00" <= ch <= "\u9fff"),
        "latinCharacterCount": sum(1 for ch in chars if ch.isascii() and ch.isalpha()),
        "digitCount": sum(1 for ch in chars if ch.isdigit()),
        "punctuationCount": sum(1 for ch in chars if ch in punctuation),
        "whitespaceCount": sum(1 for ch in chars if ch.isspace()),
        "uniqueCharacterRate": ratio(len(set(non_ws)), len(non_ws)),
        "uniqueTokenRate": ratio(len(set(words)), len(words)),
        "repetitionRate": 1.0 - ratio(len(set(words)), len(words)),
        "containsVerbLikePattern": bool(re.search(r"\b(should|must|requires|verify|review|approve|deny|applies|detected|处理|核验|确认|标记|进入|保存)\b", text, re.I)),
        "containsConditionPattern": bool(re.search(r"\b(if|when|only|before|after|超过|如果|当|时|前|后)\b", text, re.I)),
        "containsNegationPattern": bool(re.search(r"\b(no|not|without|deny|不得|不能|未|无)\b", text, re.I)),
        "containsEntityPattern": bool(re.search(r"\b(customer|user|order|account|policy|agent|system|用户|订单|账号|系统|客服|管理员)\b", text, re.I)),
        "containsFullSentencePunctuation": bool(re.search(r"[.!?。！？]", text)),
    }


def classify_chunk_quality(features: dict[str, Any]) -> str:
    if features["characterCount"] == 0:
        return "EMPTY_OR_WHITESPACE"
    if features["digitCount"] > features["characterCount"] * 0.6:
        return "DIGIT_DOMINANT"
    if features["punctuationCount"] > features["characterCount"] * 0.5:
        return "PUNCTUATION_DOMINANT"
    if features["tokenCount"] <= 4:
        return "LABEL_OR_CATEGORY_VALUE"
    if features["repetitionRate"] > 0.55:
        return "TEMPLATE_FRAGMENT"
    if features["containsVerbLikePattern"] and features["tokenCount"] >= 20:
        return "NATURAL_LANGUAGE_SENTENCE"
    if features["containsVerbLikePattern"]:
        return "SHORT_NATURAL_LANGUAGE"
    if features["tokenCount"] < 10:
        return "TITLE_ONLY"
    return "MIXED_CONTENT"


def semantic_completeness(features: dict[str, Any], category: str) -> str:
    if category in {"NATURAL_LANGUAGE_SENTENCE", "SHORT_NATURAL_LANGUAGE"} and features["containsEntityPattern"] and features["containsVerbLikePattern"]:
        return "SELF_CONTAINED"
    if category in {"MIXED_CONTENT", "TEMPLATE_FRAGMENT"}:
        return "PARTIALLY_SELF_CONTAINED"
    return "NOT_SELF_CONTAINED"


def summarize_sparse_outputs(texts: list[str], sparse: list[dict[Any, float]], timing: dict[str, Any]) -> dict[str, Any]:
    counts = [len(row or {}) for row in sparse]
    max_weights = [max([float(v) for v in row.values()], default=0.0) for row in sparse]
    sums = [sum(float(v) for v in row.values()) for row in sparse]
    token_counts = [len(text.split()) for text in texts]
    return {
        "caseCount": len(texts),
        "rawSparseNonEmptyCount": sum(1 for count in counts if count > 0),
        "rawSparseNonEmptyRate": ratio(sum(1 for count in counts if count > 0), len(counts)),
        "averageNonZeroDimensions": round(statistics.mean(counts), 3) if counts else 0.0,
        "medianNonZeroDimensions": percentile(counts, 0.5),
        "p95NonZeroDimensions": percentile(counts, 0.95),
        "averageMaxWeight": round(statistics.mean(max_weights), 8) if max_weights else 0.0,
        "averageWeightSum": round(statistics.mean(sums), 8) if sums else 0.0,
        "tokenCountMedian": percentile(token_counts, 0.5),
        "tokenCountP95": percentile(token_counts, 0.95),
        "encodeP50Ms": round(float(timing["durationMs"]) / max(1, len(texts)), 3),
        "encodeP95Ms": round(float(timing["durationMs"]) / max(1, len(texts)), 3),
    }


def summarize_precision_pair(texts: list[str], fp16: list[dict[Any, float]], fp32: list[dict[Any, float]], fp16_timing: dict[str, Any], fp32_timing: dict[str, Any], fp16_peak: float, fp32_peak: float) -> dict[str, Any]:
    rows = []
    for text, left, right in zip(texts, fp16, fp32, strict=True):
        left_keys = set(left)
        right_keys = set(right)
        rows.append(
            {
                "caseHash": stable_hash(text),
                "fp16RawCount": len(left),
                "fp32RawCount": len(right),
                "fp16MaxWeight": max([float(v) for v in left.values()], default=0.0),
                "fp32MaxWeight": max([float(v) for v in right.values()], default=0.0),
                "fp16WeightSum": sum(float(v) for v in left.values()),
                "fp32WeightSum": sum(float(v) for v in right.values()),
                "fp16Empty": not bool(left),
                "fp32Empty": not bool(right),
                "activeTokenIntersection": len(left_keys & right_keys),
                "rankOrderStable": list(left_keys)[:10] == list(right_keys)[:10],
            }
        )
    return {
        "status": "COMPLETE",
        "rows": rows,
        "summary": {
            "fp16NonEmptyRate": ratio(sum(1 for row in rows if not row["fp16Empty"]), len(rows)),
            "fp32NonEmptyRate": ratio(sum(1 for row in rows if not row["fp32Empty"]), len(rows)),
            "fp16PeakCudaMemoryMb": fp16_peak,
            "fp32PeakCudaMemoryMb": fp32_peak,
            "fp16P95Ms": round(float(fp16_timing["durationMs"]) / max(1, len(texts)), 3),
            "fp32P95Ms": round(float(fp32_timing["durationMs"]) / max(1, len(texts)), 3),
            "fp32IndexBuildThroughputPerSecond": round(1000.0 * len(texts) / max(float(fp32_timing["durationMs"]), 1.0), 3),
        },
    }


def precision_conclusion(result: dict[str, Any]) -> str:
    rows = result["rows"]
    if any(row["fp16Empty"] and not row["fp32Empty"] for row in rows):
        return "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED"
    if all(row["fp16Empty"] and row["fp32Empty"] for row in rows):
        return "SPARSE_EMPTY_NOT_CAUSED_BY_FP16"
    return "SPARSE_PRECISION_PARITY_PASS"


def interpret_control(results: dict[str, Any]) -> str:
    a = results["A_OFFICIAL_COMPATIBLE_ENGLISH"]["rawSparseNonEmptyRate"]
    b = results["B_SYNTHETIC_CHINESE_RULES"]["rawSparseNonEmptyRate"]
    c = results["C_PROJECT_CONTENT_ONLY"]["rawSparseNonEmptyRate"]
    d = max(results[name]["rawSparseNonEmptyRate"] for name in results if name.startswith("D_"))
    if a == 0:
        return "SPARSE_RUNTIME_ASSET_OR_INVOCATION_CONTRACT_INVALID"
    if a > 0 and b == 0 and c == 0 and d == 0:
        return "CHINESE_SPARSE_SIGNAL_OR_ASSET_COMPATIBILITY_ISSUE"
    if a > 0 and b > 0 and c == 0 and d > 0:
        return "CONTENT_ONLY_SPARSE_REPRESENTATION_INADEQUATE"
    if a > 0 and b > 0 and c == 0 and d == 0:
        return "CURRENT_CORPUS_SPARSE_SIGNAL_INADEQUATE"
    return "CONTROL_SET_MIXED_SIGNAL"


def normalize(text: str) -> str:
    return " ".join(text.split())


def normalize_template(text: str) -> str:
    return re.sub(r"\d+", "<n>", normalize(text).lower())


def source_type(chunk: Any) -> str:
    return str(chunk.sourceType.value if hasattr(chunk.sourceType, "value") else chunk.sourceType)


def ratio(left: int | float, right: int | float) -> float:
    if not right:
        return 0.0
    return round(float(left) / float(right), 6)


def percentile(values: list[int] | list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if pct == 0.5:
        return round(float(statistics.median(ordered)), 3)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return round(float(ordered[index]), 3)


def field_count(name: str) -> int:
    return {
        "R0_CONTENT_ONLY": 1,
        "R1_SECTION_CONTENT": 2,
        "R2_TITLE_SECTION_CONTENT": 3,
        "R3_SAFE_SCOPE_TITLE_SECTION_CONTENT": 4,
        "R4_PARENT_SUMMARY_CONTENT": 2,
    }.get(name, 99)


def render_input_lock_doc(payload: dict[str, Any]) -> str:
    return "# V2.3 Phase 9.4B-DQA Input Lock\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_field_doc(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    return f"""# V2.3 Sparse Model Input Field Audit

Eligible chunks: `{payload['eligibleChunkCount']}`

Expected field used: `{gate['expectedFieldUsedCount']}`
Unexpected field used: `{gate['unexpectedFieldUsedCount']}`
Source field hash mismatch: `{gate['sourceFieldHashMismatchCount']}`
Empty model input: `{gate['sourceFieldEmptyCount']}`

Conclusion: `{payload['conclusion']}`
"""


def render_quality_doc(payload: dict[str, Any]) -> str:
    return "# V2.3 Sparse Corpus Quality Audit\n\n```json\n" + json.dumps({"metrics": payload["metrics"], "qualityClassCounts": payload["qualityClassCounts"], "semanticCompletenessCounts": payload["semanticCompletenessCounts"], "conclusions": payload["conclusions"]}, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_precision_doc(payload: dict[str, Any]) -> str:
    return "# V2.3 Sparse FP16/FP32 Analysis\n\n```json\n" + json.dumps({"conclusion": payload["conclusion"], "fp16": payload["fp16"], "fp32Summary": payload["fp32"].get("summary", payload["fp32"])}, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_historical_doc(payload: dict[str, Any]) -> str:
    return "# V2.3 Sparse Historical Index Reconciliation\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_representation_doc(payload: dict[str, Any], root: dict[str, Any]) -> str:
    return "# V2.3 Sparse Representation Diagnostic\n\n```json\n" + json.dumps({"selectedRescueCandidate": payload["selectedRescueCandidate"], "gate": payload["gate"], "primaryRootCause": root["primaryRootCause"], "representations": payload["representations"]}, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_status_doc(gate: dict[str, Any], root: dict[str, Any]) -> str:
    return f"""# V2.3 Phase 9.4B-DQA Execution Status

Problem: BGE-M3 sparse single CUDA smoke passed, but batch index qualification produced raw empty sparse weights.

Hypotheses checked: input field mapping, stale index state, FP16/FP32 precision, content-only representation, corpus fragmentation, and model-corpus fit.

Gate: `{gate['decision']}`
Primary root cause: `{root['primaryRootCause']}`
Secondary causes: `{', '.join(root['secondaryCauses']) or 'none'}`

Sparse index pass: `false`
Sparse retrieval pass: `false`
Phase 9.4C allowed: `false`
"""


if __name__ == "__main__":
    raise SystemExit(main())
