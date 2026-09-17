import sys
from pathlib import Path

import pytest


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))


@pytest.fixture(autouse=True)
def isolate_managed_policy_index(monkeypatch):
    """Runtime-published local indexes must not change deterministic test fixtures."""
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT", "")
    monkeypatch.setenv("E_REVIEW_INPUT_GATE_SEMANTIC_ENABLED", "false")
    monkeypatch.setenv("E_REVIEW_INPUT_GATE_GUARD_ENABLED", "false")
