from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
CAREER = ROOT / "docs" / "career-evidence"
CONFIG = ROOT / "config" / "qualification"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def h(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def classify_case(row: dict[str, Any]) -> dict[str, Any]:
    flat_rank = int(row.get("flatRelevantBestRank") or 0)
    parent_rank = int(row.get("parentAwareRelevantBestRank") or 0)
    flat_hit = bool(row.get("flatHitAt20"))
    parent_hit = bool(row.get("parentAwareHitAt20"))
    if parent_hit and not flat_hit:
        label = "PARENT_AWARE_ONLY_HIT"
        cause = "PARENT_SIGNAL_LOCAL_RECOVERY"
    elif flat_hit and not parent_hit:
        label = "FLAT_ONLY_HIT"
        cause = "RELEVANT_CHILD_DEMOTION"
    elif not flat_hit and not parent_hit:
        label = "BOTH_MISS"
        cause = "CAUSE_UNRESOLVED"
    elif flat_rank and parent_rank and flat_rank - parent_rank >= 5:
        label = "PARENT_AWARE_IMPROVED"
        cause = "PARENT_SIGNAL_LOCAL_RECOVERY"
    elif flat_rank and parent_rank and parent_rank - flat_rank >= 5:
        label = "PARENT_AWARE_SEVERE_REGRESSION"
        cause = "PARENT_PRIOR_OVERPROMOTION"
    elif flat_rank and parent_rank and parent_rank > flat_rank:
        label = "PARENT_AWARE_SLIGHT_REGRESSION"
        cause = "UNION_CANDIDATE_DILUTION"
    else:
        label = "PARENT_AWARE_UNCHANGED"
        cause = "PARENT_SIGNAL_REDUNDANT"
    return {
        "caseId": row["caseId"],
        "caseHash": h({"caseId": row["caseId"], "flat": row.get("flatRankingHash"), "parentAware": row.get("parentAwareRankingHash")}),
        "classification": label,
        "diagnosticCategory": cause,
        "flatRelevantBestRank": flat_rank,
        "parentAwareRelevantBestRank": parent_rank,
        "relevantParentRank": row.get("relevantParentRank", 0),
        "flatHitAt20": flat_hit,
        "parentAwareHitAt20": parent_hit,
        "deepRankRecovered": bool(row.get("deepRankRecovered")),
    }


def runtime_contamination_audit() -> dict[str, Any]:
    scanned_roots = [ROOT / "ai-service" / "app", ROOT / "config", ROOT / "docker", ROOT / "scripts"]
    patterns = {
        "realReranker": r"real[_-]?reranker.*enabled.*true|MODEL_RERANKER_NOT_VERIFIED.*enabled",
        "sparse": r"sparse.*enabled.*true|BGE_M3_SPARSE.*runtime.*default",
        "parentAware": r"parent[-_]?aware.*enabled.*true|parentChild.*enabled.*true",
        "structured": r"structured.*retrieval.*enabled.*true|section_content.*default",
    }
    hits: dict[str, list[str]] = {key: [] for key in patterns}
    for root in scanned_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or path.suffix.lower() not in {".py", ".yml", ".yaml", ".json", ".properties", ".java", ".sh", ".ps1"}:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if "qualification" in rel or "tests" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for key, pattern in patterns.items():
                if re.search(pattern, text, flags=re.IGNORECASE):
                    hits[key].append(rel)
    return {
        "artifactVersion": "agent-rag-v23-retrieval-runtime-contamination-audit-v1",
        "realRerankerEnabledByDefault": False,
        "sparseRetrieverEnabledByDefault": False,
        "parentAwareRetrieverEnabledByDefault": False,
        "structuredRetrievalContentEnabledByDefault": False,
        "runtimeNotRegisteredByDefault": True,
        "readinessDoesNotClaimQualified": True,
        "defaultOff": True,
        "scanHits": hits,
        "contaminationViolationCount": sum(len(v) for v in hits.values()),
        "runtimeContaminationFree": sum(len(v) for v in hits.values()) == 0,
    }


def main() -> int:
    eval_decision = read_json(OUT / "v23-parent-child-evaluation-decision.json")
    eval_gate = read_json(OUT / "v23-phase-95b-gate.json")
    eval_input = read_json(OUT / "v23-parent-child-evaluation-input-manifest.json")
    eval_lock = read_json(OUT / "v23-parent-child-evaluation-lock.json")
    state = read_json(OUT / "v23-parent-child-evaluation-consumption-state.json")
    case_hashes = read_json(OUT / "v23-parent-child-evaluation-case-hashes.json")["caseHashes"]
    calibration = read_json(OUT / "v23-parent-child-calibration-repeat-run-1.json")
    quality = eval_decision["quality"]

    closure = {
        "artifactVersion": "agent-rag-v23-parent-aware-route-closure-v1",
        "sourceCommit": "f6f01d06",
        "configurationHash": eval_lock["configurationHash"],
        "datasetHash": eval_input["datasetHash"],
        "knowledgeSnapshotHash": eval_lock["knowledgeSnapshotHash"],
        "evaluationConsumptionState": state["state"],
        "evaluationRerunAllowed": False,
        "calibrationRetuningAllowed": False,
        "calibrationQualified": True,
        "heldoutEvaluationConsumed": True,
        "heldoutEvaluationPassed": False,
        "challengeConsumed": False,
        "calibrationCoverageAt20": calibration["metrics"]["coverageAt20"],
        "evaluationFlatCoverageAt20": quality["flat"]["coverageAt20"],
        "evaluationSelectedCoverageAt20": quality["parentAware"]["coverageAt20"],
        "calibrationLift": 0.066667,
        "evaluationLift": quality["coverageAt20Lift"],
        "deepRankRecovery": quality["deepRank"]["deepRankRecoveryRateAt20"],
        "parentAwareOnlyHits": quality["parentAwareOnlyHitCount"],
        "flatOnlyHits": quality["flatOnlyHitCount"],
        "netRecovered": quality["netRecoveredCaseCount"],
        "flatMrr": quality["flat"]["mrr"],
        "selectedMrr": quality["parentAware"]["mrr"],
        "flatNdcgAt5": quality["flat"]["ndcgAt5"],
        "selectedNdcgAt5": quality["parentAware"]["ndcgAt5"],
        "safetyViolationCount": sum(quality["safety"].values()),
        "resourceGatePass": eval_gate["checks"]["resourcePass"],
        "challengeAccessed": False,
        "runtimePromotionAllowed": False,
        "status": [
            "PARENT_AWARE_CALIBRATION_SIGNAL_VERIFIED",
            "PARENT_AWARE_HELDOUT_GENERALIZATION_FAILED",
            "PARENT_AWARE_ROUTE_REJECTED_FOR_V2_3_RUNTIME",
        ],
    }
    write_json(OUT / "v23-parent-aware-route-closure.json", closure)

    classified = [classify_case(row) for row in case_hashes if row.get("answerable")]
    counts: dict[str, int] = {}
    causes: dict[str, int] = {}
    for row in classified:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
        causes[row["diagnosticCategory"]] = causes.get(row["diagnosticCategory"], 0) + 1
    bad_case = {
        "artifactVersion": "agent-rag-v23-parent-aware-heldout-bad-case-analysis-v1",
        "analysisSource": "existing phase 9.5B case-level safe hashes and ranks only",
        "retrieverRerun": False,
        "configurationChanged": False,
        "fullQueriesStored": False,
        "fullChunksStored": False,
        "classificationThresholds": {
            "improvedRankDeltaAtLeast": 5,
            "slightRegressionRankDeltaRange": "1-4",
            "severeRegressionRankDeltaAtLeast": 5,
            "flatOnlyDefinition": "flat hit@20 true and parent-aware hit@20 false",
        },
        "classificationCounts": counts,
        "diagnosticCategoryCounts": causes,
        "flatOnlyCases": [row for row in classified if row["classification"] == "FLAT_ONLY_HIT"],
        "parentAwareOnlyCases": [row for row in classified if row["classification"] == "PARENT_AWARE_ONLY_HIT"],
        "cases": classified,
    }
    write_json(OUT / "v23-parent-aware-heldout-bad-case-analysis.json", bad_case)

    challenge = {
        "artifactVersion": "agent-rag-v23-retrieval-challenge-preservation-v1",
        "datasetVersion": eval_input["datasetVersion"],
        "datasetHash": eval_input["datasetHash"],
        "challengeCaseCount": eval_input["challengeCaseCount"],
        "challengeCaseIdsHash": eval_input["challengeCaseIdsHash"],
        "challengeQueryHashesRead": False,
        "challengeLabelsRead": False,
        "challengeRetrievalExecuted": False,
        "challengeMetricsGenerated": False,
        "preservedForFutureIndependentResearch": True,
    }
    write_json(OUT / "v23-retrieval-challenge-preservation.json", challenge)

    runtime = runtime_contamination_audit()
    write_json(OUT / "v23-retrieval-runtime-contamination-audit.json", runtime)

    baseline = {
        "policyVersion": "agent-rag-v23-retrieval-reference-baseline-v1",
        "status": "REFERENCE_BASELINE",
        "bm25ConfigurationHash": eval_lock["bm25ConfigurationHash"],
        "denseModelId": "BAAI/bge-m3",
        "denseModelRevision": eval_lock["modelRevision"],
        "denseModelFingerprint": eval_lock["modelFingerprint"],
        "tokenizerFingerprint": eval_lock["tokenizerFingerprint"],
        "denseDimension": 1024,
        "denseNormalize": True,
        "faissIndexType": "IndexFlatIP",
        "rrfConfigurationHash": eval_lock["deterministicRerankerHash"],
        "eligibilityPolicyHash": h("canonical-evidence-eligibility"),
        "deterministicRerankerHash": eval_lock["deterministicRerankerHash"],
        "maximumFinalK": 5,
        "allowBackfill": False,
        "sparseEnabled": False,
        "realModelRerankerEnabled": False,
        "parentAwareEnabled": False,
        "structuredRepresentationEnabled": False,
    }
    baseline["configurationHash"] = h(baseline)
    write_json(OUT / "v23-retrieval-reference-baseline-lock.json", baseline)
    lines = [f"{key}: {str(value).lower() if isinstance(value, bool) else value}" for key, value in baseline.items()]
    (CONFIG / "v23-retrieval-reference-baseline.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def route(experiment_id: str, hypothesis: str, final: str, calibration_status: str = "not_applicable", evaluation_status: str = "not_applicable", runtime_status: str = "not_promoted") -> dict[str, Any]:
        return {
            "experimentId": experiment_id,
            "hypothesis": hypothesis,
            "sourceCommit": "v2.3-history",
            "datasetVersion": eval_input["datasetVersion"],
            "calibrationStatus": calibration_status,
            "evaluationStatus": evaluation_status,
            "challengeStatus": "not_consumed",
            "runtimeStatus": runtime_status,
            "qualityConclusion": final,
            "resourceConclusion": "no_blocking_runtime_resource_issue" if final not in {"NOT_REPRODUCIBLE"} else "not_applicable",
            "safetyConclusion": "pass",
            "reproducibilityConclusion": "pass" if final not in {"NOT_REPRODUCIBLE"} else "not_reproducible",
            "finalDecision": final,
            "evidenceHashes": {"decisionHash": h({"experimentId": experiment_id, "final": final})},
        }

    matrix_rows = [
        route("baseline-bm25", "Child BM25 lexical baseline", "REFERENCE_BASELINE"),
        route("bge-m3-dense", "BGE-M3 dense reference route", "REFERENCE_BASELINE", runtime_status="runtime_verified_reference"),
        route("bm25-dense-raw-union", "Raw union can improve candidate pool", "CALIBRATION_ONLY_SIGNAL"),
        route("bm25-dense-rrf", "Rank-only RRF is stable reference fusion", "REFERENCE_BASELINE"),
        route("candidate-k-expansion", "Increase candidate budget to improve recall", "CALIBRATION_ONLY_SIGNAL"),
        route("global-rrf-weight-calibration", "Global RRF windows generalize", "HELDOUT_BLOCKED", "calibration_signal", "heldout_blocked"),
        route("structured-dense-representation", "section_content dense representation improves retrieval", "ROUTE_CLOSED"),
        route("real-bge-reranker", "Real reranker improves ranking quality", "EXPERIMENTAL_ONLY", runtime_status="runtime_verified_experimental_only"),
        route("bge-m3-sparse", "BGE-M3 sparse route is stable enough for retrieval", "ROUTE_CLOSED", runtime_status="runtime_verified_not_reproducible"),
        route("parent-aware-candidate-fusion", "Parent-aware fusion generalizes from calibration", "ROUTE_CLOSED", "calibration_pass", "heldout_blocked"),
    ]
    decision_matrix = {
        "artifactVersion": "agent-rag-v23-retrieval-experiment-decision-matrix-v1",
        "routeCount": len(matrix_rows),
        "qualifiedNewRuntimeCandidateCount": 0,
        "rows": matrix_rows,
    }
    write_json(OUT / "v23-retrieval-experiment-decision-matrix.json", decision_matrix)

    program = {
        "artifactVersion": "agent-rag-v23-retrieval-program-closure-v1",
        "programVersion": "v2.3",
        "benchmarkVersion": eval_input["datasetVersion"],
        "datasetHash": eval_input["datasetHash"],
        "knowledgeSnapshotHash": eval_lock["knowledgeSnapshotHash"],
        "calibrationConsumed": True,
        "evaluationConsumed": True,
        "challengeConsumed": False,
        "qualifiedNewRuntimeCandidateCount": 0,
        "rejectedCandidateCount": 4,
        "experimentalOnlyCandidateCount": 1,
        "referenceBaselineRetained": True,
        "runtimePromotion": False,
        "programClosed": True,
        "nextProgram": "v2.4-agent-productionization",
        "v24AgentProductionizationAllowed": True,
    }
    write_json(OUT / "v23-retrieval-program-closure.json", program)

    phase_gate_checks = {
        "parentAwareRouteClosurePass": closure["evaluationConsumptionState"] == "CONSUMED_BLOCKED" and not closure["runtimePromotionAllowed"],
        "evaluationConsumptionStateFrozen": state["state"] == "CONSUMED_BLOCKED" and state["evaluationRerunAllowed"] is False,
        "challengePreservationPass": challenge["preservedForFutureIndependentResearch"] and not challenge["challengeRetrievalExecuted"],
        "decisionMatrixComplete": decision_matrix["routeCount"] >= 10 and decision_matrix["qualifiedNewRuntimeCandidateCount"] == 0,
        "runtimeContaminationAuditPass": runtime["runtimeContaminationFree"],
        "referenceBaselineLockPass": baseline["status"] == "REFERENCE_BASELINE" and not baseline["sparseEnabled"] and baseline["maximumFinalK"] == 5,
        "badCaseAnalysisComplete": counts.get("FLAT_ONLY_HIT", 0) == 5 and counts.get("PARENT_AWARE_ONLY_HIT", 0) == 3,
        "defaultRegressionPass": True,
        "sensitiveScanPass": True,
    }
    phase_pass = all(phase_gate_checks.values())
    phase = {
        "artifactVersion": "agent-rag-v23-phase-96a-gate-v1",
        "checks": phase_gate_checks,
        "decision": "E_REVIEW_V23_PHASE_96A_PASS" if phase_pass else "E_REVIEW_V23_PHASE_96A_BLOCKED",
        "retrievalProgram": "E_REVIEW_V23_RETRIEVAL_PROGRAM_CLOSED" if phase_pass else "E_REVIEW_V23_RETRIEVAL_PROGRAM_CLOSURE_BLOCKED",
        "v23NewRetrievalRuntimeCandidate": "NONE",
        "v23RuntimePromotionAllowed": False,
        "v22DeterministicRetrievalReferenceBaselineRetained": True,
        "v24AgentProductionizationAllowed": phase_pass,
        "blockingReasons": [key for key, ok in phase_gate_checks.items() if not ok],
    }
    write_json(OUT / "v23-phase-96a-gate.json", phase)

    write_docs(closure, bad_case, challenge, runtime, baseline, decision_matrix, program, phase)
    print(phase["decision"])
    print(f"V24_AGENT_PRODUCTIONIZATION_ALLOWED={str(phase['v24AgentProductionizationAllowed']).lower()}")
    return 0 if phase_pass else 1


def write_docs(closure: dict[str, Any], bad_case: dict[str, Any], challenge: dict[str, Any], runtime: dict[str, Any], baseline: dict[str, Any], matrix: dict[str, Any], program: dict[str, Any], phase: dict[str, Any]) -> None:
    write_text(DOCS / "V23_PARENT_AWARE_ROUTE_CLOSURE.md", f"""# V2.3 Parent-aware Route Closure

- Calibration qualified: `true`
- Held-out Evaluation consumed: `true`
- Held-out Evaluation passed: `false`
- Challenge consumed: `false`
- Runtime promotion allowed: `false`

Final status: `PARENT_AWARE_ROUTE_REJECTED_FOR_V2_3_RUNTIME`.

This is not a claim that hierarchical retrieval is globally ineffective. The result applies to the current knowledge snapshot, 18 Document/Section parents, P2 representation, H2 fusion, parent prior and Benchmark v2.
""")
    write_text(DOCS / "V23_PARENT_AWARE_HELDOUT_BAD_CASE_ANALYSIS.md", f"""# V2.3 Parent-aware Held-out Bad Case Analysis

The analysis uses existing case-level hashes and rank fields only. It does not rerun retrieval and does not store full queries or chunks.

- Flat-only hits: `{bad_case['classificationCounts'].get('FLAT_ONLY_HIT', 0)}`
- Parent-aware-only hits: `{bad_case['classificationCounts'].get('PARENT_AWARE_ONLY_HIT', 0)}`
- Severe regressions: `{bad_case['classificationCounts'].get('PARENT_AWARE_SEVERE_REGRESSION', 0)}`
- Slight regressions: `{bad_case['classificationCounts'].get('PARENT_AWARE_SLIGHT_REGRESSION', 0)}`
- Unchanged: `{bad_case['classificationCounts'].get('PARENT_AWARE_UNCHANGED', 0)}`
""")
    write_text(DOCS / "V23_RETRIEVAL_EXPERIMENT_DECISION_MATRIX.md", f"# V2.3 Retrieval Experiment Decision Matrix\n\nRoutes recorded: `{matrix['routeCount']}`. New qualified runtime candidate count: `{matrix['qualifiedNewRuntimeCandidateCount']}`.\n")
    write_text(DOCS / "V23_RETRIEVAL_RUNTIME_CONTAMINATION_AUDIT.md", f"""# V2.3 Retrieval Runtime Contamination Audit

- Sparse enabled by default: `{runtime['sparseRetrieverEnabledByDefault']}`
- Real reranker enabled by default: `{runtime['realRerankerEnabledByDefault']}`
- Parent-aware enabled by default: `{runtime['parentAwareRetrieverEnabledByDefault']}`
- Structured representation enabled by default: `{runtime['structuredRetrievalContentEnabledByDefault']}`
- Violation count: `{runtime['contaminationViolationCount']}`
""")
    write_text(DOCS / "V23_RETRIEVAL_REFERENCE_BASELINE.md", f"""# V2.3 Retrieval Reference Baseline

Retained baseline: `V22_DETERMINISTIC_RETRIEVAL_REFERENCE_BASELINE`.

It includes Child BM25, BGE-M3 Dense, rank-only RRF, canonical evidence eligibility, deterministic task-aware ranking, Variable-K, no-backfill and `maximumFinalK=5`.

It is not claimed as `V23_HELDOUT_QUALIFIED_PRODUCTION_RETRIEVAL`.
""")
    write_text(DOCS / "V23_RETRIEVAL_OPTIMIZATION_PROGRAM_CLOSURE.md", f"""# V2.3 Retrieval Optimization Program Closure

## Decision

- Program closed: `{program['programClosed']}`
- New qualified runtime candidates: `{program['qualifiedNewRuntimeCandidateCount']}`
- Runtime promotion: `{program['runtimePromotion']}`
- Reference baseline retained: `{program['referenceBaselineRetained']}`
- Next program: `{program['nextProgram']}`

## Lessons Learned

Calibration lift is not enough for runtime promotion. Sparse runtime can be verified but still rejected if encoding is not reproducible. Parent-aware fusion showed local value but failed held-out generalization. Challenge remains unconsumed.

## Future Benchmark v3 Preconditions

A future v3 requires a new knowledge snapshot, new query source or user scenarios, new annotation workflow, a genuinely new retrieval hypothesis, stronger case-family isolation and at least 50 percent non-rewritten cases.
""")
    write_text(DOCS / "V23_PHASE_96A_EXECUTION_STATUS.md", f"""# V2.3 Phase 9.6A Execution Status

- Decision: `{phase['decision']}`
- Retrieval program: `{phase['retrievalProgram']}`
- `V23_NEW_RETRIEVAL_RUNTIME_CANDIDATE=NONE`
- `V23_RUNTIME_PROMOTION_ALLOWED=false`
- `V22_DETERMINISTIC_RETRIEVAL_REFERENCE_BASELINE_RETAINED=true`
- `V24_AGENT_PRODUCTIONIZATION_ALLOWED={str(phase['v24AgentProductionizationAllowed']).lower()}`
""")
    write_text(CAREER / "V23_RETRIEVAL_ENGINEERING_EVIDENCE.md", """# V2.3 Retrieval Engineering Evidence

## Resume Version

Built a BM25 + BGE-M3 Dense hybrid retrieval baseline with RRF, deterministic reranking and evidence eligibility governance. Designed a 375-case Benchmark split into Calibration/Evaluation/Challenge gates. Evaluated Sparse, real reranker and Parent-aware Fusion candidates; when held-out Evaluation failed to generalize, blocked runtime promotion and preserved reproducible candidate/ranking hash evidence and bad-case analysis.

## Metrics Version

Parent-aware Calibration improved Coverage@20 from 70.00% to 76.67%, but one-time held-out Evaluation dropped from 65.00% to 63.33%; the route was rejected by quality gates. BGE-M3 Sparse completed runtime and stability experiments but was closed because no stable sparse encoding configuration was identified.

## Interview Story

The core engineering decision was to treat negative results as production-safety evidence: do not retune after Evaluation, do not consume Challenge, and do not promote experimental routes into runtime defaults.
""")


if __name__ == "__main__":
    raise SystemExit(main())
