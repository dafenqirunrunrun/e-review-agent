from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from run_v23_candidate_fusion_evaluation import config_from_dict
from v23_candidate_fusion_common import DOCS, OUT, FusionConfig, evaluate_config, load_dataset, prepare_runtime, read_json, split_answerable, split_no_answer, write_json, write_text
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))
    evaluation = read_json(OUT / "v23-candidate-fusion-evaluation-result.json")
    if evaluation.get("status") != "PASS":
        result = {"schemaVersion": "agent-rag-v23-candidate-fusion-challenge-result-v1", "status": "NOT_RUN", "decision": "EVALUATION_NOT_PASS", "runtimeIntegrationAllowed": False}
        write_json(OUT / "v23-candidate-fusion-challenge-result.json", result)
        write_text(DOCS / "V23_CANDIDATE_FUSION_CHALLENGE.md", render_doc(result))
        print("CANDIDATE_FUSION_NOT_ROBUST")
        return 1
    cases, manifest = load_dataset()
    challenge = split_answerable(cases, "challenge")
    no_answer = split_no_answer(cases, "challenge")
    selected_cfg = evaluation["selected"]["configuration"]
    payload = benchmark_payload()
    provider, runtime = prepare_runtime(payload)
    try:
        baseline = evaluate_config(challenge, runtime, FusionConfig(20, 20, 20, 100))
        selected = evaluate_config(challenge, runtime, config_from_dict(selected_cfg))
    finally:
        try:
            provider.close()
        except Exception:
            pass
    selected_k = int(selected_cfg["postFusionCandidateK"])
    ndcg_regression = baseline["deterministicRerankerMetrics"].get("ndcgAt5", 0.0) - selected["deterministicRerankerMetrics"].get("ndcgAt5", 0.0)
    mrr_regression = baseline["deterministicRerankerMetrics"].get("mrr", 0.0) - selected["deterministicRerankerMetrics"].get("mrr", 0.0)
    checks = {
        "coverageSelectedKNotBelowBaseline": selected["rrfMetrics"].get(f"coverageAt{selected_k}", 0.0) >= baseline["rrfMetrics"].get(f"coverageAt{selected_k}", 0.0),
        "oracleCaptureSelectedKAtLeast090": selected.get("oracleCaptureRateAtSelectedK", 0.0) >= 0.90,
        "ndcgRegressionAtMost002": ndcg_regression <= 0.02,
        "mrrRegressionAtMost002": mrr_regression <= 0.02,
        "tenantViolationsZero": selected["tenantViolations"] == 0,
        "expiredEvidenceAcceptedZero": selected["expiredCandidatesAccepted"] == 0,
        "lowScoreBackfillZero": selected["lowScoreBackfillCount"] == 0,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    result = {
        "schemaVersion": "agent-rag-v23-candidate-fusion-challenge-result-v1",
        "status": status,
        "decision": "CHALLENGE_QUALIFIED" if status == "PASS" else "CANDIDATE_FUSION_NOT_ROBUST",
        "datasetHash": manifest["datasetHash"],
        "answerableCaseCount": selected["caseCount"],
        "noAnswerCaseCount": len(no_answer),
        "checks": checks,
        "baseline": baseline,
        "selected": selected,
        "runtimeIntegrationAllowed": status == "PASS",
    }
    write_json(OUT / "v23-candidate-fusion-challenge-result.json", result)
    write_text(DOCS / "V23_CANDIDATE_FUSION_CHALLENGE.md", render_doc(result))
    print("E_REVIEW_V23_CANDIDATE_FUSION_CHALLENGE_PASS" if status == "PASS" else "CANDIDATE_FUSION_NOT_ROBUST")
    return 0 if status == "PASS" else 1


def render_doc(result: dict[str, Any]) -> str:
    return "# V2.3 Candidate Fusion Challenge\n\nDecision: `" + result["decision"] + "`\n\n```json\n" + __import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


if __name__ == "__main__":
    raise SystemExit(main())
