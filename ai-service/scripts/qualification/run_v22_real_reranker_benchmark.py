from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for item in (AI_ROOT, SCRIPTS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from agent_rag_phase3a2_common import phase3a2_cases, split_cases  # noqa: E402
from agent_rag_phase3a3_common import build_provider_index, make_provider  # noqa: E402
from agent_rag_phase3a_common import phase3a_all_tenant_chunks  # noqa: E402
from app.agent_rag.eligibility import evaluate_evidence_eligibility  # noqa: E402
from app.agent_rag.metrics import macro_average, score_query  # noqa: E402
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402


DEFAULT_OUT = ROOT / "artifacts" / "real-model-chain"
BENCHMARK_VERSION = "v22-real-reranker-frozen-phase3a2-v1"
GRID = [
    {"candidateK": candidate_k, "finalK": 5, "batchSize": batch_size, "maxLength": max_length}
    for candidate_k in (8, 12, 16, 20)
    for batch_size in (2, 4, 8)
    for max_length in (256, 384, 512)
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["manifest", "calibration", "evaluation", "all"], default="all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))

    payload = benchmark_payload()
    manifest = build_manifest(payload)
    write_json(out_dir / "v22-reranker-benchmark-manifest.json", manifest)
    if args.phase == "manifest":
        print("AGENT_RAG_V22_RERANKER_BENCHMARK_MANIFEST_PASS")
        return 0

    calibration_decision = read_json(out_dir / "v22-reranker-calibration-decision.json") if args.resume else {}
    if args.phase in {"calibration", "all"} and not calibration_decision:
        calibration_decision = run_calibration(payload, manifest, out_dir)
        write_json(out_dir / "v22-reranker-calibration-decision.json", calibration_decision)
    if args.phase == "calibration":
        print("AGENT_RAG_V22_RERANKER_CALIBRATION_PASS")
        return 0

    if not calibration_decision:
        raise SystemExit("CALIBRATION_DECISION_REQUIRED")
    if calibration_decision.get("benchmarkHash") != manifest["benchmarkHash"]:
        raise SystemExit("CALIBRATION_BENCHMARK_HASH_MISMATCH")
    evaluation = run_evaluation(payload, manifest, calibration_decision, out_dir)
    write_json(out_dir / "v22-real-reranker-benchmark-summary.json", evaluation)
    if evaluation["status"] == "PASS":
        print("AGENT_RAG_V22_REAL_RERANKER_EVALUATION_PASS")
        print(evaluation["qualityDecision"])
        return 0
    print("AGENT_RAG_V22_REAL_RERANKER_EVALUATION_FAIL")
    print(evaluation["qualityDecision"])
    return 1


def apply_asset_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    embedding = manifest.get("embedding") or {}
    reranker = manifest.get("reranker") or {}
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ["RAG_BGE_M3_MODEL_PATH"] = str(embedding.get("modelPath") or "")
    os.environ.setdefault("RAG_BGE_M3_DEVICE", "cuda")
    os.environ.setdefault("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls")
    os.environ.setdefault("RAG_BGE_M3_USE_FP16", "true")
    os.environ["RAG_RERANKER_MODEL_PATH"] = str(reranker.get("modelPath") or "")
    os.environ["RAG_RERANKER_TYPE"] = "local-model"
    os.environ.setdefault("RAG_RERANKER_PROVIDER_IMPL", "flagembedding")
    os.environ.setdefault("RAG_RERANKER_DEVICE", "cuda")
    os.environ["RAG_REAL_RERANKER_REQUIRED"] = "true"


def benchmark_payload() -> dict[str, Any]:
    ingestion, chunks = phase3a_all_tenant_chunks()
    cases = phase3a2_cases(chunks)
    split = split_cases(cases)
    return {"ingestion": ingestion, "chunks": chunks, "cases": cases, "split": split}


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    split = payload["split"]
    cases = payload["cases"]
    chunks = payload["chunks"]
    serializable_cases = [
        {
            "caseId": case["caseId"],
            "category": normalize_category(case["retrievalChallengeType"]),
            "tenantId": case["tenantId"],
            "queryHash": stable_hash(case["query"]),
            "relevantChunkIdsHash": hash_ids(case["relevantChunkIds"]),
        }
        for case in cases
    ]
    benchmark_hash = stable_hash({"version": BENCHMARK_VERSION, "cases": serializable_cases})
    return {
        "schemaVersion": "agent-rag-v22-reranker-benchmark-manifest-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "benchmarkHash": benchmark_hash,
        "knowledgeHash": hash_json([chunk.contentHash for chunk in chunks]),
        "calibrationHash": split["calibrationCaseIdsHash"],
        "evaluationHash": split["evaluationCaseIdsHash"],
        "queryCount": len(cases),
        "calibrationCases": len(split["calibration"]),
        "evaluationCases": len(split["evaluation"]),
        "categoryCounts": dict(Counter(normalize_category(case["retrievalChallengeType"]) for case in cases)),
        "evaluationTimeUtc": "2026-07-22T00:00:00Z",
        "timezone": "UTC",
        "createdAtUtc": utc_now(),
    }


def run_calibration(payload: dict[str, Any], manifest: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    rows = []
    provider, runtime = prepare_runtime(payload)
    try:
        for config in GRID:
            summary = evaluate_config(payload, payload["split"]["calibration"], config, runtime=runtime, evaluation_time_utc=manifest["evaluationTimeUtc"])
            rows.append({"config": config, "summary": drop_rows(summary), "selection": selection_tuple(summary)})
            write_json(out_dir / "v22-reranker-calibration-checkpoint.json", {"benchmarkHash": manifest["benchmarkHash"], "completed": len(rows), "lastConfig": config})
    finally:
        try:
            provider.close()
        except Exception:
            pass
    selected = sorted(rows, key=lambda row: row["selection"], reverse=True)[0]
    return {
        "schemaVersion": "agent-rag-v22-reranker-calibration-decision-v1",
        "benchmarkVersion": manifest["benchmarkVersion"],
        "benchmarkHash": manifest["benchmarkHash"],
        "gridCount": len(rows),
        "selected": selected["config"],
        "selectedSummary": selected["summary"],
        "decisionRule": "safety, semantic nDCG@5, semantic MRR, overall no regression, latency",
        "createdAtUtc": utc_now(),
    }


def run_evaluation(payload: dict[str, Any], manifest: dict[str, Any], decision: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    config = dict(decision["selected"])
    provider, runtime = prepare_runtime(payload)
    try:
        summary = evaluate_config(payload, payload["split"]["evaluation"], config, runtime=runtime, evaluation_time_utc=manifest["evaluationTimeUtc"])
    finally:
        try:
            provider.close()
        except Exception:
            pass
    rows_light = [light_row(row) for row in summary["rows"]]
    metrics = drop_rows(summary)
    det_sem = metrics["subsets"]["semantic"]["deterministic"]
    real_sem = metrics["subsets"]["semantic"]["real"]
    det_overall = metrics["subsets"]["overall"]["deterministic"]
    real_overall = metrics["subsets"]["overall"]["real"]
    quality = quality_decision(metrics)
    result = {
        "schemaVersion": "agent-rag-v22-real-reranker-benchmark-summary-v1",
        "status": "PASS" if quality in {"AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED", "AGENT_RAG_V22_REAL_RERANKER_PARITY_ONLY"} else "FAIL",
        "benchmarkVersion": manifest["benchmarkVersion"],
        "benchmarkHash": manifest["benchmarkHash"],
        "knowledgeHash": manifest["knowledgeHash"],
        "calibrationHash": manifest["calibrationHash"],
        "evaluationHash": manifest["evaluationHash"],
        "selected": config,
        "caseCount": len(payload["split"]["evaluation"]),
        "categoryCounts": dict(Counter(row["category"] for row in rows_light)),
        "realRuntimeExecutions": metrics["realRuntimeExecutions"],
        "computeScoreExecutions": metrics["computeScoreExecutions"],
        "tenantViolations": metrics["tenantViolations"],
        "inactiveEvidenceLeaks": metrics["inactiveEvidenceLeaks"],
        "expiredEvidenceLeaks": metrics["expiredEvidenceLeaks"],
        "falseEvidenceCount": metrics["falseEvidenceCount"],
        "falseEvidenceRate": metrics["falseEvidenceRate"],
        "noAnswerCorrectRejection": metrics["noAnswerCorrectRejection"],
        "deterministicSemanticNdcgAt5": det_sem["ndcgAt5"],
        "realSemanticNdcgAt5": real_sem["ndcgAt5"],
        "deterministicSemanticMrr": det_sem["mrr"],
        "realSemanticMrr": real_sem["mrr"],
        "deterministicOverallNdcgAt5": det_overall["ndcgAt5"],
        "realOverallNdcgAt5": real_overall["ndcgAt5"],
        "deterministicOverallMrr": det_overall["mrr"],
        "realOverallMrr": real_overall["mrr"],
        "p50LatencyMs": metrics["latency"]["p50"],
        "p95LatencyMs": metrics["latency"]["p95"],
        "p99LatencyMs": metrics["latency"]["p99"],
        "cudaPeakMb": cuda_peak_mb(),
        "qualityDecision": quality,
        "modelBoundary": "MODEL_RERANKER_VERIFIED" if quality == "AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED" else ("MODEL_RERANKER_VERIFIED_OPTIONAL" if quality == "AGENT_RAG_V22_REAL_RERANKER_PARITY_ONLY" else "MODEL_RERANKER_NOT_VERIFIED"),
        "rowsArtifact": "v22-reranker-evaluation-rows-light.json",
        "createdAtUtc": utc_now(),
    }
    write_json(out_dir / "v22-reranker-evaluation-rows-light.json", {"benchmarkHash": manifest["benchmarkHash"], "rows": rows_light})
    return result


def prepare_runtime(payload: dict[str, Any]) -> tuple[Any, GovernedHybridRuntime]:
    provider = make_provider(os.getenv("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls"))
    index, _ = build_provider_index(provider, "v22-reranker-benchmark", payload["chunks"])
    runtime = GovernedHybridRuntime(chunks=payload["chunks"], provider=provider, faiss_index=index, fallback_provider="sparse", real_dense_required=True, sparse_weight=1.0, dense_weight=0.5)
    return provider, runtime


def evaluate_config(payload: dict[str, Any], cases: list[dict[str, Any]], config: dict[str, Any], *, runtime: GovernedHybridRuntime | None = None, evaluation_time_utc: str = "2026-07-22T00:00:00Z") -> dict[str, Any]:
    os.environ["RAG_RERANKER_CANDIDATE_K"] = str(config["candidateK"])
    os.environ["RAG_RERANKER_FINAL_K"] = str(config["finalK"])
    os.environ["RAG_RERANKER_BATCH_SIZE"] = str(config["batchSize"])
    os.environ["RAG_RERANKER_MAX_LENGTH"] = str(config["maxLength"])
    owns_runtime = runtime is None
    provider = None
    try:
        if runtime is None:
            provider, runtime = prepare_runtime(payload)
        det = GovernedReranker(RerankerConfig(requested_type="deterministic", candidate_k=config["candidateK"], final_k=config["finalK"]))
        real = GovernedReranker(RerankerConfig(requested_type="local-model", model_path=os.getenv("RAG_RERANKER_MODEL_PATH", ""), model_name="BAAI/bge-reranker-v2-m3", device=os.getenv("RAG_RERANKER_DEVICE", "cuda"), use_fp16=True, batch_size=config["batchSize"], max_length=config["maxLength"], candidate_k=config["candidateK"], final_k=config["finalK"], timeout_ms=60000, real_required=True, provider_impl=os.getenv("RAG_RERANKER_PROVIDER_IMPL", "flagembedding"), model_id="BAAI/bge-reranker-v2-m3"))
        rows = []
        for case in cases:
            base, _trace = runtime.search(case["query"], tenant_id=case["tenantId"], mode="hybrid-real", sparse_top_k=20, dense_top_k=20, fusion_top_k=config["candidateK"], rerank_top_k=None, evaluation_time_utc=evaluation_time_utc)
            started = time.perf_counter()
            det_result = det.rerank(case["query"], base, top_k=config["finalK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=evaluation_time_utc)
            real_result = real.rerank(case["query"], base, top_k=config["finalK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=evaluation_time_utc)
            latency = round((time.perf_counter() - started) * 1000, 3)
            rows.append(score_row(case, base, det_result.candidates, real_result.candidates, real_result, latency, evaluation_time_utc=evaluation_time_utc))
        return aggregate(rows)
    finally:
        if owns_runtime and provider is not None:
            try:
                provider.close()
            except Exception:
                pass


def score_row(case: dict[str, Any], hybrid: list[Any], det: list[Any], real: list[Any], real_result: Any, latency: float, *, evaluation_time_utc: str) -> dict[str, Any]:
    relevant = set(case["relevantChunkIds"])
    forbidden = set(case["forbiddenChunkIds"])
    return {
        "caseId": case["caseId"],
        "category": normalize_category(case["retrievalChallengeType"]),
        "expectedChunkIdsHash": hash_ids(case["relevantChunkIds"]),
        "hybrid": score_mode(case, hybrid),
        "deterministic": score_mode(case, det),
        "real": score_mode(case, real),
        "hybridChunkIds": [item.chunkId for item in hybrid[:5]],
        "deterministicChunkIds": [item.chunkId for item in det[:5]],
        "realChunkIds": [item.chunkId for item in real[:5]],
        "rankPositions": {chunk_id: first_rank([item.chunkId for item in real], chunk_id) for chunk_id in relevant},
        "realRuntime": real_result.effectiveType == "local-model" and not real_result.fallbackUsed,
        "computeScoreExecution": real_result.effectiveType == "local-model" and real_result.inputCount > 0,
        "tenantViolation": any(item.tenantId not in {case["tenantId"], "__public__"} for item in real),
        "inactiveEvidenceLeak": any((item.row or {}).get("active", True) is False for item in real),
        "expiredEvidenceLeak": any(evaluate_evidence_eligibility(item, case["tenantId"], evaluation_time_utc).reasonCode == "EXPIRED" for item in real),
        "falseEvidenceCount": 0 if relevant else len(real),
        "latencyMs": latency,
    }


def score_mode(case: dict[str, Any], candidates: list[Any]) -> dict[str, Any]:
    if case["retrievalChallengeType"] == "negative/no-answer":
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    return score_query(
        retrieved_chunk_ids=[item.chunkId for item in candidates],
        relevant_chunk_ids=set(case["relevantChunkIds"]),
        forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
        relevance_grades=case["relevanceGrades"],
    )


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subsets = {}
    for category in ["overall", "lexical", "semantic", "mixed", "temporal", "tenant-isolation", "no-answer"]:
        selected = rows if category == "overall" else [row for row in rows if row["category"] == category]
        subsets[category] = {
            "caseCount": len(selected),
            "hybrid": aggregate_mode([row["hybrid"] for row in selected]),
            "deterministic": aggregate_mode([row["deterministic"] for row in selected]),
            "real": aggregate_mode([row["real"] for row in selected]),
        }
    latencies = [row["latencyMs"] for row in rows]
    no_answer = [row for row in rows if row["category"] == "no-answer"]
    return {
        "caseCount": len(rows),
        "subsets": subsets,
        "realRuntimeExecutions": sum(row["realRuntime"] for row in rows),
        "computeScoreExecutions": sum(row["computeScoreExecution"] for row in rows),
        "tenantViolations": sum(row["tenantViolation"] for row in rows),
        "inactiveEvidenceLeaks": sum(row["inactiveEvidenceLeak"] for row in rows),
        "expiredEvidenceLeaks": sum(row["expiredEvidenceLeak"] for row in rows),
        "falseEvidenceCount": sum(row["falseEvidenceCount"] for row in rows),
        "falseEvidenceRate": round(sum(row["falseEvidenceCount"] for row in rows) / max(1, len(rows) * 5), 4),
        "noAnswerCorrectRejection": round(sum(1 for row in no_answer if not row["realChunkIds"]) / max(1, len(no_answer)), 4),
        "latency": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95), "p99": percentile(latencies, 0.99)},
        "rows": rows,
    }


def aggregate_mode(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    return macro_average(rows, ["hitRateAt5", "recallAt5", "mrr", "ndcgAt5"])


def quality_decision(metrics: dict[str, Any]) -> str:
    det_sem = metrics["subsets"]["semantic"]["deterministic"]
    real_sem = metrics["subsets"]["semantic"]["real"]
    det_all = metrics["subsets"]["overall"]["deterministic"]
    real_all = metrics["subsets"]["overall"]["real"]
    safety_ok = metrics["tenantViolations"] == 0 and metrics["inactiveEvidenceLeaks"] == 0 and metrics["expiredEvidenceLeaks"] == 0 and metrics["falseEvidenceCount"] == 0
    improved = real_sem["ndcgAt5"] > det_sem["ndcgAt5"] and real_sem["mrr"] > det_sem["mrr"]
    no_regression = real_all["ndcgAt5"] + 0.01 >= det_all["ndcgAt5"] and real_all["mrr"] + 0.01 >= det_all["mrr"]
    if safety_ok and improved and no_regression:
        return "AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED"
    if safety_ok and no_regression:
        return "AGENT_RAG_V22_REAL_RERANKER_PARITY_ONLY"
    return "AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION"


def selection_tuple(summary: dict[str, Any]) -> tuple[Any, ...]:
    semantic = summary["subsets"]["semantic"]
    overall = summary["subsets"]["overall"]
    return (
        summary["tenantViolations"] == 0 and summary["falseEvidenceCount"] == 0,
        semantic["real"]["ndcgAt5"],
        semantic["real"]["mrr"],
        overall["real"]["ndcgAt5"] - overall["deterministic"]["ndcgAt5"],
        -summary["latency"]["p95"],
    )


def drop_rows(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "rows"}


def light_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "caseId": row["caseId"],
        "category": row["category"],
        "expectedChunkIdsHash": row["expectedChunkIdsHash"],
        "returnedChunkIds": row["realChunkIds"],
        "rankPositions": row["rankPositions"],
        "latencyMs": row["latencyMs"],
    }


def normalize_category(value: str) -> str:
    return "no-answer" if value == "negative/no-answer" else value


def first_rank(values: list[str], target: str) -> int:
    try:
        return values.index(target) + 1
    except ValueError:
        return 0


def hash_ids(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[max(0, min(index, len(ordered) - 1))], 3)


def cuda_peak_mb() -> float:
    try:
        import torch

        return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2) if torch.cuda.is_available() else 0.0
    except Exception:
        return 0.0


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
