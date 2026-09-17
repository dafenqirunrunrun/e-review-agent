from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any

from v23_candidate_fusion_common import DOCS, OUT, FusionConfig, evaluate_config, hash_json, load_dataset, prepare_runtime, read_json, split_answerable, split_no_answer, write_json, write_text
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))
    cases, manifest = load_dataset()
    evaluation = split_answerable(cases, "evaluation")
    no_answer = split_no_answer(cases, "evaluation")
    decision = read_json(OUT / "v23-candidate-fusion-calibration-decision.json")
    selected_cfg = ((decision.get("selected") or {}).get("configuration") or {})
    if decision.get("status") != "PASS" or not selected_cfg:
        result = blocked_result("CALIBRATION_NOT_VALID", manifest, evaluation, no_answer)
        write_json(OUT / "v23-candidate-fusion-evaluation-result.json", result)
        write_text(DOCS / "V23_CANDIDATE_FUSION_EVALUATION.md", render_doc(result))
        print("E_REVIEW_V23_CANDIDATE_FUSION_EVALUATION_BLOCKED")
        return 1
    lock = {
        "schemaVersion": "agent-rag-v23-candidate-fusion-evaluation-lock-v1",
        "datasetHash": manifest["datasetHash"],
        "evaluationCaseIdsHash": hash_json([case["caseId"] for case in evaluation]),
        "noAnswerCaseIdsHash": hash_json([case["caseId"] for case in no_answer]),
        "knowledgeSnapshotHash": manifest["knowledgeSnapshotHash"],
        "indexManifestHash": manifest["indexManifestHash"],
        "configurationHash": decision["selected"]["configurationHash"],
        "codeCommit": current_commit(),
        "selectionPolicy": "one-shot evaluation; no retuning after result",
    }
    write_json(OUT / "v23-candidate-fusion-evaluation-lock.json", lock)
    payload = benchmark_payload()
    provider, runtime = prepare_runtime(payload)
    try:
        baseline = evaluate_config(evaluation, runtime, FusionConfig(20, 20, 20, 100))
        selected = evaluate_config(evaluation, runtime, config_from_dict(selected_cfg))
    finally:
        try:
            provider.close()
        except Exception:
            pass
    result = evaluate_decision(manifest, lock, baseline, selected, len(no_answer))
    write_json(OUT / "v23-candidate-fusion-evaluation-result.json", result)
    write_text(DOCS / "V23_CANDIDATE_FUSION_EVALUATION.md", render_doc(result))
    print("E_REVIEW_V23_CANDIDATE_FUSION_EVALUATION_PASS" if result["status"] == "PASS" else "E_REVIEW_V23_CANDIDATE_FUSION_EVALUATION_BLOCKED")
    return 0 if result["status"] == "PASS" else 1


def config_from_dict(value: dict[str, Any]) -> FusionConfig:
    return FusionConfig(
        bm25RetrieveK=int(value["bm25RetrieveK"]),
        denseRetrieveK=int(value["denseRetrieveK"]),
        rrfRankWindow=int(value["rrfRankWindow"]),
        postFusionCandidateK=int(value["postFusionCandidateK"]),
        maximumFinalK=int(value.get("maximumFinalK", 5)),
        rrfRankConstant=int(value.get("rrfRankConstant", 60)),
        bm25Weight=float(value.get("bm25Weight", 1.0)),
        denseWeight=float(value.get("denseWeight", 1.0)),
    )


def evaluate_decision(manifest: dict[str, Any], lock: dict[str, Any], baseline: dict[str, Any], selected: dict[str, Any], no_answer_count: int) -> dict[str, Any]:
    selected_k = int(selected["configuration"]["postFusionCandidateK"])
    baseline_coverage20 = baseline["rrfMetrics"].get("coverageAt20", 0.0)
    selected_coverage20 = selected["rrfMetrics"].get("coverageAt20", 0.0)
    ndcg_regression = baseline["deterministicRerankerMetrics"].get("ndcgAt5", 0.0) - selected["deterministicRerankerMetrics"].get("ndcgAt5", 0.0)
    mrr_regression = baseline["deterministicRerankerMetrics"].get("mrr", 0.0) - selected["deterministicRerankerMetrics"].get("mrr", 0.0)
    checks = {
        "tenantViolationsZero": selected["tenantViolations"] == 0,
        "expiredEvidenceAcceptedZero": selected["expiredCandidatesAccepted"] == 0,
        "inactiveEvidenceAcceptedZero": selected["inactiveCandidatesAccepted"] == 0,
        "lowScoreBackfillZero": selected["lowScoreBackfillCount"] == 0,
        "coverage20ImprovedByAtLeast008OrOracle20AtLeast088": selected_coverage20 >= baseline_coverage20 + 0.08 or selected.get("oracleCaptureRateAt20", 0.0) >= 0.88,
        "oracleCaptureAtSelectedKAtLeast095": selected.get("oracleCaptureRateAtSelectedK", 0.0) >= 0.95,
        "ndcgRegressionAtMost001": ndcg_regression <= 0.01,
        "mrrRegressionAtMost001": mrr_regression <= 0.01,
        "p95Within135Baseline": selected["latencyP95"] <= baseline["latencyP95"] * 1.35,
        "postFusionCandidateKAtMost50": selected_k <= 50,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    return {
        "schemaVersion": "agent-rag-v23-candidate-fusion-evaluation-result-v1",
        "status": status,
        "decision": "EVALUATION_QUALIFIED" if status == "PASS" else "EVALUATION_BLOCKED",
        "datasetHash": manifest["datasetHash"],
        "lock": lock,
        "answerableCaseCount": selected["caseCount"],
        "noAnswerCaseCount": no_answer_count,
        "checks": checks,
        "baseline": baseline,
        "selected": selected,
        "deltas": {
            "coverageAt20": round(selected_coverage20 - baseline_coverage20, 6),
            "coverageAtSelectedK": round(selected["rrfMetrics"].get(f"coverageAt{selected_k}", 0.0) - baseline["rrfMetrics"].get(f"coverageAt{selected_k}", 0.0), 6),
            "deterministicNdcgAt5Regression": round(ndcg_regression, 6),
            "deterministicMrrRegression": round(mrr_regression, 6),
            "latencyP95Ratio": round(selected["latencyP95"] / max(baseline["latencyP95"], 1e-9), 6),
        },
        "nextStep": "run challenge once" if status == "PASS" else "stop; do not tune on evaluation result and do not integrate runtime",
    }


def blocked_result(reason: str, manifest: dict[str, Any], evaluation: list[dict[str, Any]], no_answer: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "agent-rag-v23-candidate-fusion-evaluation-result-v1",
        "status": "BLOCKED",
        "decision": reason,
        "datasetHash": manifest["datasetHash"],
        "answerableCaseCount": len(evaluation),
        "noAnswerCaseCount": len(no_answer),
    }


def current_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[3], text=True).strip()


def render_doc(result: dict[str, Any]) -> str:
    return (
        "# V2.3 Candidate Fusion Evaluation\n\n"
        f"Decision: `{result['decision']}`\n\n"
        "This is a one-shot evaluation on the frozen evaluation split. Results are not used for retuning.\n\n"
        "Resume-ready note: this gate separates calibration success from held-out qualification, making the RAG optimization auditable instead of relying on post-hoc metric selection.\n\n"
        "```json\n"
        + __import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
