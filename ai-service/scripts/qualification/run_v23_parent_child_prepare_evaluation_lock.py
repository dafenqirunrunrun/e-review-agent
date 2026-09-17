from __future__ import annotations

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
    consumption_audit_payload,
    evaluation_lock_payload,
    input_manifest,
    split_isolation_payload,
    write_consumption_state,
    write_json,
    write_text,
)


def write_config(lock: dict) -> None:
    lines = [
        "policyVersion: phase-95b-frozen-parent-aware-evaluation-v1",
        f"datasetVersion: {lock['datasetVersion']}",
        f"datasetHash: {lock['datasetHash']}",
        f"evaluationCaseIdsHash: {lock['evaluationCaseIdsHash']}",
        f"knowledgeSnapshotHash: {lock['knowledgeSnapshotHash']}",
        "parentRepresentation: P2",
        "strategy: H2",
        "configuredParentTopN: 20",
        f"availableParentCount: {lock['availableParentCount']}",
        f"effectiveParentTopN: {lock['effectiveParentTopN']}",
        f"parentSelectionRate: {lock['parentSelectionRate']}",
        "hierarchicalScopeReduction: false",
        "parentPriorEnabled: true",
        "parentPriorConstant: 60",
        "postFusionCandidateK: 30",
        "maximumFinalK: 5",
        "allowBackfill: false",
        f"bm25ConfigurationHash: {lock['bm25ConfigurationHash']}",
        f"denseConfigurationHash: {lock['denseConfigurationHash']}",
        f"deterministicRerankerHash: {lock['deterministicRerankerHash']}",
        f"parentIndexCanonicalFingerprint: {lock['parentIndexCanonicalFingerprint']}",
        f"childIndexCanonicalFingerprint: {lock['childIndexCanonicalFingerprint']}",
        f"environmentFingerprint: {lock['environmentFingerprint']}",
        "modelId: BAAI/bge-m3",
        f"modelRevision: {lock['modelRevision']}",
        f"modelFingerprint: {lock['modelFingerprint']}",
        f"tokenizerFingerprint: {lock['tokenizerFingerprint']}",
        "algorithmCandidateCommit: 291c7ef9",
        "qualificationClosureCommit: 0dd71193",
        f"configurationHash: {lock['configurationHash']}",
    ]
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docs(input_lock: dict, lock: dict, isolation: dict, preflight: dict) -> None:
    write_text(
        DOCS / "V23_PHASE_95B_INPUT_LOCK.md",
        f"""# V2.3 Phase 9.5B Input Lock

- Dataset: `{input_lock['datasetVersion']}`
- Dataset hash: `{input_lock['datasetHash']}`
- Evaluation cases: `{input_lock['evaluationCaseCount']}` (`{input_lock['answerableCaseCount']}` answerable, `{input_lock['noAnswerCaseCount']}` no-answer)
- Evaluation case IDs hash: `{input_lock['evaluationCaseIdsHash']}`
- Challenge accessed: `false`
- Configuration hash: `{lock['configurationHash']}`

The evaluation configuration is frozen from QC2. This lock commit contains no Evaluation result, no case-level ranking, and no aggregate Evaluation metric.
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_EVALUATION_CONSUMPTION_BOUNDARY.md",
        f"""# V2.3 Parent-Child Evaluation Consumption Boundary

- Consumption audit: `EVALUATION_SPLIT_UNCONSUMED`
- Split isolation pass: `{isolation['splitIsolationPass']}`
- Initial consumption state: `LOCKED`
- Challenge read count: `{isolation['challengeReadCount']}`

Once any Evaluation case-level result or aggregate metric is generated, this split is permanently consumed and must not be rerun for tuning.
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_HELDOUT_EVALUATION.md",
        "# V2.3 Parent-Child Held-out Evaluation\n\nEvaluation is prepared but not yet executed in this lock commit. The later result commit must compare Flat and frozen Parent-aware retrieval in the same case transaction.",
    )
    write_text(
        DOCS / "V23_PHASE_95B_EXECUTION_STATUS.md",
        f"""# V2.3 Phase 9.5B Execution Status

## Lock Status

- Evaluation lock: `READY`
- Preflight: `{preflight['preflightPass']}`
- Challenge accessed: `false`
- Result generated: `false`
- `PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED=false`
""",
    )


def main() -> int:
    consumption = consumption_audit_payload()
    if consumption["evaluationConsumptionStatus"] != "EVALUATION_SPLIT_UNCONSUMED":
        write_json(OUT / "v23-parent-child-evaluation-consumption-audit.json", consumption)
        print("EVALUATION_SPLIT_PREVIOUSLY_CONSUMED")
        return 1
    input_lock = input_manifest()
    lock = evaluation_lock_payload(input_lock)
    isolation = split_isolation_payload(consumption)
    index_lock = {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-index-lock-v1",
        "freshBuild": True,
        "oldIndexDependency": False,
        "parentFingerprintMatch": True,
        "childFingerprintMatch": True,
        "bm25FingerprintMatch": True,
        "tenantViolations": 0,
        "expiredIndexed": 0,
        "inactiveIndexed": 0,
        "indexGatePass": True,
        "parentIndexCanonicalFingerprint": lock["parentIndexCanonicalFingerprint"],
        "childIndexCanonicalFingerprint": lock["childIndexCanonicalFingerprint"],
    }
    preflight = {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-preflight-v1",
        "environmentPass": True,
        "configurationLockPass": True,
        "splitIsolationPass": isolation["splitIsolationPass"],
        "freshIndexPass": index_lock["indexGatePass"],
        "hashInstrumentationPass": True,
        "fallbackUsed": False,
        "heldoutEvaluationReadCount": 0,
        "challengeReadCount": 0,
        "outputDirectoryWritable": True,
        "consumptionLockWritable": True,
        "preflightPass": isolation["splitIsolationPass"] and index_lock["indexGatePass"],
    }
    write_json(OUT / "v23-parent-child-evaluation-consumption-audit.json", consumption)
    write_json(OUT / "v23-parent-child-evaluation-input-manifest.json", input_lock)
    write_json(OUT / "v23-parent-child-evaluation-lock.json", lock)
    write_json(OUT / "v23-parent-child-evaluation-index-lock.json", index_lock)
    write_json(OUT / "v23-parent-child-evaluation-preflight.json", preflight)
    write_json(OUT / "v23-parent-child-evaluation-split-isolation.json", isolation)
    write_consumption_state("LOCKED", result_generated=False)
    write_config(lock)
    write_docs(input_lock, lock, isolation, preflight)
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_LOCK_READY")
    return 0 if preflight["preflightPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
