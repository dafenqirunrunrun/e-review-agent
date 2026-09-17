from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"
BENCHMARK = ROOT / "ai-service" / "scripts" / "qualification" / "run_v22_real_reranker_benchmark.py"
RERANKER = ROOT / "ai-service" / "app" / "agent_rag" / "reranker.py"


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    assets = read_json(OUT / "model-assets-summary.json")
    manifest = read_json(OUT / "v22-reranker-benchmark-manifest.json")
    calibration = read_json(OUT / "v22-reranker-calibration-decision.json")
    summary = read_json(OUT / "v22-real-reranker-benchmark-summary.json")
    rows_payload = read_json(OUT / "v22-reranker-evaluation-rows-light.json")
    soak = read_json(OUT / "v22-real-model-soak-summary.json")
    llm_summary = read_json(OUT / "v22-real-llm-quality-summary.json")
    llm_gate = read_json(OUT / "v22-real-llm-gate.json")

    lock = build_llm_soak_lock(assets, manifest, summary, soak, llm_summary, llm_gate)
    write_markdown(DOCS / "V22_LLM_AND_SOAK_EVIDENCE_LOCK.md", render_lock(lock))

    baseline = build_regression_baseline(assets, manifest, calibration, summary, rows_payload)
    write_json(OUT / "v22-reranker-regression-baseline.json", baseline)

    harness = build_harness_audit()
    write_json(OUT / "v22-reranker-harness-audit.json", harness)

    cases = build_case_analysis(rows_payload)
    write_json(OUT / "v22-reranker-regression-case-analysis.json", cases)
    write_markdown(DOCS / "V22_RERANKER_REGRESSION_DIAGNOSIS.md", render_reranker_diagnosis(baseline, harness, cases))

    print("AGENT_RAG_V22_RERANKER_REGRESSION_AUDIT_RECORDED")
    return 0


def build_llm_soak_lock(
    assets: dict[str, Any],
    manifest: dict[str, Any],
    reranker_summary: dict[str, Any],
    soak: dict[str, Any],
    llm_summary: dict[str, Any],
    llm_gate: dict[str, Any],
) -> dict[str, Any]:
    asset_items = assets.get("assets", {})
    return {
        "schemaVersion": "agent-rag-v22-llm-soak-evidence-lock-v1",
        "createdAtUtc": now(),
        "sourceCommit": "57858817",
        "decision": {
            "llmQuality": llm_gate.get("status"),
            "llmBoundary": llm_summary.get("modelBoundary"),
            "soakStatus": soak.get("status"),
            "rerankerQuality": reranker_summary.get("qualityDecision"),
            "rerankerBoundary": reranker_summary.get("modelBoundary"),
        },
        "assets": {
            name: {
                "modelId": value.get("modelId"),
                "provider": value.get("provider"),
                "revision": value.get("revision"),
                "assetFingerprint": value.get("assetFingerprint"),
                "license": value.get("license"),
                "fileCount": value.get("fileCount"),
                "totalBytes": value.get("totalBytes"),
                "path": "<repo-external-model-path-omitted>",
            }
            for name, value in asset_items.items()
        },
        "hashes": {
            "benchmarkHash": manifest.get("benchmarkHash"),
            "knowledgeHash": manifest.get("knowledgeHash"),
            "calibrationHash": manifest.get("calibrationHash"),
            "evaluationHash": manifest.get("evaluationHash"),
            "soakSummarySha256": sha256(OUT / "v22-real-model-soak-summary.json"),
            "llmQualitySummarySha256": sha256(OUT / "v22-real-llm-quality-summary.json"),
            "llmGateSha256": sha256(OUT / "v22-real-llm-gate.json"),
            "rerankerBenchmarkSummarySha256": sha256(OUT / "v22-real-reranker-benchmark-summary.json"),
        },
        "soak": {
            "durationSeconds": soak.get("durationSeconds"),
            "requestCount": soak.get("requestCount"),
            "successCount": soak.get("successCount"),
            "realBgeExecutions": soak.get("realBgeExecutions"),
            "realRerankerExecutions": soak.get("realRerankerExecutions"),
            "realLlmExecutions": soak.get("realLlmExecutions"),
            "fallbackCount": soak.get("fallbackCount"),
            "unhandledErrorCount": soak.get("unhandledErrorCount"),
            "unexpectedOom": soak.get("unexpectedOom"),
            "p50LatencyMs": soak.get("p50LatencyMs"),
            "p95LatencyMs": soak.get("p95LatencyMs"),
            "p99LatencyMs": soak.get("p99LatencyMs"),
            "cudaStartMb": soak.get("cudaStartMb"),
            "cudaPeakMb": soak.get("cudaPeakMb"),
            "cudaEndMb": soak.get("cudaEndMb"),
            "modelLoadCount": soak.get("modelLoadCount"),
            "modelEvictionCount": soak.get("modelEvictionCount"),
            "modelSwitchCount": soak.get("modelSwitchCount"),
            "stabilityDecision": soak.get("stabilityDecision"),
        },
        "llmQuality": {
            "caseCount": llm_summary.get("caseCount"),
            "datasetHash": llm_summary.get("datasetHash"),
            "schemaValidRate": llm_summary.get("hardGates", {}).get("schemaValidRate"),
            "groundedRate": llm_summary.get("hardGates", {}).get("groundedRate"),
            "tenantViolations": llm_summary.get("hardGates", {}).get("tenantViolations"),
            "promptInjectionUnsafeExecutions": llm_summary.get("hardGates", {}).get("promptInjectionUnsafeExecutions"),
            "piiLeaks": llm_summary.get("hardGates", {}).get("piiLeaks"),
            "realGenerateExecutions": llm_summary.get("realGenerateExecutions"),
            "fallbackExecutions": llm_summary.get("fallbackExecutions"),
        },
    }


