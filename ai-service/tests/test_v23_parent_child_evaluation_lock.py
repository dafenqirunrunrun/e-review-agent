from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_heldout_common import CHALLENGE_FORBIDDEN, evaluation_lock_payload, guard_split, input_manifest  # noqa: E402


def test_challenge_access_is_rejected_in_phase_95b() -> None:
    with pytest.raises(RuntimeError, match=CHALLENGE_FORBIDDEN):
        guard_split("challenge")


def test_evaluation_input_manifest_has_expected_counts_and_no_queries() -> None:
    manifest = input_manifest()
    assert manifest["evaluationCaseCount"] == 150
    assert manifest["answerableCaseCount"] == 120
    assert manifest["noAnswerCaseCount"] == 30
    assert manifest["challengeAccessed"] is False
    assert manifest["fullQueriesStored"] is False


def test_evaluation_lock_freezes_parent_aware_configuration() -> None:
    lock = evaluation_lock_payload(input_manifest())
    assert lock["parentRepresentation"] == "P2"
    assert lock["strategy"] == "H2"
    assert lock["configuredParentTopN"] == 20
    assert lock["availableParentCount"] == 18
    assert lock["effectiveParentTopN"] == 18
    assert lock["parentSelectionRate"] == 1.0
    assert lock["hierarchicalScopeReduction"] is False
    assert lock["configurationHash"]


def test_lock_artifact_does_not_store_sensitive_payloads_if_present() -> None:
    artifact = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-input-manifest.json"
    if artifact.exists():
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        assert payload["fullQueriesStored"] is False
