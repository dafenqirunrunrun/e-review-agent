from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
for item in (AI_ROOT, AI_ROOT / "scripts" / "qualification"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from run_v22_real_reranker_benchmark import benchmark_payload, build_manifest, hash_json  # noqa: E402


OUT = ROOT / "artifacts" / "real-model-chain"
DOC = ROOT / "docs" / "real-model-chain" / "V22_PHASE_86_ANSWERABILITY_CALIBRATION_REPORT.md"
MIN_CLASS_COUNT = 30


def main() -> int:
    payload = benchmark_payload()
    manifest = build_manifest(payload)
    calibration = payload["split"]["calibration"]
    answerable = [case for case in calibration if case["relevantChunkIds"]]
    no_answer = [case for case in calibration if not case["relevantChunkIds"]]
    feature_names = [
        "rerankerTop1Score",
        "rerankerTop1Top2Margin",
        "top1OriginalRank",
        "eligibleCandidateCount",
        "rerankerCandidateCount",
    ]
    insufficient = len(answerable) < MIN_CLASS_COUNT or len(no_answer) < MIN_CLASS_COUNT
    decision = {
        "schemaVersion": "agent-rag-v22-evidence-answerability-calibration-decision-v1",
        "decision": "CALIBRATION_DATA_INSUFFICIENT" if insufficient else "NO_VALID_ANSWERABILITY_POLICY",
        "policyType": "none",
        "policyVersion": "v22-answerability-policy-v1",
        "featureNames": feature_names,
        "configurationHash": hash_json({"featureNames": feature_names, "minimumClassCount": MIN_CLASS_COUNT}),
        "benchmarkHash": manifest["benchmarkHash"],
        "calibrationHash": manifest["calibrationHash"],
        "candidatePoolHash": "",
        "rerankerRevision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        "rerankerFingerprint": _reranker_fingerprint(),
        "answerableMetrics": {
            "calibrationAnswerableCaseCount": len(answerable),
            "minimumRequired": MIN_CLASS_COUNT,
        },
        "noAnswerMetrics": {
            "calibrationNoAnswerCaseCount": len(no_answer),
            "minimumRequired": MIN_CLASS_COUNT,
        },
        "eligibilityMetrics": _eligibility_metrics(),
        "selectionReason": "No-answer calibration class is below the frozen minimum; classifier calibration is not reliable and no runtime policy is emitted.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v22-evidence-answerability-calibration-decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    DOC.write_text(_report(decision), encoding="utf-8")
    print(decision["decision"])
    if decision["decision"] == "CALIBRATION_DATA_INSUFFICIENT":
        return 2
    return 1


def _eligibility_metrics() -> dict[str, Any]:
    path = OUT / "v22-reranker-correctness-gate.json"
    if not path.exists():
        return {"status": "MISSING"}
    gate = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": gate.get("status"),
        "expiredEvidenceAccepted": 0 if gate.get("checks", {}).get("postRerankerExpiredAcceptedCount") else 1,
        "tenantViolations": 0 if gate.get("checks", {}).get("tenantViolations") else 1,
        "inactiveEvidenceAccepted": 0 if gate.get("checks", {}).get("inactiveEvidenceAccepted") else 1,
        "lowScoreBackfillCount": int(gate.get("lowScoreBackfillCount") or 0),
    }


def _reranker_fingerprint() -> str:
    path = OUT / "model-assets-summary.json"
    if not path.exists():
        return ""
    assets = (json.loads(path.read_text(encoding="utf-8")).get("assets") or {}).get("reranker") or {}
    return str(assets.get("assetFingerprint") or "")


def _report(decision: dict[str, Any]) -> str:
    return f"""# V2.2 Phase 8.6 Answerability Calibration Report

## Decision

- Decision: `{decision['decision']}`
- Policy type: `{decision['policyType']}`
- Policy version: `{decision['policyVersion']}`
- Calibration answerable cases: `{decision['answerableMetrics']['calibrationAnswerableCaseCount']}`
- Calibration no-answer cases: `{decision['noAnswerMetrics']['calibrationNoAnswerCaseCount']}`
- Minimum per class: `{MIN_CLASS_COUNT}`

## Boundary

No answerability policy or calibrator artifact was emitted. Runtime integration, one-shot evaluation, E2E, and soak remain blocked until a valid frozen policy exists.
"""


if __name__ == "__main__":
    raise SystemExit(main())
