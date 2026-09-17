from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from qualification.run_v23_bge_m3_sparse_isolated_environment_audit import build_gate, compare_tokenizers  # noqa: E402


def test_tokenizer_parity_requires_token_ids_and_special_tokens():
    probe = {
        "tokenIdsHash": "a",
        "attentionMaskHash": "b",
        "tokenCount": 3,
        "specialTokenIds": {"bos": 0, "eos": 2},
    }
    assert compare_tokenizers(probe, dict(probe))["status"] == "PASS"
    changed = dict(probe)
    changed["tokenIdsHash"] = "different"
    assert compare_tokenizers(probe, changed)["status"] == "BLOCKED"


def test_environment_gate_requires_isolation_and_no_fallback():
    boundary = {"primaryEnvironmentUnchanged": True}
    sparse = {
        "isolatedEnvironment": True,
        "systemSitePackages": False,
        "pipCheckPass": True,
        "cudaAvailable": True,
        "packageVersions": {"transformers": "4.51.3", "flagEmbedding": "1.3.5", "sentenceTransformers": "3.0.1"},
        "model": {"modelId": "BAAI/bge-m3", "assetFingerprint": "abc"},
        "runtimeSmoke": {
            "realSparseExecution": True,
            "finiteWeights": True,
            "nonEmptyWeights": True,
            "fallbackUsed": False,
            "relevantGreaterThanIrrelevantSmoke": True,
            "deterministicRepeat": True,
            "crossRunDeterministic": True,
        },
    }
    assert build_gate(boundary, sparse, {"status": "PASS"})["status"] == "PASS"
    sparse["runtimeSmoke"]["fallbackUsed"] = True
    assert build_gate(boundary, sparse, {"status": "PASS"})["status"] == "BLOCKED"


@pytest.mark.real_sparse
def test_real_sparse_environment_gate_artifact_pass():
    artifact = ROOT / "artifacts" / "retrieval-optimization" / "v23-bge-m3-sparse-environment-gate.json"
    if not artifact.exists():
        pytest.skip("Run the Phase 9.4A sparse environment audit before the real_sparse marker test.")
    gate = json.loads(artifact.read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    assert gate["phase94bSparseIndexAllowed"] is True
    assert gate["checks"]["realSparseExecution"] is True
    assert gate["checks"]["nonEmptyWeights"] is True
    assert gate["checks"]["fallbackUsedFalse"] is True
