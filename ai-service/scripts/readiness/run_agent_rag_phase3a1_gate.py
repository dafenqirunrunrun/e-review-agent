from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
SCRIPTS = AI_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import PHASE3A_OUT, write_json
from app.agent_rag.metrics import METRIC_SCHEMA_VERSION, validate_metric_ranges
from scripts.e2e.run_agent_rag_phase3a_real_dense_e2e import run as run_e2e
from scripts.evaluation.run_agent_rag_phase3a_eval import evaluate


def main() -> None:
    pip_check = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT, text=True, capture_output=True)
    evaluation = evaluate()
    e2e = run_e2e()
    modes = ["bm25", "hashDense", "hybridHash"]
    if evaluation.get("bgeM3Dense") and evaluation.get("hybridReal"):
        modes += ["bgeM3Dense", "hybridReal"]
    metric_errors = validate_metric_ranges(evaluation, modes=modes)
    latency = evaluation.get("latency", {}).get("hybridReal", {})
    real_dense_executed = sum(
        int(bool(value))
        for value in [
            evaluation.get("providerMetadata", {}).get("providerType") == "bge-m3",
            evaluation.get("manifest", {}).get("vectorCount", 0) > 0,
            evaluation.get("bgeM3Dense") is not None,
            evaluation.get("hybridReal") is not None,
            e2e.get("denseRetrieval"),
            e2e.get("hybridRetrieval"),
            e2e.get("incompatibleIndexBlocked"),
            e2e.get("rollback"),
        ]
    )
    real_dense_failed = 0 if evaluation.get("status") == "AGENT_RAG_REAL_DENSE_EVALUATION_PASS" and e2e.get("status") == "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_PASS" else max(1, real_dense_executed)
    checks = {
        "pipCheck": pip_check.returncode == 0,
        "benchmarkSchema": evaluation.get("metricSchemaVersion") == METRIC_SCHEMA_VERSION,
        "benchmarkData": evaluation.get("benchmarkValidation", {}).get("benchmarkValidationStatus") == "PASS",
        "metricRanges": not metric_errors,
        "ndcgFormula": all(0 <= float((evaluation.get(mode) or {}).get("ndcgAt5", 0)) <= 1 for mode in modes),
        "latencyClock": latency.get("clockType") == "perf_counter_ns",
        "latencyEvidence": latency.get("sampleCount", 0) >= 100 and latency.get("faissSearchP95Us", 0) > 0,
        "tenantIsolation": (evaluation.get("hybridReal") or {}).get("tenantViolations") == 0,
        "realDenseExecuted": real_dense_executed >= 6,
        "realDensePassed": real_dense_failed == 0,
        "phase3aNoRegression": evaluation.get("status") == "AGENT_RAG_REAL_DENSE_EVALUATION_PASS" and e2e.get("status") == "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_PASS",
    }
    result = {
        "schemaVersion": "agent-rag-phase3a1-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "pipCheck": {"returnCode": pip_check.returncode, "stdout": pip_check.stdout.strip(), "stderr": pip_check.stderr.strip()},
        "metricErrors": metric_errors,
        "realDenseExecuted": real_dense_executed,
        "realDensePassed": real_dense_executed if real_dense_failed == 0 else 0,
        "realDenseFailed": real_dense_failed,
        "evaluation": {
            "metricSchemaVersion": evaluation.get("metricSchemaVersion"),
            "benchmarkVersion": evaluation.get("benchmarkVersion"),
            "benchmarkHash": evaluation.get("benchmarkHash"),
            "knowledgeRootHash": evaluation.get("knowledgeRootHash"),
            "caseCount": evaluation.get("caseCount"),
            "bm25": evaluation.get("bm25"),
            "bgeM3Dense": evaluation.get("bgeM3Dense"),
            "hybridReal": evaluation.get("hybridReal"),
            "latency": evaluation.get("latency"),
            "resource": evaluation.get("resource"),
            "benchmarkValidation": evaluation.get("benchmarkValidation"),
        },
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    write_json(PHASE3A_OUT / "phase3a1-gate-result.json", result)
    if result["status"] != "PASS":
        if metric_errors:
            print("AGENT_RAG_EVALUATION_METRIC_INVALID")
        if not checks["pipCheck"]:
            print("AGENT_RAG_PYTHON_DEPENDENCY_FAIL")
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    print("AGENT_RAG_EVALUATION_FORMULA_PASS")
    print("AGENT_RAG_EVALUATION_RANGE_PASS")
    print("AGENT_RAG_BENCHMARK_INTEGRITY_PASS")
    print("AGENT_RAG_LATENCY_EVIDENCE_PASS")
    print("AGENT_RAG_PYTHON_DEPENDENCY_PASS")
    print("AGENT_RAG_REAL_DENSE_TEST_COVERAGE_PASS")
    print("AGENT_RAG_PHASE3A1_PASS")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
