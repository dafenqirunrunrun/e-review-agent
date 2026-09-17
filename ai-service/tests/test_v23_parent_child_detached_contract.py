from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-qc2-detached-verify.json"


def test_detached_contract_records_dependency_audit_fields() -> None:
    if not ARTIFACT.exists():
        return
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for key in (
        "uncommittedSourceDependency",
        "oldIndexDependency",
        "oldCalibrationArtifactDependency",
        "candidateCacheDependency",
        "hardCodedLocalPath",
        "externalModelAssetFingerprintMatch",
        "knowledgeSnapshotFingerprintMatch",
    ):
        assert key in payload
    assert payload["detachedGate"] in {
        "E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_PASS",
        "E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_BLOCKED",
    }
