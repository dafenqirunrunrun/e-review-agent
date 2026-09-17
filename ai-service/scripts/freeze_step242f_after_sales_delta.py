from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_step242f_after_sales_delta import ARTIFACT_DIR, DATA_DIR, read_json, sha256_file, write_json_atomic


MANIFEST_PATH = DATA_DIR / "manifest_llm_adjudicated_v1.json"
DEV_RESULT = ARTIFACT_DIR / "dev_b2_result.json"


def main() -> int:
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("qualityThresholds", {}).get("status") == "FROZEN":
        raise RuntimeError("STEP242F_THRESHOLDS_ALREADY_FROZEN")
    dev = read_json(DEV_RESULT)
    validate_dev(dev, manifest)
    thresholds = freeze_thresholds(dev)
    manifest["status"] = "FROZEN_LLM_ADJUDICATED_READY_FOR_SINGLE_HOLDOUT_RUN"
    manifest["qualityThresholds"] = {
        "status": "FROZEN",
        "sourceSplit": "dev",
        "holdoutConsulted": False,
        "referenceVariant": "current_runtime_b2_hybrid_coverage_rerank",
        "rule": "Absolute thresholds derive from the exposed Dev result with a bounded 0.10 tolerance; exact integrity metrics remain exact.",
        "thresholds": thresholds,
        "devResultSha256": sha256_file(DEV_RESULT),
    }
    manifest["annotation"]["thresholdsFrozen"] = True
    write_json_atomic(MANIFEST_PATH, manifest)
    print(json.dumps({"gate": "PASS", "thresholds": thresholds}, ensure_ascii=False, indent=2))
    return 0


def validate_dev(dev: dict[str, Any], manifest: dict[str, Any]) -> None:
    checks = {
        "devResult": dev.get("split") == "dev" and dev.get("gate") == "PASS",
        "devUsesCurrentCorpus": dev.get("dataset", {}).get("corpusContentRootHash") == manifest.get("corpus", {}).get("contentRootHash"),
        "devUsesHybrid": dev.get("runtime", {}).get("actualMode") == "hybrid",
        "devHasNoHoldout": dev.get("dataset", {}).get("caseCount") == 16,
        "holdoutUnconsumed": not (ARTIFACT_DIR / "holdout_execution_seal.json").exists(),
    }
    if not all(checks.values()):
        raise RuntimeError(f"STEP242F_DEV_FREEZE_PRECONDITION_FAILED:{checks}")


def freeze_thresholds(dev: dict[str, Any]) -> dict[str, float]:
    metrics = dev["evaluation"]["metrics"]
    direct = dev["directPreferred"]
    return {
        "candidateEvidenceHitRateAt5": lower_bound(metrics["candidateEvidenceHitRateAt5"], 0.90),
        "mrrAt5": lower_bound(metrics["mrrAt5"], 0.60),
        "pooledNdcgAt5": lower_bound(metrics["pooledNdcgAt5"], 0.50),
        "riskCoverageAt3": lower_bound(metrics["riskCoverageAt3"], 0.80),
        "directPreferredHitRateAt3": lower_bound(direct["directPreferredHitRateAt3"], 0.70),
        "citationValidCaseRate": 1.0,
        "noAnswerAbstentionAccuracy": 1.0,
        "unjudgedItemRateAt5": 0.0,
        "duplicateItemRateAt5": 0.0,
    }


def lower_bound(value: float, floor: float) -> float:
    return round(max(floor, float(value) - 0.10), 6)


if __name__ == "__main__":
    raise SystemExit(main())
