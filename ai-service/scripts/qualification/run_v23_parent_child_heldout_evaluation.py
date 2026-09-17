from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_heldout_common import (  # noqa: E402
    CONFIG,
    DOCS,
    OUT,
    CONSUMPTION_STATE,
    decision_from_quality,
    evaluate_split,
    load_consumption_state,
    validate_transition,
    write_consumption_state,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True)
    parser.add_argument("--configuration", default=str(CONFIG))
    parser.add_argument("--consumption-state", default=str(CONSUMPTION_STATE))
    parser.add_argument("--output-dir", default=str(OUT))
    parser.add_argument("--dataset-manifest", default="")
    parser.add_argument("--environment-manifest", default="")
    parser.add_argument("--asset-manifest", default="")
    parser.add_argument("--knowledge-manifest", default="")
    parser.add_argument("--parent-index-manifest", default="")
    parser.add_argument("--child-index-manifest", default="")
    return parser.parse_args()


def write_result_docs(quality: dict, decision: dict, gate: dict) -> None:
    write_text(
        DOCS / "V23_PARENT_CHILD_EVALUATION_DEEP_RANK_ANALYSIS.md",
        f"""# V2.3 Parent-Child Evaluation Deep-Rank Analysis

- Deep-rank cases: `{quality['deepRank']['deepRankCaseCount']}`
- Recovered@20: `{quality['deepRank']['deepRankRecoveredAt20']}`
- Recovered@30: `{quality['deepRank']['deepRankRecoveredAt30']}`
- Recovery@20: `{quality['deepRank']['deepRankRecoveryRateAt20']}`
- Recovery@30: `{quality['deepRank']['deepRankRecoveryRateAt30']}`
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_EVALUATION_NO_ANSWER_ANALYSIS.md",
        f"""# V2.3 Parent-Child Evaluation No-answer Analysis

- No-answer cases: `{quality['noAnswer']['noAnswerCaseCount']}`
- Flat false evidence rate: `{quality['noAnswer']['flatFalseEvidenceRate']}`
- Parent-aware false evidence rate: `{quality['noAnswer']['parentAwareFalseEvidenceRate']}`
- Low-score backfill count: `{quality['noAnswer']['lowScoreBackfillCount']}`
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_EVALUATION_RESOURCE_ANALYSIS.md",
        f"""# V2.3 Parent-Child Evaluation Resource Analysis

- Flat P95 ms: `{quality['resource']['flatRetrievalP95Ms']}`
- Parent-aware P95 ms: `{quality['resource']['parentAwareRetrievalP95Ms']}`
- P95 latency ratio: `{quality['resource']['latencyRatioP95']}`
- Index size ratio: `{quality['resource']['indexSizeRatio']}`
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_HELDOUT_EVALUATION.md",
        f"""# V2.3 Parent-Child Held-out Evaluation

## Decision

`{decision['decision']}`

## Flat

- Coverage@20: `{quality['flat']['coverageAt20']}`
- MRR: `{quality['flat']['mrr']}`
- nDCG@5: `{quality['flat']['ndcgAt5']}`

## Parent-aware

- Coverage@20: `{quality['parentAware']['coverageAt20']}`
- MRR: `{quality['parentAware']['mrr']}`
- nDCG@5: `{quality['parentAware']['ndcgAt5']}`

## Increment

- Coverage@20 lift: `{quality['coverageAt20Lift']}`
- Parent-aware-only hits: `{quality['parentAwareOnlyHitCount']}`
- Flat-only hits: `{quality['flatOnlyHitCount']}`
- Net recovered: `{quality['netRecoveredCaseCount']}`

The mechanism is accurately described as Document/Section Parent-Chunk Retrieval with parent-aware fusion. ParentTopN covers all 18 parents, so this result must not be described as child-scope reduction.
""",
    )
    write_text(
        DOCS / "V23_PHASE_95B_EXECUTION_STATUS.md",
        f"""# V2.3 Phase 9.5B Execution Status

- Decision: `{gate['decision']}`
- Parent-aware fusion decision: `{decision['decision']}`
- Challenge accessed: `false`
- Consumption state after: `{gate['consumptionStateAfter']}`
- `PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED={str(gate['phase95cParentChildChallengeAllowed']).lower()}`

## Resume Evidence

Problem: Parent-aware retrieval improved Calibration, but had to prove generalization on a one-time held-out Evaluation split.

Action: The run froze configuration, used a consumption lock, compared Flat and Parent-aware retrieval in the same case transaction, and recorded safe candidate/ranking/final evidence hashes.

Result: See Evaluation metrics and gate decision above. No full query, chunk, parent content or prompt is stored.
""",
    )


def main() -> int:
    args = parse_args()
    if args.split != "evaluation":
        print("CHALLENGE_ACCESS_FORBIDDEN_IN_PHASE_95B" if args.split == "challenge" else f"UNSUPPORTED_SPLIT:{args.split}")
        return 1
    state = load_consumption_state()
    if state["state"] != "LOCKED":
        print(f"EVALUATION_CONSUMPTION_STATE_NOT_LOCKED:{state['state']}")
        return 1
    if not validate_transition("LOCKED", "RUNNING", result_generated=False):
        print("ILLEGAL_CONSUMPTION_STATE_TRANSITION")
        return 1
    write_consumption_state("RUNNING", result_generated=False)
    result = evaluate_split("evaluation")
    quality = result["quality"]
    decision = decision_from_quality(quality)
    consumed_state = "CONSUMED_PASS" if decision["decision"] == "PARENT_AWARE_EVALUATION_PASS" else "CONSUMED_BLOCKED"
    write_consumption_state(consumed_state, result_generated=True)
    gate_pass = decision["decision"] == "PARENT_AWARE_EVALUATION_PASS"
    gate = {
        "artifactVersion": "agent-rag-v23-phase-95b-gate-v1",
        "decision": "E_REVIEW_V23_PHASE_95B_PASS" if gate_pass else "E_REVIEW_V23_PHASE_95B_BLOCKED",
        "parentChildEvaluation": "E_REVIEW_V23_PARENT_CHILD_EVALUATION_PASS" if gate_pass else "E_REVIEW_V23_PARENT_CHILD_EVALUATION_BLOCKED",
        "parentAwareFusion": "E_REVIEW_V23_PARENT_AWARE_FUSION_EVALUATION_PASS" if gate_pass else "E_REVIEW_V23_PARENT_AWARE_FUSION_EVALUATION_BLOCKED",
        "phase95cParentChildChallengeAllowed": gate_pass,
        "consumptionStateAfter": consumed_state,
        "checks": decision["checks"],
        "blockingReasons": decision["blockingReasons"],
        "realLlmStatus": "REAL_LLM_NOT_REVALIDATED_IN_PHASE_95B_ASSET_MANIFEST_MISSING",
        "challengeAccessed": False,
    }
    write_json(OUT / "v23-parent-child-evaluation-case-hashes.json", {"caseHashes": result["caseHashes"], "fullQueriesStored": False})
    write_json(OUT / "v23-parent-child-evaluation-flat-results.json", quality["flat"])
    write_json(OUT / "v23-parent-child-evaluation-selected-results.json", quality["parentAware"])
    write_json(OUT / "v23-parent-child-evaluation-deep-rank-analysis.json", quality["deepRank"])
    write_json(OUT / "v23-parent-child-evaluation-no-answer-analysis.json", quality["noAnswer"])
    write_json(OUT / "v23-parent-child-evaluation-resource-result.json", quality["resource"])
    write_json(OUT / "v23-parent-child-evaluation-decision.json", {"decision": decision["decision"], "quality": quality, "checks": decision["checks"], "blockingReasons": decision["blockingReasons"]})
    write_json(OUT / "v23-phase-95b-gate.json", gate)
    write_result_docs(quality, decision, gate)
    if gate_pass:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_PASS")
        print("E_REVIEW_V23_PARENT_AWARE_FUSION_EVALUATION_PASS")
        print("E_REVIEW_V23_PHASE_95B_PASS")
        print("PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED=true")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_BLOCKED")
    print("E_REVIEW_V23_PHASE_95B_BLOCKED")
    print("PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED=false")
    for item in decision["blockingReasons"]:
        print(f"BLOCKED:{item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