def build_regression_baseline(
    assets: dict[str, Any],
    manifest: dict[str, Any],
    calibration: dict[str, Any],
    summary: dict[str, Any],
    rows_payload: dict[str, Any],
) -> dict[str, Any]:
    selected = summary.get("selected") or calibration.get("selected") or {}
    reranker = assets.get("assets", {}).get("reranker", {})
    rows = rows_payload.get("rows", [])
    regressed = [row.get("caseId") for row in rows if is_regressed_row(row)]
    return {
        "schemaVersion": "agent-rag-v22-reranker-regression-baseline-v1",
        "createdAtUtc": now(),
        "sourceCommit": "57858817",
        "model": {
            "modelId": reranker.get("modelId") or "BAAI/bge-reranker-v2-m3",
            "revision": reranker.get("revision"),
            "provider": reranker.get("provider"),
            "assetFingerprint": reranker.get("assetFingerprint"),
            "license": reranker.get("license"),
        },
        "configuration": {
            "dtype": "fp16",
            "useFp16": True,
            "candidateK": selected.get("candidateK"),
            "finalK": selected.get("finalK"),
            "batchSize": selected.get("batchSize"),
            "maxLength": selected.get("maxLength"),
            "normalize": True,
        },
        "benchmark": {
            "benchmarkVersion": manifest.get("benchmarkVersion") or summary.get("benchmarkVersion"),
            "benchmarkHash": manifest.get("benchmarkHash") or summary.get("benchmarkHash"),
            "knowledgeHash": manifest.get("knowledgeHash") or summary.get("knowledgeHash"),
            "calibrationHash": manifest.get("calibrationHash") or summary.get("calibrationHash"),
            "evaluationHash": manifest.get("evaluationHash") or summary.get("evaluationHash"),
        },
        "quality": {
            "status": summary.get("status"),
            "qualityDecision": summary.get("qualityDecision"),
            "modelBoundary": summary.get("modelBoundary"),
            "caseCount": summary.get("caseCount"),
            "realRuntimeExecutions": summary.get("realRuntimeExecutions"),
            "computeScoreExecutions": summary.get("computeScoreExecutions"),
            "tenantViolations": summary.get("tenantViolations"),
            "inactiveEvidenceLeaks": summary.get("inactiveEvidenceLeaks"),
            "expiredEvidenceLeaks": summary.get("expiredEvidenceLeaks"),
            "falseEvidenceCount": summary.get("falseEvidenceCount"),
            "falseEvidenceRate": summary.get("falseEvidenceRate"),
            "noAnswerCorrectRejection": summary.get("noAnswerCorrectRejection"),
            "deterministicSemanticNdcgAt5": summary.get("deterministicSemanticNdcgAt5"),
            "realSemanticNdcgAt5": summary.get("realSemanticNdcgAt5"),
            "deterministicSemanticMrr": summary.get("deterministicSemanticMrr"),
            "realSemanticMrr": summary.get("realSemanticMrr"),
            "deterministicOverallNdcgAt5": summary.get("deterministicOverallNdcgAt5"),
            "realOverallNdcgAt5": summary.get("realOverallNdcgAt5"),
            "deterministicOverallMrr": summary.get("deterministicOverallMrr"),
            "realOverallMrr": summary.get("realOverallMrr"),
            "p50LatencyMs": summary.get("p50LatencyMs"),
            "p95LatencyMs": summary.get("p95LatencyMs"),
            "p99LatencyMs": summary.get("p99LatencyMs"),
            "cudaPeakMb": summary.get("cudaPeakMb"),
        },
        "regressedCaseIds": regressed,
        "regressedCaseCount": len(regressed),
        "rowsArtifact": summary.get("rowsArtifact"),
    }


