from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.embedding import QwenOfficialTransformersEmbeddingProvider
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase
from scripts.build_step242a_rag_quality_v2 import content_root_hash, load_jsonl, sha256_file
from scripts.run_step233a_qwen_embedding_ab import (
    content_root_hash as vector_content_root_hash,
    current_config,
    release_provider,
)
from scripts.run_step233b_ranking_recovery import (
    candidate_embedding_config,
    dense_rankings,
    encoding_matches_index,
    load_reranker,
    release_reranker,
    rerank_variants,
    safe_provider_metadata,
    weighted_rrf,
)


DATA_DIR = ROOT / "data" / "benchmarks" / "rag_quality_v2"
DEFAULT_DATASET = DATA_DIR / "dataset_frozen_llm_v1.jsonl"
DEFAULT_HOLDOUT = DATA_DIR / "holdout_frozen_llm_v1.jsonl"
DEFAULT_QRELS = DATA_DIR / "qrels_frozen_llm_v1.tsv"
DEFAULT_MANIFEST = DATA_DIR / "manifest_frozen_llm_v1.json"
DEFAULT_CONTRACT = DATA_DIR / "metric_contract_frozen_llm_v1.json"
DEFAULT_CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
DEFAULT_V2_INDEX = ROOT / "artifacts" / "step233a" / "qwen_official_v2"
DEFAULT_B2_DEFINITION = ROOT / "artifacts" / "step233b" / "ranking_recovery.json"
DEFAULT_RERANKER = ROOT.parents[1] / "models" / "v2.2" / "bge-reranker-v2-m3"
DEFAULT_PARSER_GATE = ROOT / "artifacts" / "step242a" / "parser_quality_baseline.json"
DEFAULT_WORKFLOW_GATE = ROOT / "artifacts" / "step22" / "frozen_benchmark.json"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step242d"

EXPECTED_WORKFLOW_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
EXPECTED_HOLDOUT_SHA = "439ED6A72CF337760570677E1A60C566031022E01D1A50927124CED56BE687FF"
EXPECTED_QRELS_SHA = "4D8C3E73C1A90AAB419AF1A2FDDF7EBC648F0F14518C2AEC68261F5CA6A3CB28"
EXPECTED_CONTRACT_SHA = "73E3DE34EE45125CECC4F791C8D477BE162E6A982950242ADBBBF47A736EE90E"
EXPECTED_V2_INDEX_SHA = "BB5EC3372D70F78632678648E48D5992CCDD310A889C0ACBB1FB73E488A3CE4A"
EXPECTED_V2_META_SHA = "17C056B0E8A249B853B769E4C6443C27C12CFD017E0B17C5AB9BAF6BF48BF8D9"
EXPECTED_B2_DEFINITION_SHA = "8E7D7172BE133D841E7F8046D9E507273965CCCA5F24459986C9E6E9BF769F13"
EXPECTED_PROVIDER_FINGERPRINT = "cef5b930313ba2f5a0c874df6c0aff52"
EXPECTED_RERANKER_FINGERPRINT = "b545785ab1a53bb24156c98d4f77f3c0"

B2_PROTOCOL = {
    "name": "B2_hybrid_reranked_frozen_holdout",
    "queryRole": "review_text_plus_frozen_upstream_risk_hints",
    "embeddingProfile": "qwen3-official-retrieval-v2",
    "embeddingMaxLength": 512,
    "denseCandidateK": 20,
    "bm25CandidateK": 20,
    "rrfK": 60,
    "bm25Weight": 1.0,
    "denseWeight": 1.0,
    "rerankTopK": 5,
    "finalTopK": 5,
    "rerankerModel": "BAAI/bge-reranker-v2-m3",
    "rerankerDevice": "cpu",
    "noAnswerPolicy": "empty_frozen_upstream_risk_hints_abstain_before_retrieval",
}


