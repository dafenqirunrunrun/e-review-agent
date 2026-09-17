from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag_quality.models import RagQualityCase
from scripts.build_step242a_rag_quality_v2 import FROZEN_WORKFLOW, FROZEN_WORKFLOW_SHA, load_jsonl, sha256_file


DEFAULT_DATASET = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "dataset_frozen_llm_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "manifest_frozen_llm_v1.json"
DEFAULT_PARSER_BASELINE = ROOT / "artifacts" / "step242a" / "parser_quality_baseline.json"
DEFAULT_RETRIEVAL_BASELINE = ROOT / "artifacts" / "step242c" / "frozen_dev_baselines.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step242a" / "promotion_readiness.json"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check Step 24.2A promotion readiness without mutating evaluation data.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--parser-baseline", type=Path, default=DEFAULT_PARSER_BASELINE)
    parser.add_argument("--retrieval-baseline", type=Path, default=DEFAULT_RETRIEVAL_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    report = check_readiness(
        dataset_path=args.dataset.resolve(),
        manifest_path=args.manifest.resolve(),
        parser_baseline_path=args.parser_baseline.resolve(),
        retrieval_baseline_path=args.retrieval_baseline.resolve(),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.require_ready and not report["gate"].startswith("READY") else 0


def check_readiness(
    *,
    dataset_path: Path,
    manifest_path: Path,
    parser_baseline_path: Path,
    retrieval_baseline_path: Path,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    cases = [RagQualityCase.model_validate(item) for item in load_jsonl(dataset_path)]
    parser_baseline = _load_json(parser_baseline_path)
    retrieval_baseline = _load_json(retrieval_baseline_path)

    frozen_sha = sha256_file(FROZEN_WORKFLOW)
    dataset_hash_matches = sha256_file(dataset_path) == manifest.get("files", {}).get("dataset", {}).get("sha256")
    human_verified = all(
        case.annotationStatus == "human_verified"
        and case.qrelCompleteness == "complete"
        and not case.requiresAdjudication
        for case in cases
    )
    verification_mode = str(manifest.get("annotation", {}).get("verificationMode") or "human")
    llm_mode = verification_mode == "codex_single_llm_judge_with_deterministic_validation"
    llm_verified = all(
        case.annotationStatus == "llm_adjudicated"
        and case.qrelCompleteness == "complete"
        and not case.requiresAdjudication
        for case in cases
    )
    release_verified = llm_verified if llm_mode else human_verified
    holdout = [case for case in cases if case.split == "holdout"]
    checks = {
        "frozenWorkflowGoldUnchanged": frozen_sha == FROZEN_WORKFLOW_SHA,
        "datasetHashMatchesManifest": dataset_hash_matches,
        "caseCountValid": len(cases) == 120,
        "splitCountsValid": sum(case.split == "dev" for case in cases) == 80 and len(holdout) == 40,
        "holdoutCandidateExposureBlocked": all(not case.candidateExposure for case in holdout),
        "allCasesHumanVerified": human_verified,
        "allCasesLlmAdjudicated": llm_verified,
        "allCasesReleaseVerified": release_verified,
        "holdoutFrozen": manifest.get("status") in {"FROZEN", "FROZEN_LLM_ADJUDICATED"} and manifest.get("annotation", {}).get("holdoutExecutionAllowed") is True,
        "parserHardSafetyGatePassed": parser_baseline.get("hardSafetyGate") == "PASS",
        "retrievalBaselinePromotionEligible": bool(retrieval_baseline.get("variants")) and all(
            variant.get("evaluationStatus") in {"PROMOTION_ELIGIBLE", "PROMOTION_ELIGIBLE_WITH_SINGLE_JUDGE_LIMITATION"}
            for variant in retrieval_baseline.get("variants", {}).values()
        ),
        "qualityThresholdsFrozen": manifest.get("qualityThresholds", {}).get("status") == "FROZEN",
    }
    release_checks = {
        key: value
        for key, value in checks.items()
        if key not in {"allCasesHumanVerified", "allCasesLlmAdjudicated"}
    }
    blockers = [name for name, passed in release_checks.items() if not passed]
    if not release_verified:
        blockers.append("allCasesReleaseVerified" if llm_mode else "allCasesHumanVerified")
    gate = "HOLD" if blockers else ("READY_WITH_SINGLE_JUDGE_LIMITATION" if llm_mode else "READY")
    return {
        "schemaVersion": "step24.2a-promotion-readiness-v1",
        "gate": gate,
        "checks": checks,
        "blockers": blockers,
        "datasetVersion": manifest.get("datasetVersion", ""),
        "frozenWorkflowGoldSha256": frozen_sha,
        "verificationMode": verification_mode,
        "holdoutExecuted": bool(manifest.get("annotation", {}).get("holdoutExecuted", False)),
        "note": "This gate never executes Holdout or mutates labels, thresholds, retrieval, or parser behavior.",
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