def build_harness_audit() -> dict[str, Any]:
    benchmark_text = BENCHMARK.read_text(encoding="utf-8")
    reranker_text = RERANKER.read_text(encoding="utf-8")
    checks = {
        "sameQueryForHybridDeterministicReal": all(token in benchmark_text for token in ["runtime.search(case[\"query\"]", "det.rerank(case[\"query\"]", "real.rerank(case[\"query\"]"]),
        "sameKnowledgeSnapshot": "phase3a_all_tenant_chunks()" in benchmark_text,
        "sameCandidatePool": "base, _trace = runtime.search" in benchmark_text and "det.rerank(case[\"query\"], base" in benchmark_text and "real.rerank(case[\"query\"], base" in benchmark_text,
        "sameTenantFilter": "tenant_id=case[\"tenantId\"]" in benchmark_text,
        "sameFinalK": "top_k=config[\"finalK\"]" in benchmark_text,
        "identityMappingByChunkId": "item.chunkId" in benchmark_text and "rankPositions" in benchmark_text,
        "scoreDescendingSort": "key=lambda value: (-value[0], value[1].rawRank or 9999, value[1].chunkId)" in reranker_text,
        "stableTieBreakOriginalRankChunkId": "value[1].rawRank or 9999" in reranker_text and "value[1].chunkId" in reranker_text,
        "missingScoreNotHighest": "OUTPUT_COUNT_MISMATCH" in reranker_text and "_validate_score(score)" in reranker_text,
        "fallbackNotCountedAsReal": "real_result.effectiveType == \"local-model\" and not real_result.fallbackUsed" in benchmark_text,
        "noDocumentIdAsPassageInput": "item.row.get(\"content\") or item.row.get(\"text\")" in reranker_text,
        "normalizeDoesNotChangeOrderTested": False,
    }
    return {
        "schemaVersion": "agent-rag-v22-reranker-harness-audit-v1",
        "createdAtUtc": now(),
        "sourceCommit": "57858817",
        "status": "PASS_WITH_TEST_GAPS" if all(value for key, value in checks.items() if key != "normalizeDoesNotChangeOrderTested") else "NEEDS_FIX",
        "checks": checks,
        "observations": [
            "Static inspection confirms runtime sorting uses score descending with original rank and chunk id tie-breaks.",
            "Benchmark rows do not include raw reranker scores, so score normalization order must be covered by a real model unit test.",
            "No-answer cases currently return top-k candidates; this is measured as false evidence and is not hidden as a runtime pass.",
            "Expired evidence leaks are measured by the benchmark; runtime candidate validation does not currently reject effective_to rows before reranking.",
        ],
    }


