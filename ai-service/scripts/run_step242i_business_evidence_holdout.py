from __future__ import annotations

import hashlib
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.evidence_coverage import PolicyAdaptiveEvidenceBudget, PolicyEvidenceCoverageSelector
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from scripts.run_step242g_after_sales_semantic_dev import evidence_query, load_cases, write_json
from scripts.run_step242h_adaptive_evidence_budget_dev import Variant, execute_variant
from scripts.run_step242i_business_evidence_dev import VARIANT, execute_audit, summary


BINDING_DIR = ROOT / "artifacts" / "step242h_adaptive_evidence_budget" / "bound_repaired_candidate"
HOLDOUT = BINDING_DIR / "holdout_bound_candidate_v2.jsonl"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index_step242h_candidate" / "policy_chunks.jsonl"
RESULT_OUTPUT = ROOT / "artifacts" / "step242i_business_evidence_sufficiency" / "holdout_fixed8_result.json"
AUDIT_OUTPUT = ROOT / "artifacts" / "step242i_business_evidence_sufficiency" / "holdout_business_evidence_audit.json"
RETRIEVAL_WINDOW = 30
FIXED8_COVERAGE_AWARE = Variant(VARIANT, retrieval_k=30, fixed_budget=8, demand_aware=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regression", action="store_true", help="Replay existing Dev and exposed Holdout as repair regression.")
    args = parser.parse_args()
    if args.regression:
        return run_regression()
    if RESULT_OUTPUT.exists() or AUDIT_OUTPUT.exists():
        raise RuntimeError("HOLDOUT_ALREADY_EXECUTED: use --regression to preserve the first result")
    result = execute_holdout()
    write_json(RESULT_OUTPUT, result)
    audit = execute_audit(
        RESULT_OUTPUT,
        HOLDOUT,
        scope="Frozen Holdout validation after the Dev business-evidence contract passed. The runtime index and policy source corpus remain unchanged.",
        holdout_executed=True,
    )
    audit["frozenDatasetSha256"] = hashlib.sha256(HOLDOUT.read_bytes()).hexdigest().upper()
    write_json(AUDIT_OUTPUT, audit)
    print(json.dumps(summary(audit), ensure_ascii=False, indent=2))
    return 0 if audit["gate"] == "PASS" else 1


def execute_holdout(dataset_path: Path = HOLDOUT) -> dict[str, Any]:
    cases = load_cases(dataset_path)
    retriever = PolicyEvidenceRetriever.from_jsonl(CHUNKS, enable_dense=True)
    reranker = PolicyEvidenceReranker()
    retriever_readiness = retriever.readiness()
    reranker_readiness = reranker.readiness()
    if retriever_readiness.get("retrievalMode") != "hybrid":
        raise RuntimeError("STEP242I_HOLDOUT_HYBRID_NOT_READY")
    if not reranker.enabled or reranker_readiness.get("status") != "ready":
        raise RuntimeError("STEP242I_HOLDOUT_RERANKER_NOT_READY")

    candidates_by_case: dict[str, list[Any]] = {}
    query_by_case: dict[str, str] = {}
    started = time.perf_counter()
    for case in cases:
        if case.noAnswer:
            continue
        query = evidence_query(case)
        candidates = retriever.search(query, risk_hints=case.riskTypes, top_k=RETRIEVAL_WINDOW, mode="hybrid")
        if not candidates or candidates[0].retrieval.get("mode") != "hybrid":
            raise RuntimeError(f"STEP242I_HOLDOUT_HYBRID_FALLBACK:{case.caseId}")
        candidates_by_case[case.caseId] = candidates
        query_by_case[case.caseId] = query

    variant_result = execute_variant(
        FIXED8_COVERAGE_AWARE,
        cases,
        candidates_by_case,
        query_by_case,
        PolicyEvidenceCoverageSelector(),
        PolicyAdaptiveEvidenceBudget(),
        reranker,
        retriever,
    )
    return {
        "schemaVersion": "step242i-business-evidence-holdout-v1",
        "scope": "Frozen Holdout, fixed8 coverage-aware candidate strategy. No runtime index, router, or policy source changes.",
        "runtime": {
            "requestedMode": "hybrid_bge_reranked",
            "actualMode": "hybrid_bge_reranked",
            "retriever": retriever_readiness,
            "reranker": reranker_readiness,
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
        },
        "variants": {VARIANT: variant_result},
        "holdoutExecuted": True,
    }


def run_regression() -> int:
    output_dir = AUDIT_OUTPUT.parent / ("regression_" + time.strftime("%Y%m%d_%H%M%S"))
    protected = [
        HOLDOUT, BINDING_DIR / "dev_bound_candidate_v2.jsonl", CHUNKS,
        RESULT_OUTPUT, AUDIT_OUTPUT,
        ROOT / "data/policy_rag_real/index/policy_chunks.jsonl",
    ]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    evaluations = {}
    for split, dataset in (("dev", BINDING_DIR / "dev_bound_candidate_v2.jsonl"), ("exposed_holdout", HOLDOUT)):
        result = execute_holdout(dataset)
        result.update(evaluationUse="repair_regression", holdoutExecuted=False)
        result["scope"] = "Previously seen cases reused for repair regression; not an independent generalization test."
        result_path = output_dir / f"{split}_retrieval.json"
        write_json(result_path, result)
        audit = execute_audit(result_path, dataset, scope=result["scope"], holdout_executed=False)
        audit.update(evaluationUse="repair_regression", datasetSha256=before[str(dataset)])
        write_json(output_dir / f"{split}_audit.json", audit)
        evaluations[split] = summary(audit)
    baseline = execute_audit(
        RESULT_OUTPUT, HOLDOUT, scope="First-run output rescored with the same corrected audit contract.", holdout_executed=False,
    )
    write_json(output_dir / "first_run_rescored.json", baseline)
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    if before != after:
        raise RuntimeError("REGRESSION_INPUT_OR_FIRST_RESULT_CHANGED")
    report = {
        "evaluationUse": "repair_regression",
        "independentValidation": False,
        "gate": "PASS" if all(row["gate"] == "PASS" for row in evaluations.values()) else "HOLD",
        "results": evaluations,
        "firstRunSameAudit": summary(baseline),
        "inputHashesUnchanged": True,
        "protectedSha256": before,
    }
    write_json(output_dir / "summary.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "protectedSha256"}, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