class HoldoutIntegrityError(RuntimeError):
    pass


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Execute the Step 24.2D frozen B2 Holdout exactly once.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--embedding-batch-size", type=int, default=8)
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.embedding_batch_size < 1 or args.reranker_batch_size < 1:
        raise SystemExit("STEP242D_BATCH_SIZE_INVALID")

    paths = default_paths(args.output_dir.resolve())
    preflight = validate_frozen_inputs(paths)
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return 0

    assert_not_consumed(paths)
    paths["outputDir"].mkdir(parents=True, exist_ok=True)
    lock = paths["lock"]
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps({"status": "IN_PROGRESS", "startedAt": utc_now()}, ensure_ascii=False) + "\n")
        report = execute_holdout(paths, preflight, args.embedding_batch_size, args.reranker_batch_size)
        write_json_atomic(paths["report"], report)
        seal = {
            "schemaVersion": "step24.2d-holdout-execution-seal-v1",
            "status": "CONSUMED",
            "gate": report["gate"],
            "executedAt": report["executedAt"],
            "datasetVersion": report["dataset"]["version"],
            "holdoutSha256": preflight["hashes"]["holdout"],
            "qrelsSha256": preflight["hashes"]["qrels"],
            "metricContractSha256": preflight["hashes"]["metricContract"],
            "b2ProtocolHash": report["protocol"]["hash"],
            "resultSha256": sha256_file(paths["report"]),
            "rerunAllowed": False,
            "limitation": "Single machine-adjudicated Holdout execution; this is not human gold.",
        }
        write_json_atomic(paths["seal"], seal)
    finally:
        lock.unlink(missing_ok=True)

    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["gate"].startswith("PASS") else 1


def default_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "dataset": DEFAULT_DATASET,
        "holdout": DEFAULT_HOLDOUT,
        "qrels": DEFAULT_QRELS,
        "manifest": DEFAULT_MANIFEST,
        "contract": DEFAULT_CONTRACT,
        "chunks": DEFAULT_CHUNKS,
        "v2Index": DEFAULT_V2_INDEX / "policy_vectors.faiss",
        "v2Meta": DEFAULT_V2_INDEX / "policy_vectors_meta.json",
        "v2IndexDir": DEFAULT_V2_INDEX,
        "b2Definition": DEFAULT_B2_DEFINITION,
        "reranker": DEFAULT_RERANKER,
        "parserGate": DEFAULT_PARSER_GATE,
        "workflowGate": DEFAULT_WORKFLOW_GATE,
        "outputDir": output_dir,
        "report": output_dir / "frozen_holdout_b2_result.json",
        "seal": output_dir / "holdout_execution_seal.json",
        "lock": output_dir / ".holdout_execution.lock",
    }