def build_case_analysis(rows_payload: dict[str, Any]) -> dict[str, Any]:
    rows = rows_payload.get("rows", [])
    cases = []
    root_counts: dict[str, int] = {}
    for row in rows:
        root = classify_case(row)
        root_counts[root] = root_counts.get(root, 0) + 1
        ranks = [rank for rank in (row.get("rankPositions") or {}).values() if isinstance(rank, int)]
        cases.append(
            {
                "caseId": row.get("caseId"),
                "category": row.get("category"),
                "queryLengthTokens": None,
                "candidateCount": None,
                "relevantCandidateOriginalRanks": [],
                "relevantCandidateRerankedRanks": ranks,
                "relevantCandidateScores": [],
                "topReturnedChunkIds": row.get("returnedChunkIds", []),
                "truncatedCandidateCount": None,
                "rootCause": root,
                "safeSummary": "Light row artifact contains chunk ids and ranks only; original private text is intentionally omitted.",
            }
        )
    return {
        "schemaVersion": "agent-rag-v22-reranker-regression-case-analysis-v1",
        "createdAtUtc": now(),
        "sourceCommit": "57858817",
        "benchmarkHash": rows_payload.get("benchmarkHash"),
        "caseCount": len(cases),
        "rootCauseCounts": root_counts,
        "limitations": [
            "Existing light rows do not include query text, candidate pool size, raw scores, or deterministic ranks.",
            "Root-cause labels are conservative and should be refined after score-direction and parity tests run.",
        ],
        "cases": cases,
    }


def classify_case(row: dict[str, Any]) -> str:
    category = row.get("category")
    ranks = list((row.get("rankPositions") or {}).values())
    if category == "no-answer" and row.get("returnedChunkIds"):
        return "CANDIDATE_POOL_TOO_SMALL"
    if ranks and all(rank == 0 for rank in ranks):
        return "SEMANTIC_MODEL_MISMATCH"
    if any(isinstance(rank, int) and rank > 5 for rank in ranks):
        return "TRUNCATION_LOSS"
    return "UNKNOWN"


def is_regressed_row(row: dict[str, Any]) -> bool:
    if row.get("category") == "no-answer" and row.get("returnedChunkIds"):
        return True
    ranks = list((row.get("rankPositions") or {}).values())
    return bool(ranks) and not any(isinstance(rank, int) and 1 <= rank <= 5 for rank in ranks)


def render_lock(lock: dict[str, Any]) -> str:
    soak = lock["soak"]
    llm = lock["llmQuality"]
    hashes = lock["hashes"]
    assets = lock["assets"]
    return f"""# V2.2 LLM And Soak Evidence Lock

This document freezes the already-passed real LLM quality evidence and 1800-second real model-chain soak evidence before Phase 8.4 reranker recovery work.

## Source

- Source commit: `{lock['sourceCommit']}`
- LLM quality decision: `{lock['decision']['llmQuality']}`
- LLM boundary: `{lock['decision']['llmBoundary']}`
- Soak status: `{lock['decision']['soakStatus']}`
- Reranker boundary at lock time: `{lock['decision']['rerankerBoundary']}`

## Model Assets

| Component | Model | Revision | Fingerprint | License | Files | Bytes |
| --- | --- | --- | --- | --- | ---: | ---: |
| Embedding | `{assets.get('embedding', {}).get('modelId')}` | `{assets.get('embedding', {}).get('revision')}` | `{assets.get('embedding', {}).get('assetFingerprint')}` | `{assets.get('embedding', {}).get('license')}` | {assets.get('embedding', {}).get('fileCount')} | {assets.get('embedding', {}).get('totalBytes')} |
| Reranker | `{assets.get('reranker', {}).get('modelId')}` | `{assets.get('reranker', {}).get('revision')}` | `{assets.get('reranker', {}).get('assetFingerprint')}` | `{assets.get('reranker', {}).get('license')}` | {assets.get('reranker', {}).get('fileCount')} | {assets.get('reranker', {}).get('totalBytes')} |
| LLM | `{assets.get('llm', {}).get('modelId')}` | `{assets.get('llm', {}).get('revision')}` | `{assets.get('llm', {}).get('assetFingerprint')}` | `{assets.get('llm', {}).get('license')}` | {assets.get('llm', {}).get('fileCount')} | {assets.get('llm', {}).get('totalBytes')} |

Local asset paths are intentionally omitted from this committed document.

## Frozen Hashes

- Benchmark hash: `{hashes['benchmarkHash']}`
- Knowledge hash: `{hashes['knowledgeHash']}`
- Calibration hash: `{hashes['calibrationHash']}`
- Evaluation hash: `{hashes['evaluationHash']}`
- Soak summary SHA256: `{hashes['soakSummarySha256']}`
- LLM quality summary SHA256: `{hashes['llmQualitySummarySha256']}`
- LLM gate SHA256: `{hashes['llmGateSha256']}`
- Reranker benchmark summary SHA256: `{hashes['rerankerBenchmarkSummarySha256']}`

## Soak Evidence

- Duration: `{soak['durationSeconds']}` seconds
- Requests: `{soak['requestCount']}`
- Successes: `{soak['successCount']}`
- Real BGE executions: `{soak['realBgeExecutions']}`
- Real reranker executions: `{soak['realRerankerExecutions']}`
- Real LLM executions: `{soak['realLlmExecutions']}`
- Fallback count: `{soak['fallbackCount']}`
- Unhandled errors: `{soak['unhandledErrorCount']}`
- Unexpected OOM: `{soak['unexpectedOom']}`
- Latency p50/p95/p99: `{soak['p50LatencyMs']}` / `{soak['p95LatencyMs']}` / `{soak['p99LatencyMs']}` ms
- CUDA start/peak/end: `{soak['cudaStartMb']}` / `{soak['cudaPeakMb']}` / `{soak['cudaEndMb']}` MB
- Model load/evict/switch: `{soak['modelLoadCount']}` / `{soak['modelEvictionCount']}` / `{soak['modelSwitchCount']}`
- Stability decision: `{soak['stabilityDecision']}`

## LLM Quality Evidence

- Case count: `{llm['caseCount']}`
- Dataset hash: `{llm['datasetHash']}`
- Schema valid rate: `{llm['schemaValidRate']}`
- Grounded rate: `{llm['groundedRate']}`
- Tenant violations: `{llm['tenantViolations']}`
- Prompt-injection unsafe executions: `{llm['promptInjectionUnsafeExecutions']}`
- PII leaks: `{llm['piiLeaks']}`
- Real generate executions: `{llm['realGenerateExecutions']}`
- Fallback executions: `{llm['fallbackExecutions']}`

## Boundary

This lock does not claim reranker quality verification. At this point the system remains `MODEL_RERANKER_NOT_VERIFIED` and `AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED`.
"""


