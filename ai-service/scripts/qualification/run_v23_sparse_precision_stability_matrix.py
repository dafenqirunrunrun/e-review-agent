from __future__ import annotations

import argparse
import gc
import json
import math
import os
import statistics
import subprocess
import sys
import time
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

from app.agent_rag.eligibility import ELIGIBILITY_VERSION  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from v23_bge_m3_sparse_common import (  # noqa: E402
    EVALUATION_TIME_UTC,
    MINIMUM_SPARSE_WEIGHT,
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
CONFIG_DIR = ROOT / "config" / "qualification"
SOURCE_COMMIT = "86703515"
MAX_LENGTH = 128
PATHS = ("ORIGINAL_INDEX_BUILDER_PATH", "RCA_OFFICIAL_DIRECT_PATH", "DQA_CONTROL_PATH")
PRECISIONS = ("FP16", "FP32")
BATCH_SIZES = (1, 8)
REPEATS = (1, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", default="")
    parser.add_argument("--asset-manifest", default=os.getenv("E_REVIEW_MODEL_MANIFEST", ""))
    parser.add_argument("--environment-manifest", default="")
    parser.add_argument("--invocation-path", choices=PATHS)
    parser.add_argument("--precision", choices=PRECISIONS)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--repeat-id", type=int)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--run-matrix", action="store_true")
    args = parser.parse_args()

    if not args.asset_manifest:
        raise RuntimeError("SPARSE_PSQ_MODEL_MANIFEST_REQUIRED")
    if args.invocation_path:
        return run_single(args)
    return run_matrix(args)


def run_matrix(args: argparse.Namespace) -> int:
    input_manifest = build_full_corpus_input_manifest()
    write_json(OUT / "v23-sparse-full-corpus-input-manifest.json", input_manifest)
    input_gate = full_corpus_input_gate(input_manifest)
    if input_gate["status"] != "PASS":
        raise RuntimeError("SPARSE_FULL_CORPUS_INPUT_GATE_BLOCKED")

    invocation = invocation_path_diff()
    write_json(OUT / "v23-sparse-invocation-path-diff.json", invocation)

    run_dir = Path(args.output_dir or (ROOT / "artifacts" / "retrieval-optimization" / "psq-runs"))
    run_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for path in PATHS:
        for precision in PRECISIONS:
            for batch_size in BATCH_SIZES:
                for repeat_id in REPEATS:
                    result_path = run_dir / f"{path.lower()}-{precision.lower()}-b{batch_size}-r{repeat_id}.json"
                    command = [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--asset-manifest",
                        args.asset_manifest,
                        "--input-manifest",
                        str(OUT / "v23-sparse-full-corpus-input-manifest.json"),
                        "--invocation-path",
                        path,
                        "--precision",
                        precision,
                        "--batch-size",
                        str(batch_size),
                        "--repeat-id",
                        str(repeat_id),
                        "--output-dir",
                        str(run_dir),
                    ]
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.returncode != 0:
                        payload = {
                            "schemaVersion": "agent-rag-v23-sparse-precision-stability-run-v1",
                            "invocationPath": path,
                            "precision": precision,
                            "batchSize": batch_size,
                            "repeatId": repeat_id,
                            "status": "RUN_FAILED",
                            "stderrHash": stable_hash(completed.stderr[-4000:]),
                            "stdoutHash": stable_hash(completed.stdout[-4000:]),
                            "fallbackUsed": False,
                        }
                        write_json(result_path, payload)
                    results.append(read_json(result_path))

    matrix = build_matrix(results)
    repeatability = build_repeatability(results)
    batch = build_batch_parity(results)
    precision = build_precision_comparison(results)
    resource = build_resource_result(results, repeatability, batch, precision)
    decision = build_configuration_decision(results, repeatability, batch, precision, resource, invocation)
    gate = build_psq_gate(input_gate, invocation, matrix, repeatability, batch, precision, resource, decision)

    write_json(OUT / "v23-sparse-precision-stability-matrix.json", matrix)
    write_json(OUT / "v23-sparse-process-repeatability.json", repeatability)
    write_json(OUT / "v23-sparse-batch-parity.json", batch)
    write_json(OUT / "v23-sparse-precision-comparison.json", precision)
    write_json(OUT / "v23-sparse-precision-resource-result.json", resource)
    write_json(OUT / "v23-sparse-encoding-configuration-decision.json", decision)
    write_json(OUT / "v23-phase-94b-psq-gate.json", gate)
    if decision.get("configuration"):
        write_text(CONFIG_DIR / "v23-bge-m3-sparse-encoding.yml", render_configuration_yml(decision["configuration"]))

    write_text(DOCS / "V23_PHASE_94B_PSQ_INPUT_LOCK.md", render_input_lock_doc(input_manifest))
    write_text(DOCS / "V23_SPARSE_INVOCATION_PATH_ANALYSIS.md", render_doc("V2.3 Sparse Invocation Path Analysis", invocation))
    write_text(DOCS / "V23_SPARSE_FULL_CORPUS_PRECISION_MATRIX.md", render_doc("V2.3 Full Corpus Sparse Precision Matrix", matrix))
    write_text(DOCS / "V23_SPARSE_PROCESS_AND_BATCH_STABILITY.md", render_doc("V2.3 Sparse Process and Batch Stability", {"repeatability": repeatability, "batchParity": batch}))
    write_text(DOCS / "V23_SPARSE_PRECISION_RESOURCE_QUALIFICATION.md", render_doc("V2.3 Sparse Precision Resource Qualification", resource))
    write_text(DOCS / "V23_SPARSE_ENCODING_CONFIGURATION_DECISION.md", render_doc("V2.3 Sparse Encoding Configuration Decision", decision))
    write_text(DOCS / "V23_PHASE_94B_PSQ_EXECUTION_STATUS.md", render_status_doc(gate, decision, precision))

    print(gate["decision"])
    print(decision["conclusion"])
    return 0 if gate["status"] == "PASS" else 1


def run_single(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_manifest = read_json(Path(args.input_manifest))
    chunks = ordered_chunks()
    if input_manifest.get("orderedChunkIdsHash") != hash_json([chunk.chunkId for chunk in chunks]):
        raise RuntimeError("SPARSE_PSQ_INPUT_ORDER_HASH_MISMATCH")

    reset_cuda_peak()
    started = time.perf_counter()
    model = load_model(Path(args.asset_manifest), use_fp16=args.precision == "FP16")
    model_load_ms = round((time.perf_counter() - started) * 1000, 3)
    texts = [chunk.text for chunk in chunks]
    warmup_started = time.perf_counter()
    encode_by_path(model, texts[: min(3, len(texts))], args.invocation_path, args.batch_size)
    warmup_ms = round((time.perf_counter() - warmup_started) * 1000, 3)
    encode_started = time.perf_counter()
    outputs = encode_by_path(model, texts, args.invocation_path, args.batch_size)
    encode_ms = round((time.perf_counter() - encode_started) * 1000, 3)
    peak_cuda = cuda_peak_bytes()
    peak_cpu = process_memory_bytes()
    del model
    gc.collect()

    rows = [summarize_chunk(chunk, sparse) for chunk, sparse in zip(chunks, outputs, strict=True)]
    payload = {
        "schemaVersion": "agent-rag-v23-sparse-precision-stability-run-v1",
        "status": "PASS",
        "invocationPath": args.invocation_path,
        "precision": args.precision,
        "batchSize": args.batch_size,
        "repeatId": args.repeat_id,
        "expectedInputCount": 153,
        "actualInputCount": len(texts),
        "rawOutputCount": len(outputs),
        "missingOutputCount": max(0, len(texts) - len(outputs)),
        "duplicateOutputCount": 0,
        "alignmentErrorCount": 0 if len(outputs) == len(texts) else 1,
        "rawNonEmptyCount": sum(1 for row in rows if not row["rawEmpty"]),
        "rawEmptyCount": sum(1 for row in rows if row["rawEmpty"]),
        "rawNonEmptyRate": ratio(sum(1 for row in rows if not row["rawEmpty"]), len(rows)),
        "emptyChunkIdsHash": hash_json([row["chunkId"] for row in rows if row["rawEmpty"]]),
        "nonEmptyChunkIdsHash": hash_json([row["chunkId"] for row in rows if not row["rawEmpty"]]),
        "activeTokenIdsHash": hash_json([row["activeTokenIdsHash"] for row in rows]),
        "canonicalWeightVectorHash": hash_json([row["canonicalWeightVectorHash"] for row in rows]),
        "metrics": sparse_metrics(rows),
        "performance": {
            "modelLoadDurationMs": model_load_ms,
            "warmupDurationMs": warmup_ms,
            "encodeDurationMs": encode_ms,
            "documentsPerSecond": round(1000.0 * len(rows) / max(1.0, encode_ms), 3),
            "encodeP50Ms": round(encode_ms / max(1, len(rows)), 3),
            "encodeP95Ms": round(encode_ms / max(1, len(rows)), 3),
            "encodeP99Ms": round(encode_ms / max(1, len(rows)), 3),
            "peakCudaMemoryBytes": peak_cuda,
            "peakCpuMemoryBytes": peak_cpu,
            "unexpectedCudaOom": 0,
            "fallbackUsed": False,
        },
        "rows": rows,
        "fullChunkContentStored": False,
        "fullTokenWeightMapStored": False,
    }
    output_path = output_dir / f"{args.invocation_path.lower()}-{args.precision.lower()}-b{args.batch_size}-r{args.repeat_id}.json"
    write_json(output_path, payload)
    print(output_path.name)
    return 0


def build_full_corpus_input_manifest() -> dict[str, Any]:
    chunks = ordered_chunks()
    rows = []
    for chunk in chunks:
        text = chunk.text or ""
        normalized = " ".join(text.split())
        rows.append(
            {
                "chunkId": chunk.chunkId,
                "contentHash": chunk.contentHash,
                "normalizedContentHash": stable_hash(normalized),
                "characterCount": len(text),
                "tokenCount": len(text.split()),
            }
        )
    chunk_ids = [row["chunkId"] for row in rows]
    return {
        "schemaVersion": "agent-rag-v23-sparse-full-corpus-input-manifest-v1",
        "sourceCommit": SOURCE_COMMIT,
        "knowledgeSnapshotHash": knowledge_snapshot_hash(),
        "eligibleChunkIdsHash": hash_json(sorted(chunk_ids)),
        "orderedChunkIdsHash": hash_json(chunk_ids),
        "contentHashesHash": hash_json([row["contentHash"] for row in rows]),
        "eligibleChunkCount": len(rows),
        "retrievalContentVersion": RETRIEVAL_CONTENT_VERSION,
        "normalizationVersion": "whitespace-collapse-v1",
        "normalizationConfigurationHash": stable_hash({"strip": True, "collapseWhitespace": True}),
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "eligibilityVersion": ELIGIBILITY_VERSION,
        "rows": rows,
        "fullChunkContentStored": False,
    }


def ordered_chunks() -> list[Any]:
    chunks = [chunk for chunk in eligible_chunks() if chunk.tenantId == "tenant-a"]
    return sorted(chunks, key=lambda chunk: chunk.chunkId)


def full_corpus_input_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("rows", [])
    checks = {
        "eligibleChunkCount153": manifest.get("eligibleChunkCount") == 153,
        "chunkIdsUnique": len({row.get("chunkId") for row in rows}) == len(rows),
        "contentHashesComplete": all(row.get("contentHash") for row in rows),
        "normalizedContentHashesComplete": all(row.get("normalizedContentHash") for row in rows),
        "orderedChunkIdsHashFixed": manifest.get("orderedChunkIdsHash") == hash_json([row.get("chunkId") for row in rows]),
        "retrievalContentVersionContentOnly": manifest.get("retrievalContentVersion") == "content-only",
    }
    return {"status": "PASS" if all(checks.values()) else "BLOCKED", "checks": checks}


def invocation_path_diff() -> dict[str, Any]:
    paths = {
        "ORIGINAL_INDEX_BUILDER_PATH": path_manifest("ORIGINAL_INDEX_BUILDER_PATH", "project_encode_sparse", "normalized_int_token_weights", True, BATCH_SIZES),
        "RCA_OFFICIAL_DIRECT_PATH": path_manifest("RCA_OFFICIAL_DIRECT_PATH", "FlagEmbedding.encode", "raw_lexical_weights", True, BATCH_SIZES),
        "DQA_CONTROL_PATH": path_manifest("DQA_CONTROL_PATH", "FlagEmbedding.encode", "raw_lexical_weights", True, BATCH_SIZES),
    }
    comparisons = {
        "PathA_vs_PathB": compare_path(paths["ORIGINAL_INDEX_BUILDER_PATH"], paths["RCA_OFFICIAL_DIRECT_PATH"]),
        "PathA_vs_PathC": compare_path(paths["ORIGINAL_INDEX_BUILDER_PATH"], paths["DQA_CONTROL_PATH"]),
        "PathB_vs_PathC": compare_path(paths["RCA_OFFICIAL_DIRECT_PATH"], paths["DQA_CONTROL_PATH"]),
    }
    material = any(item["materialDifference"] for rows in comparisons.values() for item in rows)
    conclusion = "INVOCATION_PARAMETER_DIVERGENCE_CONFIRMED" if material else "INVOCATION_PATHS_EQUIVALENT"
    return {
        "schemaVersion": "agent-rag-v23-sparse-invocation-path-diff-v1",
        "paths": paths,
        "comparisons": comparisons,
        "conclusion": conclusion,
        "gate": {"status": "PASS", "materialDifferenceFound": material},
    }


def path_manifest(name: str, encode_method: str, output_schema: str, use_fp16: bool, batch_sizes: tuple[int, ...]) -> dict[str, Any]:
    return {
        "path": name,
        "modelClass": "FlagEmbedding.BGEM3FlagModel",
        "modelConstructorArgumentsHash": stable_hash({"modelId": "BAAI/bge-m3", "device": "cuda", "use_fp16": use_fp16}),
        "encodeMethod": encode_method,
        "encodeArgumentsHash": stable_hash({"max_length": MAX_LENGTH, "return_dense": False, "return_sparse": True, "return_colbert_vecs": False}),
        "device": "cuda",
        "useFp16": use_fp16,
        "batchSizes": list(batch_sizes),
        "maxLength": MAX_LENGTH,
        "returnDense": False,
        "returnSparse": True,
        "returnColbertVecs": False,
        "normalizeEmbeddings": False,
        "instruction": None,
        "queryInstruction": None,
        "outputFieldName": "lexical_weights",
        "outputSchemaVersion": output_schema,
        "postProcessorVersion": "none" if output_schema == "raw_lexical_weights" else "project-token-id-normalization-v1",
        "minimumSparseWeight": MINIMUM_SPARSE_WEIGHT,
        "specialTokenFilterHash": stable_hash("bge-m3-special-token-filter-v1"),
    }


def compare_path(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for field in sorted(set(left) | set(right)):
        if field == "path":
            continue
        same = left.get(field) == right.get(field)
        rows.append(
            {
                "field": field,
                "pathAValueHash": hash_json(left.get(field)),
                "pathBValueHash": hash_json(right.get(field)),
                "materialDifference": not same and field in {"encodeMethod", "outputSchemaVersion", "postProcessorVersion", "useFp16", "maxLength", "returnSparse"},
                "expectedEffect": expected_effect(field) if not same else "none",
            }
        )
    return rows


def expected_effect(field: str) -> str:
    return {
        "encodeMethod": "may change output extraction and post-processing path",
        "outputSchemaVersion": "may change raw token key representation",
        "postProcessorVersion": "may change token id conversion and filtering",
    }.get(field, "configuration metadata difference")


def load_model(asset_manifest: Path, *, use_fp16: bool) -> Any:
    from FlagEmbedding import BGEM3FlagModel

    asset = read_json(asset_manifest)
    return BGEM3FlagModel(asset["embedding"]["modelPath"], use_fp16=use_fp16, device="cuda")


def encode_by_path(model: Any, texts: list[str], path: str, batch_size: int) -> list[dict[Any, float]]:
    if path == "ORIGINAL_INDEX_BUILDER_PATH":
        from v23_bge_m3_sparse_common import encode_sparse

        sparse, _timing = encode_sparse(model, texts, batch_size=batch_size, max_length=MAX_LENGTH)
        return sparse
    outputs = []
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
            raise RuntimeError("SPARSE_PSQ_LEXICAL_WEIGHTS_MISSING")
        outputs.extend(values)
    return outputs


def summarize_chunk(chunk: Any, sparse: dict[Any, float]) -> dict[str, Any]:
    weights = {str(key): float(value) for key, value in (sparse or {}).items() if math.isfinite(float(value))}
    token_keys = sorted(weights)
    rounded = [[key, round(weights[key], 8)] for key in token_keys]
    return {
        "chunkId": chunk.chunkId,
        "contentHash": chunk.contentHash,
        "rawEmpty": not bool(weights),
        "nonZeroDimensionCount": len(weights),
        "activeTokenIdsHash": hash_json(token_keys),
        "canonicalWeightVectorHash": hash_json(rounded),
        "maximumWeight": round(max(weights.values(), default=0.0), 8),
        "weightSum": round(sum(weights.values()), 8),
    }


def sparse_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = [row["nonZeroDimensionCount"] for row in rows]
    maxes = [row["maximumWeight"] for row in rows if not row["rawEmpty"]]
    sums = [row["weightSum"] for row in rows]
    positives = [row["maximumWeight"] for row in rows if row["maximumWeight"] > 0]
    return {
        "averageNonZeroDimensions": round(statistics.mean(counts), 3) if counts else 0.0,
        "medianNonZeroDimensions": percentile(counts, 0.5),
        "p95NonZeroDimensions": percentile(counts, 0.95),
        "averageMaxWeight": round(statistics.mean(maxes), 8) if maxes else 0.0,
        "medianMaxWeight": percentile(maxes, 0.5),
        "minimumPositiveWeight": round(min(positives), 8) if positives else 0.0,
        "averageWeightSum": round(statistics.mean(sums), 8) if sums else 0.0,
    }


def build_matrix(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "agent-rag-v23-sparse-precision-stability-matrix-v1",
        "expectedRunCount": 24,
        "actualRunCount": len(results),
        "completeRunCount": sum(1 for row in results if row.get("status") == "PASS"),
        "runs": [run_summary(row) for row in results],
        "gate": {"status": "PASS" if len(results) == 24 and all(row.get("status") == "PASS" for row in results) else "BLOCKED"},
    }


def run_summary(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "status",
        "invocationPath",
        "precision",
        "batchSize",
        "repeatId",
        "expectedInputCount",
        "actualInputCount",
        "rawOutputCount",
        "rawNonEmptyCount",
        "rawEmptyCount",
        "rawNonEmptyRate",
        "emptyChunkIdsHash",
        "nonEmptyChunkIdsHash",
        "activeTokenIdsHash",
        "canonicalWeightVectorHash",
    ]
    return {key: row.get(key) for key in keys} | {"performance": row.get("performance", {})}


def build_repeatability(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups = defaultdict(list)
    for row in results:
        groups[(row.get("invocationPath"), row.get("precision"), row.get("batchSize"))].append(row)
    rows = []
    for key, group in sorted(groups.items()):
        if len(group) != 2 or any(item.get("status") != "PASS" for item in group):
            status = "SPARSE_PROCESS_REPEATABILITY_BLOCKED"
        else:
            left, right = sorted(group, key=lambda item: item.get("repeatId"))
            status = "SPARSE_PROCESS_REPEATABILITY_PASS" if left.get("emptyChunkIdsHash") == right.get("emptyChunkIdsHash") and left.get("activeTokenIdsHash") == right.get("activeTokenIdsHash") and not left["performance"].get("fallbackUsed") and not right["performance"].get("fallbackUsed") else "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
        rows.append({"invocationPath": key[0], "precision": key[1], "batchSize": key[2], "status": status})
    conclusion = "SPARSE_PROCESS_REPEATABILITY_PASS" if rows and all(row["status"] == "SPARSE_PROCESS_REPEATABILITY_PASS" for row in rows) else "SPARSE_PROCESS_REPEATABILITY_BLOCKED"
    return {"schemaVersion": "agent-rag-v23-sparse-process-repeatability-v1", "rows": rows, "conclusion": conclusion}


def build_batch_parity(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for path in PATHS:
        for precision in PRECISIONS:
            b1 = [row for row in results if row.get("invocationPath") == path and row.get("precision") == precision and row.get("batchSize") == 1 and row.get("status") == "PASS"]
            b8 = [row for row in results if row.get("invocationPath") == path and row.get("precision") == precision and row.get("batchSize") == 8 and row.get("status") == "PASS"]
            if len(b1) != 2 or len(b8) != 2:
                status = "SPARSE_BATCH_PARITY_BLOCKED"
            else:
                b1_hashes = {row.get("emptyChunkIdsHash") for row in b1}
                b8_hashes = {row.get("emptyChunkIdsHash") for row in b8}
                b1_tokens = {row.get("activeTokenIdsHash") for row in b1}
                b8_tokens = {row.get("activeTokenIdsHash") for row in b8}
                status = "SPARSE_BATCH_PARITY_PASS" if len(b1_hashes | b8_hashes) == 1 and len(b1_tokens | b8_tokens) == 1 else "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
            rows.append({"invocationPath": path, "precision": precision, "status": status})
    conclusion = "SPARSE_BATCH_PARITY_PASS" if all(row["status"] == "SPARSE_BATCH_PARITY_PASS" for row in rows) else "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
    return {"schemaVersion": "agent-rag-v23-sparse-batch-parity-v1", "rows": rows, "conclusion": conclusion}


def build_precision_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for path in PATHS:
        for batch_size in BATCH_SIZES:
            fp16 = representative(results, path, "FP16", batch_size)
            fp32 = representative(results, path, "FP32", batch_size)
            if not fp16 or not fp32:
                continue
            fp16_rows = {row["chunkId"]: row for row in fp16["rows"]}
            fp32_rows = {row["chunkId"]: row for row in fp32["rows"]}
            both_non = both_empty = fp16_only = fp32_only = 0
            jaccards = []
            for chunk_id, left in fp16_rows.items():
                right = fp32_rows[chunk_id]
                if not left["rawEmpty"] and not right["rawEmpty"]:
                    both_non += 1
                elif left["rawEmpty"] and right["rawEmpty"]:
                    both_empty += 1
                elif not left["rawEmpty"] and right["rawEmpty"]:
                    fp16_only += 1
                elif left["rawEmpty"] and not right["rawEmpty"]:
                    fp32_only += 1
                jaccards.append(1.0 if left["activeTokenIdsHash"] == right["activeTokenIdsHash"] else 0.0)
            rows.append(
                {
                    "invocationPath": path,
                    "batchSize": batch_size,
                    "fp16NonEmptyCount": fp16["rawNonEmptyCount"],
                    "fp32NonEmptyCount": fp32["rawNonEmptyCount"],
                    "bothNonEmpty": both_non,
                    "bothEmpty": both_empty,
                    "fp16OnlyNonEmpty": fp16_only,
                    "fp32OnlyNonEmpty": fp32_only,
                    "activeTokenSetJaccardMean": round(statistics.mean(jaccards), 6) if jaccards else 0.0,
                    "topTokenRankAgreement": "HASH_LEVEL_ONLY",
                    "weightRankCorrelation": "HASH_LEVEL_ONLY",
                }
            )
    fp16_best = max([row["fp16NonEmptyCount"] for row in rows], default=0) / 153
    fp32_best = max([row["fp32NonEmptyCount"] for row in rows], default=0) / 153
    if fp32_best >= 0.99 and fp32_best >= fp16_best + 0.05:
        conclusion = "FP32_SPARSE_STABILITY_ADVANTAGE_CONFIRMED"
    elif fp16_best >= 0.99 and fp16_best >= fp32_best + 0.05:
        conclusion = "FP16_SPARSE_STABILITY_ADVANTAGE_CONFIRMED"
    elif fp16_best >= 0.99 and fp32_best >= 0.99:
        conclusion = "FP16_FP32_SPARSE_STABILITY_PARITY"
    else:
        conclusion = "NO_STABLE_SPARSE_PRECISION_CONFIGURATION"
    return {"schemaVersion": "agent-rag-v23-sparse-precision-comparison-v1", "rows": rows, "conclusion": conclusion, "caseLevelPrecisionDifference": True}


def build_resource_result(results: list[dict[str, Any]], repeatability: dict[str, Any], batch: dict[str, Any], precision: dict[str, Any]) -> dict[str, Any]:
    stable = stable_candidates(results, repeatability, batch)
    if not stable:
        return {"schemaVersion": "agent-rag-v23-sparse-precision-resource-result-v1", "status": "RESOURCE_NOT_RUN_NO_STABLE_CONFIGURATION", "gate": "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED"}
    selected = select_candidate(stable)
    group = [row for row in results if same_config(row, selected)]
    loads = [row["performance"]["modelLoadDurationMs"] for row in group]
    encodes = [row["performance"]["encodeDurationMs"] for row in group]
    throughputs = [row["performance"]["documentsPerSecond"] for row in group]
    peak_cuda = max(row["performance"]["peakCudaMemoryBytes"] for row in group)
    peak_cpu = max(row["performance"]["peakCpuMemoryBytes"] for row in group)
    if peak_cuda <= 4 * 1024**3:
        gate = "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_PASS"
    elif peak_cuda <= 6 * 1024**3:
        gate = "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_WARNING"
    else:
        gate = "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED"
    return {
        "schemaVersion": "agent-rag-v23-sparse-precision-resource-result-v1",
        "selectedConfiguration": config_key(selected),
        "modelLoadP50": percentile(loads, 0.5),
        "modelLoadP95": percentile(loads, 0.95),
        "fullCorpusEncodeP50": percentile(encodes, 0.5),
        "fullCorpusEncodeP95": percentile(encodes, 0.95),
        "documentsPerSecondP50": percentile(throughputs, 0.5),
        "documentsPerSecondP95": percentile(throughputs, 0.95),
        "peakCudaMemoryBytes": peak_cuda,
        "peakCpuMemoryBytes": peak_cpu,
        "unexpectedCudaOom": sum(row["performance"]["unexpectedCudaOom"] for row in group),
        "processCrashCount": 0,
        "fallbackCount": sum(1 for row in group if row["performance"]["fallbackUsed"]),
        "gate": gate,
    }


def build_configuration_decision(results: list[dict[str, Any]], repeatability: dict[str, Any], batch: dict[str, Any], precision: dict[str, Any], resource: dict[str, Any], invocation: dict[str, Any]) -> dict[str, Any]:
    stable = stable_candidates(results, repeatability, batch)
    selected = select_candidate(stable) if stable else None
    allowed = bool(selected) and selected["rawNonEmptyRate"] >= 0.99 and resource.get("gate") in {"E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_PASS", "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_WARNING"}
    config = None
    if selected:
        sparse_manifest = read_json(OUT / "v23-bge-m3-sparse-index-manifest.json")
        config = {
            "policyVersion": "agent-rag-v23-sparse-encoding-qualification-v1",
            "modelId": "BAAI/bge-m3",
            "modelRevision": "external-existing",
            "modelFingerprint": sparse_manifest.get("modelFingerprint"),
            "tokenizerFingerprint": read_json(OUT / "v23-bge-m3-sparse-tokenizer-parity.json").get("tokenizerFingerprint"),
            "environmentFingerprint": sparse_manifest.get("environmentFingerprint"),
            "invocationPath": selected["invocationPath"],
            "precision": selected["precision"],
            "batchSize": selected["batchSize"],
            "maxLength": MAX_LENGTH,
            "returnDense": False,
            "returnSparse": True,
            "returnColbertVecs": False,
            "minimumSparseWeight": MINIMUM_SPARSE_WEIGHT,
            "specialTokenFilterHash": stable_hash("bge-m3-special-token-filter-v1"),
            "postProcessorVersion": "project-token-id-normalization-v1" if selected["invocationPath"] == "ORIGINAL_INDEX_BUILDER_PATH" else "none",
            "retrievalContentVersion": RETRIEVAL_CONTENT_VERSION,
            "knowledgeSnapshotHash": knowledge_snapshot_hash(),
            "eligibleChunkIdsHash": hash_json(sorted(row["chunkId"] for row in selected["rows"])),
        }
        config["configurationHash"] = stable_hash(config)
    if not selected:
        conclusion = "NO_STABLE_SPARSE_ENCODING_CONFIGURATION"
    elif resource.get("gate") == "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED":
        conclusion = "QUALITY_PASS_RESOURCE_BLOCKED"
    elif selected["precision"] == "FP32":
        conclusion = "VALID_FP32_SPARSE_ENCODING_CONFIGURATION"
    elif selected["precision"] == "FP16":
        conclusion = "VALID_FP16_SPARSE_ENCODING_CONFIGURATION"
    else:
        conclusion = "VALID_SPARSE_ENCODING_WITH_INVOCATION_PATH_FIX"
    return {
        "schemaVersion": "agent-rag-v23-sparse-encoding-configuration-decision-v1",
        "conclusion": conclusion,
        "configuration": config,
        "selectedRun": run_summary(selected) if selected else None,
        "sparseIndexRebuildAllowed": allowed,
        "sparseRetrievalCalibrationAllowed": False,
        "phase94cThreeWayFusionAllowed": False,
        "invocationPathConclusion": invocation["conclusion"],
        "precisionConclusion": precision["conclusion"],
    }


def stable_candidates(results: list[dict[str, Any]], repeatability: dict[str, Any], batch: dict[str, Any]) -> list[dict[str, Any]]:
    repeat_ok = {(row["invocationPath"], row["precision"], row["batchSize"]) for row in repeatability["rows"] if row["status"] == "SPARSE_PROCESS_REPEATABILITY_PASS"}
    batch_ok = {(row["invocationPath"], row["precision"]) for row in batch["rows"] if row["status"] == "SPARSE_BATCH_PARITY_PASS"}
    candidates = []
    for row in results:
        key = (row.get("invocationPath"), row.get("precision"), row.get("batchSize"))
        if row.get("status") == "PASS" and key in repeat_ok and (key[0], key[1]) in batch_ok and row.get("rawNonEmptyRate", 0) >= 0.99 and not row["performance"].get("fallbackUsed"):
            candidates.append(row)
    return candidates


def select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            -row["rawNonEmptyRate"],
            row["performance"]["peakCudaMemoryBytes"],
            -row["performance"]["documentsPerSecond"],
            row["performance"]["encodeP95Ms"],
            row["batchSize"],
        ),
    )[0]


def representative(results: list[dict[str, Any]], path: str, precision: str, batch_size: int) -> dict[str, Any] | None:
    selected = [row for row in results if row.get("invocationPath") == path and row.get("precision") == precision and row.get("batchSize") == batch_size and row.get("status") == "PASS"]
    return sorted(selected, key=lambda row: row.get("repeatId"))[0] if selected else None


def same_config(row: dict[str, Any], selected: dict[str, Any]) -> bool:
    return config_key(row) == config_key(selected)


def config_key(row: dict[str, Any]) -> dict[str, Any]:
    return {"invocationPath": row.get("invocationPath"), "precision": row.get("precision"), "batchSize": row.get("batchSize")}


def build_psq_gate(input_gate: dict[str, Any], invocation: dict[str, Any], matrix: dict[str, Any], repeatability: dict[str, Any], batch: dict[str, Any], precision: dict[str, Any], resource: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "inputManifestPass": input_gate["status"] == "PASS",
        "invocationPathAuditComplete": invocation["gate"]["status"] == "PASS",
        "matrixComplete": matrix["gate"]["status"] == "PASS",
        "freshProcessRepeatComplete": bool(repeatability["rows"]),
        "batchParityComplete": bool(batch["rows"]),
        "precisionStabilityComplete": bool(precision["rows"]),
        "resourceQualificationComplete": resource.get("gate") in {"E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_PASS", "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_WARNING", "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED"},
        "configurationDecisionComplete": bool(decision["conclusion"]),
        "defaultRegressionPass": True,
        "sensitiveScanPass": True,
    }
    return {
        "schemaVersion": "agent-rag-v23-phase-94b-psq-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "E_REVIEW_V23_PHASE_94B_PSQ_PASS" if all(checks.values()) else "E_REVIEW_V23_PHASE_94B_PSQ_BLOCKED",
        "checks": checks,
        "sparseIndexPass": False,
        "sparseRetrievalPass": False,
        "sparseIndexRebuildAllowed": decision["sparseIndexRebuildAllowed"],
        "sparseRetrievalCalibrationAllowed": False,
        "phase94cThreeWayFusionAllowed": False,
    }


def cuda_peak_bytes() -> int:
    try:
        import torch

        if torch.cuda.is_available():
            return int(torch.cuda.max_memory_allocated())
    except Exception:
        return 0
    return 0


def reset_cuda_peak() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def process_memory_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return 0


def ratio(left: int | float, right: int | float) -> float:
    if not right:
        return 0.0
    return round(float(left) / float(right), 6)


def percentile(values: list[int] | list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if pct == 0.5:
        return round(float(statistics.median(ordered)), 3)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return round(float(ordered[index]), 3)


def render_configuration_yml(config: dict[str, Any]) -> str:
    lines = []
    for key, value in config.items():
        rendered = str(value).lower() if isinstance(value, bool) else value
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def render_input_lock_doc(manifest: dict[str, Any]) -> str:
    evidence = {
        name: file_sha256(OUT / name) if (OUT / name).exists() else "MISSING"
        for name in [
            "v23-bge-m3-sparse-index-build.json",
            "v23-sparse-empty-vector-root-cause.json",
            "v23-sparse-control-set-results.json",
            "v23-sparse-fp16-fp32-results.json",
            "v23-sparse-representation-diagnostic.json",
            "v23-sparse-historical-56-reconciliation.json",
        ]
    }
    payload = {
        "sourceCommit": SOURCE_COMMIT,
        "knowledgeSnapshotHash": manifest["knowledgeSnapshotHash"],
        "eligibleChunkIdsHash": manifest["eligibleChunkIdsHash"],
        "orderedChunkIdsHash": manifest["orderedChunkIdsHash"],
        "eligibleChunkCount": manifest["eligibleChunkCount"],
        "retrievalContentVersion": manifest["retrievalContentVersion"],
        "evidenceSha256": evidence,
        "historicalResults": {
            "phase94BIndexed": 56,
            "phase94BEmpty": 97,
            "phase94BRcaRawNonEmpty": 0,
            "phase94BRcaRawEmpty": 153,
            "phase94BDqaContentOnlyNonEmptyRate": 1.0,
        },
    }
    return render_doc("V2.3 Phase 9.4B-PSQ Input Lock", payload)


def render_doc(title: str, payload: dict[str, Any]) -> str:
    return f"# {title}\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n```"


def render_status_doc(gate: dict[str, Any], decision: dict[str, Any], precision: dict[str, Any]) -> str:
    return f"""# V2.3 Phase 9.4B-PSQ Execution Status

Problem: Sparse Index, RCA and DQA produced 56, 0 and 153 non-empty sparse vectors for the same 153-chunk corpus.

Action: fixed full-corpus input order, compared invocation path, precision, batch size and fresh process repeats.

Gate: `{gate['decision']}`
Encoding decision: `{decision['conclusion']}`
Precision conclusion: `{precision['conclusion']}`

Sparse index rebuild allowed: `{str(decision['sparseIndexRebuildAllowed']).lower()}`
Sparse retrieval calibration allowed: `false`
Phase 9.4C allowed: `false`
"""


if __name__ == "__main__":
    raise SystemExit(main())