def validate_frozen_inputs(paths: dict[str, Path]) -> dict[str, Any]:
    required_files = (
        "dataset",
        "holdout",
        "qrels",
        "manifest",
        "contract",
        "chunks",
        "v2Index",
        "v2Meta",
        "b2Definition",
        "parserGate",
        "workflowGate",
    )
    missing = [name for name in required_files if not paths[name].is_file()]
    if not paths["reranker"].is_dir():
        missing.append("reranker")
    if missing:
        raise HoldoutIntegrityError(f"STEP242D_REQUIRED_ASSET_MISSING:{','.join(missing)}")

    manifest = read_json(paths["manifest"])
    contract = read_json(paths["contract"])
    parser_gate = read_json(paths["parserGate"])
    workflow_gate = read_json(paths["workflowGate"])
    b2_definition = read_json(paths["b2Definition"])
    cases = [RagQualityCase.model_validate(item) for item in load_jsonl(paths["holdout"])]
    chunks = load_policy_chunks(paths["chunks"])
    index_meta = read_json(paths["v2Meta"])
    hashes = {
        "dataset": sha256_file(paths["dataset"]),
        "holdout": sha256_file(paths["holdout"]),
        "qrels": sha256_file(paths["qrels"]),
        "metricContract": sha256_file(paths["contract"]),
        "v2Index": sha256_file(paths["v2Index"]),
        "v2Meta": sha256_file(paths["v2Meta"]),
        "b2Definition": sha256_file(paths["b2Definition"]),
        "workflowGold": str(workflow_gate.get("dataset", {}).get("sha256") or ""),
    }
    provider = index_meta.get("provider") or {}
    checks = {
        "manifestFrozen": manifest.get("status") == "FROZEN_LLM_ADJUDICATED",
        "holdoutExecutionAuthorized": manifest.get("annotation", {}).get("holdoutExecutionAllowed") is True,
        "datasetHashMatchesManifest": hashes["dataset"] == manifest.get("files", {}).get("dataset", {}).get("sha256"),
        "holdoutHashFrozen": hashes["holdout"] == EXPECTED_HOLDOUT_SHA == manifest.get("files", {}).get("holdout", {}).get("sha256"),
        "qrelsHashFrozen": hashes["qrels"] == EXPECTED_QRELS_SHA == manifest.get("files", {}).get("qrels", {}).get("sha256"),
        "metricContractHashFrozen": hashes["metricContract"] == EXPECTED_CONTRACT_SHA == manifest.get("files", {}).get("metricContract", {}).get("sha256"),
        "workflowGoldFrozen": hashes["workflowGold"] == EXPECTED_WORKFLOW_SHA == manifest.get("frozenWorkflowGold", {}).get("sha256"),
        "holdoutCountIs40": len(cases) == 40,
        "holdoutOnly": all(case.split == "holdout" for case in cases),
        "holdoutNotCandidateExposed": all(not case.candidateExposure for case in cases),
        "holdoutReleaseVerified": all(
            case.annotationStatus == "llm_adjudicated"
            and case.qrelCompleteness == "complete"
            and not case.requiresAdjudication
            for case in cases
        ),
        "corpusCountIs71": len(chunks) == 71 == int(manifest.get("corpus", {}).get("chunkCount", 0)),
        "corpusHashFrozen": content_root_hash(chunks) == manifest.get("corpus", {}).get("contentRootHash"),
        "vectorCorpusMatches": index_meta.get("contentRootHash") == vector_content_root_hash(chunks),
        "vectorCountIs71": int(index_meta.get("vectorCount", 0)) == 71,
        "vectorDimensionIs1024": int(index_meta.get("dimension", 0)) == 1024,
        "vectorIndexFrozen": hashes["v2Index"] == EXPECTED_V2_INDEX_SHA,
        "vectorMetadataFrozen": hashes["v2Meta"] == EXPECTED_V2_META_SHA,
        "embeddingProfileFrozen": provider.get("embeddingProfile") == B2_PROTOCOL["embeddingProfile"],
        "embeddingFingerprintFrozen": provider.get("modelFingerprint") == EXPECTED_PROVIDER_FINGERPRINT,
        "embeddingMaxLengthFrozen": int(provider.get("maxLength", 0)) == B2_PROTOCOL["embeddingMaxLength"],
        "b2DefinitionFrozen": hashes["b2Definition"] == EXPECTED_B2_DEFINITION_SHA,
        "b2Selected": b2_definition.get("promotion", {}).get("selectedVariant") == "B2",
        "b2ConfigFrozen": b2_definition.get("variants", {}).get("B2", {}).get("config") == {"base": "B0", "rerankTopK": 5},
        "rerankerFingerprintFrozen": b2_definition.get("reranker", {}).get("modelFingerprint") == EXPECTED_RERANKER_FINGERPRINT,
        "parserHardGatePassed": parser_gate.get("hardSafetyGate") == "PASS",
        "silentParserLossIsZero": int(parser_gate.get("silentParserLossCount", -1)) == 0,
        "workflowSafetyBound": int(workflow_gate.get("governance", {}).get("highRiskAutoPassFalseNegatives", -1)) == 0,
        "thresholdsFrozenFromDev": contract.get("qualityThresholdPolicy", {}).get("status") == "FROZEN"
        and contract.get("qualityThresholdPolicy", {}).get("frozenFromSplit") == "dev"
        and contract.get("qualityThresholdPolicy", {}).get("holdoutConsulted") is False
        and contract.get("qualityThresholdPolicy", {}).get("referenceVariant") == "B2",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise HoldoutIntegrityError(f"STEP242D_PREFLIGHT_FAILED:{','.join(failed)}")
    return {
        "schemaVersion": "step24.2d-preflight-v1",
        "gate": "PASS",
        "checks": checks,
        "hashes": hashes,
        "caseCount": len(cases),
        "riskCaseCount": sum(bool(case.riskTypes) for case in cases),
        "noAnswerCaseCount": sum(case.noAnswer for case in cases),
        "thresholds": contract["qualityThresholdPolicy"]["thresholds"],
        "singleJudgeLimitation": True,
    }


def assert_not_consumed(paths: dict[str, Path]) -> None:
    if paths["seal"].exists() or paths["report"].exists():
        raise HoldoutIntegrityError("STEP242D_HOLDOUT_ALREADY_CONSUMED")
    if paths["lock"].exists():
        raise HoldoutIntegrityError("STEP242D_HOLDOUT_EXECUTION_IN_PROGRESS")


def execute_holdout(
    paths: dict[str, Path],
    preflight: dict[str, Any],
    embedding_batch_size: int,
    reranker_batch_size: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    all_cases = [RagQualityCase.model_validate(item) for item in load_jsonl(paths["holdout"])]
    risk_cases = [case for case in all_cases if case.riskTypes]
    chunks = load_policy_chunks(paths["chunks"])
    index_meta = read_json(paths["v2Meta"])
    expanded_queries = [
        " ".join([case.reviewText, PolicyEvidenceRetriever._expand_risk_hints(case.riskTypes)]).strip()
        for case in risk_cases
    ]

    bm25_started = time.perf_counter()
    retriever = PolicyEvidenceRetriever(chunks)
    bm25_rankings = [
        retriever._bm25_search(query, case.riskTypes, top_k=B2_PROTOCOL["bm25CandidateK"])
        for query, case in zip(expanded_queries, risk_cases, strict=True)
    ]
    bm25_ms = elapsed_ms(bm25_started)

    config = current_config(batch_size=embedding_batch_size)
    provider = QwenOfficialTransformersEmbeddingProvider(candidate_embedding_config(config, index_meta))
    provider_before = safe_provider_metadata(provider.metadata())
    if provider_before.get("modelFingerprint") != EXPECTED_PROVIDER_FINGERPRINT:
        raise HoldoutIntegrityError("STEP242D_RUNTIME_EMBEDDING_FINGERPRINT_MISMATCH")
    dense_ranked, embedding_ms = dense_rankings(
        provider,
        paths["v2IndexDir"],
        chunks,
        expanded_queries,
    )
    provider_after = safe_provider_metadata(provider.metadata())
    encoding_match = encoding_matches_index(provider_after, index_meta.get("provider", {}))
    release_provider(provider)
    if not encoding_match:
        raise HoldoutIntegrityError("STEP242D_RUNTIME_EMBEDDING_PROFILE_MISMATCH")

    fusion_started = time.perf_counter()
    fused = [
        weighted_rrf(
            bm25,
            dense,
            top_k=B2_PROTOCOL["rerankTopK"],
            k=B2_PROTOCOL["rrfK"],
            bm25_weight=B2_PROTOCOL["bm25Weight"],
            dense_weight=B2_PROTOCOL["denseWeight"],
        )
        for bm25, dense in zip(bm25_rankings, dense_ranked, strict=True)
    ]
    fusion_ms = elapsed_ms(fusion_started)

    reranker, reranker_meta = load_reranker(paths["reranker"])
    if reranker_meta.get("modelFingerprint") != EXPECTED_RERANKER_FINGERPRINT:
        raise HoldoutIntegrityError("STEP242D_RUNTIME_RERANKER_FINGERPRINT_MISMATCH")
    reranked, _, reranker_ms, pair_count = rerank_variants(
        reranker,
        expanded_queries,
        fused,
        fused,
        batch_size=reranker_batch_size,
    )
    release_reranker(reranker)

    run_rows = build_run_rows(all_cases, risk_cases, reranked)
    evaluation = evaluate_retrieval_run(all_cases, run_rows, run_name=B2_PROTOCOL["name"])
    contract = read_json(paths["contract"])
    threshold_checks = evaluate_thresholds(evaluation["metrics"], contract["qualityThresholdPolicy"]["thresholds"])
    slice_checks = evaluate_slice_safety(evaluation["slices"])
    gate_checks = {
        "preflightPassed": preflight["gate"] == "PASS",
        "all40CasesEvaluated": evaluation["metrics"]["caseCount"] == 40,
        "all35RiskCasesRankable": evaluation["metrics"]["rankableCaseCount"] == 35,
        "all5NoAnswerCasesEvaluated": evaluation["metrics"]["noAnswerCaseCount"] == 5,
        "releaseVerifiedWithDeclaredLimitation": evaluation["evaluationStatus"]
        == "PROMOTION_ELIGIBLE_WITH_SINGLE_JUDGE_LIMITATION",
        "retrievalPromotionGatePassed": evaluation["promotionGate"] == "PASS",
        "allFrozenThresholdsPassed": all(threshold_checks.values()),
        "criticalSliceSafetyPassed": all(slice_checks.values()),
    }
    gate = "PASS_WITH_SINGLE_JUDGE_LIMITATION" if all(gate_checks.values()) else "FAIL"
    protocol = {
        "spec": B2_PROTOCOL,
        "hash": stable_hash(B2_PROTOCOL),
        "conditionedRetrieval": True,
        "conditionedOn": "frozen upstream riskTypes; Router quality is evaluated separately",
        "holdoutExecutionCount": 1,
        "tuningAfterExecutionAllowed": False,
    }
    return {
        "schemaVersion": "step24.2d-frozen-holdout-result-v1",
        "gate": gate,
        "executedAt": utc_now(),
        "limitation": "Machine-adjudicated single-Judge Holdout for a personal demo; not human gold.",
        "dataset": {
            "version": all_cases[0].datasetVersion,
            "caseCount": len(all_cases),
            "riskCaseCount": len(risk_cases),
            "noAnswerCaseCount": sum(case.noAnswer for case in all_cases),
            "holdoutSha256": preflight["hashes"]["holdout"],
            "candidateExposureCount": sum(case.candidateExposure for case in all_cases),
        },
        "protocol": protocol,
        "integrity": preflight,
        "runtime": {
            "embedding": provider_after,
            "index": {
                "vectorCount": index_meta.get("vectorCount"),
                "dimension": index_meta.get("dimension"),
                "indexType": index_meta.get("indexType"),
                "metric": index_meta.get("metric"),
            },
            "reranker": reranker_meta,
            "pairCount": pair_count,
            "latencyMs": {
                "bm25": bm25_ms,
                "queryEmbeddingBatch": embedding_ms,
                "rrf": fusion_ms,
                "reranker": reranker_ms,
                "total": elapsed_ms(started),
            },
        },
        "thresholdChecks": threshold_checks,
        "sliceSafetyChecks": slice_checks,
        "gateChecks": gate_checks,
        "evaluation": evaluation,
        "policy": {
            "holdoutConsumed": True,
            "rerunAllowed": False,
            "thresholdMutationAllowed": False,
            "qrelMutationAllowed": False,
            "failedPromotionRequiresNewHoldoutVersion": True,
        },
    }


def build_run_rows(
    all_cases: Iterable[RagQualityCase],
    risk_cases: list[RagQualityCase],
    rankings: list[list[tuple[float, Any]]],
) -> list[RetrievalRunCase]:
    ranking_by_case = {
        case.caseId: ranking
        for case, ranking in zip(risk_cases, rankings, strict=True)
    }
    rows: list[RetrievalRunCase] = []
    for case in all_cases:
        if not case.riskTypes:
            rows.append(
                RetrievalRunCase(
                    caseId=case.caseId,
                    abstained=True,
                    metadata={"reason": "EMPTY_FROZEN_UPSTREAM_RISK_HINTS"},
                )
            )
            continue
        hits = [
            RetrievalHit(
                chunkId=chunk.chunkId,
                score=float(score),
                sourceName=chunk.sourceName,
                sourceUrl=chunk.sourceUrl,
                sectionPath=chunk.sectionPath,
                clauseId=chunk.clauseId,
                contentHash=chunk.contentHash,
            )
            for score, chunk in ranking_by_case[case.caseId]
        ]
        rows.append(RetrievalRunCase(caseId=case.caseId, hits=hits, metadata={"variant": "B2"}))
    return rows


def evaluate_thresholds(metrics: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, bool]:
    exact_zero = {
        "unjudgedItemRateAt5",
        "duplicateItemRateAt5",
        "highRiskAutoPassCount",
        "silentParserLossCount",
    }
    checks: dict[str, bool] = {}
    for name, threshold in thresholds.items():
        if name == "highRiskAutoPassCount":
            observed = 0
        elif name == "silentParserLossCount":
            observed = 0
        else:
            observed = metrics.get(name)
        checks[name] = observed is not None and (
            float(observed) == float(threshold)
            if name in exact_zero or float(threshold) == 1.0
            else float(observed) >= float(threshold)
        )
    return checks


def evaluate_slice_safety(slices: dict[str, Any]) -> dict[str, bool]:
    risk_slices = slices.get("riskType", {})
    return {
        "everyRiskTypeHasEvidenceAt5": bool(risk_slices)
        and all(float(row.get("candidateEvidenceHitRateAt5", 0.0)) == 1.0 for row in risk_slices.values()),
        "everyRiskTypeCitationValid": bool(risk_slices)
        and all(float(row.get("citationValidCaseRate", 0.0)) == 1.0 for row in risk_slices.values()),
        "noRiskTypeHasHighRiskEvidenceMiss": bool(risk_slices)
        and all(int(row.get("highRiskEvidenceMissCountAt5", 0)) == 0 for row in risk_slices.values()),
    }


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "executedAt": report["executedAt"],
        "dataset": report["dataset"],
        "protocol": report["protocol"],
        "metrics": report["evaluation"]["metrics"],
        "thresholdChecks": report["thresholdChecks"],
        "sliceSafetyChecks": report["sliceSafetyChecks"],
        "gateChecks": report["gateChecks"],
        "latencyMs": report["runtime"]["latencyMs"],
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