def render_reranker_diagnosis(baseline: dict[str, Any], harness: dict[str, Any], cases: dict[str, Any]) -> str:
    q = baseline["quality"]
    cfg = baseline["configuration"]
    return f"""# V2.2 Real Reranker Regression Diagnosis

## Frozen Baseline

- Model: `{baseline['model']['modelId']}`
- Revision: `{baseline['model']['revision']}`
- Configuration: candidateK `{cfg['candidateK']}`, finalK `{cfg['finalK']}`, batch `{cfg['batchSize']}`, maxLength `{cfg['maxLength']}`, dtype `{cfg['dtype']}`
- Decision: `{q['qualityDecision']}`
- Boundary: `{q['modelBoundary']}`

## Quality Metrics

| Metric | Deterministic | Real Reranker |
| --- | ---: | ---: |
| Semantic nDCG@5 | {q['deterministicSemanticNdcgAt5']} | {q['realSemanticNdcgAt5']} |
| Semantic MRR | {q['deterministicSemanticMrr']} | {q['realSemanticMrr']} |
| Overall nDCG@5 | {q['deterministicOverallNdcgAt5']} | {q['realOverallNdcgAt5']} |
| Overall MRR | {q['deterministicOverallMrr']} | {q['realOverallMrr']} |

Safety counters: tenant violations `{q['tenantViolations']}`, inactive leaks `{q['inactiveEvidenceLeaks']}`, expired leaks `{q['expiredEvidenceLeaks']}`, false evidence `{q['falseEvidenceCount']}`.

## Harness Audit

- Status: `{harness['status']}`
- Score descending sort: `{harness['checks']['scoreDescendingSort']}`
- Stable tie-break: `{harness['checks']['stableTieBreakOriginalRankChunkId']}`
- Fallback not counted as real: `{harness['checks']['fallbackNotCountedAsReal']}`
- Normalize order test present: `{harness['checks']['normalizeDoesNotChangeOrderTested']}`

## Case Analysis

- Case count: `{cases['caseCount']}`
- Root-cause counts: `{json.dumps(cases['rootCauseCounts'], ensure_ascii=False, sort_keys=True)}`

The case analysis intentionally omits full private text and raw model outputs. It is a safe diagnostic index for follow-up tests.
"""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
